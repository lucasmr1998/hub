"""
Testes do claim atômico + watchdog do cron da engine de automação (hardening E3).

Cobre:
- `_claim`: CAS de uma linha — só o worker que vence a corrida recebe True.
- `rodar_novos`: rodadas concorrentes do cron não processam a mesma execução
  (o claim previne dupla execução, não só duplo-dispatch no mesmo minuto).
- `destravar_execucoes_presas`: watchdog devolve pra fila o que ficou preso em
  'rodando' além do limite, respeitando o status de origem (`modo_espera`).
"""
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from apps.automacao.execucao import _claim, destravar_execucoes_presas, rodar_novos
from apps.automacao.models import ExecucaoFluxo, Fluxo
from tests.factories import TenantFactory


def _fluxo(tenant):
    """Fluxo mínimo (só o gatilho webhook) — o grafo não importa pra claim/watchdog."""
    return Fluxo.objects.create(
        tenant=tenant, nome='Fluxo E3', ativo=True,
        grafo={'inicio': 't', 'nodes': {'t': {'tipo': 'webhook', 'config': {}}}, 'conexoes': []},
    )


@pytest.mark.django_db
def test_claim_vence_uma_vez():
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)
    ex = ExecucaoFluxo.all_tenants.create(
        tenant=tenant, fluxo=fluxo, status='pendente', agendado_para=timezone.now())

    assert _claim(ex.pk, 'pendente') is True    # ganha a corrida
    assert _claim(ex.pk, 'pendente') is False   # já não está mais 'pendente'

    ex.refresh_from_db()
    assert ex.status == 'rodando'
    assert ex.claimed_em is not None


@pytest.mark.django_db
def test_rodar_novos_nao_duplica():
    """Duas rodadas do cron sobre a mesma pendente => 1 única execução."""
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)
    ExecucaoFluxo.all_tenants.create(
        tenant=tenant, fluxo=fluxo, status='pendente',
        estado={'variaveis': {}, 'nodes': {}, 'inicio': 't'},
        agendado_para=timezone.now() - timedelta(minutes=1),
    )

    chamadas = []

    def fake_exec(fluxo_arg, contexto, *, inicio=None, execucao=None):
        chamadas.append(execucao.pk)
        execucao.status = 'completado'
        execucao.save(update_fields=['status', 'atualizado_em'])
        return execucao, None

    with mock.patch('apps.automacao.execucao.executar_e_persistir', side_effect=fake_exec):
        rodar_novos()
        rodar_novos()

    assert len(chamadas) == 1


@pytest.mark.django_db
def test_watchdog_destrava_presos():
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)
    antigo = timezone.now() - timedelta(minutes=30)   # além do limite (default 10min)
    recente = timezone.now() - timedelta(minutes=1)    # dentro do limite

    preso_pendente = ExecucaoFluxo.all_tenants.create(
        tenant=tenant, fluxo=fluxo, status='rodando', modo_espera='', claimed_em=antigo)
    preso_aguardando = ExecucaoFluxo.all_tenants.create(
        tenant=tenant, fluxo=fluxo, status='rodando', modo_espera='resposta', claimed_em=antigo)
    recente_rodando = ExecucaoFluxo.all_tenants.create(
        tenant=tenant, fluxo=fluxo, status='rodando', modo_espera='', claimed_em=recente)

    total = destravar_execucoes_presas()

    assert total == 2
    preso_pendente.refresh_from_db()
    preso_aguardando.refresh_from_db()
    recente_rodando.refresh_from_db()

    # modo_espera vazio => volta pra 'pendente'; preenchido => volta pra 'aguardando'.
    assert preso_pendente.status == 'pendente'
    assert preso_pendente.claimed_em is None
    assert preso_aguardando.status == 'aguardando'
    assert preso_aguardando.claimed_em is None
    assert recente_rodando.status == 'rodando'   # dentro do limite: intocado
