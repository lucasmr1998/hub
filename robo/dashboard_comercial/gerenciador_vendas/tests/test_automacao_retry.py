"""
Testes do retry transitório da engine de automação (hardening E4).

Um erro NÃO tratado (branch erro não conectada) num nó seguro reenfileira a
execução com backoff, retomando DO NÓ QUE FALHOU, até um teto (MAX_TENTATIVAS).
Se a branch erro está conectada, o fluxo trata o erro e completa (sem retry). Nó
marcado `retry_seguro=False` (envio real sem dedupe) vira erro final direto.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from django.utils import timezone

from apps.automacao.execucao import (
    RETRY_BACKOFF_SEGUNDOS, _no_seguro_pra_retry, executar_e_persistir, rodar_novos,
)
from apps.automacao.models import ExecucaoFluxo, Fluxo
from apps.automacao.nodes import Contexto
from tests.factories import TenantFactory


# Host que não resolve: o nó http_request falha (guard SSRF ou DNS), branch 'erro'.
_URL_INVALIDA = 'http://intencionalmente-invalido.exemplo-que-nao-resolve.local/'


def _simular_cron_vencido(ex):
    """Empurra `agendado_para` pro passado (como se o backoff já tivesse vencido)."""
    ExecucaoFluxo.all_tenants.filter(pk=ex.pk).update(
        agendado_para=timezone.now() - timedelta(seconds=1))


# ============================================================================
# Retry com DB (fluxo real que falha)
# ============================================================================

@pytest.mark.django_db
def test_erro_sem_branch_reenfileira_com_backoff():
    tenant = TenantFactory()
    fluxo = Fluxo.objects.create(
        tenant=tenant, nome='Retry E4', ativo=True,
        grafo={
            'inicio': 't',
            'nodes': {
                't': {'tipo': 'webhook', 'config': {}},
                'x': {'tipo': 'http_request', 'config': {'url': _URL_INVALIDA}},
            },
            'conexoes': [{'de': 't', 'para': 'x', 'saida': 'default'}],  # SEM branch erro
        },
    )

    # 1ª falha: reenfileira (pendente), tentativas=1, retoma do nó 'x', backoff ~300s.
    ex, res = executar_e_persistir(fluxo, Contexto(tenant=tenant))
    assert res.status == 'erro'
    assert ex.status == 'pendente'
    assert ex.tentativas == 1
    assert ex.no_pausado == 'x'
    assert ex.claimed_em is None
    delta1 = (ex.agendado_para - timezone.now()).total_seconds()
    assert 250 < delta1 < 350          # ~RETRY_BACKOFF_SEGUNDOS[0] (300)

    # 2ª rodada do cron: falha de novo => tentativas=2, backoff ~900s.
    _simular_cron_vencido(ex)
    rodar_novos()
    ex.refresh_from_db()
    assert ex.status == 'pendente'
    assert ex.tentativas == 2
    assert ex.no_pausado == 'x'
    delta2 = (ex.agendado_para - timezone.now()).total_seconds()
    assert 850 < delta2 < 950          # ~RETRY_BACKOFF_SEGUNDOS[1] (900)

    # 3ª rodada: teto atingido => erro final, sem reagendar.
    _simular_cron_vencido(ex)
    rodar_novos()
    ex.refresh_from_db()
    assert ex.status == 'erro'
    assert ex.no_pausado == ''
    assert ex.agendado_para is None
    assert ex.tentativas == len(RETRY_BACKOFF_SEGUNDOS)


@pytest.mark.django_db
def test_erro_com_branch_conectada_completa_sem_retry():
    tenant = TenantFactory()
    fluxo = Fluxo.objects.create(
        tenant=tenant, nome='Erro tratado E4', ativo=True,
        grafo={
            'inicio': 't',
            'nodes': {
                't': {'tipo': 'webhook', 'config': {}},
                'x': {'tipo': 'http_request', 'config': {'url': _URL_INVALIDA}},
                'e': {'tipo': 'set_fields', 'config': {'campos': [{'nome': 'tratado', 'valor': 'sim'}]}},
            },
            'conexoes': [
                {'de': 't', 'para': 'x', 'saida': 'default'},
                {'de': 'x', 'para': 'e', 'saida': 'erro'},   # branch erro tratada
            ],
        },
    )

    ex, res = executar_e_persistir(fluxo, Contexto(tenant=tenant))
    assert res.status == 'completado'
    assert ex.status == 'completado'
    assert ex.tentativas == 0
    assert ex.agendado_para is None


@pytest.mark.django_db
def test_no_inseguro_vira_erro_final_direto():
    """Nó `retry_seguro=False` (envio real) que falha: erro final, sem retry."""
    tenant = TenantFactory()
    fluxo = Fluxo.objects.create(
        tenant=tenant, nome='No inseguro E4', ativo=True,
        grafo={
            'inicio': 't',
            'nodes': {
                't': {'tipo': 'webhook', 'config': {}},
                # tenant sem integração Uazapi => o nó falha em execução (config válida).
                'w': {'tipo': 'whatsapp_texto',
                      'config': {'telefone': '5511999999999', 'mensagem': 'oi'}},
            },
            'conexoes': [{'de': 't', 'para': 'w', 'saida': 'default'}],
        },
    )

    ex, res = executar_e_persistir(fluxo, Contexto(tenant=tenant))
    assert res.status == 'erro'
    assert ex.status == 'erro'
    assert ex.tentativas == 0
    assert ex.no_pausado == ''
    assert ex.agendado_para is None


# ============================================================================
# _no_seguro_pra_retry (unitário, sem DB)
# ============================================================================

def _res(handle):
    return SimpleNamespace(passos=[SimpleNamespace(handle=handle)])


def test_no_seguro_falso_quando_no_marcado_inseguro():
    fluxo = SimpleNamespace(grafo={'nodes': {'x': {'tipo': 'no_inseguro'}}})
    with mock.patch('apps.automacao.execucao.tipo_por_slug',
                    return_value=SimpleNamespace(retry_seguro=False)):
        assert _no_seguro_pra_retry(fluxo, _res('x')) is False


def test_no_seguro_verdadeiro_por_default():
    fluxo = SimpleNamespace(grafo={'nodes': {'x': {'tipo': 'no_seguro'}}})
    with mock.patch('apps.automacao.execucao.tipo_por_slug',
                    return_value=SimpleNamespace(retry_seguro=True)):
        assert _no_seguro_pra_retry(fluxo, _res('x')) is True


def test_no_seguro_verdadeiro_sem_passos():
    fluxo = SimpleNamespace(grafo={'nodes': {}})
    assert _no_seguro_pra_retry(fluxo, SimpleNamespace(passos=[])) is True
