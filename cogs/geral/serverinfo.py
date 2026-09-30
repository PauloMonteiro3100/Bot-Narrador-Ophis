import discord
from discord.ext import commands

class Informacoes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="serverinfo", description="Exibe informações detalhadas sobre o servidor.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        
        if not guild:
            return await ctx.send("❌ Este comando só pode ser usado dentro de um servidor!", ephemeral=True)

        total_membros = guild.member_count
        bots = sum(1 for member in guild.members if member.bot)
        humanos = total_membros - bots
        
        admins = sum(1 for member in guild.members if member.guild_permissions.administrator)

        canais_texto = len(guild.text_channels)
        canais_voz = len(guild.voice_channels)
        categorias = len(guild.categories) 

        criacao_formatada = f"<t:{int(guild.created_at.timestamp())}:D>"

        embed = discord.Embed(
            title=f"📊 Informações do Servidor: {guild.name}",
            color=discord.Color.blue()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="`👑` Dono do Servidor", value=guild.owner.mention if guild.owner else "Desconhecido", inline=True)
        embed.add_field(name="`📅` Criado em", value=criacao_formatada, inline=True)
        embed.add_field(name="`🛡️` Cargos", value=str(len(guild.roles)), inline=True)

        embed.add_field(
            name=f"`👥` Membros ({total_membros})",
            value=f"`👤` Humanos: {humanos}\n`🤖` Bots: {bots}\n`👮` Admins: {admins}",
            inline=True
        )

        embed.add_field(
            name=f"`💬` Canais ({canais_texto + canais_voz})",
            value=f"`📝` Texto: {canais_texto}\n`🎤` Voz: {canais_voz}\n`📁` Categorias: {categorias}",
            inline=True
        )

        embed.set_footer(text=f"ID do Servidor: {guild.id}")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Informacoes(bot))