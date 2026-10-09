import asyncio
import base64
import binascii
import io
import json
import logging
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import discord
from discord import app_commands
from discord.ext import commands

if not hasattr(discord.ui, 'LayoutView'):
    raise RuntimeError('Este cog precisa de discord.py >= 2.6. Atualize a dependência.')

log = logging.getLogger(__name__)
MAX_FILE = 1_000_000
MAX_MEDIA_BYTES = 8 * 1024 * 1024


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
class Anexos:
    arquivos: list = field(default_factory=list)
    tamanho: int = 0


@dataclass
class Mensagem:
    content: str | None = None
    embeds: list | None = None
    components: list | None = None

    def envio(self):
        args = {'allowed_mentions': discord.AllowedMentions.none()}
        if self.components is not None:
            anexos = Anexos()
            view = discord.ui.LayoutView(timeout=None)
            for item in self.components:
                view.add_item(componente(item, anexos))
            exigir(view.total_children_count <= 40, 'Máximo de 40 componentes por mensagem.')
            exigir(view.content_length() <= 4000, 'O texto visível V2 excede 4.000 caracteres. Divida em mensagens.')
            args['view'] = view  # discord.py define IS_COMPONENTS_V2 automaticamente.
            if anexos.arquivos:
                args['files'] = anexos.arquivos
        else:
            args.update(content=self.content, embeds=self.embeds or [])
        return args


def validar_bool(item, chave, padrao=False):
    valor = item.get(chave, padrao)
    exigir(type(valor) is bool, f'{chave} precisa ser true ou false.')
    return valor


def id_componente(item):
    valor = item.get('id')
    exigir(
        valor is None or type(valor) is int and 0 <= valor <= 0xFFFFFFFF,
        'id de componente precisa ser um inteiro de 0 a 4294967295.',
    )
    return valor


def emoji_componente(valor):
    if valor is None or isinstance(valor, str):
        return valor
    exigir(isinstance(valor, dict), 'emoji precisa ser texto ou objeto.')
    emoji_id = valor.get('id')
    nome = valor.get('name')
    exigir(emoji_id is None or str(emoji_id).isdigit(), 'ID de emoji inválido.')
    exigir(nome is None or isinstance(nome, str), 'Nome de emoji inválido.')
    return discord.PartialEmoji(
        name=nome,
        id=int(emoji_id) if emoji_id is not None else None,
        animated=validar_bool(valor, 'animated'),
    )


