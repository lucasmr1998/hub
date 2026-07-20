"""Testes das duas telas que expoem o que o bot coletou via checklist.

1. Workspace > Checklists > "Em andamento" (`workspace:checklist_respostas`):
   lista as entidades que ja comecaram a responder, com progresso, item em que
   pararam e data da ultima resposta.
2. Bloco "Respostas do bot" no detalhe do lead (`comercial_leads:lead_detail`).

Cobre: isolamento multi tenant, paridade do progresso exibido com o servico
`progresso()`, lead sem resposta (secao nao renderiza), ordem dos itens e
entidade cujo LeadProspecto foi apagado (nao pode quebrar a tela).

Segue o padrao de tests/test_workspace_checklists.py (mk_user + set_current_tenant).
"""
import pytest
from django.urls import reverse

from apps.automacao.models import Checklist, ItemChecklist, RespostaChecklist
from apps.automacao.services.checklist import ENTIDADE_LEAD, progresso, registrar_resposta
from apps.sistema.middleware import set_current_tenant
from apps.sistema.models import Funcionalidade, PerfilPermissao, PermissaoUsuario
from tests.factories import (
    ConfigEmpresaFactory, LeadProspectoFactory, PerfilFactory, TenantFactory, UserFactory,
)


WS_FUNCS = {'workspace.ver': 'Ver Workspace', 'workspace.editar_todos': 'Editar todos'}


def _funcs(*codigos):
    out = []
    for c in codigos:
        f, _ = Funcionalidade.objects.get_or_create(
            codigo=c, defaults={'modulo': 'workspace', 'nome': WS_FUNCS.get(c, c)})
        out.append(f)
    return out


def mk_user(tenant, *codigos, is_superuser=False):
    user = UserFactory(is_staff=True, is_superuser=is_superuser)
    PerfilFactory(user=user, tenant=tenant)
    if not is_superuser:
        perfil = PerfilPermissao.objects.create(tenant=tenant, nome=f'Perfil {user.username}')
        if codigos:
            perfil.funcionalidades.add(*_funcs(*codigos))
        PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil)
    return user


@pytest.fixture
def tenant(db):
    t = TenantFactory(nome='Aurora Respostas Teste', slug='aurora-respostas-teste')
    ConfigEmpresaFactory(tenant=t)
    set_current_tenant(t)
    yield t
    set_current_tenant(None)


def _mk_checklist(tenant, **kwargs):
    defaults = {'nome': 'Roteiro de venda', 'slug': 'roteiro-venda'}
    defaults.update(kwargs)
    return Checklist.all_tenants.create(tenant=tenant, **defaults)


def _mk_item(checklist, chave, pergunta, ordem, **kwargs):
    return ItemChecklist.all_tenants.create(
        tenant=checklist.tenant, checklist=checklist,
        chave=chave, pergunta=pergunta, ordem=ordem, **kwargs,
    )


def _mk_lead(tenant, **kwargs):
    return LeadProspectoFactory(tenant=tenant, **kwargs)


# ============================================================================
# Tela "Em andamento" — permissao e isolamento de tenant
# ============================================================================

@pytest.mark.django_db
def test_respostas_exige_workspace_ver(client, tenant):
    checklist = _mk_checklist(tenant)
    client.force_login(mk_user(tenant))  # sem workspace.ver
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 403


@pytest.mark.django_db
def test_respostas_404_pra_checklist_de_outro_tenant(client, tenant):
    outro = TenantFactory(nome='Outro provedor', slug='outro-respostas-404')
    ConfigEmpresaFactory(tenant=outro)
    alheio = _mk_checklist(outro, nome='Roteiro alheio', slug='roteiro-alheio')

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[alheio.pk]))
    assert r.status_code == 404


