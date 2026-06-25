"""Testes do freio por lead no wiring (gatilhos._freio_bloqueia).

Sem DB: `ExecucaoFluxo` é mockado (cooldown via .exists(), max via .count()).
"""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.gatilhos import _freio_bloqueia

F = SimpleNamespace(tenant=SimpleNamespace(pk=1))
LEAD = SimpleNamespace(pk=9)


def _qs(exists=False, count=0):
    qs = mock.Mock()
    qs.filter.return_value.exists.return_value = exists
    qs.count.return_value = count
    return qs


def _patch(qs):
    p = mock.patch('apps.automacao.models.ExecucaoFluxo')
    p.start().all_tenants.filter.return_value = qs
    return p


def test_sem_lead_nao_barra():
    assert _freio_bloqueia(F, None, {'max_por_lead': 1}) is False


def test_sem_config_nao_barra():
    assert _freio_bloqueia(F, LEAD, {}) is False
    assert _freio_bloqueia(F, LEAD, {'max_por_lead': 0, 'cooldown_horas': 0}) is False


def test_cooldown_barra_se_recente():
    p = _patch(_qs(exists=True))
    try:
        assert _freio_bloqueia(F, LEAD, {'cooldown_horas': 24}) is True
    finally:
        p.stop()


def test_cooldown_nao_barra_se_antigo():
    p = _patch(_qs(exists=False))
    try:
        assert _freio_bloqueia(F, LEAD, {'cooldown_horas': 24}) is False
    finally:
        p.stop()


def test_max_barra_se_atingiu():
    p = _patch(_qs(count=3))
    try:
        assert _freio_bloqueia(F, LEAD, {'max_por_lead': 3}) is True
    finally:
        p.stop()


def test_max_nao_barra_abaixo():
    p = _patch(_qs(count=1))
    try:
        assert _freio_bloqueia(F, LEAD, {'max_por_lead': 3}) is False
    finally:
        p.stop()
