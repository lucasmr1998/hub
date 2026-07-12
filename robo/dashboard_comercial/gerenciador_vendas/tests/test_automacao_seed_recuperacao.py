"""Testes do seed dos fluxos das tarefas #180 (recuperacao de oportunidades
perdidas) e #181 (analise automatica de atendimentos Matrix).

Cobre: idempotencia (2 rodadas), validade estrutural dos 4 grafos, preservacao
de `ativo` num re-run, e o caminho ponta a ponta (via `executar_fluxo` direto,
sem passar pela fila deferida) do F1 (roteamento do `if` pelo bool `perdido`)
e do F4 (reabertura condicionada ao marcador `recuperacao_enviada`).
"""
from unittest import mock

import pytest
from django.core.management import call_command

from apps.automacao.management.commands.seed_fluxos_recuperacao_analise import (
    NOME_AGENTE, NOME_F1, NOME_F2, NOME_F3, NOME_F4,
)
from apps.automacao.models import Agente, Fluxo
from apps.automacao.nodes import Contexto
from apps.automacao.runtime import executar_fluxo, validar_fluxo
from apps.comercial.crm.models import MotivoPerda, NotaInterna
from tests.factories import (
    IntegracaoAPIFactory, LeadProspectoFactory, OportunidadeVendaFactory,
    PipelineEstagioFactory, TenantFactory, UserFactory,
)

TODOS_OS_NOMES = (NOME_F1, NOME_F2, NOME_F3, NOME_F4)


# ──────────────────────────────────────────────
# Idempotência + validade estrutural
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_seed_idempotente_duas_rodadas_contagens_estaveis():
    tenant = TenantFactory()

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)
    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)

    fluxos = list(Fluxo.all_tenants.filter(tenant=tenant))
    assert len(fluxos) == 4
    assert {f.nome for f in fluxos} == set(TODOS_OS_NOMES)
    assert all(f.ativo is False for f in fluxos)

    agentes = list(Agente.all_tenants.filter(tenant=tenant))
    assert len(agentes) == 1
    agente = agentes[0]
    assert agente.nome == NOME_AGENTE
    assert agente.ativo is False
    assert agente.tools == ['listar_motivos_perda']


@pytest.mark.django_db
def test_todos_os_grafos_sao_estruturalmente_validos():
    tenant = TenantFactory()
    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)

    for nome in TODOS_OS_NOMES:
        fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=nome)
        erros = validar_fluxo(fluxo.grafo)
        assert erros == [], f'{nome}: {erros}'


@pytest.mark.django_db
def test_rerun_nao_desativa_fluxo_ja_ativado():
    tenant = TenantFactory()
    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_F1)
    fluxo.ativo = True
    fluxo.save(update_fields=['ativo'])

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)

    fluxo.refresh_from_db()
    assert fluxo.ativo is True
    # os outros 3 continuam intocados (nasceram inativos e seguem assim)
    outros = Fluxo.all_tenants.filter(tenant=tenant).exclude(pk=fluxo.pk)
    assert all(f.ativo is False for f in outros)


@pytest.mark.django_db
def test_rerun_nao_reativa_agente_desligado_manualmente():
    tenant = TenantFactory()
    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)

    agente = Agente.all_tenants.get(tenant=tenant, nome=NOME_AGENTE)
    agente.ativo = True
    agente.save(update_fields=['ativo'])

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)

    agente.refresh_from_db()
    assert agente.ativo is True  # preservado, não voltou pra False


@pytest.mark.django_db
def test_tenant_inexistente_falha():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command('seed_fluxos_recuperacao_analise', tenant='nao-existe-999')


# ──────────────────────────────────────────────
# E2E F1: analise de atendimento Matrix, roteamento do `if` pelo bool `perdido`
# ──────────────────────────────────────────────

def _mensagens_matrix():
    return [
        {'boleano_entrante': '1', 'descricao_msg': 'Quero cancelar, nao vou fechar com voces',
         'data_msg': '2026-07-01 10:00:00', 'autor': ''},
        {'boleano_entrante': '0', 'descricao_msg': 'Entendi, vou registrar seu pedido',
         'data_msg': '2026-07-01 10:01:00', 'autor': 'Carla'},
    ]


