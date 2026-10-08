import asyncio
import json
import re
from pathlib import Path

import discord
from discord.ext import commands


class Tickets(commands.Cog):
    PANEL_CHANNEL_ID = 1547233923489079396
    TICKET_CATEGORY_ID = 1550630676699553872
    ADMIN_ROLE_ID = 1526645448469778674
    PANEL_TITLE = "Canal de Resgate"
    PANEL_STATE_PATH = (
        Path(__file__).resolve().parents[2] / "database" / "tickets_panel.json"
    )

    SERVICES = {
        "denuncia": ("Fazer uma denúncia", "🚨"),
        "vip": ("Comprar VIP", "💎"),
        "staff": ("Seja Staff", "🛡️"),
        "duvidas": ("Tirar dúvidas", "❓"),
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._panel_lock = asyncio.Lock()
        self._panel_ready = False

    async def cog_load(self):
        self.bot.add_view(TicketPanelView(self))
        self.bot.add_view(TicketActionsView(self))

    @commands.Cog.listener()
    async def on_ready(self):
        async with self._panel_lock:
            if self._panel_ready:
                return

            channel = self.bot.get_channel(self.PANEL_CHANNEL_ID)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(self.PANEL_CHANNEL_ID)
                except discord.HTTPException as error:
                    print(f"Erro ao localizar o canal do painel de tickets: {error}")
                    return

            if not isinstance(channel, discord.TextChannel):
                print(
                    f"Erro: o canal {self.PANEL_CHANNEL_ID} não é um canal de texto."
                )
                return

            try:
                panel_message = await self._find_panel_message(channel)
                if panel_message is None:
                    panel_message = await channel.send(
                        embed=self._create_panel_embed(),
                        view=TicketPanelView(self),
                    )
                else:
                    await panel_message.edit(
                        embed=self._create_panel_embed(),
                        view=TicketPanelView(self),
                    )

                await self._save_panel_message_id(panel_message.id)
            except discord.HTTPException as error:
                print(f"Erro ao preparar o painel de tickets: {error}")
                return
            except OSError as error:
                print(f"Erro ao gravar o estado do painel de tickets: {error}")
                return

            self._panel_ready = True

    @classmethod
    def _create_panel_embed(cls) -> discord.Embed:
        embed = discord.Embed(
            title=cls.PANEL_TITLE,
            description=(
                "Faça uma denúncia, candidate-se para a staff, compre VIP "
                "ou tire dúvidas.\n\n"
                "Selecione uma opção no menu abaixo para abrir seu atendimento."
            ),
            color=discord.Color(0x5865F2),
        )
        embed.set_footer(text="Painel fixo do sistema de tickets")
        return embed

    async def _find_panel_message(
        self, channel: discord.TextChannel
    ) -> discord.Message | None:
        stored_message_id = await self._read_panel_message_id()
        if stored_message_id is not None:
            try:
                return await channel.fetch_message(stored_message_id)
            except discord.NotFound:
                pass
            except discord.HTTPException as error:
                print(
                    f"Erro ao verificar a mensagem salva do painel "
                    f"{stored_message_id}: {error}"
                )
                return None

        if self.bot.user is None:
            print("Erro: o bot ainda não possui um usuário autenticado.")
            return None

        async for message in channel.history(limit=5000):
            if (
                message.author.id == self.bot.user.id
                and any(embed.title == self.PANEL_TITLE for embed in message.embeds)
            ):
                return message
        return None

    async def _read_panel_message_id(self) -> int | None:
        try:
            state = await asyncio.to_thread(
                self.PANEL_STATE_PATH.read_text, encoding="utf-8"
            )
        except FileNotFoundError:
            return None
        except OSError as error:
            print(f"Erro ao ler o estado do painel de tickets: {error}")
            return None

        try:
            message_id = json.loads(state).get("message_id")
        except (json.JSONDecodeError, AttributeError) as error:
            print(f"Estado do painel de tickets inválido: {error}")
            return None

        return message_id if isinstance(message_id, int) else None

    async def _save_panel_message_id(self, message_id: int):
        await asyncio.to_thread(self._write_panel_message_id, message_id)

    def _write_panel_message_id(self, message_id: int):
        self.PANEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.PANEL_STATE_PATH.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps({"message_id": message_id}),
            encoding="utf-8",
        )
        temporary_path.replace(self.PANEL_STATE_PATH)

    async def show_confirmation(
        self,
        interaction: discord.Interaction,
        service: str,
        *,
        suspect_id: str | None = None,
        report: str | None = None,
    ):
        title, emoji = self.SERVICES[service]
        description = (
            f"Confirme para abrir um canal privado para **{title.lower()}**.\n"
            "A equipe será notificada quando o canal for criado."
        )
        if service == "denuncia":
            description += (
                "\n\nApós abrir o canal, envie nele os prints e outras provas "
                "do ocorrido."
            )

        embed = discord.Embed(
            title=f"{emoji} Confirmar atendimento",
            description=(
                f"{description}\n\n**Relato:**\n{report}"
                if report is not None
                else description
            ),
            color=discord.Color(0x5865F2),
        )
        if suspect_id is not None:
            embed.add_field(name="ID do denunciado", value=suspect_id, inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=TicketConfirmationView(
                self,
                requester_id=interaction.user.id,
                service=service,
                suspect_id=suspect_id,
                report=report,
            ),
            ephemeral=True,
        )

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        service: str,
        *,
        suspect_id: str | None = None,
        report: str | None = None,
    ) -> discord.TextChannel:
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            raise ValueError("Os tickets só podem ser abertos dentro do servidor.")

        category = guild.get_channel(self.TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            raise ValueError("A categoria configurada para tickets não foi encontrada.")

        admin_role = guild.get_role(self.ADMIN_ROLE_ID)
        if admin_role is None:
            raise ValueError("O cargo de administração configurado não foi encontrado.")

        bot_member = guild.me
        if bot_member is None:
            raise ValueError("Não foi possível localizar o bot dentro do servidor.")

        requester = interaction.user
        ticket_name = self._ticket_channel_name(requester)
        permissions = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        )
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            requester: permissions,
            admin_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
            ),
            bot_member: permissions,
        }

        title, emoji = self.SERVICES[service]
        ticket_channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"ticket_owner={requester.id};service={service}",
            reason=f"Ticket de {requester} — {title}",
        )

        embed = discord.Embed(
            title=f"{emoji} {title}",
            description=(
                f"{requester.mention}, aguarde um instante até que algum "
                f"membro de {admin_role.mention} te atenda."
                + (f"\n\n**Relato:**\n{report}" if report is not None else "")
            ),
            color=discord.Color(0x5865F2),
        )
        embed.add_field(name="Solicitante", value=requester.mention, inline=True)

        if suspect_id is not None:
            embed.add_field(
                name="ID do denunciado", value=suspect_id, inline=True
            )
        if service == "denuncia":
            embed.add_field(
                name="Provas",
                value="Envie neste canal os prints e demais provas do ocorrido.",
                inline=False,
            )
        elif service != "denuncia":
            embed.add_field(
                name="Detalhes",
                value="Descreva sua solicitação para que a equipe possa te ajudar.",
                inline=False,
            )

        allowed_mentions = discord.AllowedMentions(
            users=[requester],
            roles=True,
            everyone=False,
            replied_user=False,
        )
        try:
            await ticket_channel.send(
                content=f"{requester.mention} <@&{self.ADMIN_ROLE_ID}>",
                embed=embed,
                view=TicketActionsView(self),
                allowed_mentions=allowed_mentions,
            )
        except discord.HTTPException:
            try:
                await ticket_channel.delete(
                    reason="Limpeza de ticket que não pôde ser inicializado"
                )
            except discord.HTTPException as cleanup_error:
                print(
                    f"Erro ao limpar o canal de ticket {ticket_channel.id}: "
                    f"{cleanup_error}"
                )
            raise

        return ticket_channel

    @staticmethod
    def _ticket_channel_name(member: discord.Member) -> str:
        slug = re.sub(r"[^a-z0-9-]+", "-", member.name.lower()).strip("-")
        slug = slug or "usuario"
        suffix = str(member.id)
        max_slug_length = 95 - len(suffix)
        return f"ticket-{slug[:max_slug_length]}-{suffix}"

    def is_admin(self, member: discord.Member) -> bool:
        return member.guild_permissions.administrator or any(
            role.id == self.ADMIN_ROLE_ID for role in member.roles
        )

    @staticmethod
    def get_ticket_owner(channel: discord.TextChannel) -> int | None:
        if channel.topic is None:
            return None

        match = re.search(r"(?:^|;)ticket_owner=(\d+)(?:;|$)", channel.topic)
        return int(match.group(1)) if match else None


