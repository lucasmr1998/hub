"""Service de disparo de alertas do sistema.

Tarefa Workspace #152.

Uso:
    from apps.sistema.services_alertas import disparar_alerta

    disparar_alerta(
        tipo='cron_falhou',
        titulo='CronJob processar_pendentes_hubsoft falhou',
        mensagem='Return code 1\\nLast stderr: ...',
        dedup_key='cron_falhou:processar_pendentes_hubsoft',
        tenant=lead.tenant,  # opcional
    )

Logica:
- Cria sempre o registro em DB (historia completa)
- Verifica dedup window — se chave existente nas ultimas N minutos, marca
  suprimido=True e NAO envia WhatsApp
- Senao, envia via uazapi (instancia primaria — aurora-hq por default)
- Marca enviado_em ou erro_envio
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_uazapi_aurora():
    """Pega IntegracaoAPI uazapi do tenant aurora-hq (instancia que enviara
    alertas globais do sistema). Retorna None se nao houver."""
    from apps.integracoes.models import IntegracaoAPI
    from apps.sistema.models import Tenant
    try:
        t = Tenant.objects.get(slug='aurora-hq')
    except Tenant.DoesNotExist:
        return None
    return IntegracaoAPI.all_tenants.filter(
        tenant=t, tipo='uazapi', ativa=True,
    ).first()


def _formatar_mensagem_whatsapp(alerta) -> str:
    """Mensagem que sai pelo WhatsApp."""
    tenant_part = f' ({alerta.tenant.slug})' if alerta.tenant else ''
    linhas = [
        f'🚨 *{alerta.get_tipo_display()}*{tenant_part}',
        '',
        f'*{alerta.titulo}*',
        '',
        alerta.mensagem[:1500],  # cap pra nao explodir
    ]
    if alerta.dados_extras:
        import json
        extras_str = json.dumps(alerta.dados_extras, ensure_ascii=False, indent=2)[:600]
        linhas.append('')
        linhas.append(f'```\n{extras_str}\n```')
    linhas.append('')
    linhas.append(f'_Hubtrix • Alerta #{alerta.id} • {timezone.localtime(alerta.criado_em).strftime("%d/%m/%Y %H:%M")}_')
    return '\n'.join(linhas)


def disparar_alerta(tipo: str, titulo: str, mensagem: str,
                    dedup_key: str | None = None,
                    dados_extras: dict | None = None,
                    tenant=None) -> 'AlertaSistema':
    """Cria registro + tenta enviar WhatsApp respeitando dedup.

    Args:
        tipo: chave do choices em AlertaSistema.TIPO_CHOICES
        titulo: 1 linha (vai no header do WhatsApp)
        mensagem: texto multilinha com detalhe
        dedup_key: identificador (ex: 'cron_falhou:job_X'); se vazio,
                  usa f'{tipo}:{titulo[:100]}'
        dados_extras: dict serializavel pra contexto estruturado
        tenant: Tenant opcional pra contextualizar o cliente que disparou

    Returns:
        Instancia AlertaSistema criada (com enviado_em ou erro_envio populado)
    """
    from apps.sistema.models_alertas import AlertaSistema, AlertaConfig

    config = AlertaConfig.get_solo()
    dedup_key = dedup_key or f'{tipo}:{titulo[:100]}'

    alerta = AlertaSistema.objects.create(
        tipo=tipo,
        titulo=titulo[:200],
        mensagem=mensagem,
        dados_extras=dados_extras or {},
        dedup_key=dedup_key,
        tenant=tenant,
    )

    # Dedup: tem alerta na mesma chave nos ultimos N minutos? (excluindo eu)
    janela_inicio = timezone.now() - timezone.timedelta(minutes=config.janela_dedup_minutos)
    if AlertaSistema.objects.filter(
        dedup_key=dedup_key,
        criado_em__gte=janela_inicio,
        enviado_em__isnull=False,
    ).exclude(pk=alerta.pk).exists():
        alerta.suprimido = True
        alerta.save(update_fields=['suprimido'])
        logger.info('[alertas] dedup: %s suprimido (janela %smin)', dedup_key, config.janela_dedup_minutos)
        return alerta

    # Tipos ativos: se lista vazia, todos ativos. Senao filtra.
    if config.tipos_ativos and tipo not in config.tipos_ativos:
        logger.debug('[alertas] tipo %s nao esta em tipos_ativos', tipo)
        return alerta

    if not config.enviar_whatsapp:
        return alerta

    # Envia via uazapi aurora-hq
    integ = _get_uazapi_aurora()
    if not integ:
        alerta.erro_envio = 'IntegracaoAPI uazapi de aurora-hq nao configurada'
        alerta.save(update_fields=['erro_envio'])
        logger.warning('[alertas] %s', alerta.erro_envio)
        return alerta

    try:
        from apps.integracoes.services.uazapi import UazapiService
        uaz = UazapiService(integracao=integ)
        uaz.enviar_texto(config.telefone_destino, _formatar_mensagem_whatsapp(alerta))
        alerta.enviado_em = timezone.now()
        alerta.save(update_fields=['enviado_em'])
        logger.info('[alertas] enviado: %s -> %s', alerta.id, config.telefone_destino)
    except Exception as exc:
        alerta.erro_envio = f'{type(exc).__name__}: {str(exc)[:400]}'
        alerta.save(update_fields=['erro_envio'])
        logger.error('[alertas] falha envio: %s', exc)

    return alerta
