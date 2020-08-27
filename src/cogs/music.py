from discord.ext import commands
import discord
import lavalink

class MusicCog(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.bot.music = lavalink.Client(self.bot.user.id)
    self.bot.music.add_node('localhost', 7000, 'testing', 'na', 'music-node')
    self.bot.add_listener(self.bot.music.voice_update_handler, 'on_socket_response')
    self.bot.music.add_event_hook(self.track_hook)

  @commands.command(name='join')
  async def join(self, ctx):
    member = ctx.message.author
    if member is not None and member.voice is not None:
      vc = member.voice.channel
      player = self.bot.music.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))
      if not player.is_connected:
        player.store('channel', ctx.channel.id)
        await self.connect_to(ctx.guild.id, str(vc.id))
        # await ctx.send(f'Joined {vc}')
    else:
      await ctx.send('You must be in a voice channel to play music...')

  @commands.command(name='leave')
  async def leave(self, ctx):
    member = ctx.message.author
    if member is not None and member.voice is not None:
      await self.connect_to(ctx.message.guild.id, None)
      # vc = member.voice.channel
      # await ctx.sent(f'Left {vc}')
    else:
      await ctx.send('You\'re not in a voice channel...')

  @commands.command(name='play')
  async def play(self, ctx, *, query):
    try:
      player = self.bot.music.player_manager.get(ctx.guild.id)
      query = f'ytsearch:{query}'
      results = await player.node.get_tracks(query)
      tracks = results['tracks'][0:10]
      
      query_result = ''
      for i, track in enumerate(tracks):
        query_result += f'{i+1}) {track["info"]["title"]} - {track["info"]["uri"]}\n'
      embed = discord.Embed()
      embed.description = query_result

      await ctx.channel.send(embed=embed)

      # TODO: validation
      response = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id)
      track = tracks[int(response.content)-1]

      player.add(requester=ctx.author.id, track=track)
      await ctx.send(f'Added to queue: {track["info"]["title"]}')
      if not player.is_playing:
        await player.play()
      
    except Exception as error:
      print(error)

  async def track_hook(self, event):
    if isinstance(event, lavalink.events.QueueEndEvent):
      guild_id = int(event.player.guild_id)
      await self.connect_to(guild_id, None)

  async def connect_to(self, guild_id: int, channel_id: str):
    ws = self.bot._connection._get_websocket(guild_id)
    await ws.voice_state(str(guild_id), channel_id)


def setup(bot):
  bot.add_cog(MusicCog(bot))