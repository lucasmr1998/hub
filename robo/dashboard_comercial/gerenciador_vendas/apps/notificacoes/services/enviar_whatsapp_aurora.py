"""
Envia mensagem WhatsApp usando a integracao Uazapi da Aurora HQ (tenant sistema).

Uso:
    from apps.notificacoes.services.enviar_whatsapp_aurora import enviar_whatsapp_aurora
    resposta = enviar_whatsapp_aurora('5519994576319', 'Bom dia!')

Falha silenciosa: retorna dict com 'ok': False e nao levanta excecao. Assim
o command de resumo diario nao para porque 1 destinatario falhou.
"""
import logging

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.uazapi import UazapiService, UazapiServiceError
from apps.sistema.models import Tenant

logger = logging.getLogger(__name__)


def enviar_whatsapp_aurora(telefone, mensagem):
    """
    Envia texto via Uazapi da Aurora HQ.

    Args:
        telefone: string DDI+DDD+numero (ex: '5519994576319')
        mensagem: string texto (formato WhatsApp aceita *, _, ~, ```)

    Returns:
        dict {ok: bool, resposta: any, erro: str|None}
    """
    try:
        aurora = Tenant.objects.filter(slug='aurora-hq').first()
        if not aurora:
            return _fail('Tenant aurora-hq nao encontrado')

        integ = IntegracaoAPI.objects.filter(
            tenant=aurora, tipo='uazapi', ativa=True,
        ).first()
        if not integ:
            return _fail('IntegracaoAPI uazapi ativa nao encontrada na aurora-hq')

        svc = UazapiService(integracao=integ)
        resposta = svc.enviar_texto(telefone, mensagem)
        return {'ok': True, 'resposta': resposta, 'erro': None}
    except UazapiServiceError as e:
        logger.warning(f'[enviar_whatsapp_aurora] falha Uazapi: {e}')
        return _fail(str(e))
    except Exception as e:
        logger.exception('[enviar_whatsapp_aurora] erro inesperado')
        return _fail(str(e))


def _fail(erro):
    return {'ok': False, 'resposta': None, 'erro': erro}