class TicketPanelSelect(discord.ui.Select):
    def __init__(self, tickets: Tickets):
        self.tickets = tickets
        options = [
            discord.SelectOption(label=label, value=value, emoji=emoji)
            for value, (label, emoji) in Tickets.SERVICES.items()
        ]
        super().__init__(
            placeholder="Escolha o tipo de atendimento",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="tickets:service",
        )

    async def callback(self, interaction: discord.Interaction):
        service = self.values[0]
        if service == "denuncia":
            await interaction.response.send_modal(ReportTicketModal(self.tickets))
            return

        await self.tickets.show_confirmation(interaction, service)


class TicketPanelView(discord.ui.View):
    def __init__(self, tickets: Tickets):
        super().__init__(timeout=None)
        self.add_item(TicketPanelSelect(tickets))


class ReportTicketModal(discord.ui.Modal, title="Registrar denúncia"):
    suspect_id = discord.ui.TextInput(
        label="ID do usuário denunciado",
        placeholder="Cole o ID ou a menção do usuário",
        required=True,
        max_length=25,
    )
    report = discord.ui.TextInput(
        label="Relato do ocorrido",
        placeholder="Explique o que aconteceu",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1500,
    )

    def __init__(self, tickets: Tickets):
        super().__init__(timeout=300)
        self.tickets = tickets

    async def on_submit(self, interaction: discord.Interaction):
        raw_id = self.suspect_id.value.strip()
        match = re.fullmatch(r"(?:<@!?(\d{15,22})>|(\d{15,22}))", raw_id)
        if match is None:
            await interaction.response.send_message(
                "Informe um ID de usuário válido ou uma menção como `<@123...>`.",
                ephemeral=True,
            )
            return

        await self.tickets.show_confirmation(
            interaction,
            "denuncia",
            suspect_id=match.group(1) or match.group(2),
            report=self.report.value.strip(),
        )