@pytest.mark.django_db
def test_respostas_lista_apenas_entidades_do_proprio_tenant(client, tenant):
    """Dois tenants, cada um com seu checklist, seu lead e sua resposta. A tela
    de um NUNCA pode mostrar o lead do outro."""
    checklist = _mk_checklist(tenant)
    item = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    lead = _mk_lead(tenant, nome_razaosocial='Cliente do tenant A')
    registrar_resposta(checklist, item, ENTIDADE_LEAD, lead.pk, 'Maria')

    outro = TenantFactory(nome='Outro provedor', slug='outro-respostas-iso')
    ConfigEmpresaFactory(tenant=outro)
    checklist_b = _mk_checklist(outro, nome='Roteiro B', slug='roteiro-b')
    item_b = _mk_item(checklist_b, 'nome', 'Qual seu nome?', 0)
    lead_b = _mk_lead(outro, nome_razaosocial='Cliente do tenant B')
    registrar_resposta(checklist_b, item_b, ENTIDADE_LEAD, lead_b.pk, 'Joao')

    set_current_tenant(tenant)
    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    assert b'Cliente do tenant A' in r.content
    assert b'Cliente do tenant B' not in r.content


@pytest.mark.django_db
def test_respostas_nao_vaza_resposta_de_outro_tenant_no_mesmo_id(client, tenant):
    """Caso vicioso do `entidade_id` generico: dois tenants podem ter respostas
    apontando pro MESMO id numerico. O filtro por tenant tem que separar."""
    checklist = _mk_checklist(tenant)
    item = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    lead = _mk_lead(tenant, nome_razaosocial='Lead legitimo')
    registrar_resposta(checklist, item, ENTIDADE_LEAD, lead.pk, 'Maria')

    outro = TenantFactory(nome='Outro provedor', slug='outro-respostas-colisao')
    ConfigEmpresaFactory(tenant=outro)
    checklist_b = _mk_checklist(outro, nome='Roteiro B', slug='roteiro-b-colisao')
    item_b = _mk_item(checklist_b, 'nome', 'Qual seu nome?', 0)
    # Mesmo entidade_id do lead do tenant A, de proposito.
    registrar_resposta(checklist_b, item_b, ENTIDADE_LEAD, lead.pk, 'Intruso')

    set_current_tenant(tenant)
    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    # So uma linha: a do proprio tenant.
    assert r.context['total_entidades'] == 1
    assert r.content.count(b'Lead legitimo') == 1
    assert b'Intruso' not in r.content


# ============================================================================
# Tela "Em andamento" — conteudo
# ============================================================================

@pytest.mark.django_db
def test_progresso_exibido_bate_com_o_servico(client, tenant):
    checklist = _mk_checklist(tenant)
    itens = [
        _mk_item(checklist, 'nome', 'Qual seu nome?', 0),
        _mk_item(checklist, 'cep', 'Qual seu CEP?', 1),
        _mk_item(checklist, 'plano', 'Qual plano?', 2),
    ]
    lead = _mk_lead(tenant, nome_razaosocial='Cliente parcial')
    registrar_resposta(checklist, itens[0], ENTIDADE_LEAD, lead.pk, 'Maria')
    registrar_resposta(checklist, itens[1], ENTIDADE_LEAD, lead.pk, '64000-000')

    esperado = progresso(checklist, ENTIDADE_LEAD, lead.pk)
    assert esperado['respondidos'] == 2 and esperado['total'] == 3

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    linha = r.context['linhas'][0]
    assert linha['progresso'] == esperado
    assert linha['rotulo_progresso'] == '2/3'
    # Parou no terceiro item, que e o unico ainda sem resposta.
    assert linha['proximo_item'].chave == 'plano'
    assert b'Qual plano?' in r.content


@pytest.mark.django_db
def test_checklist_completo_marca_completo_e_sem_proximo_item(client, tenant):
    checklist = _mk_checklist(tenant)
    item = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    lead = _mk_lead(tenant, nome_razaosocial='Cliente completo')
    registrar_resposta(checklist, item, ENTIDADE_LEAD, lead.pk, 'Maria')

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    linha = r.context['linhas'][0]
    assert linha['progresso']['completo'] is True
    assert linha['proximo_item'] is None
    assert b'Completo' in r.content


@pytest.mark.django_db
def test_lead_apagado_nao_quebra_a_tela(client, tenant):
    """Resposta orfa (LeadProspecto deletado depois de responder) tem que
    aparecer marcada como removida, nunca derrubar a pagina."""
    checklist = _mk_checklist(tenant)
    item = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    lead = _mk_lead(tenant, nome_razaosocial='Cliente que sumiu')
    lead_id = lead.pk
    registrar_resposta(checklist, item, ENTIDADE_LEAD, lead_id, 'Maria')
    lead.delete()

    assert RespostaChecklist.all_tenants.filter(
        tenant=tenant, entidade_id=lead_id).exists()

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    linha = r.context['linhas'][0]
    assert linha['nome'] == f'Lead #{lead_id} (removido)'
    assert linha['url_detalhe'] == ''
    assert b'(removido)' in r.content


