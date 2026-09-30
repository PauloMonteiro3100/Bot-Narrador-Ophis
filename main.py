import discord
from discord.ext import commands
import pathlib
import os
from dotenv import load_dotenv

load_dotenv()

class MeuBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='n!',
            intents=discord.Intents.all(),
            activity=discord.CustomActivity(name='Buscando Viajantes'),
        )

    async def setup_hook(self):
        for ficheiro in pathlib.Path('./cogs').rglob('*.py'):
            modulo = str(ficheiro).replace('.py', '').replace('\\', '.').replace('/', '.')
            try:
                await self.load_extension(modulo)
                print(f'Carregado: {modulo}')
            except Exception as e:
                print(f'Falha ao carregar {modulo}: {e}')
        
        await self.tree.sync()
        print("Comandos sincronizados!")



    async def on_ready(self):
        print(f'Bot online como {self.user}')


bot = MeuBot()
bot.run(os.getenv('DISCORD_TOKEN'))