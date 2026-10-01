import discord
from discord.ext import commands
import random
import time
from sqlalchemy import select

from database.connection import AsyncSessionLocal
from database.models import Usuario

class SistemaXP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.canais_permitidos_xp = [
            1533127350781214840, # Canal geral
        ]
        
        self.cooldowns_xp = {}
        
        self.CARGO_BLOQUEIO_XP = 1555194163958382612
        self.CARGO_BUFF_50 = 1555194153250586624
        self.CARGO_BUFF_25 = 1555194079711723620

        self.CARGOS_RECOMPENSA = {
            5: 1547291439967375432,
            15: 1547291877462507682,
            40: 1547292046346158140,
            50: 1547290932511248434,
            70: 1547292109533352046,
            100: 1547291050350088223,
            200: 1547291129500672062,
            400: 1547291202821423255,
            600: 1547291239668261055,
            670: 1547291289983389906,
            1000: 1547291336330444923
        }

    def calcular_nivel(self, xp: int) -> int:
        return int((xp / 100) ** 0.5)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.id not in self.canais_permitidos_xp:
            return

        user_id = message.author.id
        agora = time.time()

        ultimo_ganho = self.cooldowns_xp.get(user_id, 0)
        if agora - ultimo_ganho < 60:
            return

        role_ids = [role.id for role in message.author.roles]

        if self.CARGO_BLOQUEIO_XP in role_ids:
            return

        xp_base = random.randint(15, 25)
        if self.CARGO_BUFF_50 in role_ids:
            xp_ganho = int(xp_base * 1.50)
        elif self.CARGO_BUFF_25 in role_ids:
            xp_ganho = int(xp_base * 1.25)
        else:
            xp_ganho = xp_base

        self.cooldowns_xp[user_id] = agora

        async with AsyncSessionLocal() as session:
            stmt = select(Usuario).where(Usuario.discord_id == str(user_id))
            result = await session.execute(stmt)
            user_db = result.scalars().first()

            if not user_db:
                user_db = Usuario(discord_id=str(user_id), xp=0, pepitas=0)
                session.add(user_db)

            nivel_antigo = self.calcular_nivel(user_db.xp)
            user_db.xp += xp_ganho
            nivel_novo = self.calcular_nivel(user_db.xp)

            await session.commit()

        if nivel_novo > nivel_antigo:
            cargos_para_adicionar = []
            
            for nivel_necessario, cargo_id in self.CARGOS_RECOMPENSA.items():
                if nivel_novo >= nivel_necessario and cargo_id not in role_ids:
                    cargo_obj = message.guild.get_role(cargo_id)
                    if cargo_obj:
                        cargos_para_adicionar.append(cargo_obj)

            if cargos_para_adicionar:
                try:
                    await message.author.add_roles(*cargos_para_adicionar)
                except discord.Forbidden:
                    print("Erro: Bot sem permissão para dar o cargo de XP.")

async def setup(bot):
    await bot.add_cog(SistemaXP(bot))