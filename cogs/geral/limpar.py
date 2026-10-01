import discord
from discord.ext import commands
from discord import app_commands

class ModeracaoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="apagar", description="Apaga uma quantidade de mensagens no canal (ignora mensagens fixadas).")
    @app_commands.describe(quantidade="Quantidade de mensagens para apagar (entre 2 e 999)")
    @app_commands.default_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, quantidade: app_commands.Range[int, 2, 999]):
        await interaction.response.defer(ephemeral=True)

        def nao_esta_fixada(message: discord.Message):
            return not message.pinned

        try:
            deletadas = await interaction.channel.purge(
                limit=quantidade,
                check=nao_esta_fixada
            )

            qtd_deletadas = len(deletadas)
            await interaction.followup.send(
                f"**{qtd_deletadas}** mensagens apagadas com sucesso! ",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ O bot não possui a permissão de **Gerenciar Mensagens** neste canal.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Ocorreu um erro ao tentar apagar as mensagens: `{e}`",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ModeracaoCog(bot))