"""
Orquestracao do fluxo de aceite de contrato no HubSoft apos validacao
de documentos do LeadProspecto.

Fluxo:
1. Localiza o ServicoClienteHubsoft do lead
2. Resolve o id_cliente_servico_contrato via API Matrix
3. Anexa imagens validadas + PDF do atendimento via HubsoftService
4. Marca o contrato como aceito via HubsoftService
5. Atualiza campos de controle no LeadProspecto

As chamadas HTTP ao HubSoft moram em `apps.integracoes.services.hubsoft`.
Aqui ficam apenas a orquestracao, a integracao com a API Matrix e a
montagem dos arquivos a partir das imagens validadas.
"""
import logging
import mimetypes
import os

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# API Matrix — fallback historico (Megalink). O ideal e cada IntegracaoAPI
# carregar a sua propria URL/empresa em configuracoes_extras['matrix'].
MATRIX_API_URL_DEFAULT = "https://apimatrix.megalinkpiaui.com.br/buscar_contrato_servico"
MATRIX_EMPRESA_DEFAULT = "megalink"


def _resolver_matrix_config(integracao=None) -> tuple[str, str]:
    """
    Retorna (matrix_url, matrix_empresa) lendo de
    `IntegracaoAPI.configuracoes_extras['matrix']` quando disponivel.
    Fallback: Megalink (compatibilidade com o estado atual).
    """
    if integracao is not None:
        extras = (integracao.configuracoes_extras or {}).get('matrix') or {}
        url = extras.get('url') or MATRIX_API_URL_DEFAULT
        empresa = extras.get('empresa') or MATRIX_EMPRESA_DEFAULT
        return url, empresa
    return MATRIX_API_URL_DEFAULT, MATRIX_EMPRESA_DEFAULT


def buscar_id_contrato(id_cliente_servico: int, *, integracao=None) -> int | None:
    """
    Consulta a API Matrix para obter o id_cliente_servico_contrato vinculado
    ao servico informado. Retorna o id inteiro ou None em caso de falha.
    """
    matrix_url, matrix_empresa = _resolver_matrix_config(integracao)
    try:
        resp = requests.get(
            matrix_url,
            params={
                "id_cliente_servico": id_cliente_servico,
                "empresa": matrix_empresa,
            },
            timeout=30,
        )
        resp.raise_for_status()
        dados = resp.json()

        id_contrato = (
            dados.get("id_cliente_servico_contrato")
            or dados.get("id_contrato")
            or (dados.get("data") or {}).get("id_cliente_servico_contrato")
        )
        if not id_contrato:
            contratos = dados.get("contratos")
            if contratos and isinstance(contratos, list) and len(contratos) > 0:
                id_contrato = contratos[0]

        if id_contrato:
            return int(id_contrato)

        logger.warning(
            "API Matrix nao retornou id_cliente_servico_contrato para servico %s. Resposta: %s",
            id_cliente_servico, dados,
        )
        return None

    except Exception as exc:
        logger.error(
            "Erro ao buscar id_cliente_servico_contrato para servico %s: %s",
            id_cliente_servico, exc,
        )
        return None


def _obter_hubsoft_service():
    """Retorna instancia de HubsoftService usando a integracao ativa do tipo hubsoft."""
    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.hubsoft import HubsoftService

    integracao = IntegracaoAPI.objects.filter(tipo="hubsoft", ativa=True).first()
    if not integracao:
        raise RuntimeError("Nenhuma integracao HubSoft ativa encontrada.")
    return HubsoftService(integracao)


def _baixar_imagem(url: str) -> tuple[bytes, str] | tuple[None, None]:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        return resp.content, content_type
    except Exception as exc:
        logger.error("Erro ao baixar imagem '%s': %s", url, exc)
        return None, None


def _extensao_para_content_type(nome: str) -> str:
    tipo, _ = mimetypes.guess_type(nome)
    return tipo or "application/octet-stream"


