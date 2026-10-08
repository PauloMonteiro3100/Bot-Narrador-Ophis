import asyncio
import io
from pathlib import Path

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps


class Procurase(commands.Cog):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    TEMPLATE_PATH = PROJECT_ROOT / "assets" / "procurase_template.png"
    BUTTON_ID = "procurase:hang_poster"
    DESCRIPTION_MAX_LENGTH = 300
    DESCRIPTION_MAX_LINES = 5

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(ProcuraseView(self))

    @commands.command(name="procurase", help="Pendura seu cartaz de procurado.")
    async def procurase(self, ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member):
            await ctx.send("Este comando só pode ser usado dentro do servidor.")
            return

        try:
            await self.publish_poster(ctx.channel, ctx.author)
        except (discord.HTTPException, OSError, ValueError) as error:
            print(f"Erro ao publicar cartaz de {ctx.author.id}: {error}")
            await ctx.send("Não consegui pendurar seu cartaz. Tente novamente mais tarde.")

    async def publish_poster(
        self,
        destination: discord.abc.Messageable,
        member: discord.Member,
        description: str = "",
    ) -> None:
        avatar_bytes = await member.display_avatar.with_size(256).read()
        image_bytes = await asyncio.to_thread(
            self._render_poster,
            avatar_bytes,
            member.name,
            description,
        )

        image_file = discord.File(
            io.BytesIO(image_bytes),
            filename="procurado.png",
        )
        embed = discord.Embed(
            title=f"Procurase: {member.name}",
            color=discord.Color.dark_gold(),
        )
        embed.set_image(url="attachment://procurado.png")
        await destination.send(
            embed=embed,
            file=image_file,
            view=ProcuraseView(self),
        )

    @classmethod
    def _render_poster(
        cls, avatar_bytes: bytes, username: str, description: str
    ) -> bytes:
        with Image.open(cls.TEMPLATE_PATH) as template:
            poster = template.convert("RGB")

        with Image.open(io.BytesIO(avatar_bytes)) as avatar:
            square_avatar = ImageOps.fit(
                avatar.convert("RGB"),
                (212, 213),
                method=Image.Resampling.LANCZOS,
            )

        poster.paste(square_avatar, (287, 447))
        draw = ImageDraw.Draw(poster)
        username_font_size = 28
        username_font = ImageFont.load_default(size=username_font_size)
        while (
            draw.textlength(username, font=username_font) > 360
            and username_font_size > 16
        ):
            username_font_size -= 2
            username_font = ImageFont.load_default(size=username_font_size)
        poster_username = username
        if draw.textlength(poster_username, font=username_font) > 360:
            while (
                poster_username
                and draw.textlength(poster_username + "…", font=username_font) > 360
            ):
                poster_username = poster_username[:-1]
            poster_username = poster_username.rstrip() + "…"

        description_font = ImageFont.load_default(size=22)
        description_lines = cls._wrap_description(
            draw,
            description,
            description_font,
            max_width=360,
        )
        text_color = (54, 43, 30)

        draw.text(
            (400, 710),
            poster_username,
            font=username_font,
            fill=text_color,
            stroke_width=1,
            stroke_fill=text_color,
            anchor="mm",
        )
        draw.multiline_text(
            (222, 751),
            "\n".join(description_lines),
            font=description_font,
            fill=text_color,
            stroke_width=1,
            stroke_fill=text_color,
            spacing=4,
            align="left",
        )

        output = io.BytesIO()
        poster.save(output, format="PNG", optimize=True)
        return output.getvalue()

    @classmethod
    def _wrap_description(
        cls,
        draw: ImageDraw.ImageDraw,
        description: str,
        font: ImageFont.FreeTypeFont,
        *,
        max_width: int,
    ) -> list[str]:
        if len(description) > cls.DESCRIPTION_MAX_LENGTH:
            raise ValueError(
                f"A descrição deve ter no máximo {cls.DESCRIPTION_MAX_LENGTH} caracteres."
            )

        lines: list[str] = []
        for paragraph in description.splitlines() or [""]:
            if not paragraph:
                lines.append("")
                continue

            current_line = ""
            for word in paragraph.split():
                candidate = f"{current_line} {word}".strip()
                if draw.textlength(candidate, font=font) <= max_width:
                    current_line = candidate
                    continue

                if current_line:
                    lines.append(current_line)
                    current_line = ""

                for character in word:
                    candidate = current_line + character
                    if (
                        current_line
                        and draw.textlength(candidate, font=font) > max_width
                    ):
                        lines.append(current_line)
                        current_line = character
                    else:
                        current_line = candidate

            lines.append(current_line)

        if len(lines) > cls.DESCRIPTION_MAX_LINES:
            raise ValueError(
                "A descrição é longa demais para o cartaz. "
                f"Reduza o texto para caber em até {cls.DESCRIPTION_MAX_LINES} linhas."
            )

        return lines


class ProcuraseDescriptionModal(
    discord.ui.Modal, title="Descrição do cartaz"
):
    description_input = discord.ui.TextInput(
        label="Descrição",
        placeholder="Escreva uma descrição curta; quebras de linha são aceitas.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=Procurase.DESCRIPTION_MAX_LENGTH,
    )

    def __init__(self, cog: Procurase):
        super().__init__(timeout=300)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este formulário só pode ser usado dentro do servidor.",
                ephemeral=True,
            )
            return

        description = self.description_input.value.strip()
        if not description:
            await interaction.response.send_message(
                "Escreva uma descrição para o cartaz.",
                ephemeral=True,
            )
            return

        try:
            await asyncio.to_thread(
                self.cog._wrap_description,
                ImageDraw.Draw(Image.new("RGB", (1, 1))),
                description,
                ImageFont.load_default(size=22),
                max_width=360,
            )
        except ValueError as error:
            await interaction.response.send_message(
                str(error),
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.abc.Messageable):
            await interaction.response.send_message(
                "Não consegui localizar este canal.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self.cog.publish_poster(
                interaction.channel,
                interaction.user,
                description,
            )
        except (discord.HTTPException, OSError, ValueError) as error:
            print(
                f"Erro ao publicar cartaz de {interaction.user.id} "
                f"pelo formulário: {error}"
            )
            await interaction.followup.send(
                "Não consegui pendurar seu cartaz. Tente novamente mais tarde.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "Seu cartaz foi pendurado!",
            ephemeral=True,
        )


class ProcuraseView(discord.ui.View):
    def __init__(self, cog: Procurase):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Pendure seu cartaz",
        style=discord.ButtonStyle.primary,
        emoji="📌",
        custom_id=Procurase.BUTTON_ID,
    )
    async def hang_poster(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        del _button
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Este botão só pode ser usado dentro do servidor.",
                ephemeral=True,
            )
            return

        if interaction.user.bot:
            await interaction.response.send_message(
                "Bots não podem pendurar cartazes.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(ProcuraseDescriptionModal(self.cog))


async def setup(bot: commands.Bot):
    await bot.add_cog(Procurase(bot))
