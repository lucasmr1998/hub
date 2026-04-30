"""
Wrapper do SDK oficial Resend (https://github.com/resend/resend-python).

Configuracao via env:
    RESEND_API_KEY: chave master da Hubtrix
    RESEND_WEBHOOK_SECRET: secret pra validar assinatura dos webhooks
    RESEND_STUB_VERIFY=1: em modo stub, simula 'verified' (so pra dev sem chave)

Sem RESEND_API_KEY, opera em modo stub (gera DNS fake pra testar UI).
"""
import logging
import os
import uuid

import resend

logger = logging.getLogger(__name__)


def _api_key():
    return os.environ.get('RESEND_API_KEY', '')


def _is_stub():
    return not _api_key()


def _ensure_key():
    """Garante que o SDK tem a chave atual (env pode mudar entre requests em dev)."""
    resend.api_key = _api_key()


# ─── Domains ──────────────────────────────────────────────────────────────────

def create_domain(dominio: str, region: str = 'us-east-1') -> dict:
    """
    Cria dominio no Resend. Retorna dict com id, name, status, records.
    Records sao os DNS que o cliente precisa adicionar (SPF, DKIM, DMARC).
    """
    if _is_stub():
        return _stub_domain(dominio)

    _ensure_key()
    params: resend.Domains.CreateParams = {
        'name': dominio,
        'region': region,
    }
    return resend.Domains.create(params)


def get_domain(resend_domain_id: str) -> dict:
    """Busca status atual do dominio."""
    if _is_stub():
        if os.environ.get('RESEND_STUB_VERIFY') == '1':
            return {'id': resend_domain_id, 'status': 'verified', 'records': []}
        return {'id': resend_domain_id, 'status': 'pending', 'records': []}

    _ensure_key()
    return resend.Domains.get(domain_id=resend_domain_id)


def verify_domain(resend_domain_id: str) -> dict:
    """Dispara verificacao DNS no Resend."""
    if _is_stub():
        if os.environ.get('RESEND_STUB_VERIFY') == '1':
            return {'id': resend_domain_id, 'status': 'verified'}
        return {'id': resend_domain_id, 'status': 'pending'}

    _ensure_key()
    # SDK usa verify(domain_id=...) e retorna o dominio atualizado
    resend.Domains.verify(domain_id=resend_domain_id)
    return resend.Domains.get(domain_id=resend_domain_id)


def delete_domain(resend_domain_id: str) -> bool:
    """Apaga dominio no Resend."""
    if _is_stub():
        return True

    _ensure_key()
    try:
        resend.Domains.remove(domain_id=resend_domain_id)
        return True
    except Exception as e:
        logger.warning('Falha ao apagar dominio Resend: %s', e)
        return False


def list_domains() -> list:
    """Lista todos os dominios da conta master."""
    if _is_stub():
        return []
    _ensure_key()
    result = resend.Domains.list()
    if isinstance(result, dict):
        return result.get('data', [])
    return result or []


# ─── Send ────────────────────────────────────────────────────────────────────

def send_email(
    *,
    from_addr: str,
    from_name: str,
    to: str,
    subject: str,
    html: str,
    reply_to: str = '',
    headers: dict | None = None,
    tags: list | None = None,
) -> dict:
    """Envia email via SDK Resend. Retorna {'id': '<message_id>'}."""
    if _is_stub():
        msg_id = f'stub-{uuid.uuid4().hex[:16]}'
        logger.info(
            '[Resend STUB] enviaria de=%s to=%s subj=%s msg_id=%s',
            from_addr, to, subject[:50], msg_id,
        )
        return {'id': msg_id}

    _ensure_key()
    params: resend.Emails.SendParams = {
        'from': f'{from_name} <{from_addr}>' if from_name else from_addr,
        'to': [to] if isinstance(to, str) else to,
        'subject': subject,
        'html': html,
    }
    if reply_to:
        params['reply_to'] = reply_to
    if headers:
        params['headers'] = headers
    if tags:
        params['tags'] = tags

    return resend.Emails.send(params)


# ─── Orquestracao: cria EnvioEmail e dispara ─────────────────────────────────

