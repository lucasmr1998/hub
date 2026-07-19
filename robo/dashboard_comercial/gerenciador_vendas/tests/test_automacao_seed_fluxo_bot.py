"""Testes do seed do bot de vendas (Agente "Validador de respostas" + fluxos
"[Bot] Venda de internet: próximo passo" / "validar resposta") na engine de
automação nova.

Cobre: exigência do checklist prévio, idempotência (2 rodadas), validade
estrutural dos 2 grafos, preservação de `ativo` num re-run, as conexões dos
branches do fluxo de validação, e o caminho ponta a ponta (via `executar_fluxo`
direto, sem passar pela view HTTP) dos 2 fluxos — inclusive o roteamento pela
INTENÇÃO detectada pela IA (desistir → transbordo), que é a essência da
decisão de arquitetura: determinístico tenta primeiro, IA é segunda opinião
DENTRO do grafo, o grafo decide o que fazer com a intenção.
"""
import json
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.automacao.management.commands.seed_checklist_venda import SLUG_CHECKLIST
from apps.automacao.management.commands.seed_fluxo_bot_venda import (
    NOME_AGENTE_VALIDADOR, NOME_FLUXO_PROXIMO, NOME_FLUXO_VALIDAR,
)
from apps.automacao.models import Agente, Checklist, Fluxo, ItemChecklist
from apps.automacao.nodes import Contexto
from apps.automacao.runtime import executar_fluxo, validar_fluxo
from apps.automacao.services.checklist import registrar_resposta
from tests.factories import IntegracaoAPIFactory, LeadProspectoFactory, TenantFactory

TODOS_OS_NOMES = (NOME_FLUXO_PROXIMO, NOME_FLUXO_VALIDAR)


def _checklist_minimo(tenant):
    """Checklist mínimo (2 itens) com o mesmo slug que `seed_checklist_venda`
    usa em produção. O item 1 tem quebra de linha na pergunta de propósito:
    exercita o escape de JSON do `responder_webhook` (achado real construindo
    este fluxo com a pergunta de verdade do checklist de venda)."""
    checklist = Checklist.all_tenants.create(
        tenant=tenant, slug=SLUG_CHECKLIST, nome='Venda de internet (bot WhatsApp)',
        contexto='bot_vendas', modo_preenchimento='ia', entidade_alvo='lead', ativo=False,
    )
    item1 = ItemChecklist.all_tenants.create(
        tenant=tenant, checklist=checklist, chave='cpf_cnpj', ordem=1,
        pergunta='Oi! Pode me informar seu *CPF*?\n\n_Exemplo: 999.999.999-99_',
        tipo_resposta='texto_livre', tipo_validacao='nenhuma', obrigatorio=True,
    )
    item2 = ItemChecklist.all_tenants.create(
        tenant=tenant, checklist=checklist, chave='tipo_imovel', ordem=2,
        pergunta='Qual o tipo de imóvel?',
        tipo_resposta='opcoes',
        opcoes=[{'texto': 'Casa', 'valor': 'casa'}, {'texto': 'Empresa', 'valor': 'empresa'}],
        tipo_validacao='nenhuma', obrigatorio=True,
    )
    return checklist, item1, item2


def _ativar_agente(tenant):
    agente = Agente.all_tenants.get(tenant=tenant, nome=NOME_AGENTE_VALIDADOR)
    agente.ativo = True
    agente.save(update_fields=['ativo'])
    return agente


# ──────────────────────────────────────────────
# Pré-requisito: checklist
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_falha_sem_checklist_com_mensagem_clara():
    tenant = TenantFactory()
    with pytest.raises(CommandError, match='seed_checklist_venda'):
        call_command('seed_fluxo_bot_venda', tenant=tenant.slug)


# ──────────────────────────────────────────────
# Idempotência + validade estrutural
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_seed_idempotente_duas_rodadas_contagens_estaveis():
    tenant = TenantFactory()
    _checklist_minimo(tenant)

    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxos = list(Fluxo.all_tenants.filter(tenant=tenant))
    assert len(fluxos) == 2
    assert {f.nome for f in fluxos} == set(TODOS_OS_NOMES)
    assert all(f.ativo is False for f in fluxos)

    agentes = list(Agente.all_tenants.filter(tenant=tenant))
    assert len(agentes) == 1
    agente = agentes[0]
    assert agente.nome == NOME_AGENTE_VALIDADOR
    assert agente.ativo is False
    assert agente.equipe == 'fluxo'
    assert agente.integracao_ia is None
    assert 'PLACEHOLDER' not in agente.system_prompt
    assert '{{empresa}}' not in agente.system_prompt
    assert tenant.nome in agente.system_prompt