@pytest.mark.django_db
def test_ordena_pela_ultima_resposta_mais_recente_primeiro(client, tenant):
    checklist = _mk_checklist(tenant)
    item = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    antigo = _mk_lead(tenant, nome_razaosocial='Respondeu primeiro')
    recente = _mk_lead(tenant, nome_razaosocial='Respondeu depois')
    registrar_resposta(checklist, item, ENTIDADE_LEAD, antigo.pk, 'Ana')
    registrar_resposta(checklist, item, ENTIDADE_LEAD, recente.pk, 'Bia')

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    nomes = [linha['nome'] for linha in r.context['linhas']]
    assert nomes == ['Respondeu depois', 'Respondeu primeiro']


@pytest.mark.django_db
def test_pagina_sem_respostas_mostra_empty_state(client, tenant):
    checklist = _mk_checklist(tenant)
    _mk_item(checklist, 'nome', 'Qual seu nome?', 0)

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    assert r.context['linhas'] == []
    assert b'Ninguem respondeu este checklist ainda' in r.content


@pytest.mark.django_db
def test_pagina_25_por_vez(client, tenant):
    checklist = _mk_checklist(tenant)
    item = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    for i in range(27):
        lead = _mk_lead(tenant, nome_razaosocial=f'Cliente {i:02d}')
        registrar_resposta(checklist, item, ENTIDADE_LEAD, lead.pk, f'Resposta {i}')

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    assert len(r.context['linhas']) == 25
    assert r.context['total_entidades'] == 27

    r2 = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]), {'page': 2})
    assert r2.status_code == 200
    assert len(r2.context['linhas']) == 2


@pytest.mark.django_db
def test_template_nao_vaza_comentario_django(client, tenant):
    """Comentario `{# ... #}` multilinha nao e removido pelo engine e vaza pra
    tela. Guarda contra a regressao ja vivida no checklist_editar.html."""
    checklist = _mk_checklist(tenant)
    item = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    lead = _mk_lead(tenant, nome_razaosocial='Cliente qualquer')
    registrar_resposta(checklist, item, ENTIDADE_LEAD, lead.pk, 'Maria')

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklist_respostas', args=[checklist.pk]))
    assert r.status_code == 200
    assert b'{#' not in r.content


# ============================================================================
# Bloco "Respostas do bot" no detalhe do lead
# ============================================================================

def _mk_user_lead(tenant):
    """O detalhe do lead so exige login (sem funcionalidade especifica)."""
    return mk_user(tenant, is_superuser=True)


@pytest.mark.django_db
def test_lead_sem_respostas_nao_renderiza_a_secao(client, tenant):
    lead = _mk_lead(tenant, nome_razaosocial='Lead sem bot')

    client.force_login(_mk_user_lead(tenant))
    r = client.get(reverse('comercial_leads:lead_detail', args=[lead.pk]))
    assert r.status_code == 200
    assert r.context['grupos_respostas_bot'] == []
    assert b'Respostas do bot' not in r.content


@pytest.mark.django_db
def test_lead_com_respostas_renderiza_na_ordem_dos_itens(client, tenant):
    checklist = _mk_checklist(tenant)
    primeiro = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    segundo = _mk_item(checklist, 'cep', 'Qual seu CEP?', 1)
    terceiro = _mk_item(checklist, 'plano', 'Qual plano?', 2)
    lead = _mk_lead(tenant, nome_razaosocial='Lead com bot')

    # Registra fora de ordem de proposito: a tela ordena pelo item, nao pela
    # ordem em que o bot gravou.
    registrar_resposta(checklist, terceiro, ENTIDADE_LEAD, lead.pk, '1 Giga')
    registrar_resposta(checklist, primeiro, ENTIDADE_LEAD, lead.pk, 'Maria')
    registrar_resposta(checklist, segundo, ENTIDADE_LEAD, lead.pk, '64000-000')

    client.force_login(_mk_user_lead(tenant))
    r = client.get(reverse('comercial_leads:lead_detail', args=[lead.pk]))
    assert r.status_code == 200
    grupos = r.context['grupos_respostas_bot']
    assert len(grupos) == 1
    perguntas = [item['pergunta'] for item in grupos[0]['respostas']]
    assert perguntas == ['Qual seu nome?', 'Qual seu CEP?', 'Qual plano?']
    assert b'Respostas do bot' in r.content
    assert b'Maria' in r.content


