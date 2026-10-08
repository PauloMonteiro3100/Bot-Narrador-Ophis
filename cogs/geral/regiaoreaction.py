import discord
from discord.ext import commands


class RegiaoReaction(commands.Cog):
    CHANNEL_ID = 1547282751290482699
    MESSAGE_ID = 1547362979719286895

    REACTION_ROLES = {
        "🐬": 1547273766424420464,
        "🌵": 1547273927200477265,
        "🐂": 1547273967545356471,
        "🧀": 1547274018174803978,
        "🧉": 1547274052710834236,
        "🌍": 1547274075918041098,
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._synced = False
        self._syncing = False

    @staticmethod
    def _normalize_emoji(emoji: str) -> str:
        return emoji.replace("\ufe0f", "")

    @commands.Cog.listener()
    async def on_ready(self):
        if self._synced or self._syncing:
            return

        self._syncing = True
        try:
            self._synced = await self._add_missing_reactions()
        finally:
            self._syncing = False

    async def _add_missing_reactions(self) -> bool:
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.CHANNEL_ID)
            except discord.HTTPException as error:
                print(f"Erro ao localizar o canal de regiões: {error}")
                return False

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            print(f"Erro: o canal {self.CHANNEL_ID} não é um canal de texto.")
            return False

        try:
            message = await channel.fetch_message(self.MESSAGE_ID)
        except discord.HTTPException as error:
            print(f"Erro ao buscar a mensagem de regiões {self.MESSAGE_ID}: {error}")
            return False

        existing_reactions = {
            self._normalize_emoji(reaction.emoji)
            for reaction in message.reactions
            if isinstance(reaction.emoji, str)
        }
        all_reactions_added = True

        for emoji in self.REACTION_ROLES:
            if self._normalize_emoji(emoji) in existing_reactions:
                continue

            try:
                await message.add_reaction(emoji)
            except discord.Forbidden as error:
                print(
                    f"Sem permissão para adicionar {emoji} à mensagem "
                    f"{self.MESSAGE_ID}: {error}"
                )
                all_reactions_added = False
            except discord.HTTPException as error:
                print(
                    f"Erro ao adicionar {emoji} à mensagem "
                    f"{self.MESSAGE_ID}: {error}"
                )
                all_reactions_added = False

        return all_reactions_added

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, add=False)

    async def _handle_reaction(
        self, payload: discord.RawReactionActionEvent, *, add: bool
    ):
        if (
            payload.channel_id != self.CHANNEL_ID
            or payload.message_id != self.MESSAGE_ID
        ):
            return

        emoji_name = payload.emoji.name or ""
        role_id = self.REACTION_ROLES.get(self._normalize_emoji(emoji_name))
        if role_id is None:
            return

        if self.bot.user and payload.user_id == self.bot.user.id:
            return

        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            print(f"Erro: não foi possível localizar o servidor {payload.guild_id}.")
            return

        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException as error:
                print(f"Erro ao localizar o membro {payload.user_id}: {error}")
                return

        role = guild.get_role(role_id)
        if role is None:
            print(f"Erro: o cargo {role_id} não existe no servidor {guild.id}.")
            return

        try:
            if add:
                await member.add_roles(role, reason="Região selecionada por reação")
            else:
                await member.remove_roles(role, reason="Reação de região removida")
        except discord.Forbidden as error:
            action = "adicionar" if add else "remover"
            print(f"Sem permissão para {action} o cargo {role_id}: {error}")
        except discord.HTTPException as error:
            action = "adicionar" if add else "remover"
            print(f"Erro ao {action} o cargo {role_id}: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RegiaoReaction(bot))