def _setup_f1(tenant, *, perdida=False):
    """`perdida` controla o estágio da op: o handler `motivo_perda` só aplica o
    motivo sugerido pelo agente quando a op JÁ está em estágio `is_final_perdido`
    (rede de segurança do piloto fluxo 25, nunca poluir op aberta)."""
    IntegracaoAPIFactory(tenant=tenant, tipo='openai', ativa=True)
    user = UserFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    estagio = PipelineEstagioFactory(
        tenant=tenant, is_final_perdido=perdida, tipo='perdido' if perdida else 'novo')
    op = OportunidadeVendaFactory(tenant=tenant, lead=lead, estagio=estagio, responsavel=user)
    return lead, op


def _ativar_agente_e_fluxo(tenant, nome_fluxo):
    """O seed nasce tudo INATIVO (agente incluso). Pra exercitar o `ia_agente`
    (que só acha o Agente com `ativo=True`) num teste E2E, o teste liga
    explicitamente, simula alguém ativando o fluxo de verdade no editor."""
    agente = Agente.all_tenants.get(tenant=tenant, nome=NOME_AGENTE)
    agente.ativo = True
    agente.save(update_fields=['ativo'])
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=nome_fluxo)
    fluxo.ativo = True
    fluxo.save(update_fields=['ativo'])
    return fluxo


@pytest.mark.django_db
def test_e2e_f1_perdido_true_cria_nota_marca_e_define_motivo():
    tenant = TenantFactory()
    motivo = MotivoPerda.objects.create(tenant=tenant, nome='Sem retorno', ativo=True)
    lead, op = _setup_f1(tenant, perdida=True)

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)
    fluxo = _ativar_agente_e_fluxo(tenant, NOME_F1)

    resposta_llm = (
        '{"resumo": "Cliente desistiu e pediu para nao ser mais contatado.", '
        '"perdido": true, "motivo_nome": "Sem retorno", "confianca": "alta", '
        '"conclusao": "Perda sugerida: Sem retorno (confianca alta)"}'
    )
    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op,
                    variaveis={'id_atendimento_matrix': '999'})

    with mock.patch('apps.automacao.nodes.matrix_atendimento.consultar_atendimento') as m_consultar, \
         mock.patch('apps.automacao.services.ia.chamar_llm_com_tools', return_value=resposta_llm):
        m_consultar.return_value = {
            'status': 'finalizado', 'agente': 'Joana', 'mensagens': _mensagens_matrix(),
        }
        resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro

    op.refresh_from_db()
    assert 'analise_atendimento_matrix' in (op.dados_custom or {})
    assert op.motivo_perda_ref_id == motivo.pk

    nota = NotaInterna.objects.filter(oportunidade=op).first()
    assert nota is not None
    assert 'Cliente desistiu' in nota.conteudo
    assert 'Perda sugerida: Sem retorno (confianca alta)' in nota.conteudo

    passos = {p.handle: p for p in resultado.passos}
    assert passos['motivo'].branch == 'sucesso'
    assert ctx.nodes['motivo']['aplicado'] is True


@pytest.mark.django_db
def test_e2e_f1_perdido_false_nao_define_motivo():
    tenant = TenantFactory()
    MotivoPerda.objects.create(tenant=tenant, nome='Sem retorno', ativo=True)
    lead, op = _setup_f1(tenant)

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)
    fluxo = _ativar_agente_e_fluxo(tenant, NOME_F1)

    resposta_llm = (
        '{"resumo": "Cliente confirmou interesse e vai fechar na proxima semana.", '
        '"perdido": false, "motivo_nome": null, "confianca": "media", '
        '"conclusao": "Sem perda identificada no atendimento."}'
    )
    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op,
                    variaveis={'id_atendimento_matrix': '998'})

    with mock.patch('apps.automacao.nodes.matrix_atendimento.consultar_atendimento') as m_consultar, \
         mock.patch('apps.automacao.services.ia.chamar_llm_com_tools', return_value=resposta_llm):
        m_consultar.return_value = {
            'status': 'finalizado', 'agente': 'Joana', 'mensagens': _mensagens_matrix(),
        }
        resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro

    op.refresh_from_db()
    # a nota e o marcador rodam sempre; só o `definir_propriedade_oportunidade` (branch true do if) não roda
    assert 'analise_atendimento_matrix' in (op.dados_custom or {})
    assert op.motivo_perda_ref_id is None

    nota = NotaInterna.objects.filter(oportunidade=op).first()
    assert nota is not None
    assert 'Sem perda identificada no atendimento.' in nota.conteudo

    passos = {p.handle: p for p in resultado.passos}
    assert passos['se_perdido'].branch == 'false'
    assert 'motivo' not in passos  # nó downstream do branch true nunca rodou