def disparar_para_lead(*, template, lead, remetente=None, automacao=None, contexto_extra=None):
    """Renderiza template, cria EnvioEmail, dispara via Resend. Retorna EnvioEmail."""
    from apps.marketing.emails.models import EnvioEmail, RemetenteEmail

    if not template:
        raise ValueError('template obrigatorio')
    if not lead or not getattr(lead, 'email', None):
        raise ValueError('lead com email obrigatorio')

    if remetente is None:
        tenant_id = getattr(template, 'tenant_id', None)
        remetente = RemetenteEmail.all_tenants.filter(
            tenant_id=tenant_id, padrao=True, ativo=True,
        ).first()

    if not remetente:
        raise ValueError('Sem remetente padrao configurado pro tenant. Configure em /marketing/emails/dominios/.')

    if not remetente.dominio.esta_verificado:
        raise ValueError(f'Dominio {remetente.dominio.dominio} nao esta verificado.')

    contexto = {'lead': lead}
    if contexto_extra:
        contexto.update(contexto_extra)

    assunto = _render_simple(template.assunto or '', contexto)
    html = template.html_compilado or ''
    html = _render_simple(html, contexto)

    envio = EnvioEmail.objects.create(
        template=template,
        remetente=remetente,
        lead=lead,
        automacao=automacao,
        email_destino=lead.email,
        assunto_renderizado=assunto[:300],
        status='pendente',
    )

    try:
        result = send_email(
            from_addr=remetente.email_completo,
            from_name=remetente.nome_exibicao,
            to=lead.email,
            subject=assunto,
            html=html,
            reply_to=remetente.reply_to or '',
            tags=[
                {'name': 'tracking_id', 'value': str(envio.tracking_id)},
                {'name': 'tenant', 'value': str(envio.tenant_id)},
            ],
        )
        envio.resend_message_id = result.get('id', '')
        envio.status = 'enviado'
        envio.save(update_fields=['resend_message_id', 'status'])
    except Exception as e:
        envio.status = 'erro'
        envio.erro_detalhe = str(e)[:1000]
        envio.save(update_fields=['status', 'erro_detalhe'])
        logger.exception('Falha ao enviar email pelo Resend')
        raise

    return envio


def _render_simple(texto, contexto):
    """Render simples de {{lead.nome}}. Pra prod real, usar Django Template."""
    if not texto or '{{' not in texto:
        return texto
    import re
    def replace(m):
        path = m.group(1).strip()
        try:
            obj = contexto
            for k in path.split('.'):
                if isinstance(obj, dict):
                    obj = obj.get(k, '')
                else:
                    obj = getattr(obj, k, '')
            return str(obj)
        except Exception:
            return ''
    return re.sub(r'\{\{\s*([^}]+)\s*\}\}', replace, texto)


# ─── Webhook signature ───────────────────────────────────────────────────────

def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Valida HMAC da Svix (Resend usa Svix pra webhooks).
    Em prod, recomendado usar `pip install svix` e Webhook(secret).verify().
    Implementacao simplificada aqui pra evitar dependencia extra.
    """
    secret = os.environ.get('RESEND_WEBHOOK_SECRET', '')
    if not secret:
        # Sem secret configurado (dev): aceita
        return True
    if not signature_header:
        return False

    import base64
    import hashlib
    import hmac

    try:
        sigs = [s.strip() for s in signature_header.split(' ') if s.strip()]
        # Decodifica secret (whsec_xxx)
        if secret.startswith('whsec_'):
            key_bytes = base64.b64decode(secret[6:] + '=' * (-len(secret[6:]) % 4))
        else:
            key_bytes = secret.encode()
        for sig in sigs:
            if not sig.startswith('v1,'):
                continue
            received = sig[3:]
            mac = hmac.new(key_bytes, payload_bytes, hashlib.sha256).digest()
            expected = base64.b64encode(mac).decode()
            if hmac.compare_digest(received, expected):
                return True
        return False
    except Exception as e:
        logger.warning('verify_webhook_signature: %s', e)
        return False


# ─── Stub helper ─────────────────────────────────────────────────────────────

def _stub_domain(dominio: str) -> dict:
    """Resposta fake pra dev sem chave."""
    fake_id = f'stub-{uuid.uuid4().hex[:16]}'
    return {
        'id': fake_id,
        'name': dominio,
        'status': 'pending',
        'region': 'us-east-1',
        'records': [
            {'record': 'SPF', 'name': dominio, 'type': 'TXT', 'ttl': 'Auto', 'status': 'not_started', 'value': 'v=spf1 include:resend.com ~all'},
            {'record': 'DKIM', 'name': f'resend._domainkey.{dominio}', 'type': 'TXT', 'ttl': 'Auto', 'status': 'not_started', 'value': 'p=...stubkey...'},
            {'record': 'DMARC', 'name': f'_dmarc.{dominio}', 'type': 'TXT', 'ttl': 'Auto', 'status': 'not_started', 'value': 'v=DMARC1; p=none;'},
        ],
    }
