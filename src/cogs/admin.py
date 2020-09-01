from discord.ext import commands
from .utils import checks
import discord

class Admin(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.command(name='reload', help='Reloads specified extension')
  @checks.is_owner()
  async def _reload(self, ctx, *, module: str):
    # TODO: error handling / refactor
    if module == 'cogs.music': await self.bot.get_cog('Music').destroy_nodes()
    self.bot.unload_extension(module)

    self.bot.load_extension(module)

    await ctx.send(f'Reloaded {module}', delete_after=10)


def setup(bot):
  bot.add_cog(Admin(bot))