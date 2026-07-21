"""Testes do seed do bot de vendas: fluxo ÚNICO "[Bot] Venda de internet"
(Agente "Validador de respostas" + um switch de entrada roteando
proximo_passo/validar/recontato) na engine de automação nova.

Cobre: exigência do checklist prévio, idempotência (2 rodadas), validade
estrutural do grafo, preservação de `ativo` num re-run, remoção guardada dos
2 fluxos separados da versão anterior, e o caminho ponta a ponta (via
`executar_fluxo` direto a partir do `webhook`, SEM lead pré-injetado no
`Contexto` — prova que o gap do lead fechou) dos 3 ramos — incluindo as 3
correções: `ura.total_opcoes` sai como INT de verdade no JSON, `status_lead`
é decisão do grafo (0 int vs "em_andamento" string), e o ramo "recontato"
(3º endpoint do contrato, nunca tinha sido construído) existe e funciona.
"""
import json
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.automacao.management.commands.seed_checklist_venda import SLUG_CHECKLIST
from apps.automacao.management.commands.seed_fluxo_bot_venda import (
    LIMITE_TENTATIVAS_RECONTATO, NOME_AGENTE_VALIDADOR, NOME_FLUXO,
    NOME_FLUXO_ANTIGO_PROXIMO, NOME_FLUXO_ANTIGO_VALIDAR,
)
from apps.automacao.models import Agente, Checklist, ExecucaoFluxo, Fluxo, ItemChecklist
from apps.automacao.nodes import Contexto
from apps.automacao.runtime import executar_fluxo, validar_fluxo
from apps.automacao.services.checklist import registrar_resposta
from tests.factories import IntegracaoAPIFactory, LeadProspectoFactory, TenantFactory


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


def _rodar(fluxo, tenant, payload):
    """Roda o fluxo a partir do início (`webhook`), com Contexto SEM nenhuma
    entidade pré-injetada — só `variaveis.payload`, exatamente como o caminho
    HTTP real (`views.webhook_receber`) monta o Contexto. Prova que o gap do
    lead fechou de verdade (o nó `carregar_lead` é quem resolve o lead)."""
    ctx = Contexto(tenant=tenant, variaveis={'payload': payload})
    resultado = executar_fluxo(fluxo.grafo, ctx)
    return resultado, ctx


def _corpo_resposta(ctx):
    return json.loads(ctx.variaveis['_resposta_webhook']['corpo'])


# ──────────────────────────────────────────────
# Pré-requisito: checklist
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_falha_sem_checklist_com_mensagem_clara():
    tenant = TenantFactory()
    with pytest.raises(CommandError, match='seed_checklist_venda'):
        call_command('seed_fluxo_bot_venda', tenant=tenant.slug)


@pytest.mark.django_db
def test_tenant_inexistente_falha():
    with pytest.raises(CommandError, match='não encontrado'):
        call_command('seed_fluxo_bot_venda', tenant='tenant-que-nao-existe')


# ──────────────────────────────────────────────
# Idempotência + validade estrutural (UM fluxo só)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_seed_idempotente_duas_rodadas_um_fluxo_so():
    tenant = TenantFactory()
    _checklist_minimo(tenant)

    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxos = list(Fluxo.all_tenants.filter(tenant=tenant))
    assert len(fluxos) == 1
    fluxo = fluxos[0]
    assert fluxo.nome == NOME_FLUXO
    assert fluxo.ativo is False

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
def test_grafo_e_estruturalmente_valido():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    erros = validar_fluxo(fluxo.grafo)
    assert erros == [], erros


@pytest.mark.django_db
def test_rerun_nao_desativa_fluxo_ja_ativado():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    fluxo.ativo = True
    fluxo.save(update_fields=['ativo'])

    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxo.refresh_from_db()
    assert fluxo.ativo is True


