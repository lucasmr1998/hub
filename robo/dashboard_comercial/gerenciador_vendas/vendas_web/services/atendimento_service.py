"""
Serviço responsável por buscar dados do atendimento via API externa,
gerar um arquivo HTML com o histórico de mensagens e salvá-lo em disco.
"""
import logging
import os
import re
import requests

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

API_URL = os.environ.get('MATRIX_API_URL', 'https://megalink.matrixdobrasil.ai/rest/v1/atendimento')
API_TOKEN = os.environ.get('MATRIX_API_TOKEN')
if not API_TOKEN:
    logger.warning("MATRIX_API_TOKEN não definido. Integração Matrix desabilitada.")
PASTA_CONVERSAS = "conversas_atendimento"

# Mapa simples de códigos de emoji usados na API (ex: ##1f680##)
_EMOJI_MAP = {
    "1f680": "🚀",
    "263a": "☺️",
    "1f600": "😀",
    "1f4e3": "📣",
    "1f4f6": "📶",
    "1f4b0": "💰",
}


def _substituir_emojis(texto: str) -> str:
    """Substitui padrões ##codigo## pelos emojis correspondentes."""
    def _replace(match):
        codigo = match.group(1).lower()
        return _EMOJI_MAP.get(codigo, match.group(0))
    return re.sub(r"##([0-9a-fA-F]+)##", _replace, texto)


def _mascarar_cpf(cpf: str) -> str:
    """Exibe apenas os 3 primeiros e os 2 últimos dígitos do CPF."""
    digitos = re.sub(r"\D", "", cpf)
    if len(digitos) == 11:
        return f"{digitos[:3]}.***.***-{digitos[-2:]}"
    return cpf


