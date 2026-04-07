"""
Renderer: converte JSON de blocos do editor visual em HTML responsivo para email.

Cada bloco é um dict com 'tipo' e 'props'. O renderer gera HTML inline-styled
compatível com clientes de email (Gmail, Outlook, etc).
"""

from django.utils.html import escape


# ============================================================================
# CONFIGURAÇÃO PADRÃO
# ============================================================================

CONFIG_PADRAO = {
    'largura': 600,
    'cor_fundo': '#f5f5f5',
    'cor_fundo_conteudo': '#ffffff',
    'fonte_padrao': "Arial, Helvetica, sans-serif",
}


# ============================================================================
# RENDERIZADORES DE BLOCO
# ============================================================================

def _render_cabecalho(props):
    logo_url = props.get('logo_url', '')
    cor_fundo = props.get('cor_fundo', '#1a1a2e')
    altura = props.get('altura', 80)
    alinhamento = props.get('alinhamento', 'center')

    conteudo = ''
    if logo_url:
        conteudo = f'<img src="{escape(logo_url)}" alt="Logo" style="max-height:{altura - 20}px; display:block;">'
    else:
        conteudo = '&nbsp;'

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="background-color:{escape(cor_fundo)}; padding:16px 24px; text-align:{alinhamento}; height:{altura}px;">
            {conteudo}
        </td>
    </tr>
</table>'''


def _render_texto(props, fonte):
    conteudo = props.get('conteudo', '')
    alinhamento = props.get('alinhamento', 'left')
    padding = props.get('padding', '20px 24px')
    cor_texto = props.get('cor_texto', '#333333')
    tamanho_fonte = props.get('tamanho_fonte', '14px')

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{padding}; font-family:{fonte}; font-size:{tamanho_fonte}; line-height:1.6; color:{escape(cor_texto)}; text-align:{alinhamento};">
            {conteudo}
        </td>
    </tr>
</table>'''


def _render_imagem(props):
    url = props.get('url', '')
    alt = props.get('alt_text', 'Imagem')
    largura = props.get('largura', '100%')
    link = props.get('link', '')
    border_radius = props.get('border_radius', '0')
    alinhamento = props.get('alinhamento', 'center')
    padding = props.get('padding', '10px 24px')

    img = f'<img src="{escape(url)}" alt="{escape(alt)}" style="max-width:{largura}; height:auto; display:block; border-radius:{border_radius};" width="{largura}">'

    if link:
        img = f'<a href="{escape(link)}" target="_blank">{img}</a>'

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{padding}; text-align:{alinhamento};">
            {img}
        </td>
    </tr>
</table>'''


def _render_botao(props, fonte):
    texto = props.get('texto', 'Clique aqui')
    url = props.get('url', '#')
    cor_botao = props.get('cor_botao', '#3b82f6')
    cor_texto = props.get('cor_texto', '#ffffff')
    border_radius = props.get('border_radius', '6px')
    tamanho = props.get('tamanho', 'medio')
    alinhamento = props.get('alinhamento', 'center')
    padding = props.get('padding', '16px 24px')

    tamanhos = {
        'pequeno': 'padding:8px 20px; font-size:12px;',
        'medio': 'padding:12px 28px; font-size:14px;',
        'grande': 'padding:14px 36px; font-size:16px;',
    }
    estilo_tamanho = tamanhos.get(tamanho, tamanhos['medio'])

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{padding}; text-align:{alinhamento};">
            <a href="{escape(url)}" target="_blank" style="display:inline-block; background-color:{escape(cor_botao)}; color:{escape(cor_texto)}; text-decoration:none; font-family:{fonte}; font-weight:600; border-radius:{border_radius}; {estilo_tamanho}">
                {escape(texto)}
            </a>
        </td>
    </tr>
</table>'''


def _render_divisor(props):
    estilo = props.get('estilo', 'solid')
    cor = props.get('cor', '#e5e7eb')
    espessura = props.get('espessura', '1px')
    largura = props.get('largura', '100%')
    margem = props.get('margem', '10px 24px')

    if estilo == 'espaco':
        return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr><td style="padding:{margem};">&nbsp;</td></tr>
</table>'''

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{margem};">
            <hr style="border:none; border-top:{espessura} {estilo} {escape(cor)}; width:{largura}; margin:0 auto;">
        </td>
    </tr>
</table>'''


def _render_espacamento(props):
    altura = props.get('altura', 20)
    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr><td style="height:{altura}px; line-height:{altura}px; font-size:1px;">&nbsp;</td></tr>