@pytest.mark.django_db
def test_rerun_nao_reativa_agente_desligado_manualmente():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    agente = _ativar_agente(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    agente.refresh_from_db()
    assert agente.ativo is True  # preservado, não voltou pra False


# ──────────────────────────────────────────────
# Grafo: nós e conexões esperados (switch de entrada + os 3 ramos)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_grafo_tem_switch_de_entrada_com_3_ramos():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    grafo = fluxo.grafo
    nodes = grafo['nodes']

    assert nodes[grafo['inicio']]['tipo'] == 'webhook'
    assert nodes['hidratar']['tipo'] == 'carregar_lead'
    assert nodes['roteia']['tipo'] == 'switch'

    regras = {r['saida']: r for r in nodes['roteia']['config']['regras']}
    assert set(regras) == {'proximo_passo', 'validar', 'recontato'}

    por_saida = {(c['de'], c['saida']): c['para'] for c in grafo['conexoes']}
    assert por_saida[('roteia', 'proximo_passo')] == 'proximo'
    assert por_saida[('roteia', 'validar')] == 'validar'
    assert por_saida[('roteia', 'recontato')] == 'proximo_recontato'


@pytest.mark.django_db
def test_grafo_ramo_proximo_passo_decide_status_lead():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    grafo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO).grafo
    nodes = grafo['nodes']
    assert nodes['progresso']['tipo'] == 'checklist_progresso'
    assert nodes['ja_respondeu']['tipo'] == 'if'

    por_saida = {(c['de'], c['saida']): c['para'] for c in grafo['conexoes']}
    assert por_saida[('proximo', 'tem_item')] == 'progresso'
    assert por_saida[('proximo', 'completo')] == 'resp_fim'
    assert por_saida[('proximo', 'erro')] == 'resp_erro'
    assert por_saida[('progresso', 'completo')] == 'ja_respondeu'
    assert por_saida[('progresso', 'incompleto')] == 'ja_respondeu'
    assert por_saida[('ja_respondeu', 'true')] == 'resp_pergunta'
    assert por_saida[('ja_respondeu', 'false')] == 'resp_pergunta_inicio'


@pytest.mark.django_db
def test_grafo_ramo_validar_tem_nos_e_branches_esperados():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    grafo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO).grafo
    nodes = grafo['nodes']
    assert nodes['validar']['tipo'] == 'checklist_validar'
    assert nodes['agente']['tipo'] == 'ia_agente'
    assert nodes['json']['tipo'] == 'extrair_json'

    por_saida = {(c['de'], c['saida']): c['para'] for c in grafo['conexoes']}
    # Resposta valida passa pela checagem de cliente HubSoft antes de responder.
    assert por_saida[('validar', 'valida')] == 'e_cpf'
    assert por_saida[('validar', 'erro')] == 'resp_erro'
    assert por_saida[('validar', 'invalida')] == 'agente'
    assert por_saida[('agente', 'sucesso')] == 'json'
    assert por_saida[('json', 'sucesso')] == 'se_valido'
    assert por_saida[('se_valido', 'true')] == 'resp_ok_ia'
    assert por_saida[('se_valido', 'false')] == 'se_desistiu'
    assert por_saida[('se_desistiu', 'true')] == 'resp_transbordo'
    assert por_saida[('se_desistiu', 'false')] == 'resp_repergunta'


@pytest.mark.django_db
def test_grafo_ramo_recontato_existe():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    grafo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO).grafo
    nodes = grafo['nodes']
    assert nodes['proximo_recontato']['tipo'] == 'checklist_proximo_item'
    assert nodes['se_esgotou']['tipo'] == 'if'
    assert nodes['se_esgotou']['config']['direita'] == str(LIMITE_TENTATIVAS_RECONTATO)

    por_saida = {(c['de'], c['saida']): c['para'] for c in grafo['conexoes']}
    assert por_saida[('proximo_recontato', 'tem_item')] == 'se_esgotou'
    assert por_saida[('proximo_recontato', 'completo')] == 'resp_recontato_encerrar'
    assert por_saida[('se_esgotou', 'true')] == 'resp_recontato_encerrar'
    assert por_saida[('se_esgotou', 'false')] == 'resp_recontato_insistir'


# ──────────────────────────────────────────────
# Remoção guardada dos 2 fluxos antigos
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_remove_fluxos_antigos_inativos_e_sem_execucoes():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    Fluxo.all_tenants.create(
        tenant=tenant, nome=NOME_FLUXO_ANTIGO_PROXIMO, grafo={}, ativo=False)
    Fluxo.all_tenants.create(
        tenant=tenant, nome=NOME_FLUXO_ANTIGO_VALIDAR, grafo={}, ativo=False)

    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    assert not Fluxo.all_tenants.filter(tenant=tenant, nome=NOME_FLUXO_ANTIGO_PROXIMO).exists()
    assert not Fluxo.all_tenants.filter(tenant=tenant, nome=NOME_FLUXO_ANTIGO_VALIDAR).exists()
    assert Fluxo.all_tenants.filter(tenant=tenant, nome=NOME_FLUXO).exists()