def anexar_documentos_e_aceitar_contrato(lead) -> bool:
    """
    Fluxo completo de anexacao de documentos e aceite de contrato no HubSoft.

    1. Localiza o ServicoClienteHubsoft do lead
    2. Busca o id_cliente_servico_contrato via API Matrix
    3. Obtem o HubsoftService autenticado
    4. Anexa cada imagem validada (baixada da URL)
    5. Anexa o PDF do atendimento (se existir)
    6. Marca o contrato como aceito
    7. Atualiza lead.anexos_contrato_enviados, contrato_aceito e data_aceite_contrato

    Retorna True se anexos foram enviados (aceite e best-effort).
    """
    from apps.integracoes.services.hubsoft import HubsoftServiceError

    if lead.anexos_contrato_enviados:
        logger.info("Lead %s ja teve documentos anexados ao contrato. Pulando.", lead.pk)
        return True

    cliente_hubsoft = lead.clientes_hubsoft.first()
    if not cliente_hubsoft:
        logger.warning(
            "Lead %s nao possui ClienteHubsoft vinculado. Nao e possivel anexar documentos.",
            lead.pk,
        )
        return False

    servico = cliente_hubsoft.servicos.first()
    if not servico:
        logger.warning(
            "ClienteHubsoft %s (lead %s) nao possui servicos. Nao e possivel anexar documentos.",
            cliente_hubsoft.pk, lead.pk,
        )
        return False

    try:
        hubsoft_service = _obter_hubsoft_service()
    except Exception as exc:
        logger.error("Nao foi possivel instanciar HubsoftService: %s", exc)
        return False

    id_contrato = buscar_id_contrato(
        servico.id_cliente_servico,
        integracao=hubsoft_service.integracao,
    )
    if not id_contrato:
        logger.error(
            "Nao foi possivel obter id_cliente_servico_contrato para servico %s (lead %s).",
            servico.id_cliente_servico, lead.pk,
        )
        return False

    from apps.comercial.leads.models import ImagemLeadProspecto

    arquivos: list[tuple[str, bytes, str]] = []
    erros_download = 0

    imagens_validas = lead.imagens.filter(
        status_validacao=ImagemLeadProspecto.STATUS_VALIDO
    )

    for imagem in imagens_validas:
        conteudo, content_type = _baixar_imagem(imagem.link_url)
        if conteudo is None:
            erros_download += 1
            continue

        url_path = imagem.link_url.rstrip("/").split("/")[-1]
        if "." not in url_path:
            ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
            url_path = f"documento_{imagem.pk}.{ext}"

        descricao_prefix = imagem.descricao.replace(" ", "_")[:30] if imagem.descricao else "doc"
        nome_arquivo = f"{descricao_prefix}_{url_path}"
        arquivos.append((nome_arquivo, conteudo, content_type))

    # PDF da conversa (HubSoft nao aceita text/html)
    if lead.html_conversa_path:
        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root:
            base_dir = getattr(settings, "BASE_DIR", None)
            media_root = os.path.join(str(base_dir), "media") if base_dir else "/tmp"

        caminho_html = os.path.join(media_root, lead.html_conversa_path)
        if os.path.exists(caminho_html):
            try:
                from weasyprint import HTML as WeasyHTML
                pdf_bytes = WeasyHTML(filename=caminho_html).write_pdf()
                # weasyprint gera %🖤 (emoji UTF-8) no segundo comentario do PDF,
                # o que quebra alguns viewers (incluindo HubSoft). Substituido por
                # bytes binarios validos conforme spec PDF.
                pdf_bytes = pdf_bytes.replace(
                    b"%\xf0\x9f\x96\xa4", b"%\xe2\xe3\xcf\xd3", 1,
                )
                arquivos.append((f"conversa_atendimento_{lead.pk}.pdf", pdf_bytes, "application/pdf"))
            except Exception as exc:
                logger.error(
                    "Erro ao converter HTML para PDF (lead %s): %s. Arquivo nao sera anexado.",
                    lead.pk, exc,
                )
        else:
            logger.warning(
                "Arquivo HTML do atendimento nao encontrado em '%s' (lead %s).",
                caminho_html, lead.pk,
            )

    if not arquivos:
        logger.error(
            "Nenhum arquivo disponivel para enviar ao contrato %s (lead %s). "
            "Downloads com erro: %d. Nao sera feito o aceite.",
            id_contrato, lead.pk, erros_download,
        )
        return False

    try:
        hubsoft_service.anexar_arquivos_contrato(id_contrato, arquivos, lead=lead)
    except HubsoftServiceError as exc:
        logger.error(
            "Falha ao enviar arquivos ao contrato %s (lead %s): %s. Nao sera feito o aceite.",
            id_contrato, lead.pk, exc,
        )
        return False

    lead.anexos_contrato_enviados = True
    lead.save(update_fields=["anexos_contrato_enviados"])
    logger.info(
        "[ANEXOS] Lead %s — %d arquivo(s) enviado(s) com sucesso ao contrato %s.",
        lead.pk, len(arquivos), id_contrato,
    )

    contrato_aceito = False
    try:
        hubsoft_service.aceitar_contrato(
            id_contrato,
            observacao="Contrato aceito automaticamente apos validacao de documentos.",
            lead=lead,
        )
        contrato_aceito = True
    except HubsoftServiceError as exc:
        logger.warning(
            "Contrato %s nao pode ser aceito agora (lead %s): %s",
            id_contrato, lead.pk, exc,
        )

    if contrato_aceito and not lead.contrato_aceito:
        lead.contrato_aceito = True
        lead.data_aceite_contrato = timezone.now()
        lead.save(update_fields=["contrato_aceito", "data_aceite_contrato"])

    logger.info(
        "[RESUMO] Lead %s — %d arquivo(s) enviado(s) (%d erro(s) de download). Contrato %s aceito: %s.",
        lead.pk, len(arquivos), erros_download, id_contrato, contrato_aceito,
    )

    return True
