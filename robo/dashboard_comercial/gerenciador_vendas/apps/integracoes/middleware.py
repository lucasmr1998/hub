"""Middleware de observabilidade pra endpoints publicos do N8N.

Toda chamada pra /api/public/n8n/* eh registrada em LogWebhookN8N.
Status 5xx dispara notificacao pros admins do tenant Aurora-HQ
(rate-limit de 1 alerta por endpoint a cada 5min).
"""
import logging
import time
from django.utils import timezone

logger = logging.getLogger(__name__)

_ULTIMO_ALERTA = {}  # key=(endpoint) -> timestamp, anti-spam in-memory
_DEDUP_WINDOW_S = 300  # 5min


class WebhookN8NObservabilityMiddleware:
    PREFIX = '/api/public/n8n/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.PREFIX):
            return self.get_response(request)

        inicio = time.time()
        try:
            response = self.get_response(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            duracao_ms = int((time.time() - inicio) * 1000)
            try:
                self._registrar(request, status, duracao_ms)
                if status >= 500:
                    self._alertar(request, status)
            except Exception as exc:
                logger.exception('[WebhookN8NObservability] erro registrando log: %s', exc)
        return response

    def _registrar(self, request, status, duracao_ms):
        from .models_audit import LogWebhookN8N
        body_preview = ''
        try:
            body = getattr(request, '_body', None) or request.body
            if isinstance(body, bytes):
                body_preview = body[:2000].decode('utf-8', errors='replace')
            else:
                body_preview = str(body)[:2000]
        except Exception:
            body_preview = '(body unreadable)'
        LogWebhookN8N.objects.create(
            endpoint=request.path,
            metodo=request.method,
            status_code=status,
            duracao_ms=duracao_ms,
            ip_origem=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            body_preview=body_preview,
            criado_em=timezone.now(),
        )

    def _alertar(self, request, status):
        agora = time.time()
        key = (request.path, status)
        ultimo = _ULTIMO_ALERTA.get(key, 0)
        if agora - ultimo < _DEDUP_WINDOW_S:
            return
        _ULTIMO_ALERTA[key] = agora

        try:
            from apps.sistema.models import Tenant
            from apps.notificacoes.services.notificacao_service import criar_notificacao
            from django.contrib.auth.models import User

            aurora = Tenant.objects.filter(slug='aurora-hq', ativo=True).first()
            if not aurora:
                return
            admins = User.objects.filter(
                perfil__tenant=aurora, is_active=True,
            )
            destinatarios = [u for u in admins if u.is_superuser]
            for admin in destinatarios:
                criar_notificacao(
                    tenant=aurora,
                    codigo_tipo='inatividade_atendente',  # reaproveita tipo de alerta tecnico
                    titulo=f'[FALHA WEBHOOK N8N] HTTP {status} em {request.path}',
                    mensagem=f'Endpoint {request.path} retornou {status}. Verificar logs imediatamente.',
                    destinatario=admin,
                    url_acao='/aurora-admin/webhooks/',
                    prioridade='urgente',
                    dados_contexto={'endpoint': request.path, 'status': status},
                )
        except Exception as exc:
            logger.error('[WebhookN8NObservability] falha enviando alerta: %s', exc)
