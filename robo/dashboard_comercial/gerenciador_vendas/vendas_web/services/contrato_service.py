"""
Servico responsavel por anexar documentos ao contrato no HubSoft e aceita-lo,
apos todas as imagens de um LeadProspecto serem validadas.

Fluxo:
1. Busca o id_cliente_servico_contrato via API Matrix
2. Anexa cada imagem validada (baixada da URL) ao contrato no HubSoft
3. Anexa o HTML do atendimento ao contrato no HubSoft
4. Marca o contrato como aceito no HubSoft
5. Atualiza os campos de controle no LeadProspecto
"""
import io
import logging
import mimetypes
import os
import time

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# API Matrix para buscar o id do contrato vinculado ao servico
MATRIX_API_URL = "https://apimatrix.megalinkpiaui.com.br/buscar_contrato_servico"
MATRIX_EMPRESA = "megalink"

# Endpoints HubSoft
ENDPOINT_ANEXO = "/api/v1/integracao/cliente/contrato/adicionar_anexo_contrato/{id_contrato}"
ENDPOINT_ACEITAR = "/api/v1/integracao/cliente/contrato/aceitar_contrato"


def buscar_id_contrato(id_cliente_servico: int) -> int | None:
    """
    Consulta a API Matrix para obter o id_cliente_servico_contrato
    vinculado ao servico informado.
    Retorna o id inteiro ou None em caso de falha.
    """
    try:
        resp = requests.get(
            MATRIX_API_URL,
            params={
                "id_cliente_servico": id_cliente_servico,
                "empresa": MATRIX_EMPRESA,
            },
            timeout=30,
        )
        resp.raise_for_status()
        dados = resp.json()

        # A API retorna: {"contratos": [40082], "id_cliente_servico": X, "status": "success"}
        # Tambem pode retornar como campo direto em outros cenarios
        id_contrato = (
            dados.get("id_cliente_servico_contrato")
            or dados.get("id_contrato")
            or (dados.get("data") or {}).get("id_cliente_servico_contrato")
        )

        # Caso o id venha dentro de um array "contratos"
        if not id_contrato:
            contratos = dados.get("contratos")
            if contratos and isinstance(contratos, list) and len(contratos) > 0:
                id_contrato = contratos[0]

        if id_contrato:
            return int(id_contrato)

        logger.warning(
            "API Matrix nao retornou id_cliente_servico_contrato para servico %s. Resposta: %s",
            id_cliente_servico,
            dados,
        )
        return None

    except Exception as exc:
        logger.error(
            "Erro ao buscar id_cliente_servico_contrato para servico %s: %s",
            id_cliente_servico,
            exc,
        )
        return None


def _obter_hubsoft_service():
    """
    Retorna uma instancia de HubsoftService usando a integracao ativa do tipo hubsoft.
    Lanca Exception se nao encontrar.
    """
    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.hubsoft import HubsoftService

    integracao = IntegracaoAPI.objects.filter(tipo="hubsoft", ativa=True).first()
    if not integracao:
        raise RuntimeError("Nenhuma integracao HubSoft ativa encontrada.")

    return HubsoftService(integracao)


def _registrar_log_contrato(integracao, lead, endpoint, metodo, payload, resposta_json,
                            status_code, sucesso, erro, tempo_ms):
    """Registra uma chamada de contrato no LogIntegracao."""
    try:
        from apps.integracoes.models import LogIntegracao
        LogIntegracao.objects.create(
            integracao=integracao,
            lead=lead,
            endpoint=endpoint,
            metodo=metodo,
            payload_enviado=payload,
            resposta_recebida=resposta_json,
            status_code=status_code,
            sucesso=sucesso,
            mensagem_erro=erro,
            tempo_resposta_ms=tempo_ms,
        )
    except Exception as exc:
        logger.warning("Nao foi possivel registrar log de integracao: %s", exc)


