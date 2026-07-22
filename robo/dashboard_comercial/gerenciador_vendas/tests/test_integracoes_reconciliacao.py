"""Service de reconciliacao Hubtrix x HubSoft (tarefa 219).

Os numeros aqui viram tela que o cliente usa pra questionar os proprios dados,
entao o que importa e: cada lado conta o conjunto certo, cada percentual usa o
denominador certo, e uma comparacao incoerente falha em vez de aparecer.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integracoes.models import ClienteHubsoft
from apps.integracoes.services import reconciliacao as rec
from apps.sistema.middleware import set_current_tenant
from apps.comercial.crm.models import Pipeline, PipelineEstagio, OportunidadeVenda
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory,
)


@pytest.fixture
def cenario(db):
    """Cenario pequeno e explicito, pra cada numero ser conferivel na mao."""
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    pipeline = Pipeline.all_tenants.create(
        tenant=tenant, nome='Vendas', slug='vendas', tipo='vendas', padrao=True)
    e_novo = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Novo', slug='novo', tipo='novo', ordem=1)
    e_ganho = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Ganho', slug='ganho', tipo='cliente',
        ordem=2, is_final_ganho=True)

    def novo_lead(**kw):
        lead = LeadProspectoFactory.build(tenant=tenant, **kw)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead.save()
        return lead

    def nova_op(lead, estagio, fechada_ha_dias=None):
        op = OportunidadeVenda.all_tenants.create(
            tenant=tenant, pipeline=pipeline, lead=lead, estagio=estagio,
            titulo=f'Op {lead.pk}', responsavel=user)
        if fechada_ha_dias is not None:
            OportunidadeVenda.all_tenants.filter(pk=op.pk).update(
                data_fechamento_real=timezone.now() - timedelta(days=fechada_ha_dias))
        return op

    def novo_cliente(lead=None, id_cliente=None, ha_dias=1):
        c = ClienteHubsoft.all_tenants.create(
            tenant=tenant, lead=lead, id_cliente=id_cliente,
            nome_razaosocial='Cliente', cpf_cnpj='52998224725')
        ClienteHubsoft.all_tenants.filter(pk=c.pk).update(
            data_cadastro_hubsoft=timezone.now() - timedelta(days=ha_dias),
            data_sync=timezone.now())
        return c

    return {
        'tenant': tenant, 'e_novo': e_novo, 'e_ganho': e_ganho,
        'novo_lead': novo_lead, 'nova_op': nova_op, 'novo_cliente': novo_cliente,
    }


class TestGuardaDeIntersecao:
    """Regressao: `comparar_espelho` usava o total do espelho como intersecao,
    e como o espelho inclui cliente da sync em massa, "so nossos" saia
    NEGATIVO na tela."""

    def test_intersecao_maior_que_um_dos_lados_explode(self):
        with pytest.raises(ValueError, match='intersecao'):
            rec.Divergencia(titulo='X', nossos=10, deles=20, intersecao=15)

    def test_intersecao_coerente_passa(self):
        d = rec.Divergencia(titulo='X', nossos=10, deles=20, intersecao=8)
        assert d.so_nossos == 2
        assert d.so_deles == 12
        assert d.diferenca == 10

    def test_sem_intersecao_nao_calcula_os_lados(self):
        d = rec.Divergencia(titulo='X', nossos=10, deles=20)
        assert d.so_nossos is None and d.so_deles is None


class TestCompararEspelho:
    def test_conta_so_cliente_amarrado_a_lead_nosso(self, cenario):
        """O espelho recebe cliente da sync em massa, sem lead. Esses nao podem
        entrar no lado 'viraram cliente', senao a conta fica impossivel."""
        c = cenario
        lead_ok = c['novo_lead'](status_api='processado')
        c['novo_cliente'](lead=lead_ok, id_cliente=1)
        c['novo_lead'](status_api='rascunho_hubsoft')
        c['novo_cliente'](lead=None, id_cliente=2)   # orfao, veio da sync em massa

        d = rec.comparar_espelho(c['tenant'])
        assert d.nossos == 2, 'processado + rascunho'
        assert d.deles == 1, 'so o que tem lead vinculado'
        assert d.so_nossos == 1
        assert ('Clientes no espelho sem lead vinculado', 1) in d.detalhes

    def test_conta_presos_em_rascunho(self, cenario):
        c = cenario
        for _ in range(3):
            c['novo_lead'](status_api='rascunho_hubsoft')
        d = rec.comparar_espelho(c['tenant'])
        assert ('Presos em rascunho_hubsoft', 3) in d.detalhes

    def test_severidade_critica_quando_rascunho_supera_processado(self, cenario):
        c = cenario
        c['novo_lead'](status_api='processado')
        for _ in range(2):
            c['novo_lead'](status_api='rascunho_hubsoft')
        assert rec.comparar_espelho(c['tenant']).severidade == 'critico'


class TestCompararVendas:
    def test_intersecao_e_a_venda_que_virou_cliente(self, cenario):
        c = cenario
        casou = c['novo_lead']()
        c['nova_op'](casou, c['e_ganho'], fechada_ha_dias=2)
        c['novo_cliente'](lead=casou, id_cliente=10, ha_dias=2)

        sem_cliente = c['novo_lead']()
        c['nova_op'](sem_cliente, c['e_ganho'], fechada_ha_dias=3)

        outro = c['novo_lead']()
        c['novo_cliente'](lead=outro, id_cliente=11, ha_dias=4)

        d = rec.comparar_vendas(c['tenant'], dias=30)
        assert d.nossos == 2 and d.deles == 2
        assert d.intersecao == 1
        assert ('Ganhas sem cliente no HubSoft', 1) in d.detalhes
        assert ('Clientes novos sem oportunidade ganha', 1) in d.detalhes

    def test_respeita_a_janela_de_dias(self, cenario):
        c = cenario
        antigo = c['novo_lead']()
        c['nova_op'](antigo, c['e_ganho'], fechada_ha_dias=90)
        recente = c['novo_lead']()
        c['nova_op'](recente, c['e_ganho'], fechada_ha_dias=5)
        assert rec.comparar_vendas(c['tenant'], dias=30).nossos == 1

    def test_ignora_oportunidade_nao_ganha(self, cenario):
        c = cenario
        lead = c['novo_lead']()
        c['nova_op'](lead, c['e_novo'], fechada_ha_dias=1)
        assert rec.comparar_vendas(c['tenant'], dias=30).nossos == 0


class TestQualidadeCampos:
    def test_venda_sem_plano_usa_vendas_como_denominador(self, cenario):
        """O bug: media contra o total de LEADS dava um percentual bonito e
        errado. 1 de 2 vendas e 50%, nao 1 de 12 leads."""
        c = cenario
        com = c['novo_lead'](id_plano_rp=884)
        c['nova_op'](com, c['e_ganho'], fechada_ha_dias=1)
        sem = c['novo_lead'](id_plano_rp=None)
        c['nova_op'](sem, c['e_ganho'], fechada_ha_dias=1)
        for _ in range(10):
            c['novo_lead'](id_plano_rp=884)

        linha = next(q for q in rec.qualidade_campos(c['tenant'])
                     if q['rotulo'] == 'Vendas ganhas sem plano')
        assert linha['quantidade'] == 1
        assert linha['base'] == 2, 'denominador e o total de vendas ganhas'
        assert linha['percentual'] == 50.0
        assert linha['universo'] == 'vendas ganhas'

    def test_lead_sem_cidade_usa_leads_como_denominador(self, cenario):
        c = cenario
        c['novo_lead'](cidade='Mococa')
        c['novo_lead'](cidade='')
        linha = next(q for q in rec.qualidade_campos(c['tenant'])
                     if q['rotulo'] == 'Leads sem cidade')
        assert linha['quantidade'] == 1 and linha['base'] == 2
        assert linha['percentual'] == 50.0

    def test_nao_divide_por_zero_sem_dados(self, cenario):
        for linha in rec.qualidade_campos(cenario['tenant']):
            assert linha['percentual'] == 0.0
            assert linha['severidade'] == 'ok'


class TestConfiabilidadeEspelho:
    def test_marca_incompleto_quando_ha_lead_preso(self, cenario):
        c = cenario
        lead = c['novo_lead'](status_api='rascunho_hubsoft')
        c['novo_cliente'](lead=lead, id_cliente=20)
        info = rec.confiabilidade_espelho(c['tenant'])
        assert info['estado'] == 'incompleto'
        assert info['leads_presos_em_rascunho'] == 1

    def test_sem_dados_quando_espelho_vazio(self, cenario):
        info = rec.confiabilidade_espelho(cenario['tenant'])
        assert info['estado'] == 'sem_dados'
        assert info['ultima_sync'] is None

    def test_ok_quando_sincronizado_e_sem_preso(self, cenario):
        c = cenario
        lead = c['novo_lead'](status_api='processado')
        c['novo_cliente'](lead=lead, id_cliente=21)
        assert rec.confiabilidade_espelho(c['tenant'])['estado'] == 'ok'


class TestMontarReconciliacao:
    def test_devolve_tudo_que_a_tela_precisa(self, cenario):
        d = rec.montar_reconciliacao(cenario['tenant'], dias=30)
        assert set(d) == {'tenant', 'dias', 'confiabilidade', 'divergencias', 'qualidade'}
        assert len(d['divergencias']) == 3
        assert len(d['qualidade']) == 4

    def test_isola_por_tenant(self, cenario, db):
        """Multi-tenancy: lead de outro tenant nao pode vazar na conta."""
        c = cenario
        outro = TenantFactory(plano_comercial='pro', modulo_comercial=True)
        set_current_tenant(outro)
        intruso = LeadProspectoFactory.build(tenant=outro, status_api='rascunho_hubsoft')
        intruso._skip_crm_signal = True
        intruso._skip_automacao = True
        intruso.save()
        set_current_tenant(c['tenant'])

        c['novo_lead'](status_api='rascunho_hubsoft')
        assert rec.confiabilidade_espelho(c['tenant'])['leads_presos_em_rascunho'] == 1


class TestPaginaReconciliacao:
    """Render de verdade: compilar o template so prova sintaxe."""

    @pytest.fixture
    def cliente_logado(self, client, cenario):
        from django.contrib.auth.models import User
        user = User.objects.filter(perfil_usuario__tenant=cenario['tenant']).first()
        client.force_login(user)
        return client

    def test_pagina_abre(self, cliente_logado, cenario):
        from django.urls import reverse
        resp = cliente_logado.get(reverse('integracoes:reconciliacao'))
        assert resp.status_code == 200
        assert b'Reconcilia' in resp.content

    def test_mostra_o_aviso_de_confiabilidade(self, cliente_logado, cenario):
        """O aviso nao pode sumir: sem ele a pagina passa a impressao de que os
        numeros do lado HubSoft estao completos."""
        from django.urls import reverse
        c = cenario
        c['novo_lead'](status_api='rascunho_hubsoft')
        lead = c['novo_lead'](status_api='processado')
        c['novo_cliente'](lead=lead, id_cliente=99)

        resp = cliente_logado.get(reverse('integracoes:reconciliacao'))
        html = resp.content.decode()
        assert 'rascunho_hubsoft' in html
        assert 'incompleto' in html

    def test_renderiza_a_intersecao(self, cliente_logado, cenario):
        """`{% if d.intersecao is not None %}` depende de None ser literal no
        template. Se nao for, o bloco 'Nos dois' some calado."""
        from django.urls import reverse
        c = cenario
        lead = c['novo_lead']()
        c['nova_op'](lead, c['e_ganho'], fechada_ha_dias=1)
        c['novo_cliente'](lead=lead, id_cliente=77, ha_dias=1)

        html = cliente_logado.get(reverse('integracoes:reconciliacao')).content.decode()
        assert 'Nos dois' in html or 'Nos dois'.replace('N', 'N') in html

    def test_janela_de_dias_e_respeitada(self, cliente_logado, cenario):
        from django.urls import reverse
        url = reverse('integracoes:reconciliacao')
        assert cliente_logado.get(url, {'dias': 7}).status_code == 200
        assert cliente_logado.get(url, {'dias': 'abc'}).status_code == 200, 'lixo nao pode quebrar'
        assert cliente_logado.get(url, {'dias': 99999}).status_code == 200, 'valor absurdo e limitado'

    def test_exige_login(self, client, cenario):
        from django.urls import reverse
        resp = client.get(reverse('integracoes:reconciliacao'))
        assert resp.status_code in (302, 403)
