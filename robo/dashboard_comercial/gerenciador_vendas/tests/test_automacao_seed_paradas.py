"""Testes do seed do fluxo de follow-up de oportunidade parada (pedido da Gabi,
Nuvyon): `apps/automacao/management/commands/seed_fluxo_oportunidades_paradas.py`.

Cobre: idempotência (2 rodadas), validade estrutural do grafo, preservação de
`ativo` num re-run, tenant inexistente falha, e a config do gatilho (intervalo
curto pra granularidade fina do SLA + cooldown + teto por rodada).
"""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.automacao.management.commands.seed_fluxo_oportunidades_paradas import NOME_FLUXO
from apps.automacao.models import Fluxo
from apps.automacao.runtime import validar_fluxo
from tests.factories import TenantFactory


@pytest.mark.django_db
def test_seed_idempotente_duas_rodadas_contagem_estavel():
    tenant = TenantFactory()

    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)
    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)

    fluxos = list(Fluxo.all_tenants.filter(tenant=tenant))
    assert len(fluxos) == 1
    assert fluxos[0].nome == NOME_FLUXO


@pytest.mark.django_db
def test_fluxo_nasce_inativo():
    tenant = TenantFactory()

    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    assert fluxo.ativo is False


@pytest.mark.django_db
def test_grafo_e_estruturalmente_valido():
    tenant = TenantFactory()

    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    assert validar_fluxo(fluxo.grafo) == []


@pytest.mark.django_db
def test_rerun_nao_reativa_fluxo_desligado_nem_ativa_sozinho():
    tenant = TenantFactory()
    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    fluxo.ativo = True
    fluxo.save(update_fields=['ativo'])

    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)

    fluxo.refresh_from_db()
    assert fluxo.ativo is True  # preservado, o comando nunca liga/desliga num re-run


@pytest.mark.django_db
def test_tenant_inexistente_falha():
    with pytest.raises(CommandError):
        call_command('seed_fluxo_oportunidades_paradas', tenant='nao-existe-999')


@pytest.mark.django_db
def test_config_do_gatilho_agenda():
    tenant = TenantFactory()
    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    trigger = fluxo.grafo['nodes'][fluxo.grafo['inicio']]
    assert trigger['tipo'] == 'agenda'

    config = trigger['config']
    assert config['varredura'] == 'oportunidades_paradas'
    assert int(config['intervalo_minutos']) == 15
    assert int(config['cooldown_horas']) == 24
    assert int(config['max_por_rodada']) == 10
    assert int(config['max_por_lead']) == 1
    assert fluxo.agenda_intervalo_minutos == 15


@pytest.mark.django_db
def test_grafo_tem_tarefa_e_nota_sem_marcador_dados_custom():
    """Diferente do fluxo de recuperação de perdidas: aqui não há nó de marcador
    em dados_custom (o follow-up é recorrente, o freio é o cooldown do gatilho)."""
    tenant = TenantFactory()
    call_command('seed_fluxo_oportunidades_paradas', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    tipos = {n.get('tipo') for n in fluxo.grafo['nodes'].values()}
    assert tipos == {'agenda', 'criar_tarefa', 'criar_nota'}
    assert 'definir_propriedade_oportunidade' not in tipos