@pytest.mark.django_db
def test_todos_os_grafos_sao_estruturalmente_validos():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    for nome in TODOS_OS_NOMES:
        fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=nome)
        erros = validar_fluxo(fluxo.grafo)
        assert erros == [], f'{nome}: {erros}'


@pytest.mark.django_db
def test_rerun_nao_desativa_fluxo_ja_ativado():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_PROXIMO)
    fluxo.ativo = True
    fluxo.save(update_fields=['ativo'])

    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxo.refresh_from_db()
    assert fluxo.ativo is True
    outro = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_VALIDAR)
    assert outro.ativo is False


@pytest.mark.django_db
def test_rerun_nao_reativa_agente_desligado_manualmente():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    agente = _ativar_agente(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    agente.refresh_from_db()
    assert agente.ativo is True  # preservado, não voltou pra False


@pytest.mark.django_db
def test_tenant_inexistente_falha():
    with pytest.raises(CommandError, match='não encontrado'):
        call_command('seed_fluxo_bot_venda', tenant='tenant-que-nao-existe')


# ──────────────────────────────────────────────
# Grafo do fluxo "validar resposta": nós e conexões dos 3 branches
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_grafo_validar_tem_nos_e_branches_esperados():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_VALIDAR)
    grafo = fluxo.grafo
    nodes = grafo['nodes']

    assert nodes['validar']['tipo'] == 'checklist_validar'
    assert nodes['agente']['tipo'] == 'ia_agente'
    assert nodes['json']['tipo'] == 'extrair_json'
    assert nodes['se_valido']['tipo'] == 'if'
    assert nodes['se_desistiu']['tipo'] == 'if'

    por_saida = {(c['de'], c['saida']): c['para'] for c in grafo['conexoes']}
    assert por_saida[('validar', 'valida')] == 'resp_ok'
    assert por_saida[('validar', 'erro')] == 'resp_erro'
    assert por_saida[('validar', 'invalida')] == 'agente'
    assert por_saida[('agente', 'sucesso')] == 'json'
    assert por_saida[('json', 'sucesso')] == 'se_valido'
    assert por_saida[('se_valido', 'true')] == 'resp_ok_ia'
    assert por_saida[('se_valido', 'false')] == 'se_desistiu'
    assert por_saida[('se_desistiu', 'true')] == 'resp_transbordo'
    assert por_saida[('se_desistiu', 'false')] == 'resp_repergunta'


# ──────────────────────────────────────────────
# E2E: fluxo "próximo passo"
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_e2e_proximo_passo_lead_sem_respostas_devolve_primeira_pergunta():
    tenant = TenantFactory()
    _checklist, item1, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_PROXIMO)
    lead = LeadProspectoFactory(tenant=tenant)

    ctx = Contexto(tenant=tenant, lead=lead, variaveis={'payload': {'lead_id': lead.id}})
    resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro
    resp = ctx.variaveis['_resposta_webhook']
    assert resp['status'] == 200
    corpo = json.loads(resp['corpo'])  # prova que o corpo é JSON válido de verdade
    assert corpo['proximo_passo'] == 'seguir_pergunta'
    assert corpo['deve_perguntar'] is True
    assert corpo['proxima_pergunta_id'] == item1.pk
    assert corpo['mensagem_inicial'] == item1.pergunta  # inclui a quebra de linha real
    assert corpo['lead_id'] == lead.id


@pytest.mark.django_db
def test_e2e_proximo_passo_tudo_respondido_devolve_encerrar():
    tenant = TenantFactory()
    checklist, item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_PROXIMO)
    lead = LeadProspectoFactory(tenant=tenant)
    registrar_resposta(checklist, item1, 'lead', lead.pk, '11144477735', valor_processado='11144477735')
    registrar_resposta(checklist, item2, 'lead', lead.pk, '1', valor_processado='casa')

    ctx = Contexto(tenant=tenant, lead=lead, variaveis={'payload': {'lead_id': lead.id}})
    resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro
    corpo = json.loads(ctx.variaveis['_resposta_webhook']['corpo'])
    assert corpo['proximo_passo'] == 'red_encerrar'
    assert corpo['deve_perguntar'] is False


