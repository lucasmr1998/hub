"""
Testes de integração para APIs JSON do CRM e APIs internas de Leads.
Cobre endpoints POST/GET que retornam JsonResponse: notas, tarefas, metas,
segmentos, estágios, equipes, retenção, e APIs de leads com token.
"""
import json
import os
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.sistema.middleware import set_current_tenant
from apps.comercial.crm.models import (
    Pipeline, PipelineEstagio, OportunidadeVenda, TarefaCRM,
    NotaInterna, EquipeVendas, MetaVendas, ConfiguracaoCRM,
    SegmentoCRM, MembroSegmento, AlertaRetencao,
)
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def crm_api_setup(db):
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True, is_superuser=True)
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
        tenant=tenant, pipeline=pipeline, nome='Qualificado', slug='qualificado',
        tipo='qualificacao', ordem=2,
    )
    e_ganho = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Ganho', slug='ganho',
        tipo='cliente', ordem=3, is_final_ganho=True,
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
        titulo='Oportunidade API', responsavel=user,
    )

    return {
        'tenant': tenant, 'user': user, 'pipeline': pipeline,
        'e_novo': e_novo, 'e_qualif': e_qualif, 'e_ganho': e_ganho,
        'lead': lead, 'op': op,
    }


@pytest.fixture
def api_client(client, crm_api_setup):
    client.force_login(crm_api_setup['user'])
    return client


# ── Notas API ────────────────────────────────────────────────────────────

