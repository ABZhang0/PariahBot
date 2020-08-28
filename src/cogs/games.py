from discord.ext import commands
import discord
import random


class Games(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.command(name='blackjack', help='Play blackjack')
  async def blackjack(self, ctx):
    deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]*4
    player_hand = []
    for _ in range(2):
      random.shuffle(deck)
      card = deck.pop()
      player_hand.append(card)
    player_total = sum(player_hand)
    player_embed = discord.Embed(title=f'{ctx.author.name}\'s hand', description=f'{player_hand}')
    player_embed_msg = await ctx.send(embed=player_embed)

    if player_total == 21:
      await ctx.send('Blackjack! You win this time...')
      return
    
    stand = False
    while(player_total <= 21 and not stand):
      response = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id)
      if response.content == 'stand':
        stand = True
      else:
        card = deck.pop()
        player_hand.append(card)
        player_total += card
        player_embed.description = f'{player_hand}'
        await player_embed_msg.edit(embed=player_embed)

    if player_total > 21:
      await ctx.send('You bust! Dealer wins!')
      return

    card = deck.pop()
    dealer_hand = [card]
    dealer_total = card
    dealer_embed = discord.Embed(title=f'Dealer\'s hand', description=f'{dealer_hand}')
    dealer_embed_msg = await ctx.send(embed=dealer_embed)
    while dealer_total < 17:
      card = deck.pop()
      dealer_hand.append(card)
      dealer_total += card
      dealer_embed.description = f'{dealer_hand}'
      await dealer_embed_msg.edit(embed=dealer_embed)

    if dealer_total > 21:
      await ctx.send('Dealer busts! You win this time...')
      return

    if player_total > dealer_total:
      await ctx.send('You win this time...')
    elif dealer_total > player_total:
      await ctx.send('Dealer wins!')
    else:
      await ctx.send('Tie.')

    


def setup(bot):
  bot.add_cog(Games(bot))