# ──────────────────────────────────────────────
# E2E: fluxo "validar resposta"
# ──────────────────────────────────────────────

@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm')
def test_e2e_validar_resposta_valida_por_opcao_nao_chama_ia(mock_llm):
    tenant = TenantFactory()
    _checklist, _item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_VALIDAR)
    lead = LeadProspectoFactory(tenant=tenant)

    ctx = Contexto(tenant=tenant, lead=lead, variaveis={
        'payload': {'lead_id': lead.id, 'question_id': item2.pk, 'answer': '1'},
    })
    resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro
    mock_llm.assert_not_called()
    corpo = json.loads(ctx.variaveis['_resposta_webhook']['corpo'])
    assert corpo['resposta_correta'] is True
    assert corpo['needsReception'] == 'false'
    passos = {p.handle: p for p in resultado.passos}
    assert passos['validar'].branch == 'valida'
    assert 'agente' not in passos


@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm')
def test_e2e_validar_ia_aceita_resposta_ambigua(mock_llm):
    tenant = TenantFactory()
    IntegracaoAPIFactory(tenant=tenant, tipo='openai', ativa=True)
    _checklist, _item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    _ativar_agente(tenant)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_VALIDAR)
    lead = LeadProspectoFactory(tenant=tenant)

    mock_llm.return_value = json.dumps({
        'valido': True, 'dados_extraidos': {'tipo_imovel': 'casa'},
        'mensagem_bot': '', 'motivo_invalido': '', 'confianca': 0.9,
        'intencao_detectada': 'ok',
    })

    ctx = Contexto(tenant=tenant, lead=lead, variaveis={
        'payload': {'lead_id': lead.id, 'question_id': item2.pk, 'answer': 'minha casa mesmo'},
    })
    resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro
    mock_llm.assert_called_once()
    passos = {p.handle: p for p in resultado.passos}
    assert passos['validar'].branch == 'invalida'
    assert passos['se_valido'].branch == 'true'
    corpo = json.loads(ctx.variaveis['_resposta_webhook']['corpo'])
    assert corpo['resposta_correta'] is True
    assert corpo['needsReception'] == 'false'

    # a mensagem que foi pro LLM carrega a pergunta original + a resposta do cliente
    mensagens = mock_llm.call_args[0][1]
    conteudo_user = mensagens[-1]['content']
    assert item2.pergunta in conteudo_user
    assert 'minha casa mesmo' in conteudo_user


@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm')
def test_e2e_validar_ia_detecta_desistencia_cai_no_transbordo(mock_llm):
    tenant = TenantFactory()
    IntegracaoAPIFactory(tenant=tenant, tipo='openai', ativa=True)
    _checklist, _item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    _ativar_agente(tenant)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO_VALIDAR)
    lead = LeadProspectoFactory(tenant=tenant)

    mock_llm.return_value = json.dumps({
        'valido': False, 'dados_extraidos': {}, 'mensagem_bot': 'Tudo bem, vou te transferir.',
        'motivo_invalido': 'cliente desistiu', 'confianca': 0.95,
        'intencao_detectada': 'desistir',
    })

    ctx = Contexto(tenant=tenant, lead=lead, variaveis={
        'payload': {'lead_id': lead.id, 'question_id': item2.pk, 'answer': 'na verdade desisto, obrigado'},
    })
    resultado = executar_fluxo(fluxo.grafo, ctx)

    assert resultado.status == 'completado', resultado.erro
    passos = {p.handle: p for p in resultado.passos}
    assert passos['se_valido'].branch == 'false'
    assert passos['se_desistiu'].branch == 'true'
    corpo = json.loads(ctx.variaveis['_resposta_webhook']['corpo'])
    assert corpo['needsReception'] == 'true'
    assert corpo['resposta_correta'] is False
    assert 'transferir' in corpo['retorno_erro_api'].lower()