@pytest.mark.django_db
def test_nao_remove_fluxo_antigo_ativo():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    antigo = Fluxo.all_tenants.create(
        tenant=tenant, nome=NOME_FLUXO_ANTIGO_PROXIMO, grafo={}, ativo=True)

    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    assert Fluxo.all_tenants.filter(pk=antigo.pk).exists()


@pytest.mark.django_db
def test_nao_remove_fluxo_antigo_com_execucoes():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    antigo = Fluxo.all_tenants.create(
        tenant=tenant, nome=NOME_FLUXO_ANTIGO_VALIDAR, grafo={}, ativo=False)
    ExecucaoFluxo.all_tenants.create(tenant=tenant, fluxo=antigo)

    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)

    assert Fluxo.all_tenants.filter(pk=antigo.pk).exists()


# ──────────────────────────────────────────────
# E2E: ramo "proximo_passo" (rodado do webhook, SEM lead pré-injetado)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_e2e_proximo_passo_lead_sem_respostas_status_lead_0_int_e_total_opcoes_int():
    tenant = TenantFactory()
    _checklist, item1, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990001')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'proximo_passo', 'cellphone': '5589999990001', 'lead_id': lead.id,
    })

    assert resultado.status == 'completado', resultado.erro
    resp = ctx.variaveis['_resposta_webhook']
    assert resp['status'] == 200
    corpo = json.loads(resp['corpo'])  # prova que o corpo é JSON válido de verdade

    assert corpo['proximo_passo'] == 'seguir_pergunta'
    assert corpo['deve_perguntar'] is True
    assert corpo['proxima_pergunta_id'] == item1.pk
    assert corpo['mensagem_inicial'] == item1.pergunta  # inclui a quebra de linha real
    assert corpo['lead_id'] == lead.id

    # CORREÇÃO 2: lead nunca respondeu nada -> status_lead = 0 (INT, sem aspas)
    assert corpo['status_lead'] == 0
    assert isinstance(corpo['status_lead'], int)
    assert not isinstance(corpo['status_lead'], bool)

    # CORREÇÃO 1: ura.total_opcoes sai como INT de verdade (item1 é texto livre: 0 opções)
    assert isinstance(corpo['ura']['total_opcoes'], int)
    assert corpo['ura']['total_opcoes'] == 0


@pytest.mark.django_db
def test_e2e_proximo_passo_com_opcoes_total_opcoes_int_maior_que_zero():
    tenant = TenantFactory()
    checklist, item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990002')
    registrar_resposta(checklist, item1, 'lead', lead.pk, '11144477735', valor_processado='11144477735')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'proximo_passo', 'cellphone': '5589999990002',
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['proxima_pergunta_id'] == item2.pk
    assert isinstance(corpo['ura']['total_opcoes'], int)
    assert corpo['ura']['total_opcoes'] == 2  # item2 tem 2 opções (Casa/Empresa)
    assert corpo['ura']['opcoes'] == [{'texto': 'Casa', 'valor': 'casa'}, {'texto': 'Empresa', 'valor': 'empresa'}]

    # CORREÇÃO 2: já tem 1 resposta -> status_lead = "em_andamento" (string)
    assert corpo['status_lead'] == 'em_andamento'
    assert isinstance(corpo['status_lead'], str)


@pytest.mark.django_db
def test_e2e_proximo_passo_tudo_respondido_devolve_encerrar():
    tenant = TenantFactory()
    checklist, item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990003')
    registrar_resposta(checklist, item1, 'lead', lead.pk, '11144477735', valor_processado='11144477735')
    registrar_resposta(checklist, item2, 'lead', lead.pk, '1', valor_processado='casa')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'proximo_passo', 'cellphone': '5589999990003',
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['proximo_passo'] == 'red_encerrar'
    assert corpo['deve_perguntar'] is False


# ──────────────────────────────────────────────
# E2E: ramo "validar"
# ──────────────────────────────────────────────

