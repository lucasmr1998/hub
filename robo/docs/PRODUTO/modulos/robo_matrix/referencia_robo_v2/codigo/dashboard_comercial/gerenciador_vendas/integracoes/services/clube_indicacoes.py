"""Notifica o Clube de Benefícios quando um lead de indicação converte ou é habilitado."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def lead_e_indicacao_clube(lead):
    if not lead:
        return False
    if getattr(lead, 'canal_entrada', None) == 'indicacao':
        return True
    if getattr(lead, 'origem', None) == 'indicacao':
        return True
    if (getattr(lead, 'id_indicador', None) or '').strip():
        return True
    return False


def _clube_webhook_url(sufixo):
    """Monta URL do webhook no Clube a partir de CLUBE_WEBHOOK_URL (conversão)."""
    base = getattr(settings, 'CLUBE_WEBHOOK_URL', '').strip()
    if not base:
        return ''
    if sufixo == 'conversao':
        return base
    if '/conversao/' in base:
        return base.replace('/conversao/', f'/{sufixo}/')
    return f'{base.rstrip("/")}/{sufixo}/'


def _post_clube_webhook(url, payload, lead_id, evento):
    secret = getattr(settings, 'CLUBE_WEBHOOK_SECRET', '').strip()
    if not url or not secret:
        logger.debug('CLUBE_WEBHOOK_URL/CLUBE_WEBHOOK_SECRET não configurados — sync Clube ignorada.')
        return False

    payload = {**payload, 'secret_key': secret}
    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code >= 400:
            logger.warning(
                'Clube rejeitou %s do lead #%s: HTTP %s — %s',
                evento,
                lead_id,
                resp.status_code,
                resp.text[:300],
            )
            return False
        data = resp.json() if resp.content else {}
        if not data.get('ok'):
            logger.warning(
                'Clube não confirmou %s do lead #%s: %s',
                evento,
                lead_id,
                data.get('error') or data,
            )
            return False
        return data
    except Exception as e:
        logger.warning('Falha ao notificar Clube (%s) do lead #%s: %s', evento, lead_id, e)
        return False


def notificar_clube_conversao_indicacao(lead, valor_venda=None):
    """
    POST webhook no Clube para marcar indicação como convertida.
    Falha na rede não propaga — operação comercial já concluiu.
    """
    if not lead_e_indicacao_clube(lead):
        return False

    payload = {
        'lead_id': lead.id,
        'telefone': lead.telefone or '',
        'id_indicador': (getattr(lead, 'id_indicador', None) or '').strip(),
    }
    if valor_venda is not None and valor_venda != '':
        payload['valor_venda'] = str(valor_venda)
    elif getattr(lead, 'valor', None):
        payload['valor_venda'] = str(lead.valor)

    data = _post_clube_webhook(_clube_webhook_url('conversao'), payload, lead.id, 'conversão')
    if not data:
        return False
    logger.info(
        'Lead Comercial #%s → indicação Clube #%s convertida (reenvio=%s)',
        lead.id,
        data.get('indicacao_id'),
        data.get('ja_convertida', False),
    )
    return True


def notificar_clube_contrato_aceito_indicacao(lead, data_contrato_aceito=None):
    """
    POST webhook no Clube quando o contrato do lead de indicação é aceito.
    Falha na rede não propaga.
    """
    if not lead_e_indicacao_clube(lead):
        return False

    payload = {
        'lead_id': lead.id,
        'telefone': lead.telefone or '',
        'id_indicador': (getattr(lead, 'id_indicador', None) or '').strip(),
    }
    dt = data_contrato_aceito or getattr(lead, 'data_aceite_contrato', None)
    if dt:
        payload['data_contrato_aceito'] = dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)

    data = _post_clube_webhook(_clube_webhook_url('contrato'), payload, lead.id, 'contrato aceito')
    if not data:
        return False
    logger.info(
        'Lead Comercial #%s → indicação Clube #%s contrato aceito (reenvio=%s)',
        lead.id,
        data.get('indicacao_id'),
        data.get('ja_aceito', False),
    )
    return True


def notificar_clube_habilitacao_indicacao(lead, valor_venda=None):
    """
    POST webhook no Clube quando o serviço do lead fica habilitado no HubSoft.
    Atualiza comissão prevista do embaixador.
    """
    if not lead_e_indicacao_clube(lead):
        return False

    payload = {
        'lead_id': lead.id,
        'telefone': lead.telefone or '',
        'id_indicador': (getattr(lead, 'id_indicador', None) or '').strip(),
    }
    if valor_venda is not None and valor_venda != '':
        payload['valor_venda'] = str(valor_venda)

    data = _post_clube_webhook(_clube_webhook_url('habilitacao'), payload, lead.id, 'habilitação')
    if not data:
        return False
    logger.info(
        'Lead Comercial #%s → indicação Clube #%s comissão sincronizada (habilitado)',
        lead.id,
        data.get('indicacao_id'),
    )
    return True
