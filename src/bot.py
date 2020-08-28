import os
import discord
from dotenv import load_dotenv
import random
from discord.ext import commands
from googleapiclient.discovery import build

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

API_KEY = os.getenv('YOUTUBE_API_KEY')
youtube = build('youtube', 'v3', developerKey=API_KEY)

bot = commands.Bot(command_prefix='!')


@bot.command(name='weaksauce', help='Calls Yichen weaksauce')
async def weaksauce(ctx):
  response = '<@!118714407642464257> you\'re weaksauce!'
  await ctx.send(response)


@bot.command(name='youtube', help='Searches for YouTube video')
async def search(ctx, *query):
  req = youtube.search().list(q=' '.join(query[:]), part='snippet', type='video', maxResults=1)
  res = req.execute()
  video_id = res['items'][0]['id']['videoId']
  response = f'https://www.youtube.com/watch?v={video_id}'
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


@bot.command(name='ping', help='Returns bot latency in ms')
async def ping(ctx):
  await ctx.send(f'Latency: {round(bot.latency*1000)}ms')


@bot.event
async def on_ready():
  print(f'{bot.user} has logged in.')
  bot.load_extension('cogs.music')
  bot.load_extension('cogs.games')

bot.run(TOKEN)