@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm')
def test_e2e_validar_resposta_valida_por_opcao_nao_chama_ia(mock_llm):
    tenant = TenantFactory()
    _checklist, _item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990004')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990004',
        'question_id': item2.pk, 'answer': '1',
    })

    assert resultado.status == 'completado', resultado.erro
    mock_llm.assert_not_called()
    corpo = _corpo_resposta(ctx)
    # TEXTO, nao booleano: o bot do Matrix nao compara booleano JSON cru
    # na condicao do no de decisao (ver seed_fluxo_bot_venda).
    assert corpo['resposta_correta'] == 'true'
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
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990005')

    mock_llm.return_value = json.dumps({
        'valido': True, 'dados_extraidos': {'tipo_imovel': 'casa'},
        'mensagem_bot': '', 'motivo_invalido': '', 'confianca': 0.9,
        'intencao_detectada': 'ok',
    })

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990005',
        'question_id': item2.pk, 'answer': 'minha casa mesmo',
    })

    assert resultado.status == 'completado', resultado.erro
    mock_llm.assert_called_once()
    passos = {p.handle: p for p in resultado.passos}
    assert passos['validar'].branch == 'invalida'
    assert passos['se_valido'].branch == 'true'
    corpo = _corpo_resposta(ctx)
    # TEXTO, nao booleano: o bot do Matrix nao compara booleano JSON cru
    # na condicao do no de decisao (ver seed_fluxo_bot_venda).
    assert corpo['resposta_correta'] == 'true'
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
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990006')

    mock_llm.return_value = json.dumps({
        'valido': False, 'dados_extraidos': {}, 'mensagem_bot': 'Tudo bem, vou te transferir.',
        'motivo_invalido': 'cliente desistiu', 'confianca': 0.95,
        'intencao_detectada': 'desistir',
    })

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990006',
        'question_id': item2.pk, 'answer': 'na verdade desisto, obrigado',
    })

    assert resultado.status == 'completado', resultado.erro
    passos = {p.handle: p for p in resultado.passos}
    assert passos['se_valido'].branch == 'false'
    assert passos['se_desistiu'].branch == 'true'
    corpo = _corpo_resposta(ctx)
    # needsReception é STRING "true"/"false" no contrato, não boolean
    assert corpo['needsReception'] == 'true'
    assert isinstance(corpo['needsReception'], str)
    # TEXTO, nao booleano: o bot do Matrix nao compara booleano JSON cru
    # na condicao do no de decisao (ver seed_fluxo_bot_venda).
    assert corpo['resposta_correta'] == 'false'
    assert 'transferir' in corpo['retorno_erro_api'].lower()


# ──────────────────────────────────────────────
# E2E: ramo "recontato" (novo, nunca tinha sido construído)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_e2e_recontato_tentativa_1_reprergunta_com_a_pergunta_atual():
    tenant = TenantFactory()
    _checklist, item1, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990007')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'recontato', 'cellphone': '5589999990007',
        'tentativa': 1, 'pergunta_id': item1.pk,
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['acao'] == 'reperguntar'
    assert corpo['reperguntar'] is True
    assert corpo['deve_transbordar'] == 'false'
    assert 'Ainda esta ai?' in corpo['mensagem']
    assert item1.pergunta in corpo['mensagem']


@pytest.mark.django_db
def test_e2e_recontato_tentativa_3_encerra():
    tenant = TenantFactory()
    _checklist, item1, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990008')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'recontato', 'cellphone': '5589999990008',
        'tentativa': 3, 'pergunta_id': item1.pk,
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['acao'] == 'encerrar'
    assert corpo['reperguntar'] is False
    assert corpo['deve_transbordar'] == 'true'


@pytest.mark.django_db
def test_e2e_recontato_nada_pendente_encerra_sem_vazar_template():
    tenant = TenantFactory()
    checklist, item1, item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990009')
    registrar_resposta(checklist, item1, 'lead', lead.pk, '11144477735', valor_processado='11144477735')
    registrar_resposta(checklist, item2, 'lead', lead.pk, '1', valor_processado='casa')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'recontato', 'cellphone': '5589999990009',
        'tentativa': 1, 'pergunta_id': item2.pk,
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['acao'] == 'encerrar'
    assert '{{' not in corpo['mensagem']


# ──────────────────────────────────────────────
# Gap do lead: `carregar_lead` acha por telefone com/sem 55/DDD, rodando o
# fluxo inteiro a partir do webhook (prova ponta a ponta, não só do node isolado)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_e2e_gap_lead_acha_por_telefone_com_55_quando_salvo_sem():
    tenant = TenantFactory()
    _checklist, item1, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='89999990010')  # salvo sem 55

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'proximo_passo', 'cellphone': '5589999990010',  # payload manda com 55
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['lead_id'] == lead.id
    assert corpo['proxima_pergunta_id'] == item1.pk


