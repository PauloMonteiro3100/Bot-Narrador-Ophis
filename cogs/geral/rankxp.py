import discord
from discord.ext import commands
from sqlalchemy import select

from database.connection import AsyncSessionLocal
from database.models import Usuario

class RankXPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def calcular_nivel(self, xp: int) -> int:
        return int((xp / 100) ** 0.5)

    @commands.hybrid_command(name="rankxp", description="Mostra o Top 5 membros com mais XP no servidor.")
    async def rankxp(self, ctx: commands.Context):
        async with AsyncSessionLocal() as session:
            stmt = select(Usuario).order_by(Usuario.xp.desc()).limit(5)
            result = await session.execute(stmt)
            top_usuarios = result.scalars().all()

            if not top_usuarios:
                return await ctx.send("❌ Ninguém ganhou XP no servidor ainda!", ephemeral=True)

            embed = discord.Embed(
                title="🏆 Top 5 - Rank de XP",
                description="Os membros mais falantes e ativos do servidor!",
                color=discord.Color.gold()
            )

            medalhas = ["🥇", "🥈", "🥉", "🏅", "🏅"]

            for index, user_db in enumerate(top_usuarios):
                membro = ctx.guild.get_member(int(user_db.discord_id))
                nome = membro.mention if membro else f"Desconhecido ({user_db.discord_id})"
                nivel = self.calcular_nivel(user_db.xp)
                
                embed.add_field(
                    name=f"{medalhas[index]} {index + 1}º Lugar",
                    value=f"**Usuário:** {nome}\n**Nível:** {nivel} | **XP:** {user_db.xp}",
                    inline=False
                )

            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(RankXPCog(bot))