def anexar_arquivos_contrato(
    hubsoft_service,
    id_contrato: int,
    arquivos: list[tuple[str, bytes, str]],
    lead=None,
) -> bool:
    """
    Envia múltiplos arquivos de uma só vez ao contrato no HubSoft.

    O HubSoft exige chaves indexadas: files[0], files[1], ...
    com o nome fixo 'file' em cada tupla, conforme documentação oficial:
        ('files[0]', ('file', open(...), 'application/octet-stream'))

    Parâmetros:
        arquivos: lista de tuplas (nome_arquivo, conteudo_bytes, content_type)

    Retorna True se a API retornar status 'success', False caso contrário.
    """
    token = hubsoft_service.obter_token()
    endpoint = ENDPOINT_ANEXO.format(id_contrato=id_contrato)
    url = f"{hubsoft_service.base_url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    # Monta a lista no formato exigido pelo HubSoft: files[0], files[1], ...
    # O segundo elemento da tupla é (nome_real_do_arquivo, bytes, content_type)
    files_payload = [
        (f"files[{i}]", (nome_arquivo, io.BytesIO(conteudo), content_type))
        for i, (nome_arquivo, conteudo, content_type) in enumerate(arquivos)
    ]

    nomes = [nome for nome, _, _ in arquivos]
    total_bytes = sum(len(c) for _, c, _ in arquivos)

    logger.info(
        "[ANEXO] Enviando %d arquivo(s) para contrato %s | arquivos: %s | total: %d bytes | URL: %s",
        len(arquivos), id_contrato, nomes, total_bytes, url,
    )

    inicio = time.time()
    resposta_json = {}
    try:
        resp = requests.post(
            url,
            headers=headers,
            data={},
            files=files_payload,
            timeout=120,
        )
        tempo_ms = int((time.time() - inicio) * 1000)
        try:
            resposta_json = resp.json()
        except Exception:
            resposta_json = {"raw": resp.text[:2000]}
    except Exception as exc:
        tempo_ms = int((time.time() - inicio) * 1000)
        logger.error(
            "[ANEXO] Erro de conexao ao anexar arquivos ao contrato %s: %s",
            id_contrato, exc,
        )
        _registrar_log_contrato(
            integracao=hubsoft_service.integracao,
            lead=lead,
            endpoint=endpoint,
            metodo="POST",
            payload={"id_contrato": id_contrato, "arquivos": nomes, "total_bytes": total_bytes},
            resposta_json={},
            status_code=0,
            sucesso=False,
            erro=str(exc),
            tempo_ms=tempo_ms,
        )
        return False

    sucesso = resp.status_code in (200, 201) and resposta_json.get("status") == "success"

    if sucesso:
        logger.info(
            "[ANEXO] ✅ %d arquivo(s) anexado(s) ao contrato %s com sucesso | HTTP %s | %sms | numero_contrato=%s",
            len(arquivos), id_contrato, resp.status_code, tempo_ms,
            resposta_json.get("numero_contrato", "?"),
        )
    else:
        logger.error(
            "[ANEXO] ❌ Falha ao anexar arquivos ao contrato %s | HTTP %s | %sms | resposta: %s",
            id_contrato, resp.status_code, tempo_ms, resposta_json,
        )

    _registrar_log_contrato(
        integracao=hubsoft_service.integracao,
        lead=lead,
        endpoint=endpoint,
        metodo="POST",
        payload={"id_contrato": id_contrato, "arquivos": nomes, "total_bytes": total_bytes},
        resposta_json=resposta_json,
        status_code=resp.status_code,
        sucesso=sucesso,
        erro="" if sucesso else f"HTTP {resp.status_code}: {resposta_json.get('msg', resp.text[:200])}",
        tempo_ms=tempo_ms,
    )

    return sucesso


def aceitar_contrato(hubsoft_service, id_contrato: int, lead=None) -> bool:
    """
    Marca o contrato como aceito no HubSoft.
    Registra o resultado no LogIntegracao.
    Retorna True em caso de sucesso, False em caso de falha.
    """
    token = hubsoft_service.obter_token()
    url = f"{hubsoft_service.base_url}{ENDPOINT_ACEITAR}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    agora = timezone.localtime(timezone.now())
    payload = {
        "ids_cliente_servico_contrato": [id_contrato],
        "data_aceito": agora.strftime("%Y-%m-%d"),
        "hora_aceito": agora.strftime("%H:%M"),
        "observacao": "Contrato aceito automaticamente apos validacao de documentos.",
    }

    logger.info(
        "[ACEITE] Marcando contrato %s como aceito | URL: %s | payload: %s",
        id_contrato, url, payload,
    )

    inicio = time.time()
    resposta_json = {}
    try:
        resp = requests.put(url, json=payload, headers=headers, timeout=30)
        tempo_ms = int((time.time() - inicio) * 1000)
        try:
            resposta_json = resp.json()
        except Exception:
            resposta_json = {"raw": resp.text[:2000]}
    except Exception as exc:
        tempo_ms = int((time.time() - inicio) * 1000)
        logger.error("[ACEITE] ❌ Erro de conexao ao aceitar contrato %s: %s", id_contrato, exc)
        _registrar_log_contrato(
            integracao=hubsoft_service.integracao,
            lead=lead,
            endpoint=ENDPOINT_ACEITAR,
            metodo="PUT",
            payload=payload,
            resposta_json={},
            status_code=0,
            sucesso=False,
            erro=str(exc),
            tempo_ms=tempo_ms,
        )
        return False

    sucesso = resp.status_code in (200, 201) and resposta_json.get("status") == "success"

    if sucesso:
        logger.info(
            "[ACEITE] ✅ Contrato %s aceito com sucesso | HTTP %s | %sms | resposta: %s",
            id_contrato, resp.status_code, tempo_ms, resposta_json,
        )
    else:
        logger.error(
            "[ACEITE] ❌ Falha ao aceitar contrato %s | HTTP %s | %sms | resposta: %s",
            id_contrato, resp.status_code, tempo_ms, resposta_json,
        )

    _registrar_log_contrato(
        integracao=hubsoft_service.integracao,
        lead=lead,
        endpoint=ENDPOINT_ACEITAR,
        metodo="PUT",
        payload=payload,
        resposta_json=resposta_json,
        status_code=resp.status_code,
        sucesso=sucesso,
        erro="" if sucesso else f"HTTP {resp.status_code}: {resposta_json.get('msg', resp.text[:200])}",
        tempo_ms=tempo_ms,
    )

    return sucesso


