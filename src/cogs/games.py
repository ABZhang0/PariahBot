from discord.ext import commands
import discord
import random
import os
from pymongo import MongoClient
import asyncio

class Games(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

    CONNECTION_STRING = os.getenv('MONGO_CONNECTION_STRING')
    self.cluster = MongoClient(CONNECTION_STRING)
    self.db = self.cluster['pariah-bot-db']
    self.collection = self.db['users-info']

  @commands.command(name='blackjack', help='Play blackjack')
  async def blackjack(self, ctx, *query):
    # TODO: refactor function to be more concise
    if query and query[0] == 'stats':
      user = self.collection.find_one({'_id': ctx.author.id})
      if not user:
        await ctx.send('Can\'t find you in my records :(')
        return
      wins, lost, tied = user['blackjack_record']['wins'], user['blackjack_record']['lost'], user['blackjack_record']['tied']
      user_embed = discord.Embed(title=f'{ctx.author.name}\'s blackjack record')
      user_embed.add_field(name='Wins', value=wins)
      user_embed.add_field(name='Lost', value=lost)
      user_embed.add_field(name='Tied', value=tied)
      user_embed.add_field(name='Win Rate', value=f'{round(100*wins/(wins+lost+tied), 2)}%')
      await ctx.send(embed=user_embed)
    elif not query:
      player_win = await self.blackjack_game(ctx)
      if player_win == None:
        self.collection.update_one({'_id': ctx.author.id}, {'$inc': {'blackjack_record.wins': 0, 'blackjack_record.lost': 0, 'blackjack_record.tied': 1}}, upsert=True)
      elif player_win:
        self.collection.update_one({'_id': ctx.author.id}, {'$inc': {'blackjack_record.wins': 1, 'blackjack_record.lost': 0, 'blackjack_record.tied': 0}}, upsert=True)
      else:
        self.collection.update_one({'_id': ctx.author.id}, {'$inc': {'blackjack_record.wins': 0, 'blackjack_record.lost': 1, 'blackjack_record.tied': 0}}, upsert=True)
    else:
      await ctx.send('Invalid query for blackjack...')

  async def blackjack_game(self, ctx):
    deck = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]*4
    random.shuffle(deck)

    player_hand = []
    player_total = 0
    for _ in range(2):
      card = deck.pop()
      player_total += card
      player_hand.append(self.card_converter(card))
    player_embed = discord.Embed(title=f'{ctx.author.name}\'s hand', description=f'{", ".join(map(str, player_hand))}')
    player_embed.add_field(name='Total', value=player_total)
    player_embed_msg = await ctx.send(embed=player_embed)

    if player_total == 21:
      await ctx.send('Blackjack! You win this time...')
      return True
    
    stand = False
    while(player_total <= 21 and not stand):
      response = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id, timeout=30)
      if response.content == 'stand':
        stand = True
      else:
        card = deck.pop()
        player_total += card
        player_hand.append(self.card_converter(card))
        player_embed.description = f'{", ".join(map(str, player_hand))}'
        player_embed.set_field_at(0, name='Total', value=player_total)
        await player_embed_msg.edit(embed=player_embed)

    if player_total > 21:
      await ctx.send('You bust! Dealer wins!')
      return False

    dealer_hand = []
    dealer_total = 0
    dealer_embed = discord.Embed(title=f'Dealer\'s hand', description=f'{", ".join(map(str, dealer_hand))}')
    dealer_embed.add_field(name='Total', value=dealer_total)
    dealer_embed_msg = await ctx.send(embed=dealer_embed)
    while dealer_total < 17:
      await asyncio.sleep(0.5)
      card = deck.pop()
      dealer_total += card
      dealer_hand.append(self.card_converter(card))
      dealer_embed.description = f'{", ".join(map(str, dealer_hand))}'
      dealer_embed.set_field_at(0, name='Total', value=dealer_total)
      await dealer_embed_msg.edit(embed=dealer_embed)

    if dealer_total > 21:
      await ctx.send('Dealer busts! You win this time...')
      return True

    if player_total > dealer_total:
      await ctx.send('You win this time...')
      return True
    elif dealer_total > player_total:
      await ctx.send('Dealer wins!')
      return False
    else:
      await ctx.send('Tie.')
      return None

  def card_converter(self, card: int):
    if card == 1:
      return 'A'
    elif card == 11:
      return 'J'
    elif card == 12:
      return 'Q'
    elif card == 13:
      return 'K'
    else:
      return card

  @commands.command(name='roll', help='Simulates rolling dice')
  async def roll(self, ctx, number_of_dice: int, number_of_sides: int):
    dice = [
      random.choice(range(1, number_of_sides + 1))
      for _ in range(number_of_dice)
    ]
    response = ', '.join(str(i) for i in dice)
    if number_of_dice > 1: response += '\nSum: ' + str(sum(dice))
    await ctx.send(response)


def setup(bot):
  bot.add_cog(Games(bot))