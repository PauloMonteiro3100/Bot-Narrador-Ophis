import discord
from discord.ext import commands
from discord import app_commands
from sqlalchemy import update

from database.connection import AsyncSessionLocal
from database.models import Usuario

class ModalResetXP(discord.ui.Modal, title='Aviso de Segurança: Reset Global'):
    senha = discord.ui.TextInput(
        label='Senha de Confirmação',
        style=discord.TextStyle.short,
        placeholder='Insira a senha',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        if self.senha.value == "1234":
            async with AsyncSessionLocal() as session:
                stmt = update(Usuario).values(xp=0)
                await session.execute(stmt)
                await session.commit()
            
            await interaction.response.send_message("O XP de todos foi zerado.", ephemeral=True)
        else:
            await interaction.response.send_message("Senha incorreta!", ephemeral=True)

class AdminXPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="resetar_xp_global", description="Zera o XP de todos os membros.")
    @app_commands.default_permissions(administrator=True)
    async def resetar_xp_global(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ModalResetXP())

async def setup(bot):
    await bot.add_cog(AdminXPCog(bot))