@pytest.mark.django_db
def test_e2e_gap_lead_acha_por_telefone_sem_ddd_quando_salvo_com_55_e_ddd():
    tenant = TenantFactory()
    _checklist, item1, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990011')  # salvo com 55+DDD

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'proximo_passo', 'cellphone': '999990011',  # payload manda só o número local
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['lead_id'] == lead.id
    assert corpo['proxima_pergunta_id'] == item1.pk


@pytest.mark.django_db
def test_e2e_gap_lead_cria_lead_quando_nao_acha_e_segue_o_fluxo():
    tenant = TenantFactory()
    _checklist, item1, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'proximo_passo', 'cellphone': '5589999990012',
    })

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    assert corpo['proxima_pergunta_id'] == item1.pk
    assert corpo['status_lead'] == 0  # lead novo, nenhuma resposta ainda
    assert ctx.lead is not None
    assert ctx.lead.telefone == '5589999990012'


@pytest.mark.django_db
def test_e2e_gap_lead_sem_telefone_nem_criar_cai_no_erro_estrutural_sem_derrubar():
    tenant = TenantFactory()
    _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)

    # payload sem `cellphone`: `hidratar` não acha nem cria lead nenhum; o
    # fluxo não pode travar/derrubar — cai no erro estrutural compartilhado.
    resultado, ctx = _rodar(fluxo, tenant, {'acao': 'proximo_passo'})

    assert resultado.status == 'completado', resultado.erro
    corpo = _corpo_resposta(ctx)
    # TEXTO, nao booleano: o bot do Matrix nao compara booleano JSON cru
    # na condicao do no de decisao (ver seed_fluxo_bot_venda).
    assert corpo['resposta_correta'] == 'false'
    assert corpo['needsReception'] == 'true'


# ──────────────────────────────────────────────
# E2E: checagem de cliente HubSoft no ramo "validar"
# ──────────────────────────────────────────────

@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm')
@mock.patch('apps.automacao.nodes.hubsoft_consultar_cliente.consultar_cliente')
def test_e2e_cpf_de_quem_ja_e_cliente_transborda(mock_consulta, mock_llm):
    """CPF de assinante nao segue vendendo: transborda pro atendimento humano."""
    tenant = TenantFactory()
    _checklist, item_cpf, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    LeadProspectoFactory(tenant=tenant, telefone='5589999990010')
    # Forma real da resposta do HubSoft quando ACHA (verificada em producao).
    mock_consulta.return_value = {
        'status': 'success', 'msg': 'Dados consultados com sucesso',
        'clientes': [{'id_cliente': 123, 'nome_razaosocial': 'Fulano'}],
    }

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990010',
        'question_id': item_cpf.pk, 'answer': '111.444.777-35',
    })

    assert resultado.status == 'completado', resultado.erro
    mock_consulta.assert_called_once()
    mock_llm.assert_not_called()
    passos = {p.handle: p for p in resultado.passos}
    assert passos['e_cpf'].branch == 'true'
    assert passos['e_cliente'].branch == 'true'
    corpo = _corpo_resposta(ctx)
    # A resposta do cliente ESTAVA certa; o que muda e o destino do atendimento.
    assert corpo['resposta_correta'] == 'true'
    assert corpo['needsReception'] == 'true'
    assert corpo['isAClient'] is True
    assert corpo['message']


@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm')
@mock.patch('apps.automacao.nodes.hubsoft_consultar_cliente.consultar_cliente')
def test_e2e_cpf_de_quem_nao_e_cliente_segue_a_venda(mock_consulta, mock_llm):
    """HubSoft devolve `clientes` VAZIO pra quem nao e cliente, nao erro."""
    tenant = TenantFactory()
    _checklist, item_cpf, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    LeadProspectoFactory(tenant=tenant, telefone='5589999990011')
    mock_consulta.return_value = {
        'status': 'success', 'msg': 'Dados consultados com sucesso', 'clientes': [],
    }

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990011',
        'question_id': item_cpf.pk, 'answer': '111.444.777-35',
    })

    assert resultado.status == 'completado', resultado.erro
    passos = {p.handle: p for p in resultado.passos}
    assert passos['e_cliente'].branch == 'false'
    corpo = _corpo_resposta(ctx)
    assert corpo['needsReception'] == 'false'
    assert corpo['isAClient'] is False
    mock_llm.assert_not_called()


