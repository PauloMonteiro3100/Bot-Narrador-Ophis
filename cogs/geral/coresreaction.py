import discord
from discord.ext import commands


class CoresReaction(commands.Cog):
    CHANNEL_ID = 1544126418500194304

    REACTION_ROLES = {
        1548105467610533939: (
            ("☁️", 1547359193361555486),
            ("🌪️", 1547359300534411386),
            ("🩶", 1547359406277140510),
            ("🧷", 1547359581544517772),
            ("🦇", 1547359713966948483),
            ("🕷️", 1547359804727492668),
        ),
        1548105470642757723: (
            ("🍪", 1547363020735389786),
            ("🥐", 1547363167913508995),
            ("🫗", 1547363279255506966),
            ("🥥", 1547363387602772118),
            ("🪵", 1547363493181915207),
            ("🍫", 1547363580557525092),
        ),
        1548105476292747265: (
            ("🧱", 1547354478372720650),
            ("🍒", 1547354042471153754),
            ("🍁", 1547353951945490482),
            ("🍎", 1547353681996025966),
            ("🩸", 1547353549523128421),
            ("💋", 1547353420657066134),
        ),
        1548105479421435957: (
            ("🍞", 1547356775689232474),
            ("🍊", 1547355159519039558),
            ("🎃", 1547355271544840382),
            ("🥞", 1547355354520756224),
            ("🏵️", 1547369884546240592),
            ("🥮", 1547355458812121239),
        ),
        1548105483963998349: (
            ("🌙", 1547357558220660736),
            ("🍯", 1547357717620990032),
            ("🐥", 1547357825359941712),
            ("🧇", 1547358019010961479),
            ("🍂", 1547358127228198933),
            ("🐿️", 1547358244572373023),
        ),
        1548105492151402578: (
            ("🍏", 1547351711184723988),
            ("🍵", 1547351566305067079),
            ("🥬", 1547351459031425044),
            ("🌿", 1547351355512070154),
            ("🍀", 1547351228386910218),
            ("🌲", 1547351111034347530),
        ),
        1548105495338946621: (
            ("🧊", 1547350614214975568),
            ("🫧", 1547350515124539522),
            ("💍", 1547350400255008809),
            ("🪼", 1547350227168526466),
            ("🌊", 1547346877660536984),
            ("🌃", 1547345987704725614),
        ),
        1548105498732142593: (
            ("🦄", 1547360359856341052),
            ("🪻", 1547360493675487363),
            ("🌂", 1547360573086502922),
            ("👾", 1547360727453532241),
            ("🍇", 1547360950695497778),
            ("🔮", 1547360855698571355),
        ),
        1548105501810892894: (
            ("🍥", 1547361723223244881),
            ("🍧", 1547361835345514537),
            ("🌸", 1547361922150695062),
            ("🌺", 1547362325126975499),
            ("🍷", 1547362440038318112),
            ("🥀", 1547362518018818119),
        ),
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._reaction_roles = {
            (message_id, self._normalize_emoji(emoji)): role_id
            for message_id, reactions in self.REACTION_ROLES.items()
            for emoji, role_id in reactions
        }
        self._syncing = False
        self._synced = False

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
                print(f"Erro ao localizar o canal de cargos por reação: {error}")
                return False

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            print(f"Erro: o canal {self.CHANNEL_ID} não é um canal de texto.")
            return False

        all_reactions_added = True
        for message_id, reactions in self.REACTION_ROLES.items():
            try:
                message = await channel.fetch_message(message_id)
            except discord.HTTPException as error:
                print(f"Erro ao buscar a mensagem {message_id}: {error}")
                all_reactions_added = False
                continue

            for emoji, _ in reactions:
                try:
                    await message.add_reaction(emoji)
                except discord.Forbidden as error:
                    print(
                        f"Sem permissão para adicionar {emoji} à mensagem "
                        f"{message_id}: {error}"
                    )
                    all_reactions_added = False
                except discord.HTTPException as error:
                    print(
                        f"Erro ao adicionar {emoji} à mensagem "
                        f"{message_id}: {error}"
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
        if payload.channel_id != self.CHANNEL_ID:
            return

        emoji_name = payload.emoji.name or ""
        role_id = self._reaction_roles.get(
            (payload.message_id, self._normalize_emoji(emoji_name))
        )
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
                await member.add_roles(role, reason="Cargo selecionado por reação")
            else:
                await member.remove_roles(role, reason="Reação de cargo removida")
        except discord.Forbidden as error:
            action = "adicionar" if add else "remover"
            print(f"Sem permissão para {action} o cargo {role_id}: {error}")
        except discord.HTTPException as error:
            action = "adicionar" if add else "remover"
            print(f"Erro ao {action} o cargo {role_id}: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(CoresReaction(bot))
