"""
Testes de integração para views do CRM.
Cobre: pipeline, oportunidades, tarefas, notas, equipes, metas, configurações.
"""
import json
import pytest
from django.urls import reverse

from apps.sistema.middleware import set_current_tenant
from apps.comercial.crm.models import (
    Pipeline, PipelineEstagio, OportunidadeVenda, TarefaCRM,
    NotaInterna, EquipeVendas, ConfiguracaoCRM,
)
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory,
)


@pytest.fixture
def crm_setup(db):
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    pipeline = Pipeline.all_tenants.create(
        tenant=tenant, nome='Vendas', slug='vendas', tipo='vendas', padrao=True,
    )
    e_novo = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Novo', slug='novo', tipo='novo', ordem=1,
    )
    e_qualif = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Qualificado', slug='qualificado', tipo='qualificacao', ordem=2,
    )
    e_ganho = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Ganho', slug='ganho', tipo='cliente', ordem=3, is_final_ganho=True,
    )
    e_perdido = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Perdido', slug='perdido', tipo='perdido', ordem=4, is_final_perdido=True,
    )

    ConfiguracaoCRM.all_tenants.create(
        tenant=tenant, pipeline_padrao=pipeline, estagio_inicial_padrao=e_novo,
    )

    lead = LeadProspectoFactory.build(tenant=tenant, score_qualificacao=8)
    lead._skip_crm_signal = True
    lead._skip_automacao = True
    lead.save()

    op = OportunidadeVenda.all_tenants.create(
        tenant=tenant, pipeline=pipeline, lead=lead, estagio=e_novo,
        titulo='Oportunidade Teste', responsavel=user,
    )

    return {
        'tenant': tenant, 'user': user, 'pipeline': pipeline,
        'e_novo': e_novo, 'e_qualif': e_qualif, 'e_ganho': e_ganho, 'e_perdido': e_perdido,
        'lead': lead, 'op': op,
    }


@pytest.fixture
def logged_client(client, crm_setup):
    client.force_login(crm_setup['user'])
    return client


# ── Pipeline ──────────────────────────────────────────────────────────────

class TestPipelineViews:
    def test_pipeline_page_loads(self, logged_client):
        resp = logged_client.get(reverse('crm:pipeline'))
        assert resp.status_code == 200

    def test_pipeline_view(self, logged_client):
        resp = logged_client.get(reverse('crm:pipeline_view'))
        assert resp.status_code == 200

    def test_api_pipeline_dados(self, logged_client, crm_setup):
        resp = logged_client.get(reverse('crm:api_pipeline_dados'), {'pipeline_id': crm_setup['pipeline'].pk})
        assert resp.status_code == 200
        data = resp.json()
        assert 'estagios' in data

    def test_api_mover_oportunidade(self, logged_client, crm_setup):
        resp = logged_client.post(
            reverse('crm:api_mover_oportunidade'),
            json.dumps({'oportunidade_id': crm_setup['op'].pk, 'estagio_id': crm_setup['e_qualif'].pk}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        crm_setup['op'].refresh_from_db()
        assert crm_setup['op'].estagio == crm_setup['e_qualif']


# ── Oportunidades ─────────────────────────────────────────────────────────

class TestOportunidadeViews:
    def test_lista(self, logged_client):
        resp = logged_client.get(reverse('crm:oportunidades_lista'))
        assert resp.status_code == 200

    def test_detalhe(self, logged_client, crm_setup):
        resp = logged_client.get(reverse('crm:oportunidade_detalhe', args=[crm_setup['op'].pk]))
        assert resp.status_code == 200
        assert b'Oportunidade Teste' in resp.content

    def test_api_notas(self, logged_client, crm_setup):
        NotaInterna.all_tenants.create(
            tenant=crm_setup['tenant'], oportunidade=crm_setup['op'],
            lead=crm_setup['lead'], autor=crm_setup['user'],
            conteudo='Nota teste', tipo='geral',
        )
        resp = logged_client.get(reverse('crm:api_notas_oportunidade', args=[crm_setup['op'].pk]))
        assert resp.status_code == 200


# ── Tarefas ───────────────────────────────────────────────────────────────

class TestTarefaViews:
    def test_lista(self, logged_client, crm_setup):
        TarefaCRM.all_tenants.create(
            tenant=crm_setup['tenant'], titulo='Tarefa Teste',
            responsavel=crm_setup['user'], lead=crm_setup['lead'],
        )
        resp = logged_client.get(reverse('crm:tarefas_lista'))
        assert resp.status_code == 200
        assert b'Tarefa Teste' in resp.content

    def test_concluir(self, logged_client, crm_setup):
        tarefa = TarefaCRM.all_tenants.create(
            tenant=crm_setup['tenant'], titulo='Concluir',
            responsavel=crm_setup['user'], status='pendente',
        )
        resp = logged_client.post(reverse('crm:api_tarefa_concluir', args=[tarefa.pk]))
        assert resp.status_code == 200
        tarefa.refresh_from_db()
        assert tarefa.status == 'concluida'


# ── Equipes ───────────────────────────────────────────────────────────────

class TestEquipeViews:
    def test_page_loads(self, logged_client):
        resp = logged_client.get(reverse('crm:equipes'))
        assert resp.status_code == 200


# ── Metas ─────────────────────────────────────────────────────────────────

class TestMetaViews:
    def test_page_loads(self, logged_client):
        resp = logged_client.get(reverse('crm:metas'))
        assert resp.status_code == 200


# ── Desempenho ────────────────────────────────────────────────────────────

class TestDesempenhoViews:
    def test_page_loads(self, logged_client):
        resp = logged_client.get(reverse('crm:desempenho'))
        assert resp.status_code == 200

    def test_api_dados(self, logged_client):
        resp = logged_client.get(reverse('crm:api_desempenho_dados'))
        assert resp.status_code == 200


# ── Configurações ─────────────────────────────────────────────────────────

class TestConfiguracoesCRMViews:
    def test_page_loads(self, logged_client, crm_setup):
        # A view redireciona se não encontra pipeline_atual, o que é válido
        resp = logged_client.get(reverse('crm:configuracoes'))
        assert resp.status_code in [200, 302]

    def test_criar_estagio_get_not_allowed(self, logged_client):
        resp = logged_client.get(reverse('crm:api_criar_estagio'))
        assert resp.status_code == 405  # Method Not Allowed

    def test_reordenar_get_not_allowed(self, logged_client):
        resp = logged_client.get(reverse('crm:api_reordenar_estagios'))
        assert resp.status_code == 405


# ── Segmentos ─────────────────────────────────────────────────────────────

class TestSegmentoViews:
    def test_lista(self, logged_client):
        resp = logged_client.get(reverse('crm:segmentos_lista'))
        assert resp.status_code == 200


# ── Auth ──────────────────────────────────────────────────────────────────

class TestCRMAuthRequired:
    @pytest.mark.parametrize('url_name', [
        'crm:pipeline', 'crm:oportunidades_lista', 'crm:tarefas_lista',
        'crm:equipes', 'crm:metas', 'crm:configuracoes', 'crm:desempenho',
        'crm:segmentos_lista',
    ])
    def test_redirect_without_login(self, client, url_name, db):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