@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.hubsoft_consultar_cliente.consultar_cliente')
def test_e2e_hubsoft_fora_do_ar_nao_trava_a_venda(mock_consulta):
    """Integracao caida perde a checagem, nunca o atendimento."""
    tenant = TenantFactory()
    _checklist, item_cpf, _item2 = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    LeadProspectoFactory(tenant=tenant, telefone='5589999990012')
    mock_consulta.side_effect = RuntimeError('HubSoft indisponivel')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990012',
        'question_id': item_cpf.pk, 'answer': '111.444.777-35',
    })

    assert resultado.status == 'completado', resultado.erro
    passos = {p.handle: p for p in resultado.passos}
    assert passos['consultar_cliente'].branch == 'erro'
    corpo = _corpo_resposta(ctx)
    assert corpo['resposta_correta'] == 'true'
    assert corpo['needsReception'] == 'false'


@pytest.mark.django_db
@mock.patch('apps.automacao.nodes.hubsoft_consultar_cliente.consultar_cliente')
def test_e2e_pergunta_que_nao_e_cpf_nao_consulta_o_hubsoft(mock_consulta):
    """Uma chamada de API por resposta seria desperdicio e latencia (o bot tem
    45s de teto por turno). So o CPF dispara a consulta."""
    tenant = TenantFactory()
    _checklist, _item_cpf, item_tipo = _checklist_minimo(tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    LeadProspectoFactory(tenant=tenant, telefone='5589999990013')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990013',
        'question_id': item_tipo.pk, 'answer': '1',
    })

    assert resultado.status == 'completado', resultado.erro
    mock_consulta.assert_not_called()
    passos = {p.handle: p for p in resultado.passos}
    assert passos['e_cpf'].branch == 'false'
    assert _corpo_resposta(ctx)['resposta_correta'] == 'true'


# ──────────────────────────────────────────────
# E2E: checagem de cobertura ao confirmar o endereço
# ──────────────────────────────────────────────

def _item_endereco(checklist, tenant):
    """Item de confirmação de endereço + o CEP já respondido antes dele, que é
    o mínimo que a consulta precisa (o service completa o resto via ViaCEP)."""
    from apps.automacao.management.commands.seed_fluxo_bot_venda import (
        CHAVE_ENDERECO_CONFIRMADO,
    )
    cep = ItemChecklist.all_tenants.create(
        tenant=tenant, checklist=checklist, chave='cep', ordem=3,
        pergunta='Qual o seu CEP?', tipo_resposta='texto_livre',
        tipo_validacao='nenhuma', obrigatorio=True,
    )
    conf = ItemChecklist.all_tenants.create(
        tenant=tenant, checklist=checklist, chave=CHAVE_ENDERECO_CONFIRMADO, ordem=4,
        pergunta='Está tudo certo com esse endereço?', tipo_resposta='texto_livre',
        tipo_validacao='nenhuma', obrigatorio=True,
    )
    return cep, conf


@pytest.mark.django_db
@mock.patch('apps.comercial.viabilidade.services.consultar_viabilidade')
def test_e2e_endereco_com_cobertura_segue_a_venda(mock_viab):
    from apps.comercial.viabilidade.services import ResultadoViabilidade

    tenant = TenantFactory()
    checklist, _i1, _i2 = _checklist_minimo(tenant)
    item_cep, item_conf = _item_endereco(checklist, tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990020')
    registrar_resposta(checklist, item_cep, 'lead', lead.pk, '64000000')
    mock_viab.return_value = ResultadoViabilidade(
        status='cobertura_ok', cep_consultado='64000000', fonte='hubsoft',
    )

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990020',
        'question_id': item_conf.pk, 'answer': 'sim',
    })

    assert resultado.status == 'completado', resultado.erro
    mock_viab.assert_called_once()
    passos = {p.handle: p for p in resultado.passos}
    assert passos['e_endereco'].branch == 'true'
    assert passos['viabilidade'].branch == 'cobertura_ok'
    corpo = _corpo_resposta(ctx)
    assert corpo['needsReception'] == 'false'