</table>'''


def _render_colunas(props, fonte):
    layout = props.get('layout', '2')
    gap = props.get('gap', '16px')
    colunas = props.get('colunas', [])
    padding = props.get('padding', '10px 24px')

    layouts = {
        '1': ['100%'],
        '2': ['50%', '50%'],
        '3': ['33.33%', '33.33%', '33.33%'],
        '1-2': ['33.33%', '66.67%'],
        '2-1': ['66.67%', '33.33%'],
    }
    larguras = layouts.get(str(layout), layouts['2'])

    tds = ''
    for i, coluna in enumerate(colunas):
        if i >= len(larguras):
            break
        blocos_html = ''
        for bloco in coluna.get('blocos', []):
            blocos_html += _render_bloco(bloco, fonte)

        largura_col = larguras[i]
        tds += f'<td style="width:{largura_col}; vertical-align:top; padding:0 {gap};">{blocos_html}</td>\n'

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{padding};">
            <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                <tr>{tds}</tr>
            </table>
        </td>
    </tr>
</table>'''


def _render_card_plano(props, fonte):
    nome = props.get('nome', 'Plano')
    preco = props.get('preco', '')
    beneficios = props.get('beneficios', [])
    texto_botao = props.get('texto_botao', 'Assinar')
    url_botao = props.get('url_botao', '#')
    cor_destaque = props.get('cor_destaque', '#3b82f6')
    cor_fundo = props.get('cor_fundo', '#ffffff')
    padding = props.get('padding', '16px 24px')

    lista = ''
    for b in beneficios:
        lista += f'<li style="padding:4px 0; font-size:13px; color:#555;">{escape(b)}</li>'

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{padding};">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:{escape(cor_fundo)}; border:2px solid {escape(cor_destaque)}; border-radius:10px; overflow:hidden;" role="presentation">
                <tr>
                    <td style="background:{escape(cor_destaque)}; color:#fff; text-align:center; padding:14px; font-family:{fonte}; font-size:18px; font-weight:700;">
                        {escape(nome)}
                    </td>
                </tr>
                <tr>
                    <td style="text-align:center; padding:20px 16px 10px; font-family:{fonte};">
                        <div style="font-size:28px; font-weight:800; color:{escape(cor_destaque)};">{escape(preco)}</div>
                    </td>
                </tr>
                <tr>
                    <td style="padding:10px 24px 20px; font-family:{fonte};">
                        <ul style="list-style:none; padding:0; margin:0;">{lista}</ul>
                    </td>
                </tr>
                <tr>
                    <td style="text-align:center; padding:0 24px 20px;">
                        <a href="{escape(url_botao)}" target="_blank" style="display:inline-block; background:{escape(cor_destaque)}; color:#fff; text-decoration:none; padding:10px 28px; border-radius:6px; font-family:{fonte}; font-weight:600; font-size:14px;">
                            {escape(texto_botao)}
                        </a>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>'''


def _render_lista(props, fonte):
    itens = props.get('itens', [])
    estilo = props.get('estilo', 'check')
    cor_icone = props.get('cor_icone', '#3b82f6')
    padding = props.get('padding', '10px 24px')

    icones = {
        'check': '&#10003;',
        'bullet': '&#8226;',
        'star': '&#9733;',
        'arrow': '&#10148;',
    }
    icone = icones.get(estilo, icones['check'])

    linhas = ''
    for i, item in enumerate(itens):
        numero = f'{i + 1}.' if estilo == 'numero' else icone
        linhas += f'''<tr>
    <td style="padding:4px 8px 4px 0; color:{escape(cor_icone)}; font-size:14px; vertical-align:top; width:24px; text-align:center; font-family:{fonte};">{numero}</td>
    <td style="padding:4px 0; font-size:14px; color:#333; font-family:{fonte};">{escape(item)}</td>
</tr>'''

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{padding};">
            <table cellpadding="0" cellspacing="0" role="presentation">{linhas}</table>
        </td>
    </tr>
</table>'''


