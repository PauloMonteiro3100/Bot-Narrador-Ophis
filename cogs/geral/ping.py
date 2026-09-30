import discord
from discord.ext import commands

class Utilidades(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping', help='Mostra a latência do bot.')
    async def ping(self, ctx):
        latencia = round(self.bot.latency * 1000)
        await ctx.send(f'Pong! 🏓 `{latencia}ms`')

async def setup(bot):
    await bot.add_cog(Utilidades(bot))