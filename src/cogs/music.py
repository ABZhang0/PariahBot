from discord.ext import commands
from typing import Union
import discord
import wavelink
import asyncio
import time
import itertools
from dotenv import load_dotenv
import os


class Timer:
  def __init__(self, timeout, callback):
    self._timeout = timeout
    self._callback = callback
    self._task = asyncio.ensure_future(self._job())

  async def _job(self):
    await asyncio.sleep(self._timeout)
    await self._callback()

  def cancel(self):
    self._task.cancel()


class TrackDeque(asyncio.Queue):
  async def put_front(self, item):
    while self.full():
      putter = self._loop.create_future()
      self._putters.append(putter)
      try:
        await putter
      except:
        putter.cancel()  # Just in case putter is not done yet.
        try:
          # Clean self._putters from canceled putters.
          self._putters.remove(putter)
        except ValueError:
          # The putter could be removed from self._putters by a
          # previous get_nowait call.
          pass
        if not self.full() and not putter.cancelled():
          # We were woken up by get_nowait(), but can't take
          # the call.  Wake up the next in line.
          self._wakeup_next(self._putters)
        raise
    return self.put_front_nowait(item)

  def put_front_nowait(self, item):
    # if self.full():
    #   raise QueueFull
    self._put_front(item)
    self._unfinished_tasks += 1
    self._finished.clear()
    self._wakeup_next(self._getters)

  def _put_front(self, item):
    self._queue.appendleft(item)


class MusicController:
  def __init__(self, bot, guild_id):
    self.bot = bot
    self.guild_id = guild_id
    self.channel = None

    self.next = asyncio.Event()
    self.queue = TrackDeque()

    self.volume = 40
    self.now_playing = None
    self.afk_timer = None

    self.bot.loop.create_task(self.controller_loop())

  async def controller_loop(self):
    await self.bot.wait_until_ready()

    player = self.bot.wavelink.get_player(self.guild_id)
    await player.set_volume(self.volume)

    while True:
      if self.now_playing:
        await self.now_playing.delete()

      self.next.clear()

      self.afk_timer = Timer(300, self.afk_disconnect) # 5 min timeout
      track = await self.queue.get() # waits if queue empty
      self.afk_timer.cancel()
      
      await player.play(track)
      await self.bot.change_presence(activity=discord.Game(name=track.info['title']))
      self.now_playing = track.info['title']
      await self.channel.send(f'Now playing: **{self.now_playing}**', delete_after=10)

      await self.next.wait()

  async def afk_disconnect(self):
    player = self.bot.wavelink.get_player(self.guild_id)
    await player.stop()
    await player.disconnect()
    if self.channel: await self.channel.send('Disconnected player due to inactivity...', delete_after=10)
  