@pytest.mark.django_db
def test_valor_normalizado_so_aparece_quando_difere_do_bruto(client, tenant):
    checklist = _mk_checklist(tenant)
    igual = _mk_item(checklist, 'nome', 'Qual seu nome?', 0)
    diferente = _mk_item(checklist, 'cep', 'Qual seu CEP?', 1)
    lead = _mk_lead(tenant, nome_razaosocial='Lead normalizado')

    registrar_resposta(checklist, igual, ENTIDADE_LEAD, lead.pk, 'Maria', valor_processado='Maria')
    registrar_resposta(checklist, diferente, ENTIDADE_LEAD, lead.pk, '64.000-000', valor_processado='64000000')

    client.force_login(_mk_user_lead(tenant))
    r = client.get(reverse('comercial_leads:lead_detail', args=[lead.pk]))
    assert r.status_code == 200
    respostas = r.context['grupos_respostas_bot'][0]['respostas']
    por_pergunta = {item['pergunta']: item for item in respostas}
    assert por_pergunta['Qual seu nome?']['valor_normalizado'] == ''
    assert por_pergunta['Qual seu CEP?']['valor_normalizado'] == '64000000'
    assert b'Normalizado' in r.content


@pytest.mark.django_db
def test_respostas_do_lead_agrupadas_por_checklist(client, tenant):
    venda = _mk_checklist(tenant, nome='Roteiro de venda', slug='roteiro-venda')
    suporte = _mk_checklist(tenant, nome='Triagem de suporte', slug='triagem-suporte')
    item_venda = _mk_item(venda, 'plano', 'Qual plano?', 0)
    item_suporte = _mk_item(suporte, 'problema', 'Qual o problema?', 0)
    lead = _mk_lead(tenant, nome_razaosocial='Lead dois roteiros')

    registrar_resposta(venda, item_venda, ENTIDADE_LEAD, lead.pk, '1 Giga')
    registrar_resposta(suporte, item_suporte, ENTIDADE_LEAD, lead.pk, 'Sem sinal')

    client.force_login(_mk_user_lead(tenant))
    r = client.get(reverse('comercial_leads:lead_detail', args=[lead.pk]))
    assert r.status_code == 200
    grupos = r.context['grupos_respostas_bot']
    assert len(grupos) == 2
    nomes = [g['checklist'].nome for g in grupos]
    assert nomes == ['Roteiro de venda', 'Triagem de suporte']
    assert all(len(g['respostas']) == 1 for g in grupos)


@pytest.mark.django_db
def test_lead_nao_mostra_resposta_de_outro_tenant_com_mesmo_id(client, tenant):
    """`entidade_id` e generico: sem filtro por tenant, o lead do tenant A
    mostraria a resposta que o tenant B gravou pro mesmo id numerico."""
    lead = _mk_lead(tenant, nome_razaosocial='Lead do tenant A')

    outro = TenantFactory(nome='Outro provedor', slug='outro-lead-colisao')
    ConfigEmpresaFactory(tenant=outro)
    checklist_b = _mk_checklist(outro, nome='Roteiro B', slug='roteiro-b-lead')
    item_b = _mk_item(checklist_b, 'nome', 'Pergunta do tenant B', 0)
    registrar_resposta(checklist_b, item_b, ENTIDADE_LEAD, lead.pk, 'Vazamento')

    set_current_tenant(tenant)
    client.force_login(_mk_user_lead(tenant))
    r = client.get(reverse('comercial_leads:lead_detail', args=[lead.pk]))
    assert r.status_code == 200
    assert r.context['grupos_respostas_bot'] == []
    assert b'Vazamento' not in r.content