@pytest.mark.django_db
def test_e2e_f1_perdido_true_mas_op_nao_esta_perdida_nao_ganha_motivo():
    """Rede de segurança do piloto fluxo 25: mesmo se o LLM classifica a
    conversa como perdida (com um motivo válido do catálogo), o handler
    `motivo_perda` só escreve `motivo_perda_ref` quando a oportunidade JÁ está
    em estágio `is_final_perdido`, evita poluir dado de uma op ainda aberta.
    O nó não vira erro (skip é branch de sucesso; nota e marcador seguem
    normalmente)."""
    tenant = TenantFactory()
    MotivoPerda.objects.create(tenant=tenant, nome='Sem retorno', ativo=True)
    lead, op = _setup_f1(tenant, perdida=False)

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)
    fluxo = _ativar_agente_e_fluxo(tenant, NOME_F1)

    resposta_llm = (
        '{"resumo": "Cliente desistiu e pediu para nao ser mais contatado.", '
        '"perdido": true, "motivo_nome": "Sem retorno", "confianca": "alta", '
        '"conclusao": "Perda sugerida: Sem retorno (confianca alta)"}'
    )
    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op,
                    variaveis={'id_atendimento_matrix': '997'})

    with mock.patch('apps.automacao.nodes.matrix_atendimento.consultar_atendimento') as m_consultar, \
         mock.patch('apps.automacao.services.ia.chamar_llm_com_tools', return_value=resposta_llm):
        m_consultar.return_value = {
            'status': 'finalizado', 'agente': 'Joana', 'mensagens': _mensagens_matrix(),
        }
        resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro

    op.refresh_from_db()
    assert 'analise_atendimento_matrix' in (op.dados_custom or {})  # marcador roda sempre
    assert op.motivo_perda_ref_id is None  # skip: op não perdida
    assert NotaInterna.objects.filter(oportunidade=op).exists()  # nota roda sempre

    passos = {p.handle: p for p in resultado.passos}
    assert passos['se_perdido'].branch == 'true'  # LLM disse perdido=true
    assert passos['motivo'].status == 'ok'
    assert passos['motivo'].branch == 'sucesso'  # skip é sucesso, não erro/retry
    assert ctx.nodes['motivo']['aplicado'] is False
    assert ctx.nodes['motivo']['motivo_skip'] == 'op_nao_perdida'


# ──────────────────────────────────────────────
# E2E F4: lead respondeu → reabre (condicionado ao marcador recuperacao_enviada)
# ──────────────────────────────────────────────

def _setup_f4(tenant, *, com_marcador):
    user = UserFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido')
    dados_custom = {'recuperacao_enviada': '2026-06-01T10:00:00'} if com_marcador else {}
    op = OportunidadeVendaFactory(
        tenant=tenant, lead=lead, estagio=estagio_perdido, responsavel=user,
        dados_custom=dados_custom,
    )
    return lead, op


@pytest.mark.django_db
def test_e2e_f4_com_marcador_reabre_e_cria_nota():
    tenant = TenantFactory()
    PipelineEstagioFactory(tenant=tenant, slug='em-atendimento', is_final_perdido=False)
    lead, op = _setup_f4(tenant, com_marcador=True)

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_F4)

    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op, variaveis={'status': 'resposta'})
    resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro

    op.refresh_from_db()
    assert op.estagio.slug == 'em-atendimento'
    nota = NotaInterna.objects.filter(oportunidade=op).first()
    assert nota is not None
    assert 'reaberta' in nota.conteudo.lower()


@pytest.mark.django_db
def test_e2e_f4_sem_marcador_nao_reabre():
    tenant = TenantFactory()
    PipelineEstagioFactory(tenant=tenant, slug='em-atendimento', is_final_perdido=False)
    lead, op = _setup_f4(tenant, com_marcador=False)
    estagio_original_id = op.estagio_id

    call_command('seed_fluxos_recuperacao_analise', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_F4)

    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op, variaveis={'status': 'resposta'})
    resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro

    op.refresh_from_db()
    assert op.estagio_id == estagio_original_id  # não reabriu
    assert not NotaInterna.objects.filter(oportunidade=op).exists()