class TicketConfirmationView(discord.ui.View):
    def __init__(
        self,
        tickets: Tickets,
        *,
        requester_id: int,
        service: str,
        suspect_id: str | None,
        report: str | None,
    ):
        super().__init__(timeout=300)
        self.tickets = tickets
        self.requester_id = requester_id
        self.service = service
        self.suspect_id = suspect_id
        self.report = report

    @discord.ui.button(
        label="Confirmar",
        style=discord.ButtonStyle.green,
        custom_id="tickets:confirm",
    )
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Somente quem iniciou esta solicitação pode confirmá-la.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            ticket_channel = await self.tickets.create_ticket(
                interaction,
                self.service,
                suspect_id=self.suspect_id,
                report=self.report,
            )
        except (ValueError, discord.HTTPException) as error:
            print(f"Erro ao criar ticket para {interaction.user.id}: {error}")
            await interaction.followup.send(
                "Não foi possível criar o canal do ticket. Avise a equipe "
                "ou tente novamente mais tarde.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Seu ticket foi criado: {ticket_channel.mention}",
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(
        label="Cancelar",
        style=discord.ButtonStyle.red,
        custom_id="tickets:cancel",
    )
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Somente quem iniciou esta solicitação pode cancelá-la.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            content="Solicitação cancelada.",
            embed=None,
            view=None,
        )
        self.stop()


class TicketActionsView(discord.ui.View):
    def __init__(self, tickets: Tickets, *, claimed: bool = False):
        super().__init__(timeout=None)
        self.tickets = tickets
        self.claim.disabled = claimed
        if claimed:
            self.claim.label = "Ticket resgatado"

    @discord.ui.button(
        label="Resgatar Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="tickets:claim",
    )
    async def claim(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este botão só pode ser usado no servidor.",
                ephemeral=True,
            )
            return
        if not self.tickets.is_admin(interaction.user):
            await interaction.response.send_message(
                "Somente a administração pode resgatar este ticket.",
                ephemeral=True,
            )
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Este botão só pode ser usado dentro de um ticket.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🎫 Ticket resgatado por {interaction.user.mention}.",
            allowed_mentions=discord.AllowedMentions(
                users=[interaction.user],
                everyone=False,
            ),
        )
        try:
            await interaction.message.edit(
                view=TicketActionsView(self.tickets, claimed=True)
            )
        except discord.HTTPException as error:
            print(f"Erro ao atualizar o botão de resgate do ticket: {error}")

    @discord.ui.button(
        label="Finalizar Atendimento",
        style=discord.ButtonStyle.danger,
        custom_id="tickets:close",
    )
    async def close(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este botão só pode ser usado no servidor.",
                ephemeral=True,
            )
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Este botão só pode ser usado dentro de um ticket.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        is_requester = (
            self.tickets.get_ticket_owner(channel) == interaction.user.id
        )
        if not is_requester and not self.tickets.is_admin(interaction.user):
            await interaction.response.send_message(
                "Somente quem abriu o ticket ou a administração pode finalizá-lo.",
                ephemeral=True,
            )
            return

        if channel.category_id != self.tickets.TICKET_CATEGORY_ID:
            await interaction.response.send_message(
                "Este canal não pertence à categoria de tickets.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await channel.send(
                "🙏 Obrigado por utilizar nossos serviços. "
                "Este canal será encerrado em 5 segundos."
            )
            await asyncio.sleep(5)
            await channel.delete(reason=f"Ticket finalizado por {interaction.user}")
        except discord.HTTPException as error:
            print(f"Erro ao finalizar o ticket {channel.id}: {error}")
            await interaction.followup.send(
                "Não foi possível encerrar o canal do ticket. Avise a equipe.",
                ephemeral=True,
            )
            return

        await interaction.followup.send("Ticket encerrado.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
