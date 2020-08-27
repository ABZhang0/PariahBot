from discord.ext import commands
from typing import Union
import discord
import wavelink
import asyncio
import time

class MusicController:
  def __init__(self, bot, guild_id):
    self.bot = bot
    self.guild_id = guild_id
    self.channel = None

    self.next = asyncio.Event()
    self.queue = asyncio.Queue()

    self.volume = 40
    self.now_playing = None

    self.bot.loop.create_task(self.controller_loop())

  async def controller_loop(self):
    await self.bot.wait_until_ready()

    player = self.bot.wavelink.get_player(self.guild_id)
    await player.set_volume(self.volume)

    while True:
      if self.now_playing:
        await self.now_playing.delete()

      self.next.clear()

      song = await self.queue.get()
      await player.play(song)
      # TODO: troubleshoot
      # self.now_playing = await self.channel.send(f'Now playing: {song}')

      await self.next.wait()


class Music(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.controllers = {}
    if not hasattr(bot, 'wavelink'): self.bot.wavelink = wavelink.Client(bot=self.bot)
    self.bot.loop.create_task(self.start_nodes())

  async def start_nodes(self):
    await self.bot.wait_until_ready()
    node = await self.bot.wavelink.initiate_node(host='localhost', port=7000, rest_uri='http://localhost:7000', password='testing', identifier='TEST', region='us_east')
    node.set_hook(self.on_event_hook)

  async def on_event_hook(self, event):
    if isinstance(event, (wavelink.TrackEnd, wavelink.TrackException)):
      controller = self.get_controller(event.player)
      controller.next.set()

  def get_controller(self, value: Union[commands.Context, wavelink.Player]):
    if isinstance(value, commands.Context):
      gid = value.guild.id
    else:
      gid = value.guild_id

    try:
      controller = self.controllers[gid]
    except KeyError:
      controller = MusicController(self.bot, gid)
      self.controllers[gid] = controller

    return controller
  
  @commands.command(name='join')
  async def join(self, ctx, *, channel: discord.VoiceChannel=None):
    if not channel:
      try:
        channel = ctx.author.voice.channel
      except AttributeError:
        ctx.send('Please specify a channel to join...')

    controller = self.get_controller(ctx)
    controller.channel = channel

    player = self.bot.wavelink.get_player(ctx.guild.id)
    await ctx.send(f'Connecting to **{channel.name}**')
    await player.connect(channel.id)

  @commands.command(name='disconnect')
  async def stop(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)

    try:
      del self.controllers[ctx.guild.id]
    except KeyError:
      await player.disconnect()
      return await ctx.send('There\'s no controller to stop...', delete_after=10)

    await player.disconnect()
    await ctx.send('Disconnected player and killed controller...', delete_after=10)

  @commands.command(name='play')
  async def play(self, ctx, *, query):
    query = f'ytsearch:{query}'

    tracks = await self.bot.wavelink.get_tracks(f'{query}')
    if not tracks:
      return await ctx.send('Couldn\'t find any songs with that query :(')

    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.is_connected:
      await ctx.invoke(self.connect_)

    tracks = tracks[0:10]
    query_result = ''
    for i, track in enumerate(tracks):
      s = track.info['length']/1000
      query_result += f'{i+1}) {track.info["title"]} - {time.strftime("%M:%S", time.gmtime(s))}\n{track.info["uri"]}\n'
    embed = discord.Embed()
    embed.description = query_result
    await ctx.channel.send(embed=embed)

    # TODO: validation
    response = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id)
    track = tracks[int(response.content)-1]

    controller = self.get_controller(ctx)
    await controller.queue.put(track)
    await ctx.send(f'Added to the queue: **{str(track)}**')

  @commands.command(name='pause')
  async def pause(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.is_playing:
      return await ctx.send('I\'m not playing anything!', delete_after=10)

    await ctx.send('Pausing the song!', delete_after=10)
    await player.set_pause(True)

  @commands.command(name='resume')
  async def resume(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.paused:
      return await ctx.send('I\'m not currently paused!', delete_after=10)

    await ctx.send('Resuming the song!', delete_after=10)
    await player.set_pause(False)

  @commands.command(name='skip')
  async def skip(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)
    if not player.is_playing:
      return await ctx.send('I\'m not playing anything!', delete_after=10)

    await ctx.send('Skipping the song!', delete_after=10)
    await player.stop()

  @commands.command(name='nowplaying')
  async def now_playing(self, ctx):
    player = self.bot.wavelink.get_player(ctx.guild.id)

    if not player.current:
      return await ctx.send('I\'m not playing anything!', delete_after=10)

    controller = self.get_controller(ctx)
    # await controller.now_playing.delete()

    controller.now_playing = await ctx.send(f'Now playing: **{player.current}**')


def setup(bot):
  bot.add_cog(Music(bot))