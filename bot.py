import os
import discord
from dotenv import load_dotenv
import random
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

bot = commands.Bot(command_prefix='!')

@bot.command(name='weaksauce', help='Calls Yichen weaksauce')
async def weaksauce(ctx):
  response = '<@!118714407642464257> you\'re weaksauce!'
  await ctx.send(response)

@bot.command(name='roll', help='Simulates rolling dice')
async def roll(ctx, number_of_dice: int, number_of_sides: int):
  dice = [
    random.choice(range(1, number_of_sides + 1))
    for _ in range(number_of_dice)
  ]
  response = ', '.join(str(i) for i in dice)
  if number_of_dice > 1: response += '\nSum: ' + str(sum(dice))
  await ctx.send(response)

@bot.event
async def on_ready():
  guild = discord.utils.get(bot.guilds, name=GUILD)
  print(
      f'{bot.user} is connected to the following guild:\n'
      f'{guild.name}(id: {guild.id})'
  )

bot.run(TOKEN)