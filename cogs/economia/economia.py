import discord
from discord.ext import commands
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Usuario

class Economia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    async def obter_usuario(self, session, discord_id: int):
        id_str = str(discord_id)
        resultado = await session.execute(select(Usuario).where(Usuario.discord_id == id_str))
        usuario = resultado.scalars().first()
        
        if not usuario:
            usuario = Usuario(discord_id=id_str, pepitas=0)
            session.add(usuario)
            await session.commit()
            await session.refresh(usuario)
            
        return usuario





    @commands.hybrid_command(name="saldo", description="Veja quantas Pepitas de Ouro você ou outro usuário tem.")
    async def saldo(self, ctx: commands.Context, membro: discord.Member = None):
        # Se não mencionar ninguém, o alvo é quem enviou o comando
        alvo = membro or ctx.author 

        async with AsyncSessionLocal() as session:
            usuario_db = await self.obter_usuario(session, alvo.id)
            
            embed = discord.Embed(
                title="<:pepita:1554731685994827846> Saldo de Pepitas de Ouro",
                description=f"O saldo de {alvo.mention} é de **{usuario_db.pepitas} Pepitas de Ouro <:pepita:1554731685994827846>**.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)








    @commands.hybrid_command(name="trabalhar", description="Trabalhe para ganhar Pepitas de Ouro (Cooldown: 8 horas).")
    @commands.cooldown(1, 28800, commands.BucketType.user)
    async def trabalhar(self, ctx: commands.Context):
        ganho = random.randint(200, 500)
        adicional_noturno = datetime.now(ZoneInfo("America/Sao_Paulo")).hour >= 22
        if adicional_noturno:
            ganho += ganho // 2

        async with AsyncSessionLocal() as session:
            usuario_db = await self.obter_usuario(session, ctx.author.id)
            
            usuario_db.pepitas += ganho
            await session.commit()
            
            detalhe_adicional = " (inclui adicional noturno de 50%)" if adicional_noturno else ""
            await ctx.send(
                f"Você trabalhou duro nas minas e encontrou <:pepita:1554731685994827846> "
                f"**{ganho} Pepitas de Ouro**{detalhe_adicional}! Volte daqui a 8 horas."
            )









    @commands.hybrid_command(name="pagar", description="Transfira Pepitas de Ouro para outro usuário.")
    async def pagar(self, ctx: commands.Context, membro: discord.Member, valor: int):
        if valor <= 0:
            return await ctx.send("❌ Você precisa transferir um valor maior que zero!", ephemeral=True)
        if membro == ctx.author:
            return await ctx.send("❌ Você não pode pagar a si mesmo!", ephemeral=True)
        if membro.bot:
            return await ctx.send("❌ Bots não têm contas bancárias!", ephemeral=True)

        async with AsyncSessionLocal() as session:
            pagador_db = await self.obter_usuario(session, ctx.author.id)
            
            if pagador_db.pepitas < valor:
                return await ctx.send(f"❌ Saldo insuficiente! Você tem apenas **{pagador_db.pepitas} Pepitas de Ouro**.", ephemeral=True)

            recebedor_db = await self.obter_usuario(session, membro.id)
            
            pagador_db.pepitas -= valor
            recebedor_db.pepitas += valor
            await session.commit()

            await ctx.send(f"Transferência concluída! Você enviou <:pepita:1554731685994827846> **{valor} Pepitas de Ouro** para {membro.mention}.")

    @trabalhar.error
    async def erro_trabalhar(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutos = int(error.retry_after // 60)
            segundos = int(error.retry_after % 60)
            await ctx.send(f"⏳ Você está exausto! Descanse por mais **{minutos}m e {segundos}s** antes de voltar a trabalhar.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economia(bot))