def _baixar_imagem(url: str) -> tuple[bytes, str] | tuple[None, None]:
    """
    Baixa uma imagem da URL informada.
    Retorna (conteudo_bytes, content_type) ou (None, None) em caso de falha.
    """
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        return resp.content, content_type
    except Exception as exc:
        logger.error("Erro ao baixar imagem '%s': %s", url, exc)
        return None, None


def _extensao_para_content_type(nome: str) -> str:
    """Retorna o content-type baseado na extensao do arquivo."""
    tipo, _ = mimetypes.guess_type(nome)
    return tipo or "application/octet-stream"


def anexar_documentos_e_aceitar_contrato(lead) -> bool:
    """
    Fluxo completo de anexacao de documentos e aceite de contrato no HubSoft.

    1. Localiza o ServicoClienteHubsoft do lead
    2. Busca o id_cliente_servico_contrato via API Matrix
    3. Obtem o HubsoftService autenticado
    4. Anexa cada imagem validada (baixada da URL)
    5. Anexa o HTML do atendimento (se existir)
    6. Marca o contrato como aceito
    7. Atualiza lead.anexos_contrato_enviados, contrato_aceito e data_aceite_contrato

    Retorna True se todo o fluxo foi concluido com sucesso.
    """
    if lead.anexos_contrato_enviados:
        logger.info(
            "Lead %s ja teve documentos anexados ao contrato. Pulando.",
            lead.pk,
        )
        return True

    # 1. Localizar o ServicoClienteHubsoft
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
            cliente_hubsoft.pk,
            lead.pk,
        )
        return False

    # 2. Buscar id_cliente_servico_contrato via API Matrix
    id_contrato = buscar_id_contrato(servico.id_cliente_servico)
    if not id_contrato:
        logger.error(
            "Nao foi possivel obter id_cliente_servico_contrato para servico %s (lead %s).",
            servico.id_cliente_servico,
            lead.pk,
        )
        return False

    # 3. Obter HubsoftService autenticado
    try:
        hubsoft_service = _obter_hubsoft_service()
    except Exception as exc:
        logger.error("Nao foi possivel instanciar HubsoftService: %s", exc)
        return False

    # 4. Montar lista de arquivos a enviar (imagens + HTML)
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

    # HTML do atendimento — convertido para PDF (HubSoft nao aceita text/html)
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
                # Corrige o segundo comentário do PDF: weasyprint gera %🖤 (emoji UTF-8)
                # que causa falha em alguns viewers (incluindo HubSoft).
                # Substituímos por %âãÏÓ — bytes > 127 válidos conforme spec PDF.
                pdf_bytes = pdf_bytes.replace(
                    b"%\xf0\x9f\x96\xa4",  # %🖤
                    b"%\xe2\xe3\xcf\xd3",  # %âãÏÓ (comentário binário padrão)
                    1,
                )
                arquivos.append((f"conversa_atendimento_{lead.pk}.pdf", pdf_bytes, "application/pdf"))
                logger.info(
                    "[ANEXO] HTML do atendimento convertido para PDF (%d bytes) — lead %s.",
                    len(pdf_bytes), lead.pk,
                )
            except Exception as exc:
                logger.error(
                    "Erro ao converter HTML para PDF (lead %s): %s. "
                    "O arquivo de conversa nao sera anexado.",
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

    # 5. Enviar todos os arquivos em uma unica requisicao (formato files[0], files[1], ...)
    anexos_ok = anexar_arquivos_contrato(hubsoft_service, id_contrato, arquivos, lead=lead)

    if not anexos_ok:
        logger.error(
            "Falha ao enviar arquivos ao contrato %s (lead %s). Nao sera feito o aceite.",
            id_contrato, lead.pk,
        )
        return False

    # 6. Marcar anexos como enviados independentemente do aceite
    lead.anexos_contrato_enviados = True
    lead.save(update_fields=["anexos_contrato_enviados"])
    logger.info(
        "[ANEXOS] Lead %s — %d arquivo(s) enviado(s) com sucesso ao contrato %s.",
        lead.pk, len(arquivos), id_contrato,
    )

    # 7. Aceitar contrato (pode nao estar disponivel dependendo do status do servico)
    contrato_aceito = aceitar_contrato(hubsoft_service, id_contrato, lead=lead)

    # 8. Atualizar campos de controle no lead
    if contrato_aceito and not lead.contrato_aceito:
        lead.contrato_aceito = True
        lead.data_aceite_contrato = timezone.now()
        lead.save(update_fields=["contrato_aceito", "data_aceite_contrato"])

    logger.info(
        "[RESUMO] Lead %s — %d arquivo(s) enviado(s) (%d erro(s) de download). Contrato %s aceito: %s.",
        lead.pk, len(arquivos), erros_download, id_contrato, contrato_aceito,
    )

    return True  # Sucesso parcial: anexos enviados; aceite depende do status do contrato no HubSoft