def buscar_dados_atendimento(codigo_atendimento: str) -> dict | None:
    """
    Chama GET /rest/v1/atendimento?codigo_atendimento=<codigo>.
    Retorna o dict do JSON ou None em caso de erro.
    """
    try:
        resp = requests.get(
            API_URL,
            params={"codigo_atendimento": codigo_atendimento},
            headers={
                "Authorization": API_TOKEN,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error(
            "Erro ao buscar atendimento %s da API externa: %s",
            codigo_atendimento,
            exc,
        )
        return None


def _gerar_html(dados: dict, lead=None) -> str:
    """
    Recebe o dict retornado pela API e devolve uma string HTML
    com o histórico de mensagens formatado como chat.
    O parâmetro `lead` é usado como fallback para CPF e Email quando
    a API não retorna esses dados.
    """
    id_atendimento = dados.get("id_atendimento", "")
    protocolo = dados.get("protocolo", "")
    data_entrada = dados.get("data_entrada", "")
    status = dados.get("status", "")
    servico = dados.get("servico", "")
    conta = dados.get("conta", "")
    agente = dados.get("agente", "") or "—"

    contato = dados.get("contato", {})
    nome_contato = contato.get("contato", "")
    telefone_contato = contato.get("telefone", "")

    # CPF: usa o da API; se vazio, usa o do lead
    cpf_api = contato.get("cpf", "")
    if not cpf_api and lead and getattr(lead, "cpf_cnpj", None):
        cpf_api = lead.cpf_cnpj
    cpf_contato = _mascarar_cpf(cpf_api) if cpf_api else "—"

    # Email: usa o da API; se vazio, usa o do lead
    email_api = contato.get("email", "")
    if not email_api and lead and getattr(lead, "email", None):
        email_api = lead.email
    email_contato = email_api or "—"

    mensagens = dados.get("mensagens", [])

    linhas_msgs = []
    for msg in mensagens:
        entrante = msg.get("boleano_entrante", "0") == "1"
        autor = msg.get("autor", "")
        data_msg = msg.get("data_msg", "")
        texto = _substituir_emojis(msg.get("descricao_msg", ""))
        tipo = msg.get("tip_msg", "TEXTO")

        lado_classe = "msg-cliente" if entrante else "msg-bot"
        lado_label = "cliente" if entrante else "bot"
        texto_html = texto.replace("\n", "<br>")

        linhas_msgs.append(f"""
        <div class="msg-wrapper {lado_label}">
            <div class="bubble {lado_classe}">
                <div class="msg-autor">{autor}</div>
                <div class="msg-texto">{texto_html}</div>
                <div class="msg-meta">{data_msg} &middot; {tipo}</div>
            </div>
        </div>""")

    corpo_msgs = "\n".join(linhas_msgs) if linhas_msgs else "<p>Nenhuma mensagem registrada.</p>"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Conversa #{id_atendimento} — {nome_contato}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f0f2f5;
            color: #1a1a1a;
            padding: 24px 16px;
        }}
        .container {{ max-width: 780px; margin: 0 auto; }}

        /* Cabeçalho */
        .header {{
            background: #075e54;
            color: #fff;
            border-radius: 12px 12px 0 0;
            padding: 20px 24px;
        }}
        .header h1 {{ font-size: 1.2rem; margin-bottom: 4px; }}
        .header .meta {{ font-size: 0.82rem; opacity: 0.85; line-height: 1.6; }}
        .header .badge {{
            display: inline-block;
            background: #128c7e;
            border-radius: 20px;
            padding: 2px 10px;
            font-size: 0.75rem;
            margin-top: 6px;
        }}

        /* Card de contato */
        .contact-card {{
            background: #fff;
            border-left: 4px solid #25d366;
            padding: 14px 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px 32px;
            font-size: 0.88rem;
        }}
        .contact-card .field {{ display: flex; flex-direction: column; }}
        .contact-card .label {{ font-size: 0.73rem; color: #777; text-transform: uppercase; }}
        .contact-card .value {{ font-weight: 600; color: #1a1a1a; }}

        /* Área de chat */
        .chat-area {{
            background: #e5ddd5;
            background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23c9bdb5' fill-opacity='0.18'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            padding: 20px 16px;
            min-height: 300px;
            border-radius: 0 0 12px 12px;
        }}
        .msg-wrapper {{
            display: flex;
            margin-bottom: 10px;
        }}
        .msg-wrapper.cliente {{ justify-content: flex-start; }}
        .msg-wrapper.bot     {{ justify-content: flex-end; }}

        .bubble {{
            max-width: 72%;
            padding: 9px 13px 6px;
            border-radius: 8px;
            font-size: 0.9rem;
            line-height: 1.45;
            box-shadow: 0 1px 2px rgba(0,0,0,.13);
            position: relative;
        }}
        .msg-cliente {{
            background: #fff;
            border-top-left-radius: 2px;
        }}
        .msg-bot {{
            background: #dcf8c6;
            border-top-right-radius: 2px;
        }}
        .msg-autor {{
            font-size: 0.73rem;
            font-weight: 700;
            color: #075e54;
            margin-bottom: 3px;
        }}
        .msg-bot .msg-autor {{ color: #128c7e; }}
        .msg-texto {{ word-break: break-word; }}
        .msg-meta {{
            font-size: 0.68rem;
            color: #999;
            text-align: right;
            margin-top: 4px;
        }}

        /* Rodapé */
        .footer {{
            text-align: center;
            font-size: 0.74rem;
            color: #aaa;
            margin-top: 16px;
        }}
    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <h1>Conversa — {nome_contato}</h1>
        <div class="meta">
            Protocolo: <strong>{protocolo}</strong> &nbsp;|&nbsp;
            Atendimento: <strong>#{id_atendimento}</strong><br>
            Entrada: {data_entrada} &nbsp;|&nbsp; Agente: {agente}<br>
            Serviço: {servico} &nbsp;|&nbsp; Conta: {conta}
        </div>
        <div class="badge">{status}</div>
    </div>

    <div class="contact-card">
        <div class="field">
            <span class="label">Nome</span>
            <span class="value">{nome_contato}</span>
        </div>
        <div class="field">
            <span class="label">Telefone</span>
            <span class="value">{telefone_contato}</span>
        </div>
        <div class="field">
            <span class="label">CPF</span>
            <span class="value">{cpf_contato}</span>
        </div>
        <div class="field">
            <span class="label">Email</span>
            <span class="value">{email_contato}</span>
        </div>
    </div>

    <div class="chat-area">
        {corpo_msgs}
    </div>

    <div class="footer">
        Gerado automaticamente em {timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")}
    </div>

</div>
</body>
</html>"""


def gerar_html_atendimento(lead, codigo_atendimento: str) -> str | None:
    """
    Busca os dados do atendimento, gera o HTML e salva em disco.
    Atualiza lead.html_conversa_path e lead.data_geracao_html.
    Retorna o caminho relativo do arquivo ou None em caso de falha.
    """
    dados = buscar_dados_atendimento(codigo_atendimento)
    if not dados:
        return None

    html = _gerar_html(dados, lead=lead)

    # Diretório de destino: BASE_DIR/media/conversas_atendimento/
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        # Fallback: pasta media/ ao lado do manage.py
        base_dir = getattr(settings, "BASE_DIR", None)
        media_root = os.path.join(str(base_dir), "media") if base_dir else "/tmp"

    pasta = os.path.join(media_root, PASTA_CONVERSAS)
    os.makedirs(pasta, exist_ok=True)

    nome_arquivo = f"{lead.pk}_{codigo_atendimento}.html"
    caminho_absoluto = os.path.join(pasta, nome_arquivo)
    caminho_relativo = os.path.join(PASTA_CONVERSAS, nome_arquivo)

    try:
        with open(caminho_absoluto, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError as exc:
        logger.error(
            "Erro ao salvar HTML do atendimento %s (lead %s): %s",
            codigo_atendimento,
            lead.pk,
            exc,
        )
        return None

    lead.html_conversa_path = caminho_relativo
    lead.data_geracao_html = timezone.now()
    lead.save(update_fields=["html_conversa_path", "data_geracao_html"])

    logger.info(
        "HTML do atendimento %s gerado para lead %s em %s",
        codigo_atendimento,
        lead.pk,
        caminho_absoluto,
    )
    return caminho_relativo