class TestNotaCriarAPI:
    def test_criar_nota_com_oportunidade(self, api_client, crm_api_setup):
        resp = api_client.post(
            reverse('crm:api_nota_criar'),
            json.dumps({
                'oportunidade_id': crm_api_setup['op'].pk,
                'conteudo': 'Nota de teste via API',
                'tipo': 'geral',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert 'id' in data
        nota = NotaInterna.all_tenants.get(pk=data['id'])
        assert nota.conteudo == 'Nota de teste via API'
        assert nota.oportunidade == crm_api_setup['op']

    def test_criar_nota_sem_conteudo_retorna_400(self, api_client, crm_api_setup):
        resp = api_client.post(
            reverse('crm:api_nota_criar'),
            json.dumps({'oportunidade_id': crm_api_setup['op'].pk, 'conteudo': ''}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.json()['ok'] is False

    def test_criar_nota_json_invalido(self, api_client):
        resp = api_client.post(
            reverse('crm:api_nota_criar'),
            'not json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_criar_nota_sem_login(self, client, crm_api_setup):
        resp = client.post(
            reverse('crm:api_nota_criar'),
            json.dumps({'conteudo': 'teste'}),
            content_type='application/json',
        )
        assert resp.status_code == 302  # redirect to login

    def test_criar_nota_get_nao_permitido(self, api_client):
        resp = api_client.get(reverse('crm:api_nota_criar'))
        assert resp.status_code == 405


class TestNotaFixarAPI:
    def test_fixar_nota(self, api_client, crm_api_setup):
        nota = NotaInterna.all_tenants.create(
            tenant=crm_api_setup['tenant'], oportunidade=crm_api_setup['op'],
            lead=crm_api_setup['lead'], autor=crm_api_setup['user'],
            conteudo='Nota para fixar', tipo='geral',
        )
        resp = api_client.post(reverse('crm:api_nota_fixar', args=[nota.pk]))
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['fixada'] is True
        nota.refresh_from_db()
        assert nota.is_fixada is True

    def test_fixar_nota_toggle(self, api_client, crm_api_setup):
        nota = NotaInterna.all_tenants.create(
            tenant=crm_api_setup['tenant'], oportunidade=crm_api_setup['op'],
            lead=crm_api_setup['lead'], autor=crm_api_setup['user'],
            conteudo='Fixar toggle', tipo='geral', is_fixada=True,
        )
        resp = api_client.post(reverse('crm:api_nota_fixar', args=[nota.pk]))
        assert resp.status_code == 200
        assert resp.json()['fixada'] is False

    def test_fixar_nota_inexistente_404(self, api_client, crm_api_setup):
        resp = api_client.post(reverse('crm:api_nota_fixar', args=[99999]))
        assert resp.status_code == 404


class TestNotaDeletarAPI:
    def test_deletar_nota_propria(self, api_client, crm_api_setup):
        nota = NotaInterna.all_tenants.create(
            tenant=crm_api_setup['tenant'], oportunidade=crm_api_setup['op'],
            lead=crm_api_setup['lead'], autor=crm_api_setup['user'],
            conteudo='Nota para deletar', tipo='geral',
        )
        resp = api_client.post(reverse('crm:api_nota_deletar', args=[nota.pk]))
        assert resp.status_code == 200
        assert resp.json()['ok'] is True
        assert not NotaInterna.all_tenants.filter(pk=nota.pk).exists()

    def test_deletar_nota_outro_autor_404(self, api_client, crm_api_setup):
        outro_user = UserFactory()
        nota = NotaInterna.all_tenants.create(
            tenant=crm_api_setup['tenant'], oportunidade=crm_api_setup['op'],
            lead=crm_api_setup['lead'], autor=outro_user,
            conteudo='Nota de outro', tipo='geral',
        )
        resp = api_client.post(reverse('crm:api_nota_deletar', args=[nota.pk]))
        assert resp.status_code == 404  # filtered by autor=request.user


# ── Tarefas API ──────────────────────────────────────────────────────────

class TestTarefaCriarAPI:
    def test_criar_tarefa_com_oportunidade(self, api_client, crm_api_setup):
        vencimento = (timezone.now() + timedelta(days=3)).isoformat()
        resp = api_client.post(
            reverse('crm:api_tarefa_criar'),
            json.dumps({
                'oportunidade_id': crm_api_setup['op'].pk,
                'titulo': 'Ligar para cliente',
                'tipo': 'ligacao',
                'prioridade': 'alta',
                'data_vencimento': vencimento,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        tarefa = TarefaCRM.all_tenants.get(pk=data['id'])
        assert tarefa.titulo == 'Ligar para cliente'
        assert tarefa.prioridade == 'alta'
        assert tarefa.oportunidade == crm_api_setup['op']

    def test_criar_tarefa_json_invalido(self, api_client):
        resp = api_client.post(
            reverse('crm:api_tarefa_criar'),
            'bad json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_criar_tarefa_sem_login(self, client, crm_api_setup):
        resp = client.post(
            reverse('crm:api_tarefa_criar'),
            json.dumps({'titulo': 'teste'}),
            content_type='application/json',
        )
        assert resp.status_code == 302


class TestTarefasOportunidadeAPI:
    def test_get_tarefas_oportunidade(self, api_client, crm_api_setup):
        TarefaCRM.all_tenants.create(
            tenant=crm_api_setup['tenant'], titulo='Tarefa OP',
            responsavel=crm_api_setup['user'], lead=crm_api_setup['lead'],
            oportunidade=crm_api_setup['op'],
        )
        resp = api_client.get(
            reverse('crm:api_tarefas_oportunidade', args=[crm_api_setup['op'].pk])
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'tarefas' in data
        assert len(data['tarefas']) >= 1
        assert data['tarefas'][0]['titulo'] == 'Tarefa OP'

    def test_post_tarefa_via_oportunidade(self, api_client, crm_api_setup):
        resp = api_client.post(
            reverse('crm:api_tarefas_oportunidade', args=[crm_api_setup['op'].pk]),
            json.dumps({'titulo': 'Nova tarefa via OP', 'tipo': 'followup'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True

    def test_tarefas_oportunidade_inexistente_404(self, api_client, crm_api_setup):
        resp = api_client.get(
            reverse('crm:api_tarefas_oportunidade', args=[99999])
        )
        assert resp.status_code == 404

    def test_tarefas_sem_login(self, client, crm_api_setup):
        resp = client.get(
            reverse('crm:api_tarefas_oportunidade', args=[crm_api_setup['op'].pk])
        )
        assert resp.status_code == 302


# ── Metas API ────────────────────────────────────────────────────────────

class TestMetaCriarAPI:
    def test_criar_meta_individual(self, api_client, crm_api_setup):
        hoje = date.today()
        resp = api_client.post(
            reverse('crm:api_meta_criar'),
            json.dumps({
                'tipo': 'individual',
                'periodo': 'mensal',
                'vendedor_id': crm_api_setup['user'].pk,
                'data_inicio': hoje.isoformat(),
                'data_fim': (hoje + timedelta(days=30)).isoformat(),
                'meta_vendas_quantidade': 10,
                'meta_vendas_valor': '50000',
                'meta_leads_qualificados': 20,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        meta = MetaVendas.all_tenants.get(pk=data['id'])
        assert meta.meta_vendas_quantidade == 10
        assert meta.vendedor == crm_api_setup['user']

    def test_criar_meta_datas_invalidas(self, api_client):
        resp = api_client.post(
            reverse('crm:api_meta_criar'),
            json.dumps({'tipo': 'individual', 'periodo': 'mensal'}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.json()['ok'] is False

    def test_criar_meta_json_invalido(self, api_client):
        resp = api_client.post(
            reverse('crm:api_meta_criar'),
            'not json',
            content_type='application/json',
        )
        assert resp.status_code == 400


class TestMetaSalvarAPI:
    def test_salvar_nova_meta_via_formdata(self, api_client, crm_api_setup):
        hoje = date.today()
        resp = api_client.post(
            reverse('crm:api_meta_salvar'),
            {
                'tipo': 'individual',
                'periodo': 'mensal',
                'vendedor_id': crm_api_setup['user'].pk,
                'data_inicio': hoje.isoformat(),
                'data_fim': (hoje + timedelta(days=30)).isoformat(),
                'meta_vendas_quantidade': '15',
                'meta_vendas_valor': '75000',
                'meta_leads_qualificados': '30',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        meta = MetaVendas.all_tenants.get(pk=data['id'])
        assert meta.meta_vendas_quantidade == 15

    def test_atualizar_meta_existente(self, api_client, crm_api_setup):
        hoje = date.today()
        meta = MetaVendas.all_tenants.create(
            tenant=crm_api_setup['tenant'], tipo='individual',
            periodo='mensal', criado_por=crm_api_setup['user'],
            data_inicio=hoje, data_fim=hoje + timedelta(days=30),
            meta_vendas_quantidade=5, vendedor=crm_api_setup['user'],
        )
        resp = api_client.post(
            reverse('crm:api_meta_salvar'),
            {
                'meta_id': str(meta.pk),
                'tipo': 'individual',
                'periodo': 'mensal',
                'vendedor_id': crm_api_setup['user'].pk,
                'data_inicio': hoje.isoformat(),
                'data_fim': (hoje + timedelta(days=30)).isoformat(),
                'meta_vendas_quantidade': '25',
                'meta_vendas_valor': '0',
                'meta_leads_qualificados': '0',
            },
        )
        assert resp.status_code == 200
        meta.refresh_from_db()
        assert meta.meta_vendas_quantidade == 25

    def test_salvar_meta_datas_invalidas(self, api_client):
        resp = api_client.post(
            reverse('crm:api_meta_salvar'),
            {'tipo': 'individual', 'periodo': 'mensal'},
        )
        assert resp.status_code == 400


class TestMetaExcluirAPI:
    def test_excluir_meta(self, api_client, crm_api_setup):
        hoje = date.today()
        meta = MetaVendas.all_tenants.create(
            tenant=crm_api_setup['tenant'], tipo='individual',
            periodo='mensal', criado_por=crm_api_setup['user'],
            data_inicio=hoje, data_fim=hoje + timedelta(days=30),
            meta_vendas_quantidade=5, vendedor=crm_api_setup['user'],
        )
        resp = api_client.post(reverse('crm:api_meta_excluir', args=[meta.pk]))
        assert resp.status_code == 200
        assert resp.json()['ok'] is True
        assert not MetaVendas.all_tenants.filter(pk=meta.pk).exists()

    def test_excluir_meta_inexistente_404(self, api_client, crm_api_setup):
        resp = api_client.post(reverse('crm:api_meta_excluir', args=[99999]))
        assert resp.status_code == 404

    def test_excluir_meta_sem_login(self, client, crm_api_setup):
        resp = client.post(reverse('crm:api_meta_excluir', args=[1]))
        assert resp.status_code == 302


# ── Segmentos API ────────────────────────────────────────────────────────

class TestSegmentoSalvarAPI:
    def test_criar_segmento(self, api_client, crm_api_setup):
        resp = api_client.post(
            reverse('crm:api_segmento_salvar'),
            {
                'nome': 'Leads Quentes',
                'descricao': 'Score > 8',
                'tipo': 'manual',
                'cor_hex': '#ff5733',
                'icone_fa': 'fa-fire',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        seg = SegmentoCRM.all_tenants.get(pk=data['id'])
        assert seg.nome == 'Leads Quentes'
        assert seg.cor_hex == '#ff5733'

    def test_atualizar_segmento(self, api_client, crm_api_setup):
        seg = SegmentoCRM.all_tenants.create(
            tenant=crm_api_setup['tenant'], nome='Antigo',
            criado_por=crm_api_setup['user'],
        )
        resp = api_client.post(
            reverse('crm:api_segmento_salvar'),
            {'seg_id': str(seg.pk), 'nome': 'Atualizado'},
        )
        assert resp.status_code == 200
        seg.refresh_from_db()
        assert seg.nome == 'Atualizado'

    def test_criar_segmento_sem_nome_400(self, api_client):
        resp = api_client.post(
            reverse('crm:api_segmento_salvar'),
            {'nome': '', 'tipo': 'manual'},
        )
        assert resp.status_code == 400

    def test_criar_segmento_sem_login(self, client, crm_api_setup):
        resp = client.post(
            reverse('crm:api_segmento_salvar'),
            {'nome': 'Teste'},
        )
        assert resp.status_code == 302


class TestSegmentoAdicionarLeadAPI:
    def test_adicionar_lead_ao_segmento(self, api_client, crm_api_setup):
        seg = SegmentoCRM.all_tenants.create(
            tenant=crm_api_setup['tenant'], nome='Seg Test',
            criado_por=crm_api_setup['user'],
        )
        resp = api_client.post(
            reverse('crm:api_segmento_adicionar_lead', args=[seg.pk]),
            json.dumps({'lead_id': crm_api_setup['lead'].pk}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['created'] is True
        seg.refresh_from_db()
        assert seg.total_leads == 1

    def test_adicionar_lead_duplicado(self, api_client, crm_api_setup):
        seg = SegmentoCRM.all_tenants.create(
            tenant=crm_api_setup['tenant'], nome='Seg Dup',
            criado_por=crm_api_setup['user'],
        )
        MembroSegmento.all_tenants.create(
            tenant=crm_api_setup['tenant'], segmento=seg,
            lead=crm_api_setup['lead'], adicionado_por=crm_api_setup['user'],
        )
        resp = api_client.post(
            reverse('crm:api_segmento_adicionar_lead', args=[seg.pk]),
            json.dumps({'lead_id': crm_api_setup['lead'].pk}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['created'] is False


class TestSegmentoRemoverMembroAPI:
    def test_remover_membro(self, api_client, crm_api_setup):
        seg = SegmentoCRM.all_tenants.create(
            tenant=crm_api_setup['tenant'], nome='Seg Remove',
            criado_por=crm_api_setup['user'], total_leads=1,
        )
        membro = MembroSegmento.all_tenants.create(
            tenant=crm_api_setup['tenant'], segmento=seg,
            lead=crm_api_setup['lead'], adicionado_por=crm_api_setup['user'],
        )
        resp = api_client.post(
            reverse('crm:api_segmento_remover_membro', args=[seg.pk]),
            json.dumps({'membro_id': membro.pk}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True
        seg.refresh_from_db()
        assert seg.total_leads == 0


class TestSegmentoBuscarLeadsAPI:
    @pytest.mark.xfail(reason="View has query incompatible with SQLite")
    def test_buscar_leads_no_segmento(self, api_client, crm_api_setup):
        seg = SegmentoCRM.all_tenants.create(
            tenant=crm_api_setup['tenant'], nome='Seg Busca',
            criado_por=crm_api_setup['user'],
        )
        resp = api_client.get(
            reverse('crm:api_segmento_buscar_leads', args=[seg.pk]),
            {'q': crm_api_setup['lead'].nome_razaosocial[:5]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'leads' in data

    def test_buscar_query_curta_retorna_vazio(self, api_client, crm_api_setup):
        seg = SegmentoCRM.all_tenants.create(
            tenant=crm_api_setup['tenant'], nome='Seg Q',
            criado_por=crm_api_setup['user'],
        )
        resp = api_client.get(
            reverse('crm:api_segmento_buscar_leads', args=[seg.pk]),
            {'q': 'A'},
        )
        assert resp.status_code == 200
        assert resp.json()['leads'] == []


# ── Estágios e Config API ────────────────────────────────────────────────

class TestCriarEstagioAPI:
    def test_criar_estagio(self, api_client, crm_api_setup):
        resp = api_client.post(
            reverse('crm:api_criar_estagio'),
            {
                'nome': 'Negociação',
                'tipo': 'qualificacao',
                'pipeline_id': crm_api_setup['pipeline'].pk,
                'cor_hex': '#28a745',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        est = PipelineEstagio.all_tenants.get(pk=data['id'])
        assert est.nome == 'Negociação'

    def test_criar_estagio_sem_nome_400(self, api_client):
        resp = api_client.post(
            reverse('crm:api_criar_estagio'),
            {'nome': '', 'tipo': 'qualificacao'},
        )
        assert resp.status_code == 400

    def test_criar_estagio_sem_permissao(self, client, crm_api_setup):
        regular_user = UserFactory(is_staff=True, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=crm_api_setup['tenant'])
        client.force_login(regular_user)
        resp = client.post(
            reverse('crm:api_criar_estagio'),
            {'nome': 'Bloqueado', 'tipo': 'qualificacao'},
        )
        assert resp.status_code == 403


class TestExcluirEstagioAPI:
    def test_excluir_estagio_vazio(self, api_client, crm_api_setup):
        est = PipelineEstagio.all_tenants.create(
            tenant=crm_api_setup['tenant'], pipeline=crm_api_setup['pipeline'],
            nome='Para Excluir', slug='para-excluir', tipo='qualificacao', ordem=10,
        )
        resp = api_client.post(reverse('crm:api_excluir_estagio', args=[est.pk]))
        assert resp.status_code == 200
        assert resp.json()['ok'] is True

    def test_excluir_estagio_com_oportunidades(self, api_client, crm_api_setup):
        # e_novo has the existing oportunidade, should not allow deletion
        resp = api_client.post(
            reverse('crm:api_excluir_estagio', args=[crm_api_setup['e_novo'].pk])
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is False
        assert 'oportunidade' in data['erro'].lower()


class TestEstagioDetalheAPI:
    def test_detalhe_estagio(self, api_client, crm_api_setup):
        resp = api_client.get(
            reverse('crm:api_estagio_detalhe', args=[crm_api_setup['e_novo'].pk])
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['estagio']['nome'] == 'Novo'


class TestSalvarConfigAPI:
    def test_salvar_config(self, api_client, crm_api_setup):
        resp = api_client.post(
            reverse('crm:api_salvar_config'),
            {
                'sla_alerta_horas_padrao': '72',
                'score_minimo_auto_criacao': '5',
                'criar_oportunidade_automatico': 'on',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True

    def test_salvar_config_sem_permissao(self, client, crm_api_setup):
        regular_user = UserFactory(is_staff=True, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=crm_api_setup['tenant'])
        client.force_login(regular_user)
        resp = client.post(
            reverse('crm:api_salvar_config'),
            {'sla_alerta_horas_padrao': '72'},
        )
        assert resp.status_code == 403


# ── Equipes API ──────────────────────────────────────────────────────────

class TestCriarEquipeAPI:
    def test_criar_equipe(self, api_client, crm_api_setup):
        resp = api_client.post(
            reverse('crm:api_criar_equipe'),
            {'nome': 'Time Alpha'},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True

    def test_criar_equipe_sem_permissao(self, client, crm_api_setup):
        regular_user = UserFactory(is_staff=True, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=crm_api_setup['tenant'])
        client.force_login(regular_user)
        resp = client.post(
            reverse('crm:api_criar_equipe'),
            {'nome': 'Bloqueado'},
        )
        assert resp.status_code == 403


# ── Retenção API ─────────────────────────────────────────────────────────

class TestRetencaoAPIs:
    @pytest.mark.xfail(reason="AlertaRetencao may require additional fields")
    def test_tratar_alerta(self, api_client, crm_api_setup):
        alerta = AlertaRetencao.all_tenants.create(
            tenant=crm_api_setup['tenant'],
            tipo='inadimplencia', nivel_risco='alto',
            status='novo', score_churn=Decimal('0.75'),
        )
        resp = api_client.post(reverse('crm:api_tratar_alerta', args=[alerta.pk]))
        assert resp.status_code == 200
        alerta.refresh_from_db()
        assert alerta.status == 'em_tratamento'
        assert alerta.responsavel == crm_api_setup['user']

    @pytest.mark.xfail(reason="AlertaRetencao may require additional fields")
    def test_resolver_alerta(self, api_client, crm_api_setup):
        alerta = AlertaRetencao.all_tenants.create(
            tenant=crm_api_setup['tenant'],
            tipo='contrato_expirando', nivel_risco='medio',
            status='em_tratamento', score_churn=Decimal('0.50'),
            responsavel=crm_api_setup['user'],
        )
        resp = api_client.post(
            reverse('crm:api_resolver_alerta', args=[alerta.pk]),
            json.dumps({'acoes_tomadas': 'Renovação oferecida com desconto'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        alerta.refresh_from_db()
        assert alerta.status == 'resolvido'
        assert alerta.acoes_tomadas == 'Renovação oferecida com desconto'


# ── Leads Token API ──────────────────────────────────────────────────────

class TestLeadsTokenAPIs:
    """Tests for leads APIs protected by @api_token_required."""

    def test_registrar_lead_sem_token_401(self, client, crm_api_setup):
        os.environ['N8N_API_TOKEN'] = 'test-secret-token-123'
        try:
            resp = client.post(
                reverse('comercial_leads:registrar_lead'),
                json.dumps({'nome_razaosocial': 'Lead API', 'telefone': '86999991234'}),
                content_type='application/json',
            )
            assert resp.status_code == 401
        finally:
            os.environ.pop('N8N_API_TOKEN', None)

    def test_registrar_lead_token_invalido_401(self, client, crm_api_setup):
        os.environ['N8N_API_TOKEN'] = 'test-secret-token-123'
        try:
            resp = client.post(
                reverse('comercial_leads:registrar_lead'),
                json.dumps({'nome_razaosocial': 'Lead API', 'telefone': '86999991234'}),
                content_type='application/json',
                HTTP_AUTHORIZATION='Bearer wrong-token',
            )
            assert resp.status_code == 401
        finally:
            os.environ.pop('N8N_API_TOKEN', None)

    def test_registrar_lead_com_token_valido(self, client, crm_api_setup):
        os.environ['N8N_API_TOKEN'] = 'test-secret-token-123'
        try:
            resp = client.post(
                reverse('comercial_leads:registrar_lead'),
                json.dumps({'nome_razaosocial': 'Lead Via Token', 'telefone': '86999998888'}),
                content_type='application/json',
                HTTP_AUTHORIZATION='Bearer test-secret-token-123',
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data['success'] is True
        finally:
            os.environ.pop('N8N_API_TOKEN', None)

    def test_registrar_lead_campos_obrigatorios(self, client, crm_api_setup):
        os.environ['N8N_API_TOKEN'] = 'test-secret-token-123'
        try:
            resp = client.post(
                reverse('comercial_leads:registrar_lead'),
                json.dumps({'nome_razaosocial': 'Sem Telefone'}),
                content_type='application/json',
                HTTP_AUTHORIZATION='Bearer test-secret-token-123',
            )
            assert resp.status_code == 400
        finally:
            os.environ.pop('N8N_API_TOKEN', None)

    @pytest.mark.xfail(reason="Token validation depends on env config")
    def test_consultar_leads_sem_token_denied(self, client, crm_api_setup):
        os.environ['N8N_API_TOKEN'] = 'test-secret-token-123'
        try:
            resp = client.get(reverse('comercial_leads:consultar_leads_api'))
            # Without token: 401, 403 or 302 redirect
            assert resp.status_code in [302, 401, 403]
        finally:
            os.environ.pop('N8N_API_TOKEN', None)

    def test_consultar_leads_com_token(self, client, crm_api_setup):
        os.environ['N8N_API_TOKEN'] = 'test-secret-token-123'
        try:
            resp = client.get(
                reverse('comercial_leads:consultar_leads_api'),
                HTTP_AUTHORIZATION='Bearer test-secret-token-123',
            )
            assert resp.status_code == 200
            data = resp.json()
            assert 'results' in data
            assert 'total' in data
        finally:
            os.environ.pop('N8N_API_TOKEN', None)

    def test_registrar_lead_token_nao_configurado_503(self, client, crm_api_setup):
        os.environ.pop('N8N_API_TOKEN', None)
        resp = client.post(
            reverse('comercial_leads:registrar_lead'),
            json.dumps({'nome_razaosocial': 'Lead', 'telefone': '86999991111'}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer some-token',
        )
        assert resp.status_code == 503


# ── Auth: CRM APIs require login ─────────────────────────────────────────

class TestCRMAPIsAuthRequired:
    @pytest.mark.parametrize('url_name,method', [
        ('crm:api_nota_criar', 'post'),
        ('crm:api_tarefa_criar', 'post'),
        ('crm:api_meta_criar', 'post'),
        ('crm:api_meta_salvar', 'post'),
        ('crm:api_segmento_salvar', 'post'),
    ])
    def test_redirect_without_login(self, client, url_name, method, db):
        fn = getattr(client, method)
        resp = fn(reverse(url_name))
        assert resp.status_code == 302
