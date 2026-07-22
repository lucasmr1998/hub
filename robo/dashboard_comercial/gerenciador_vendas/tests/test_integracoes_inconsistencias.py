"""Pagina de inconsistencias Hubtrix x HubSoft (tarefa 221).

Lista as vendas que existem no HubSoft e nunca viraram lead aqui, agrupadas por
origem. O que importa nos testes: o agrupamento por origem separa falha nossa de
canal descoberto, e a tela nunca deixa "lista vazia" passar por "esta tudo certo"
quando o espelho esta parado.
"""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.integracoes.models import ClienteHubsoft
from apps.integracoes.services import inconsistencias as svc
from apps.sistema.middleware import set_current_tenant
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory,
)


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    seq = {'n': 1000}

    def cliente(origem='', com_lead=False, dias_atras=1, nome='Fulano'):
        seq['n'] += 1
        lead = None
        if com_lead:
            lead = LeadProspectoFactory.build(tenant=tenant)
            lead._skip_crm_signal = True
            lead._skip_automacao = True
            lead.save()
        c = ClienteHubsoft.all_tenants.create(
            tenant=tenant, lead=lead, id_cliente=seq['n'], codigo_cliente=seq['n'],
            nome_razaosocial=nome, cpf_cnpj='52998224725', origem_cliente=origem,
        )
        quando = timezone.now() - timedelta(days=dias_atras)
        ClienteHubsoft.all_tenants.filter(pk=c.pk).update(
            data_cadastro_hubsoft=quando, data_sync=timezone.now())
        return c

    return {'tenant': tenant, 'user': user, 'cliente': cliente}


class TestVendasSemCard:
    def test_lista_so_cliente_sem_lead(self, cenario):
        c = cenario
        c['cliente'](origem='INDICAÇÃO', com_lead=False)
        c['cliente'](origem='INDICAÇÃO', com_lead=True)   # tem lead: nao entra

        grupos = svc.vendas_sem_card(c['tenant'])
        assert len(grupos) == 1
        assert grupos[0].quantidade == 1

    def test_agrupa_por_origem(self, cenario):
        c = cenario
        for _ in range(3):
            c['cliente'](origem='WHATSAPP ATIVO')
        c['cliente'](origem='PRESENCIAL LOJA')

        grupos = {g.origem: g.quantidade for g in svc.vendas_sem_card(c['tenant'])}
        assert grupos == {'WHATSAPP ATIVO': 3, 'PRESENCIAL LOJA': 1}

    def test_origem_vazia_ganha_rotulo_proprio(self, cenario):
        """Origem em branco foi 22%% dos casos reais. Nao pode virar string vazia
        na tela nem sumir do agrupamento."""
        cenario['cliente'](origem='')
        grupos = svc.vendas_sem_card(cenario['tenant'])
        assert grupos[0].origem == svc.ORIGEM_VAZIA

    def test_canal_integrado_e_marcado_como_anomalia(self, cenario):
        """"WhatsApp Empresa (Matrix)" alimenta o Hubtrix: venda que entra por
        ali e nao vira lead e falha nossa, nao canal descoberto."""
        c = cenario
        c['cliente'](origem='WHATSAPP EMPRESA (MATRIX)')
        c['cliente'](origem='PRESENCIAL LOJA')

        por_origem = {g.origem: g.anomalia for g in svc.vendas_sem_card(c['tenant'])}
        assert por_origem['WHATSAPP EMPRESA (MATRIX)'] is True
        assert por_origem['PRESENCIAL LOJA'] is False

    def test_anomalia_vem_primeiro(self, cenario):
        """Ordem importa: o que exige acao nossa nao pode ficar embaixo de uma
        lista longa de canal descoberto."""
        c = cenario
        for _ in range(5):
            c['cliente'](origem='PRESENCIAL LOJA')
        c['cliente'](origem='WHATSAPP EMPRESA (MATRIX)')

        assert svc.vendas_sem_card(c['tenant'])[0].anomalia is True

    def test_respeita_o_periodo(self, cenario):
        c = cenario
        c['cliente'](origem='INDICAÇÃO', dias_atras=1)
        c['cliente'](origem='INDICAÇÃO', dias_atras=400)

        hoje = timezone.localdate()
        grupos = svc.vendas_sem_card(c['tenant'], inicio=hoje - timedelta(days=7), fim=hoje)
        assert sum(g.quantidade for g in grupos) == 1

    def test_isola_por_tenant(self, cenario, db):
        c = cenario
        outro = TenantFactory(plano_comercial='pro', modulo_comercial=True)
        ClienteHubsoft.all_tenants.create(
            tenant=outro, id_cliente=99991, codigo_cliente=99991,
            nome_razaosocial='De outro tenant', origem_cliente='INDICAÇÃO')
        c['cliente'](origem='INDICAÇÃO')

        assert sum(g.quantidade for g in svc.vendas_sem_card(c['tenant'])) == 1


class TestEstadoDoEspelho:
    def test_marca_desatualizado_sem_nenhuma_sync(self, cenario):
        info = svc.estado_do_espelho(cenario['tenant'])
        assert info['ultima_sync'] is None
        assert info['desatualizado'] is True

    def test_conta_quantos_estao_sem_lead(self, cenario):
        c = cenario
        c['cliente'](com_lead=False)
        c['cliente'](com_lead=False)
        c['cliente'](com_lead=True)

        info = svc.estado_do_espelho(c['tenant'])
        assert info['total'] == 3 and info['sem_lead'] == 2

    def test_sync_recente_nao_e_desatualizado(self, cenario):
        cenario['cliente']()
        assert svc.estado_do_espelho(cenario['tenant'])['desatualizado'] is False


class TestPagina:
    @pytest.fixture
    def logado(self, client, cenario):
        client.force_login(cenario['user'])
        return client

    def test_abre(self, logado, cenario):
        resp = logado.get(reverse('integracoes:inconsistencias'))
        assert resp.status_code == 200

    def test_mostra_o_estado_do_espelho_junto_da_lista(self, logado, cenario):
        """Regressao de comportamento: lista vazia com espelho parado nao pode
        parecer 'esta tudo certo'."""
        html = logado.get(reverse('integracoes:inconsistencias')).content.decode()
        assert 'espelho' in html.lower()
        assert 'Buscar no HubSoft' in html

    def test_lista_as_vendas_agrupadas(self, logado, cenario):
        cenario['cliente'](origem='WHATSAPP ATIVO', nome='Cliente Sem Card')
        html = logado.get(reverse('integracoes:inconsistencias')).content.decode()
        assert 'WHATSAPP ATIVO' in html
        assert 'Cliente Sem Card' in html

    def test_exige_login(self, client, cenario):
        resp = client.get(reverse('integracoes:inconsistencias'))
        assert resp.status_code in (302, 403)


class TestAtualizarEspelho:
    def test_sem_integracao_devolve_erro_sem_explodir(self, cenario):
        r = svc.atualizar_espelho(cenario['tenant'])
        assert r['ok'] is False
        assert 'integracao' in r['erro'].lower()
