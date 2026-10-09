"""Criador de mensagens: embeds clássicos e Components V2.

Requer Python 3.10 ou superior.
Instalação: python -m pip install -U 'discord.py>=2.6,<3'
Substitua o cog antigo, mantenha seu load_extension e sincronize a árvore de
comandos pelo procedimento que o bot já usa. Não carregue os dois cogs juntos.

/criarembed: formulário para JSON de até 4.000 caracteres.
/criarembedarquivo arquivo: anexe JSON UTF-8 de até 1 MB (ideal para as regras).
A prévia e a confirmação são privadas. Só publica após aprovação do autor.

V2 suportado: Container (17), TextDisplay (10), MediaGallery (12), Separator
(14). Outros componentes são recusados explicitamente: botões interativos
personalizados precisam de callbacks próprios, não basta importar seu JSON.
Embeds clássicos continuam aceitos. Não misture embeds/content com V2.
IDs de componentes e actions vazio de exportadores são dispensáveis.

Exemplo V2 (troque a URL por uma imagem acessível e mantenha parâmetros):
{"components":[{"type":17,"components":[
 {"type":12,"items":[{"media":{"url":"https://seu-site/banner.gif"}}]},
 {"type":10,"content":"# Regras\\nBem-vindo(a)!"},
 {"type":14},
 {"type":10,"content":"Respeite todos os membros."}
]}]}

O limite do texto visível V2 é validado separadamente do tamanho do JSON.
Links temporários do Discord podem expirar: recopie links válidos completos.
Este cog não envia arquivos de mídia: attachment:// exige implementação de
anexos e não é aceito aqui. AllowedMentions.none evita pings acidentais.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import discord
from discord import app_commands
from discord.ext import commands

if not hasattr(discord.ui, 'LayoutView'):
    raise RuntimeError('Este cog precisa de discord.py >= 2.6. Atualize a dependência.')

log = logging.getLogger(__name__)
MAX_FILE = 1_000_000


class JSONInvalido(ValueError):
    pass


def exigir(condicao, mensagem):
    if not condicao:
        raise JSONInvalido(mensagem)


def imagem_url(valor):
    exigir(isinstance(valor, str), 'A imagem precisa de media.url.')
    url = urlsplit(valor)
    exigir(url.scheme in ('https', 'http') and bool(url.netloc),
           'Use uma URL http/https completa para a imagem; attachment:// não é suportado.')
    return valor


@dataclass
class Mensagem:
    content: str | None = None
    embeds: list | None = None
    components: list | None = None

    def envio(self):
        args = {'allowed_mentions': discord.AllowedMentions.none()}
        if self.components is not None:
            view = discord.ui.LayoutView(timeout=None)
            for item in self.components:
                view.add_item(componente(item))
            exigir(view.total_children_count <= 40, 'Máximo de 40 componentes por mensagem.')
            exigir(view.content_length() <= 4000, 'O texto visível V2 excede 4.000 caracteres. Divida em mensagens.')
            args['view'] = view  # discord.py define IS_COMPONENTS_V2 automaticamente.
        else:
            args.update(content=self.content, embeds=self.embeds or [])
        return args


def componente(item, dentro=False):
    exigir(isinstance(item, dict), 'Cada componente precisa ser um objeto JSON.')
    tipo = item.get('type')
    if tipo == 10:
        texto = item.get('content')
        exigir(isinstance(texto, str) and 0 < len(texto) <= 4000, 'TextDisplay exige texto de 1 a 4.000 caracteres.')
        return discord.ui.TextDisplay(texto)
    if tipo == 12:
        itens = item.get('items')
        exigir(isinstance(itens, list) and 1 <= len(itens) <= 10, 'MediaGallery exige de 1 a 10 imagens.')
        galeria = []
        for entrada in itens:
            exigir(isinstance(entrada, dict) and isinstance(entrada.get('media'), dict), 'Item de galeria inválido.')
            descricao = entrada.get('description')
            exigir(descricao is None or isinstance(descricao, str) and len(descricao) <= 1024, 'Descrição da imagem inválida.')
            galeria.append(discord.MediaGalleryItem(
                imagem_url(entrada['media'].get('url')),
                description=descricao, spoiler=bool(entrada.get('spoiler', False))))
        return discord.ui.MediaGallery(*galeria)
    if tipo == 14:
        espaco = item.get('spacing', 1)
        exigir(espaco in (1, 2), 'Separator.spacing deve ser 1 ou 2.')
        return discord.ui.Separator(visible=bool(item.get('divider', True)), spacing=discord.SeparatorSpacing(espaco))
    if tipo == 17:
        exigir(not dentro, 'Não coloque um Container dentro de outro Container.')
        filhos = item.get('components')
        exigir(isinstance(filhos, list) and 1 <= len(filhos) <= 39, 'Container precisa ter componentes (máximo 39 aqui).')
        cor = item.get('accent_color')
        exigir(cor is None or type(cor) is int and 0 <= cor <= 0xFFFFFF, 'accent_color precisa ser um inteiro RGB válido.')
        return discord.ui.Container(*(componente(f, True) for f in filhos),
                                    accent_colour=cor, spoiler=bool(item.get('spoiler', False)))
    raise JSONInvalido(f'Componente type={tipo} não suportado. Este cog aceita 10, 12, 14 e 17.')


def interpretar(texto):
    try:
        dados = json.loads(texto)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise JSONInvalido('JSON inválido: envie JSON puro, sem ``` e sem escapes copiados do chat.') from exc
    if isinstance(dados, list):
        dados = {'embeds': dados}
    exigir(isinstance(dados, dict), 'Use um objeto de mensagem ou uma lista de embeds.')
    exigir(not dados.get('actions'), 'actions com conteúdo exige programação própria e não será ignorado.')
    exigir(not any(dados.get(k) for k in ('attachments', 'poll', 'stickers', 'sticker_ids', 'tts')),
           'Este importador não aceita anexos, enquetes, stickers ou TTS.')
    if dados.get('components'):
        exigir(not dados.get('content') and not dados.get('embeds'), 'V2 não aceita content/embeds junto dos componentes. Use TextDisplay.')
        exigir(isinstance(dados['components'], list) and len(dados['components']) <= 40, 'Lista de componentes inválida.')
        mensagem = Mensagem(components=dados['components'])
        mensagem.envio()  # Valida antes de publicar a prévia.
        return mensagem
    exigir(not (int(dados.get('flags', 0)) & 32768), 'Flags V2 sem componentes: informe components.')
    if 'embeds' not in dados and any(k in dados for k in ('title', 'description', 'fields', 'image', 'thumbnail', 'author', 'footer')):
        exigir(not dados.get('content'), 'Para misturar texto e embed, use {"content": ..., "embeds": [...]} .')
        lista = [dados]
    else:
        lista = dados.get('embeds', [])
    exigir(isinstance(lista, list) and len(lista) <= 10, 'Máximo de 10 embeds.')
    embeds = []
    for obj in lista:
        exigir(isinstance(obj, dict), 'Cada embed precisa ser um objeto.')
        try:
            embed = discord.Embed.from_dict(obj)
            exigir(bool(embed), 'Foi encontrado um embed vazio.')
            exigir(len(embed.title or '') <= 256 and len(embed.description or '') <= 4096, 'Título/descrição do embed excede o limite.')
            exigir(len(embed.fields) <= 25, 'Máximo de 25 campos por embed.')
            for campo in embed.fields:
                exigir(0 < len(campo.name) <= 256 and 0 < len(campo.value) <= 1024, 'Campo de embed vazio ou grande demais.')
            exigir(len(embed.footer.text or '') <= 2048 and len(embed.author.name or '') <= 256, 'Autor/rodapé grande demais.')
            embeds.append(embed)
        except (TypeError, AttributeError, KeyError) as exc:
            raise JSONInvalido('Estrutura de embed inválida.') from exc
    exigir(sum(len(e) for e in embeds) <= 6000, 'O texto dos embeds excede 6.000 caracteres no total.')
    content = dados.get('content') or None
    exigir(content is None or isinstance(content, str) and len(content) <= 2000, 'content deve ter até 2.000 caracteres.')
    exigir(bool(content or embeds), 'Nenhum texto, embed ou componente encontrado.')
    return Mensagem(content=content, embeds=embeds)


def administrador(interaction):
    return interaction.guild is not None and isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator


class ConfirmarEmbedView(discord.ui.View):
    def __init__(self, mensagem, autor, canal):
        super().__init__(timeout=120)
        self.mensagem, self.autor, self.canal = mensagem, autor, canal
        self.lock = asyncio.Lock()
        self.finalizado = False
        self.controle = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor or not administrador(interaction):
            await interaction.response.send_message('Somente o administrador que criou a prévia pode confirmar.', ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        async with self.lock:
            if self.finalizado:
                return
            self.finalizado = True
            if self.controle:
                try:
                    await self.controle.edit(content='Prévia expirada. Execute o comando novamente.', view=None)
                except discord.HTTPException:
                    pass

    @discord.ui.button(label='Aprovar e Enviar', style=discord.ButtonStyle.green)
    async def aprovar(self, interaction, button):
        await interaction.response.defer()
        async with self.lock:
            if self.finalizado:
                return
            self.finalizado = True  # Um clique somente, inclusive durante o envio.
            try:
                exigir(self.canal is not None and hasattr(self.canal, 'send'), 'Canal indisponível.')
                enviado = await self.canal.send(**self.mensagem.envio())
            except (discord.HTTPException, JSONInvalido) as exc:
                log.warning('Falha ao publicar mensagem: %s', exc)
                resultado = 'Não foi possível confirmar o envio. Verifique o canal e os logs antes de tentar de novo (evite duplicar a mensagem).'
            else:
                resultado = f'Mensagem enviada! {enviado.jump_url}'
            self.stop()
            await interaction.edit_original_response(content=resultado, view=None)

    @discord.ui.button(label='Cancelar', style=discord.ButtonStyle.red)
    async def cancelar(self, interaction, button):
        await interaction.response.defer()
        async with self.lock:
            if self.finalizado:
                return
            self.finalizado = True
            self.stop()
            await interaction.edit_original_response(content='Envio cancelado.', view=None)

    async def on_error(self, interaction, error, item):
        log.error('Erro no controle da prévia', exc_info=(type(error), error, error.__traceback__))
        await interaction.followup.send('Falha no controle. Confira o canal antes de repetir o envio.', ephemeral=True)


async def mostrar_previa(interaction, texto):
    if not administrador(interaction):
        await interaction.followup.send('Comando exclusivo de administradores em servidores.', ephemeral=True)
        return
    try:
        mensagem = interpretar(texto)
        # Prévia V2 em mensagem própria: nunca mistura content/embeds/View comum.
        await interaction.followup.send(**mensagem.envio(), ephemeral=True, wait=True)
        view = ConfirmarEmbedView(mensagem, interaction.user.id, interaction.channel)
        view.controle = await interaction.followup.send(
            'Confira a prévia acima. Publicar neste canal? (expira em 2 minutos)',
            view=view, ephemeral=True, wait=True)
    except (ValueError, TypeError, RecursionError) as exc:
        await interaction.followup.send(f'JSON recusado: {str(exc)[:1000]}', ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.exception('Discord recusou a prévia')
        await interaction.followup.send('O Discord recusou a prévia. Confira URLs das imagens, limites e permissões. Detalhes no log do bot.', ephemeral=True)


class EmbedModal(discord.ui.Modal, title='Criar mensagem via JSON'):
    json_input = discord.ui.TextInput(label='JSON: embeds ou Components V2',
        style=discord.TextStyle.long, required=True, max_length=4000,
        placeholder='JSON grande? Use /criarembedarquivo e anexe o arquivo .json.')

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await mostrar_previa(interaction, self.json_input.value)


class CriarEmbedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='criarembed', description='Cria mensagem por JSON com prévia privada.')
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def criarembed(self, ctx: commands.Context):
        if ctx.interaction:
            await ctx.interaction.response.send_modal(EmbedModal())
        else:
            await ctx.send('Use /criarembed ou /criarembedarquivo.')

    @app_commands.command(name='criarembedarquivo', description='Importa um arquivo JSON com prévia antes de publicar.')
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(arquivo='Arquivo .json UTF-8 (até 1 MB); não anexe o arquivo Python.')
    async def criarembedarquivo(self, interaction: discord.Interaction, arquivo: discord.Attachment):
        if not administrador(interaction):
            await interaction.response.send_message('Apenas administradores.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not arquivo.filename.lower().endswith('.json') or arquivo.size > MAX_FILE:
            await interaction.followup.send('Envie um arquivo .json de até 1 MB.', ephemeral=True)
            return
        try:
            texto = (await arquivo.read()).decode('utf-8-sig')
        except UnicodeDecodeError:
            await interaction.followup.send('Salve o JSON com codificação UTF-8.', ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.followup.send('Não foi possível baixar o anexo. Envie novamente.', ephemeral=True)
            return
        await mostrar_previa(interaction, texto)


async def setup(bot):
    await bot.add_cog(CriarEmbedCog(bot))