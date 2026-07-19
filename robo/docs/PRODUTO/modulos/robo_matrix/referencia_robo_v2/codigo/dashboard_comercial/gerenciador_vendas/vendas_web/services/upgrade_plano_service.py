"""
Serviços de upgrade de plano.

Concentra a lógica de "transformar um AtendimentoFluxo do tipo upgrade
finalizado em uma row de `UpgradePlano` com `status='finalizado'`".

A row criada é capturada automaticamente pelo polling externo
`polling_upgrade_plano.py` (projeto `web_driver_conversao_lead`) e
executada via webdriver no HubSoft.

CONVENÇÃO DAS QUESTÕES DO FLUXO DE UPGRADE
──────────────────────────────────────────
Pra esse helper achar as respostas certas no `dados_respostas`, o seed do
fluxo grava cada questão com um marcador específico em
`variaveis_contexto` (campo JSONField já existente):

    Q? "Escolher serviço"        → variaveis_contexto = {'upgrade_role': 'servico'}
    Q? "Escolher plano novo"     → variaveis_contexto = {'upgrade_role': 'plano'}
    Q? "Confirmar"               → variaveis_contexto = {'upgrade_role': 'confirmacao'}

Assim, mesmo que o seed mude a ordem das questões no futuro, o helper
continua achando as respostas corretas.
"""

import logging
from typing import Optional

from django.db import transaction

logger = logging.getLogger(__name__)


def _extrair_resposta_por_role(atendimento, role: str) -> Optional[str]:
    """Procura uma questão do fluxo com `variaveis_contexto.upgrade_role == role`
    e devolve a resposta dada (string)."""
    fluxo = atendimento.fluxo
    for q in fluxo.questoes.all().order_by('indice'):
        vc = q.variaveis_contexto or {}
        if isinstance(vc, dict) and vc.get('upgrade_role') == role:
            dados = atendimento.dados_respostas.get(str(q.indice), {})
            resp = dados.get('resposta')
            if resp not in (None, ''):
                return str(resp)
    return None


def enriquecer_contexto_upgrade(atendimento, contexto=None) -> dict:
    """Para fluxos de upgrade, injeta no `contexto` tudo que as fontes
    dinâmicas e a validação precisam, derivando direto do atendimento —
    assim o canal (n8n/WhatsApp) só precisa mandar o `atendimento_id`,
    sem fazer plumbing manual de `lead_id`/`id_servico_hubsoft_atual`.

    Injeta (sem sobrescrever o que já veio no contexto):
      - lead_id                  → do atendimento
      - atendimento_id           → do atendimento
      - id_servico_hubsoft_atual → resolvido da resposta da questão
                                   com upgrade_role='servico'
                                   (id_cliente_servico → id_servico)

    Em fluxos que não são de upgrade, devolve o contexto intacto.
    """
    ctx = dict(contexto or {})
    try:
        if atendimento.fluxo.tipo_fluxo != 'upgrade':
            return ctx
    except Exception:
        return ctx

    if atendimento.lead_id and not ctx.get('lead_id'):
        ctx['lead_id'] = atendimento.lead_id
    if atendimento.pk and not ctx.get('atendimento_id'):
        ctx['atendimento_id'] = atendimento.pk

    if ctx.get('id_servico_hubsoft_atual') is None:
        id_cs = _extrair_resposta_por_role(atendimento, 'servico')
        if id_cs:
            try:
                from integracoes.models import ServicoClienteHubsoft
                scs = ServicoClienteHubsoft.objects.filter(
                    id_cliente_servico=id_cs).first()
                if scs and scs.id_servico:
                    ctx['id_servico_hubsoft_atual'] = scs.id_servico
            except Exception:
                logger.exception(
                    "enriquecer_contexto_upgrade: falha ao resolver "
                    "id_servico_hubsoft_atual (id_cs=%r)", id_cs,
                )
    return ctx


@transaction.atomic
def criar_upgrade_plano_do_atendimento(atendimento):
    """A partir de um `AtendimentoFluxo` finalizado de upgrade, monta e
    cria a row em `UpgradePlano`. Idempotente: se já foi criado um
    upgrade pra esse atendimento, retorna o existente.

    Devolve a row `UpgradePlano` ou `None` se faltou dado essencial.
    """
    # Import local pra evitar import circular com models.py
    from vendas_web.models import UpgradePlano

    # Idempotência: usamos atendimento.observacoes/notas pra marcar?
    # Simples: procuramos por upgrade já criado mencionando esse atendimento.
    marca = f"atendimento={atendimento.pk}"
    ja_criado = UpgradePlano.objects.filter(
        lead_id=atendimento.lead_id,
        observacoes__contains=marca,
    ).first()
    if ja_criado:
        logger.info(
            "criar_upgrade_plano_do_atendimento: upgrade %s já existe para atendimento %s",
            ja_criado.pk, atendimento.pk,
        )
        return ja_criado

    id_cs = _extrair_resposta_por_role(atendimento, 'servico')
    id_plano = _extrair_resposta_por_role(atendimento, 'plano')
    confirmou = (_extrair_resposta_por_role(atendimento, 'confirmacao') or '').lower()

    if not id_cs or not id_plano:
        logger.warning(
            "criar_upgrade_plano_do_atendimento: respostas insuficientes "
            "no atendimento %s (id_cs=%r, id_plano=%r)",
            atendimento.pk, id_cs, id_plano,
        )
        return None

    if confirmou and confirmou not in ('sim', 's', 'yes', 'y', '1', 'confirmo', 'true'):
        logger.info(
            "criar_upgrade_plano_do_atendimento: cliente NÃO confirmou no atendimento %s (resp=%r) — nada a criar",
            atendimento.pk, confirmou,
        )
        return None

    try:
        id_cs_int = int(id_cs)
        id_plano_int = int(id_plano)
    except (TypeError, ValueError):
        logger.error(
            "criar_upgrade_plano_do_atendimento: respostas não-numéricas no atendimento %s "
            "(id_cs=%r, id_plano=%r)", atendimento.pk, id_cs, id_plano,
        )
        return None

    upgrade = UpgradePlano.objects.create(
        lead_id=atendimento.lead_id,
        status='finalizado',  # polling pega imediatamente
        id_cliente_servico=id_cs_int,
        id_plano_novo=id_plano_int,
        observacoes=(
            f"Criado automaticamente a partir do fluxo de upgrade "
            f"[{marca}] em {atendimento.data_conclusao or '—'}."
        ),
    )
    logger.info(
        "criar_upgrade_plano_do_atendimento: upgrade %s criado (cs=%s, plano_novo=%s) "
        "a partir do atendimento %s",
        upgrade.pk, id_cs_int, id_plano_int, atendimento.pk,
    )
    return upgrade