@pytest.mark.django_db
@mock.patch('apps.comercial.viabilidade.services.consultar_viabilidade')
@pytest.mark.parametrize('status_viab,branch', [
    ('fora_cobertura', 'fora_cobertura'),
    # `pendente_revisao` tambem transborda: NAO sabemos se atende, e cravar
    # "sem cobertura" em cima de resposta desconhecida derruba venda boa.
    ('nao_consultado', 'pendente_revisao'),
    ('endereco_incompleto', 'pendente_revisao'),
])
def test_e2e_endereco_sem_cobertura_confirmada_transborda(mock_viab, status_viab, branch):
    from apps.comercial.viabilidade.services import ResultadoViabilidade

    tenant = TenantFactory()
    checklist, _i1, _i2 = _checklist_minimo(tenant)
    item_cep, item_conf = _item_endereco(checklist, tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990021')
    registrar_resposta(checklist, item_cep, 'lead', lead.pk, '64000000')
    mock_viab.return_value = ResultadoViabilidade(
        status=status_viab, cep_consultado='64000000', fonte='hubsoft',
    )

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990021',
        'question_id': item_conf.pk, 'answer': 'sim',
    })

    assert resultado.status == 'completado', resultado.erro
    passos = {p.handle: p for p in resultado.passos}
    assert passos['viabilidade'].branch == branch
    corpo = _corpo_resposta(ctx)
    # A resposta do cliente estava certa; o que muda e o destino do atendimento.
    assert corpo['resposta_correta'] == 'true'
    assert corpo['needsReception'] == 'true'
    assert corpo['message']


@pytest.mark.django_db
@mock.patch('apps.comercial.viabilidade.services.consultar_viabilidade')
def test_e2e_pergunta_comum_nao_consulta_viabilidade(mock_viab):
    """Só a confirmação de endereço dispara a consulta."""
    tenant = TenantFactory()
    checklist, _item_cpf, item_tipo = _checklist_minimo(tenant)
    _item_endereco(checklist, tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    LeadProspectoFactory(tenant=tenant, telefone='5589999990022')

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990022',
        'question_id': item_tipo.pk, 'answer': '1',
    })

    assert resultado.status == 'completado', resultado.erro
    mock_viab.assert_not_called()
    passos = {p.handle: p for p in resultado.passos}
    assert passos['e_endereco'].branch == 'false'
    assert _corpo_resposta(ctx)['needsReception'] == 'false'


@pytest.mark.django_db
@mock.patch('apps.comercial.viabilidade.services.consultar_viabilidade')
def test_e2e_endereco_ainda_nao_respondido_nao_vaza_template_pra_consulta(mock_viab):
    """Campos de endereço que o cliente ainda não respondeu chegam VAZIOS na
    consulta, não como `{{nodes.respostas.cidade}}` literal.

    O `Contexto.resolver` devolve o template cru quando o caminho não existe
    (decisão do runtime). No roteiro, a confirmação do endereço vem ANTES de
    cidade/rua/bairro, então esses campos ainda não existem no dicionário de
    respostas. Sem a limpeza, o HubSoft recebia o template como se fosse o nome
    da cidade e devolvia erro: o bot transbordava até em CEP com cobertura.
    Achado testando contra produção."""
    from apps.comercial.viabilidade.services import ResultadoViabilidade

    tenant = TenantFactory()
    checklist, _i1, _i2 = _checklist_minimo(tenant)
    item_cep, item_conf = _item_endereco(checklist, tenant)
    call_command('seed_fluxo_bot_venda', tenant=tenant.slug)
    fluxo = Fluxo.all_tenants.get(tenant=tenant, nome=NOME_FLUXO)
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990023')
    registrar_resposta(checklist, item_cep, 'lead', lead.pk, '13327450')
    mock_viab.return_value = ResultadoViabilidade(
        status='cobertura_ok', cep_consultado='13327450', fonte='hubsoft',
    )

    resultado, ctx = _rodar(fluxo, tenant, {
        'acao': 'validar', 'cellphone': '5589999990023',
        'question_id': item_conf.pk, 'answer': 'sim',
    })

    assert resultado.status == 'completado', resultado.erro
    _args, kwargs = mock_viab.call_args
    for campo in ('logradouro', 'numero', 'bairro', 'cidade', 'uf'):
        assert '{{' not in (kwargs.get(campo) or ''), f'{campo} vazou template'
        assert (kwargs.get(campo) or '') == '', f'{campo} deveria estar vazio'
    # O CEP, esse sim respondido, tem que chegar de verdade.
    assert mock_viab.call_args[0][1] == '13327450'
    assert _corpo_resposta(ctx)['needsReception'] == 'false'
