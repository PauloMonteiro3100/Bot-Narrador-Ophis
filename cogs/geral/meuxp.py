import discord
from discord.ext import commands
from sqlalchemy import select

from database.connection import AsyncSessionLocal
from database.models import Usuario

class MeuXPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def calcular_nivel(self, xp: int) -> int:
        return int((xp / 100) ** 0.5)

    def xp_para_proximo_nivel(self, nivel_atual: int) -> int:
        return ((nivel_atual + 1) ** 2) * 100

    @commands.hybrid_command(name="meuxp", description="Veja seu nível atual, XP e progresso para o próximo nível.")
    async def meuxp(self, ctx: commands.Context, membro: discord.Member = None):
        alvo = membro or ctx.author
        
        async with AsyncSessionLocal() as session:
            stmt = select(Usuario).where(Usuario.discord_id == str(alvo.id))
            result = await session.execute(stmt)
            user_db = result.scalars().first()

            xp_atual = user_db.xp if user_db else 0
            
            nivel_atual = self.calcular_nivel(xp_atual)
            xp_proximo = self.xp_para_proximo_nivel(nivel_atual)
            xp_faltante = xp_proximo - xp_atual

            xp_base_nivel = (nivel_atual ** 2) * 100
            progresso_atual = xp_atual - xp_base_nivel
            total_nivel_atual = xp_proximo - xp_base_nivel
            
            porcentagem = int((progresso_atual / total_nivel_atual) * 10) if total_nivel_atual > 0 else 0
            barra = ("🟩" * porcentagem) + ("⬛" * (10 - porcentagem))
            porcentagem_texto = int((progresso_atual / total_nivel_atual) * 100)

            embed = discord.Embed(
                title=f"📊 Status de XP - {alvo.display_name}",
                color=discord.Color.blue()
            )
            if alvo.display_avatar:
                embed.set_thumbnail(url=alvo.display_avatar.url)
                
            embed.add_field(name="Nível Atual", value=f"**{nivel_atual}**", inline=True)
            embed.add_field(name="XP Total", value=f"**{xp_atual}**", inline=True)
            embed.add_field(name="Próximo Nível", value=f"Faltam **{xp_faltante} XP**", inline=False)
            embed.add_field(name="Progresso", value=f"{barra} ({porcentagem_texto}%)", inline=False)

            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MeuXPCog(bot))