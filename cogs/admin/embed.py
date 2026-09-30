import discord
from discord.ext import commands
import json

class ConfirmarEmbedView(discord.ui.View):
    def __init__(self, content, embeds):
        super().__init__(timeout=120)
        self.content = content
        self.embeds = embeds

    @discord.ui.button(label="Aprovar e Enviar", style=discord.ButtonStyle.green, custom_id="aprovar")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Embed enviado!", embed=None, view=None)
        await interaction.channel.send(content=self.content, embeds=self.embeds)
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red, custom_id="cancelar")
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="embed cancelado", embed=None, view=None)
        self.stop()

class EmbedModal(discord.ui.Modal, title='Criar Embed via JSON'):
    json_input = discord.ui.TextInput(
        label='Cole o código JSON do Embed aqui',
        style=discord.TextStyle.long,
        placeholder='{"content": "Mensagem...", "embeds": [{"title": "Meu Embed", "description": "..."}]}',
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            dados = json.loads(self.json_input.value)
            
            embeds_prontos = []
            texto_content = None

            if isinstance(dados, dict):
                if "embeds" in dados:
                    embeds_prontos = [discord.Embed.from_dict(e) for e in dados["embeds"]]
                else:
                    embeds_prontos = [discord.Embed.from_dict(dados)]
                texto_content = dados.get("content")
            
            elif isinstance(dados, list):
                embeds_prontos = [discord.Embed.from_dict(e) for e in dados if isinstance(e, dict)]

            if not embeds_prontos and not texto_content:
                return await interaction.response.send_message("❌ Nenhum conteúdo ou embed válido encontrado no JSON.", ephemeral=True)

            view = ConfirmarEmbedView(content=texto_content, embeds=embeds_prontos)
            
            mensagem_preview = "**Pré-visualização do Embed:**\n"
            if texto_content:
                mensagem_preview += texto_content
                
            await interaction.response.send_message(
                content=mensagem_preview, 
                embeds=embeds_prontos, 
                view=view, 
                ephemeral=True
            )

        except json.JSONDecodeError:
            await interaction.response.send_message("❌ Erro de formatação: O código colado não é um JSON válido. Verifique se copiou tudo corretamente.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao montar o embed: `{e}`", ephemeral=True)

class CriarEmbedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="criarembed", description="Abre uma janela para criar um embed via código JSON.")
    @commands.has_permissions(administrator=True)
    async def criarembed(self, ctx: commands.Context):
        if ctx.interaction:
            await ctx.interaction.response.send_modal(EmbedModal())
        else:
            await ctx.send("❌ Por favor, use este comando com a barra (`/criarembed`) para abrir o formulário.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CriarEmbedCog(bot))