def _render_depoimento(props, fonte):
    texto = props.get('texto', '')
    nome = props.get('nome', '')
    cargo = props.get('cargo', '')
    foto_url = props.get('foto_url', '')
    padding = props.get('padding', '16px 24px')

    foto_html = ''
    if foto_url:
        foto_html = f'<img src="{escape(foto_url)}" alt="{escape(nome)}" style="width:48px; height:48px; border-radius:50%; display:block;">'

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="padding:{padding};">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb; border-left:4px solid #3b82f6; border-radius:0 8px 8px 0;" role="presentation">
                <tr>
                    <td style="padding:20px 24px; font-family:{fonte};">
                        <p style="font-size:14px; font-style:italic; color:#555; line-height:1.6; margin:0 0 12px;">&ldquo;{escape(texto)}&rdquo;</p>
                        <table cellpadding="0" cellspacing="0" role="presentation">
                            <tr>
                                {'<td style="padding-right:12px; vertical-align:middle;">' + foto_html + '</td>' if foto_html else ''}
                                <td style="vertical-align:middle;">
                                    <div style="font-size:13px; font-weight:700; color:#333;">{escape(nome)}</div>
                                    <div style="font-size:12px; color:#888;">{escape(cargo)}</div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>'''


def _render_rodape(props, fonte):
    texto = props.get('texto', '')
    cor_fundo = props.get('cor_fundo', '#1a1a2e')
    cor_texto = props.get('cor_texto', '#aaaaaa')
    link_descadastro = props.get('link_descadastro', True)
    redes_sociais = props.get('redes_sociais', {})
    padding = props.get('padding', '24px')

    redes_html = ''
    icones_redes = {
        'facebook': '&#xf09a;',
        'instagram': '&#xf16d;',
        'linkedin': '&#xf0e1;',
        'youtube': '&#xf167;',
    }
    for rede, url in redes_sociais.items():
        if url:
            redes_html += f'<a href="{escape(url)}" target="_blank" style="color:{escape(cor_texto)}; text-decoration:none; margin:0 6px; font-size:16px;">{rede.title()}</a> '

    descadastro_html = ''
    if link_descadastro:
        descadastro_html = f'<p style="margin:8px 0 0;"><a href="{{{{link_descadastro}}}}" style="color:{escape(cor_texto)}; text-decoration:underline; font-size:11px;">Descadastrar</a></p>'

    return f'''<table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
        <td style="background-color:{escape(cor_fundo)}; padding:{padding}; text-align:center; font-family:{fonte}; font-size:12px; color:{escape(cor_texto)};">
            {redes_html}
            <p style="margin:8px 0 0; line-height:1.5;">{texto}</p>
            {descadastro_html}
        </td>
    </tr>
</table>'''


def _render_html_custom(props):
    return props.get('html', '')


# ============================================================================
# DISPATCHER
# ============================================================================

RENDERERS = {
    'cabecalho': lambda p, f: _render_cabecalho(p),
    'texto': _render_texto,
    'imagem': lambda p, f: _render_imagem(p),
    'botao': _render_botao,
    'divisor': lambda p, f: _render_divisor(p),
    'espacamento': lambda p, f: _render_espacamento(p),
    'colunas': _render_colunas,
    'card_plano': _render_card_plano,
    'lista': _render_lista,
    'depoimento': _render_depoimento,
    'rodape': lambda p, f: _render_rodape(p, f),
    'html_custom': lambda p, f: _render_html_custom(p),
}


def _render_bloco(bloco, fonte):
    """Renderiza um único bloco em HTML."""
    tipo = bloco.get('tipo', '')
    props = bloco.get('props', {})
    renderer = RENDERERS.get(tipo)
    if renderer:
        return renderer(props, fonte)
    return f'<!-- bloco desconhecido: {escape(tipo)} -->'


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def renderizar_email(config, blocos):
    """
    Converte config + lista de blocos em HTML de email responsivo.

    Args:
        config: dict com configurações globais (largura, cores, fonte)
        blocos: list de dicts com 'tipo', 'id', 'props'

    Returns:
        string HTML completa pronta para envio
    """
    cfg = {**CONFIG_PADRAO, **(config or {})}
    largura = cfg['largura']
    cor_fundo = cfg['cor_fundo']
    cor_conteudo = cfg['cor_fundo_conteudo']
    fonte = cfg['fonte_padrao']

    # Renderiza todos os blocos
    blocos_html = ''
    for bloco in (blocos or []):
        blocos_html += _render_bloco(bloco, fonte)

    return f'''<!DOCTYPE html>
<html lang="pt-BR" xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Email</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
        table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; }}
        img {{ -ms-interpolation-mode:bicubic; border:0; outline:none; text-decoration:none; }}
        body {{ margin:0; padding:0; width:100% !important; }}
        a[x-apple-data-detectors] {{ color:inherit !important; text-decoration:none !important; }}
        @media only screen and (max-width: 620px) {{
            .email-container {{ width:100% !important; max-width:100% !important; }}
            .email-container td {{ padding-left:16px !important; padding-right:16px !important; }}
            .stack-column {{ display:block !important; width:100% !important; }}
        }}
    </style>
</head>
<body style="margin:0; padding:0; background-color:{escape(cor_fundo)}; font-family:{fonte};">
    <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background-color:{escape(cor_fundo)};">
        <tr>
            <td align="center" style="padding:24px 0;">
                <!--[if mso]><table role="presentation" width="{largura}"><tr><td><![endif]-->
                <table class="email-container" width="{largura}" cellpadding="0" cellspacing="0" role="presentation" style="max-width:{largura}px; width:100%; background-color:{escape(cor_conteudo)}; border-radius:8px; overflow:hidden;">
                    <tr>
                        <td>
                            {blocos_html}
                        </td>
                    </tr>
                </table>
                <!--[if mso]></td></tr></table><![endif]-->
            </td>
        </tr>
    </table>
</body>
</html>'''
