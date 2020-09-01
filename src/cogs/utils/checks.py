from discord.ext import commands

def is_owner():
  return commands.check(lambda ctx: ctx.message.author.id == 189247380598685696)