def criar_midia(valor, anexos, *, arquivo=False):
    if isinstance(valor, dict):
        valor = valor.get('url')
    exigir(isinstance(valor, str) and valor, 'Mídia precisa ser uma URL ou data URI.')
    if valor.startswith('data:'):
        try:
            cabecalho, conteudo_b64 = valor.split(',', 1)
        except ValueError as exc:
            raise JSONInvalido('Imagem data URI inválida.') from exc
        tipo_mime = cabecalho[5:].split(';', 1)[0].lower()
        exigir(cabecalho.endswith(';base64') and '/' in tipo_mime,
               'Mídia inline precisa indicar um MIME type e usar base64.')
        if not arquivo:
            exigir(
                tipo_mime in ('image/png', 'image/jpeg', 'image/gif', 'image/webp'),
                'Imagem inline precisa ser PNG, JPEG, GIF ou WebP em base64.',
            )
        try:
            conteudo = base64.b64decode(conteudo_b64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise JSONInvalido('Imagem data URI inválida.') from exc
        exigir(bool(conteudo), 'Imagem inline vazia.')
        exigir(anexos.tamanho + len(conteudo) <= MAX_MEDIA_BYTES, 'As mídias inline excedem 8 MB por mensagem.')
        extensao = {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'image/webp': 'webp',
        }.get(tipo_mime, 'bin')
        upload = discord.File(io.BytesIO(conteudo), filename=f'component-media-{len(anexos.arquivos) + 1}.{extensao}')
        anexos.arquivos.append(upload)
        anexos.tamanho += len(conteudo)
        return upload
    exigir(not arquivo, 'File V2 exige uma mídia inline em base64; URLs externas não são anexos.')
    return imagem_url(valor)


def callback_sem_acao(item):
    async def responder(interaction):
        await interaction.response.send_message(
            'Este componente foi importado sem uma ação configurada.',
            ephemeral=True,
        )

    item.callback = responder
    return item


def componente(item, anexos, dentro=False):
    exigir(isinstance(item, dict), 'Cada componente precisa ser um objeto JSON.')
    tipo = item.get('type')
    exigir(type(tipo) is int, 'type do componente precisa ser um número inteiro.')
    componente_id = id_componente(item)
    if tipo == 10:
        texto = item.get('content')
        exigir(isinstance(texto, str) and 0 < len(texto) <= 4000, 'TextDisplay exige texto de 1 a 4.000 caracteres.')
        return discord.ui.TextDisplay(texto, id=componente_id)
    if tipo == 11:
        descricao = item.get('description')
        exigir(descricao is None or isinstance(descricao, str) and len(descricao) <= 1024, 'Descrição da miniatura inválida.')
        return discord.ui.Thumbnail(
            criar_midia(item.get('media'), anexos),
            description=descricao,
            spoiler=validar_bool(item, 'spoiler'),
            id=componente_id,
        )
    if tipo == 12:
        itens = item.get('items')
        exigir(isinstance(itens, list) and 1 <= len(itens) <= 10, 'MediaGallery exige de 1 a 10 imagens.')
        galeria = []
        for entrada in itens:
            exigir(isinstance(entrada, dict), 'Item de galeria inválido.')
            descricao = entrada.get('description')
            exigir(descricao is None or isinstance(descricao, str) and len(descricao) <= 1024, 'Descrição da imagem inválida.')
            galeria.append(discord.MediaGalleryItem(
                criar_midia(entrada.get('media'), anexos),
                description=descricao,
                spoiler=validar_bool(entrada, 'spoiler'),
            ))
        return discord.ui.MediaGallery(*galeria, id=componente_id)
    if tipo == 13:
        arquivo_json = item.get('file')
        exigir(isinstance(arquivo_json, dict), 'File V2 precisa de file.url.')
        return discord.ui.File(
            criar_midia(arquivo_json, anexos, arquivo=True),
            spoiler=validar_bool(item, 'spoiler'),
            id=componente_id,
        )
    if tipo == 14:
        espaco = item.get('spacing', 1)
        exigir(type(espaco) is int and espaco in (1, 2), 'Separator.spacing deve ser 1 ou 2.')
        return discord.ui.Separator(
            visible=validar_bool(item, 'divider', True),
            spacing=discord.SeparatorSpacing(espaco),
            id=componente_id,
        )
    if tipo == 17:
        exigir(not dentro, 'Não coloque um Container dentro de outro Container.')
        filhos = item.get('components')
        exigir(isinstance(filhos, list) and 1 <= len(filhos) <= 39, 'Container precisa ter componentes (máximo 39 aqui).')
        cor = item.get('accent_color')
        exigir(cor is None or type(cor) is int and 0 <= cor <= 0xFFFFFF, 'accent_color precisa ser um inteiro RGB válido.')
        return discord.ui.Container(
            *(componente(f, anexos, True) for f in filhos),
            accent_colour=cor,
            spoiler=validar_bool(item, 'spoiler'),
            id=componente_id,
        )
    if tipo == 9:
        filhos = item.get('components')
        exigir(isinstance(filhos, list) and 1 <= len(filhos) <= 3, 'Section precisa ter de 1 a 3 componentes de texto.')
        textos = [componente(filho, anexos, True) for filho in filhos]
        exigir(all(isinstance(filho, discord.ui.TextDisplay) for filho in textos), 'Section aceita apenas TextDisplay como conteúdo.')
        acessorio = componente(item.get('accessory'), anexos, True)
        exigir(isinstance(acessorio, (discord.ui.Thumbnail, discord.ui.Button)), 'Section precisa de Thumbnail ou Button como accessory.')
        return discord.ui.Section(*textos, accessory=acessorio, id=componente_id)
    if tipo == 1:
        filhos = item.get('components')
        exigir(isinstance(filhos, list) and 1 <= len(filhos) <= 5, 'ActionRow precisa ter de 1 a 5 componentes.')
        itens = [componente(filho, anexos, True) for filho in filhos]
        exigir(
            all(isinstance(filho, discord.ui.Button) for filho in itens)
            or len(itens) == 1 and isinstance(
                itens[0],
                (
                    discord.ui.Select,
                    discord.ui.UserSelect,
                    discord.ui.RoleSelect,
                    discord.ui.MentionableSelect,
                    discord.ui.ChannelSelect,
                ),
            ),
            'ActionRow aceita até 5 botões ou um único select.',
        )
        return discord.ui.ActionRow(*itens, id=componente_id)
    if tipo == 2:
        estilo = item.get('style', 2)
        if isinstance(estilo, str):
            try:
                estilo = discord.ButtonStyle[estilo.lower()]
            except KeyError as exc:
                raise JSONInvalido('style de botão inválido.') from exc
        exigir(type(estilo) is int or isinstance(estilo, discord.ButtonStyle), 'style de botão inválido.')
        url = item.get('url')
        custom_id = item.get('custom_id')
        sku_id = item.get('sku_id')
        exigir(
            sku_id is None or str(sku_id).isdigit(),
            'sku_id precisa ser um identificador numérico.',
        )
        button = discord.ui.Button(
            style=estilo if isinstance(estilo, discord.ButtonStyle) else discord.ButtonStyle(estilo),
            label=item.get('label'),
            disabled=validar_bool(item, 'disabled'),
            custom_id=custom_id,
            url=url,
            emoji=emoji_componente(item.get('emoji')),
            sku_id=int(sku_id) if sku_id is not None and str(sku_id).isdigit() else None,
            id=componente_id,
        )
        exigir(
            (button.url is not None or button.sku_id is not None or button.custom_id is not None),
            'Button precisa de custom_id, url ou sku_id.',
        )
        return callback_sem_acao(button) if button.custom_id else button
    if tipo in (3, 5, 6, 7, 8):
        custom_id = item.get('custom_id')
        exigir(isinstance(custom_id, str) and 0 < len(custom_id) <= 100, 'Select precisa de custom_id.')
        opcoes = item.get('options', [])
        if tipo == 3:
            exigir(isinstance(opcoes, list) and 1 <= len(opcoes) <= 25, 'String Select exige de 1 a 25 opções.')
            exigir(
                all(
                    isinstance(opcao, dict)
                    and isinstance(opcao.get('label'), str)
                    and isinstance(opcao.get('value'), str)
                    for opcao in opcoes
                ),
                'Cada opção de String Select precisa de label e value em texto.',
            )
            opcoes = [
                discord.SelectOption(
                    label=opcao.get('label'),
                    value=opcao.get('value'),
                    description=opcao.get('description'),
                    emoji=emoji_componente(opcao.get('emoji')),
                    default=validar_bool(opcao, 'default'),
                )
                for opcao in opcoes if isinstance(opcao, dict)
            ]
            exigir(len(opcoes) == len(item.get('options', [])), 'Opção de Select inválida.')
        kwargs = {
            'custom_id': custom_id,
            'placeholder': item.get('placeholder'),
            'min_values': item.get('min_values', 1),
            'max_values': item.get('max_values', 1),
            'disabled': validar_bool(item, 'disabled'),
            'required': validar_bool(item, 'required', True),
            'id': componente_id,
        }
        if tipo == 3:
            select = discord.ui.Select(options=opcoes, **kwargs)
        elif tipo == 5:
            exigir(not item.get('default_values'), 'Select default_values não é suportado por este importador.')
            select = discord.ui.UserSelect(**kwargs)
        elif tipo == 6:
            exigir(not item.get('default_values'), 'Select default_values não é suportado por este importador.')
            select = discord.ui.RoleSelect(**kwargs)
        elif tipo == 7:
            exigir(not item.get('default_values'), 'Select default_values não é suportado por este importador.')
            select = discord.ui.MentionableSelect(**kwargs)
        else:
            canais = item.get('channel_types', [])
            exigir(isinstance(canais, list), 'channel_types precisa ser uma lista.')
            exigir(all(type(canal) is int for canal in canais), 'channel_types deve conter números inteiros.')
            exigir(not item.get('default_values'), 'Select default_values não é suportado por este importador.')
            select = discord.ui.ChannelSelect(
                channel_types=[discord.ChannelType(canal) for canal in canais],
                **kwargs,
            )
        return callback_sem_acao(select)
    raise JSONInvalido(
        f'Componente type={tipo} não suportado. Tipos de mensagem aceitos: 1, 2, 3, 5-14 e 17.'
    )


def interpretar(texto):
    try:
        dados = json.loads(texto)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise JSONInvalido('JSON inválido: envie JSON puro, sem ``` e sem escapes copiados do chat.') from exc
    if isinstance(dados, list):
        if any(isinstance(item, dict) and type(item.get('type')) is int for item in dados):
            dados = {'components': dados}
        else:
            dados = {'embeds': dados}
    exigir(isinstance(dados, dict), 'Use um objeto de mensagem ou uma lista de embeds.')
    if type(dados.get('type')) is int:
        dados = {'components': [dados]}
    exigir(not dados.get('actions'), 'actions com conteúdo exige programação própria e não será ignorado.')
    exigir(not any(dados.get(k) for k in ('attachments', 'poll', 'stickers', 'sticker_ids', 'tts')),
           'Este importador não aceita anexos, enquetes, stickers ou TTS.')
    if 'components' in dados:
        exigir(not dados.get('content') and not dados.get('embeds'), 'V2 não aceita content/embeds junto dos componentes. Use TextDisplay.')
        exigir(isinstance(dados['components'], list) and 1 <= len(dados['components']) <= 40, 'Lista de componentes inválida.')
        mensagem = Mensagem(components=dados['components'])
        mensagem.envio()  # Valida antes de publicar a prévia.
        return mensagem
    flags = dados.get('flags', 0)
    exigir(type(flags) is int and not flags & 32768, 'Flags V2 sem componentes: informe components.')
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
    async def aprovar(self, interaction, _button):
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
    async def cancelar(self, interaction, _button):
        await interaction.response.defer()
        async with self.lock:
            if self.finalizado:
                return
            self.finalizado = True
            self.stop()
            await interaction.edit_original_response(content='Envio cancelado.', view=None)

    async def on_error(self, interaction, error, _item):
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