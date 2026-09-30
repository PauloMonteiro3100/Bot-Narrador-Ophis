import os
import discord
from discord.ext import commands

class WelcomeEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        raw_id = os.getenv("WELCOME_CHANNEL_ID")
        self.channel_id = int(raw_id) if raw_id and raw_id.isdigit() else None
        self.image_url = (
            "https://media.discordapp.net/attachments/1481365841592320202/"
            "1531722823041683576/d70b23e4bcc843ca98b4607aab5b570e.gif"
            "?ex=6ab2c20b&is=6ab1708b&hm=93c8ee2a67f5256d2e8d8e2b45c2d20293a8182450d799283863dcdb1faab3ce&="
        )

    def create_welcome_embed(self, member: discord.Member) -> discord.Embed:
        guild_name = member.guild.name
        
        
        description_text = (
            f"A viagem foi longa {member.mention}. Através da janela, você viu o cenário "
            f"mudar até atingir o seu destino: **{guild_name}**˖\n\n"
            f"Assim que pisa fora do ônibus, um papel no chão atrai a sua atenção. "
            f"Trata-se de um <#1526672033499320491>, você decide lê-lo antes de continuar a jornada."
        )

        embed = discord.Embed(
            description=description_text,
            color=discord.Color(0x3D4A2E)
        )
        embed.set_image(url=self.image_url)

        
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        return embed

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self.channel_id:
            print("Erro: WELCOME_CHANNEL_ID não configurado no .env.")
            return

        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print(f"Erro: Não foi possível localizar o canal de ID {self.channel_id}.")
            return

        embed = self.create_welcome_embed(member)

        try:
            await channel.send(
                content=f"<:fogueira:1553985937497923624> {member.mention} entrou no acampamento!",
                embed=embed
            )
        except discord.Forbidden:
            print(f"Erro: Sem permissão para enviar mensagens no canal #{channel.name}.")
        except discord.HTTPException as e:
            print(f"Erro de conexão ao enviar mensagem de boas-vindas: {e}")

    @commands.hybrid_command(name="testwelcome", aliases=["testarboasvindas"], help="Testa o envio da mensagem de boas-vindas.")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx: commands.Context):
        embed = self.create_welcome_embed(ctx.author)
        await ctx.send(
            content=f"<:fogueira:1553985937497923624> {ctx.author.mention} entrou no acampamento!",
            embed=embed
        )

async def setup(bot):
    await bot.add_cog(WelcomeEvent(bot))