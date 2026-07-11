"""Nó `agenda` (gatilho de varredura) — unit (sem DB, sem rede)."""
from unittest import mock

from apps.automacao.nodes import tipo_por_slug


def test_registrado():
    assert tipo_por_slug('agenda') is not None


def test_validar_config_varredura_inexistente():
    no = tipo_por_slug('agenda')
    erros = no.validar_config({'varredura': 'nao_existe', 'intervalo_minutos': 30})
    assert any('varredura' in e for e in erros)


def test_validar_config_intervalo_invalido():
    no = tipo_por_slug('agenda')
    with mock.patch.dict('apps.automacao.varreduras.VARREDURAS', {'fake': lambda t, c: []}):
        erros_zero = no.validar_config({'varredura': 'fake', 'intervalo_minutos': 0})
        erros_negativo = no.validar_config({'varredura': 'fake', 'intervalo_minutos': -5})
        erros_texto = no.validar_config({'varredura': 'fake', 'intervalo_minutos': 'abc'})
    assert any('intervalo_minutos' in e for e in erros_zero)
    assert any('intervalo_minutos' in e for e in erros_negativo)
    assert any('intervalo_minutos' in e for e in erros_texto)


def test_validar_config_ok_com_varredura_mockada():
    no = tipo_por_slug('agenda')
    with mock.patch.dict('apps.automacao.varreduras.VARREDURAS', {'fake': lambda t, c: []}):
        erros = no.validar_config({'varredura': 'fake', 'intervalo_minutos': 15})
    assert erros == []


def test_executar_passa_adiante():
    no = tipo_por_slug('agenda')
    res = no.executar({'varredura': 'oportunidades_perdidas'}, {}, contexto=None)
    assert res.branch == 'default'
    assert res.output == {'varredura': 'oportunidades_perdidas'}
