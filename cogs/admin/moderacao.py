import discord
from discord.ext import commands
from datetime import timedelta

class Moderacao(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


# ----------------------------------- KICK -------------------------------------------

    @commands.hybrid_command(name="kick", description="Expulsa um membro do servidor.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Nenhum motivo especificado."):
        if membro == ctx.author:
            return await ctx.send("Pode se expulsar não mano, ta doido?", ephemeral=True)
            
        await membro.kick(reason=motivo)
        await ctx.send(f"`✅` O membro {membro.mention} foi expulso por {ctx.author.mention}. Motivo: {motivo}")


# ----------------------------------- BAN -------------------------------------------

    @commands.hybrid_command(name="ban", description="Bane um membro do servidor.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Nenhum motivo especificado."):
        if membro == ctx.author:
            return await ctx.send("Eu poderia te banir mesmo só de sacanagem!", ephemeral=True)

        await membro.ban(reason=motivo)
        await ctx.send(f"`🔨` {membro.mention} foi banido por {ctx.author.mention}. Motivo: {motivo}")

# ----------------------------------- MUTE -------------------------------------------

    @commands.hybrid_command(name="mute", description="Muta um membro por um tempo ae.")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, membro: discord.Member, minutos: int, *, motivo: str = "Nenhum motivo especificado."):
        if membro == ctx.author:
            return await ctx.send("Não da pra se mutar pae", ephemeral=True)

        duracao = timedelta(minutes=minutos)
        
        try:
            await membro.timeout(duracao, reason=motivo)
            await ctx.send(f"`🔇` {membro.mention} foi mutado por {minutos} minuto(s). Motivo: {motivo}")
        except discord.Forbidden:
            await ctx.send("❌ Não tenho permissão para mutar este membro.")

# ----------------------------------- UNMUTE -------------------------------------------

    @commands.hybrid_command(name="unmute", description="Desmuta o membro.")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Nenhum motivo especificado."):
        await membro.timeout(None, reason=motivo)
        await ctx.send(f"`🔊` {membro.mention} foi desmutado.")

async def setup(bot):
    await bot.add_cog(Moderacao(bot))