class Music(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.controllers = {}
    if not hasattr(bot, 'wavelink'): self.bot.wavelink = wavelink.Client(bot=self.bot)
    self.bot.loop.create_task(self.start_nodes())

  async def destroy_nodes(self):
    await self.node.destroy()

  async def start_nodes(self):
    await self.bot.wait_until_ready()

    load_dotenv()
    WAVELINK_HOST = os.getenv('WAVELINK_HOST')
    WAVELINK_PORT = os.getenv('WAVELINK_PORT')
    WAVELINK_URI = os.getenv('WAVELINK_URI')
    WAVELINK_PASSWORD = os.getenv('WAVELINK_PASSWORD')

    self.node = await self.bot.wavelink.initiate_node(
      host=WAVELINK_HOST,
      port=WAVELINK_PORT,
      rest_uri=WAVELINK_URI,
      password=WAVELINK_PASSWORD,
      identifier='TEST',
      region='us_east',
      heartbeat=45 # heroku websocket timeout is 55 seconds
    )
    self.node.set_hook(self.on_event_hook)

  async def on_event_hook(self, event):
    if isinstance(event, (wavelink.TrackEnd, wavelink.TrackException)):
      controller = self.get_controller(event.player)
      controller.now_playing = await controller.bot.change_presence(activity=None)
      controller.next.set()

  def get_controller(self, value: Union[commands.Context, wavelink.Player]):
    if isinstance(value, commands.Context):
      guild_id = value.guild.id
    else:
      guild_id = value.guild_id

    try:
      controller = self.controllers[guild_id]
    except KeyError:
      controller = MusicController(self.bot, guild_id)
      self.controllers[guild_id] = controller

    return controller
  
  @commands.command(name='join', help='Invites bot to channel')
  async def join(self, ctx, *, voice_channel: discord.VoiceChannel=None):
    if not voice_channel:
      try:
        voice_channel = ctx.author.voice.channel
      except AttributeError:
        ctx.send('Please specify a channel to join...')

    controller = self.get_controller(ctx)
    controller.channel = ctx.message.channel

    player = self.bot.wavelink.get_player(ctx.guild.id)
    await ctx.send(f'Connecting to **{voice_channel.name}**')
    await player.connect(voice_channel.id)

  @commands.command(name='disconnect', help='Removes bot from channel')
  async def stop(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)

    try:
      del self.controllers[ctx.guild.id]
    except KeyError:
      await player.stop()
      await player.disconnect()
      return await ctx.send('There\'s no controller to stop...', delete_after=10)

    await player.stop()
    await player.disconnect()
    await ctx.send('Disconnected player and killed controller...', delete_after=10)

  @commands.command(name='play', help='Returns song results by query')
  async def play(self, ctx, *, query):
    query = f'ytsearch:{query}'

    tracks = await self.bot.wavelink.get_tracks(f'{query}')
    if not tracks:
      return await ctx.send('Couldn\'t find any songs with that query :(')

    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.is_connected:
      await ctx.invoke(self.join)

    tracks = tracks[0:10]
    query_result = ''
    for i, track in enumerate(tracks):
      s = track.info['length']/1000
      query_result += f'**{i+1})** {track.info["title"]} - {time.strftime("%H:%M:%S", time.gmtime(s))}\n{track.info["uri"]}\n'
    query_embed = discord.Embed(description=query_result)
    await ctx.channel.send(embed=query_embed)

    # TODO: validation
    response = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id, timeout=30)
    track = tracks[int(response.content)-1]

    controller = self.get_controller(ctx)
    controller.channel = ctx.message.channel
    await controller.queue.put(track)
    await ctx.send(f'Added to the queue: **{str(track)}**')

  @commands.command(name='pause', help='Pauses currently playing song')
  async def pause(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.is_playing:
      return await ctx.send('I\'m not playing anything!', delete_after=10)

    await ctx.send('Pausing the song!', delete_after=10)
    await player.set_pause(True)

  @commands.command(name='resume', help='Resumes currently paused song')
  async def resume(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.paused:
      return await ctx.send('I\'m not currently paused!', delete_after=10)

    await ctx.send('Resuming the song!', delete_after=10)
    await player.set_pause(False)

  @commands.command(name='skip', help='Skips currently playing song')
  async def skip(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.is_playing:
      return await ctx.send('I\'m not playing anything!', delete_after=10)

    await ctx.send('Skipping the song!', delete_after=10)
    await player.stop()

  @commands.command(name='volume', help='Adjust music volume')
  async def volume(self, ctx, *, direction: str):
    if direction != 'up' and direction != 'down':
      await ctx.send('Invalid volume input...')
      return
    
    player = self.bot.wavelink.get_player(ctx.guild.id)
    controller = self.get_controller(ctx)
    if direction == 'up':
      controller.volume *= 2
    elif direction == 'down':
      controller.volume //= 2
    
    clamp = lambda v, min_v, max_v: max(min(max_v, v), min_v)
    controller.volume = clamp(controller.volume, 1, 200)

    await ctx.send(f'Setting player volume to {controller.volume}', delete_after=10)
    await player.set_volume(controller.volume)

  @commands.command(name='nowplaying', help='Returns currently playing song')
  async def now_playing(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)

    if not player.current:
      return await ctx.send('I\'m not playing anything!', delete_after=10)

    controller = self.get_controller(ctx)
    # await controller.now_playing.delete()

    controller.now_playing = await ctx.send(f'Now playing: **{player.current}**')

  @commands.command(name='repeat', help='Adds current song into the front of the queue')
  async def repeat(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    track = player.current
    if not track:
      return await ctx.send('I\'m not playing anything!', delete_after=10)

    controller = self.get_controller(ctx)
    await controller.queue.put_front(track)
    await ctx.send(f'Added to the queue: **{str(track)}**')

  @commands.command(name='queue', help='Returns song queue info')
  async def queue(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    controller = self.get_controller(ctx)

    if not player.current or not controller.queue._queue:
      return await ctx.send('There are no songs currently in the queue.', delete_after=10)

    upcoming = list(itertools.islice(controller.queue._queue, 0, 5))

    fmt = '\n'.join(f'**`{str(track)}`**' for track in upcoming)
    embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt)

    await ctx.send(f'Total number of songs in queue: {len(controller.queue._queue)}')
    await ctx.send(embed=embed)


def setup(bot):
  bot.add_cog(Music(bot))