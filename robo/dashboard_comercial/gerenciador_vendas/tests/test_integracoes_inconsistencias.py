"""Inconsistencias entre as vendas do HubSoft e o nosso funil (tarefa 221).

O que importa nos testes:
  - o cruzamento tenta CPF e depois telefone, e diz por qual casou
  - venda com lead mas sem oportunidade ganha e RECUPERAVEL, nao "fora"
  - transferencia de titularidade nao conta como venda perdida
  - canal integrado que escapa e marcado como anomalia e vem primeiro
"""
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.integracoes.services import inconsistencias as svc
from apps.sistema.middleware import set_current_tenant
from apps.comercial.crm.models import Pipeline, PipelineEstagio, OportunidadeVenda
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory,
)


def venda(cpf='', tel='', origem='INDICAÇÃO', nome='Fulano', cod=1):
    return svc.Venda(
        codigo_cliente=cod, nome=nome, cpf_cnpj=cpf, telefone=tel,
        origem=origem, plano='NUVYON 500MB', data_venda='01/07/2026',
        status_servico='Serviço Habilitado',
    )


@pytest.fixture
def cenario(db):
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

    def lead(cpf='', tel='', ganhou=False):
        l = LeadProspectoFactory.build(tenant=tenant, cpf_cnpj=cpf, telefone=tel)
        l._skip_crm_signal = True
        l._skip_automacao = True
        l.save()
        OportunidadeVenda.all_tenants.create(
            tenant=tenant, pipeline=pipeline, lead=l,
            estagio=e_ganho if ganhou else e_novo,
            titulo=f'Op {l.pk}', responsavel=user)
        return l

    return {'tenant': tenant, 'user': user, 'lead': lead}


class TestClassificacao:
    def test_casa_por_cpf(self, cenario):
        c = cenario
        l = c['lead'](cpf='52998224725', ganhou=True)
        r = svc._classificar(c['tenant'], [venda(cpf='52998224725')])

        assert len(r['com_venda']) == 1
        assert r['com_venda'][0].casou_por == 'cpf'
        assert r['com_venda'][0].lead_id == l.pk

    def test_cai_pro_telefone_quando_nao_ha_cpf(self, cenario):
        c = cenario
        c['lead'](cpf='', tel='19998887766', ganhou=True)
        r = svc._classificar(c['tenant'], [venda(cpf='', tel='19998887766')])

        assert len(r['com_venda']) == 1
        assert r['com_venda'][0].casou_por == 'telefone'

    def test_lead_sem_venda_ganha_e_RECUPERAVEL_nao_fora(self, cenario):
        """A distincao que importa: a venda existe dos dois lados, so nao foi
        marcada aqui. Contar isso como 'fora do funil' acusaria o time por algo
        que e um clique."""
        c = cenario
        c['lead'](cpf='52998224725', ganhou=False)
        r = svc._classificar(c['tenant'], [venda(cpf='52998224725')])

        assert len(r['so_lead']) == 1
        assert len(r['sem_nada']) == 0

    def test_sem_lead_nenhum_vai_pra_fora(self, cenario):
        r = svc._classificar(cenario['tenant'], [venda(cpf='11144477735')])
        assert len(r['sem_nada']) == 1
        assert r['sem_nada'][0].casou_por == ''

    def test_cpf_tem_prioridade_sobre_telefone(self, cenario):
        """Telefone compartilhado (casa, familia) nao pode vencer o documento."""
        c = cenario
        certo = c['lead'](cpf='52998224725', tel='19998887766', ganhou=True)
        c['lead'](cpf='11144477735', tel='19998887766', ganhou=True)

        r = svc._classificar(c['tenant'], [venda(cpf='52998224725', tel='19998887766')])
        assert r['com_venda'][0].lead_id == certo.pk


class TestAgrupamento:
    def test_canal_integrado_e_anomalia(self):
        assert svc.GrupoOrigem(origem='WHATSAPP EMPRESA (MATRIX)').anomalia is True
        assert svc.GrupoOrigem(origem='WHATSAPP ATIVO').anomalia is False
        assert svc.GrupoOrigem(origem='PRESENCIAL LOJA').anomalia is False

    def test_titularidade_nao_e_venda(self):
        assert svc.GrupoOrigem(origem='TRANSFERENCIA DE TITULARIDADE').nao_e_venda is True
        assert svc.GrupoOrigem(origem='INDICAÇÃO').nao_e_venda is False

    def test_ordem_anomalia_primeiro_titularidade_ultimo(self):
        """Ordem carrega significado: o que exige acao nossa no topo, o que nem e
        venda no fim."""
        vs = ([venda(origem='PRESENCIAL LOJA', cpf=str(i)) for i in range(5)]
              + [venda(origem='TRANSFERENCIA DE TITULARIDADE', cpf='90')]
              + [venda(origem='WHATSAPP EMPRESA (MATRIX)', cpf='91')])
        ordem = [g.origem for g in svc._agrupar_por_origem(vs)]

        assert ordem[0] == 'WHATSAPP EMPRESA (MATRIX)'
        assert ordem[-1] == 'TRANSFERENCIA DE TITULARIDADE'

    def test_agrupa_e_conta(self):
        vs = [venda(origem='WHATSAPP ATIVO', cpf=str(i)) for i in range(3)]
        vs += [venda(origem='INDICAÇÃO', cpf='99')]
        assert {g.origem: g.quantidade for g in svc._agrupar_por_origem(vs)} == {
            'WHATSAPP ATIVO': 3, 'INDICAÇÃO': 1}


class TestEtiquetaPorLinha:
    """A tabela e plana, entao a etiqueta que antes vinha do cabecalho do grupo
    tem que resolver por venda. Se divergir do grupo, a tela passa a contradizer
    o proprio chip de filtro."""

    @pytest.mark.parametrize('origem,esperado', [
        ('WHATSAPP EMPRESA (MATRIX)', 'falha nossa'),
        ('MATRIX', 'falha nossa'),
        ('TRANSFERENCIA DE TITULARIDADE', 'nao e venda'),
        ('INDICAÇÃO', 'canal fora do funil'),
        ('WHATSAPP ATIVO', 'canal fora do funil'),
        (svc.ORIGEM_VAZIA, 'canal fora do funil'),
    ])
    def test_tipo_label(self, origem, esperado):
        assert venda(origem=origem).tipo_label == esperado

    def test_venda_concorda_com_o_grupo(self):
        for origem in ['WHATSAPP EMPRESA (MATRIX)', 'TRANSFERENCIA DE TITULARIDADE',
                       'INDICAÇÃO', 'WHATSAPP ATIVO', svc.ORIGEM_VAZIA]:
            v, g = venda(origem=origem), svc.GrupoOrigem(origem=origem)
            assert v.anomalia is g.anomalia, origem
            assert v.nao_e_venda is g.nao_e_venda, origem


class TestMontarPagina:
    def _com_vendas(self, vendas):
        return patch.object(svc, '_buscar_vendas_hubsoft', return_value=vendas)

    def test_separa_titularidade_da_venda_real(self, cenario):
        vs = [venda(origem='TRANSFERENCIA DE TITULARIDADE', cpf=str(i)) for i in range(3)]
        vs += [venda(origem='WHATSAPP ATIVO', cpf=str(10 + i)) for i in range(4)]

        with self._com_vendas(vs):
            d = svc.montar_pagina(cenario['tenant'], forcar=True)

        assert d['total_sem_nada'] == 7
        assert d['titularidade'] == 3
        assert d['venda_real_fora'] == 4

    def test_conta_os_quatro_grupos(self, cenario):
        c = cenario
        c['lead'](cpf='52998224725', ganhou=True)
        c['lead'](cpf='11144477735', ganhou=False)
        c['lead'](cpf='', tel='19991112233', ganhou=False)
        vs = [venda(cpf='52998224725'), venda(cpf='11144477735'),
              venda(cpf='', tel='19991112233'), venda(cpf='99988877766')]

        with self._com_vendas(vs):
            d = svc.montar_pagina(c['tenant'], forcar=True)

        assert d['total'] == 4
        assert d['com_venda'] == 1
        assert d['so_lead_cpf'] == 1
        assert d['so_lead_tel'] == 1
        assert d['total_sem_nada'] == 1

    def test_usa_cache_e_forcar_ignora(self, cenario):
        with patch.object(svc, '_buscar_vendas_hubsoft',
                          return_value=[venda(cpf='1')]) as m:
            svc.montar_pagina(cenario['tenant'], forcar=True)
            svc.montar_pagina(cenario['tenant'])          # deve vir do cache
            assert m.call_count == 1
            svc.montar_pagina(cenario['tenant'], forcar=True)
            assert m.call_count == 2


class TestPagina:
    @pytest.fixture
    def logado(self, client, cenario):
        client.force_login(cenario['user'])
        return client

    def test_abre(self, logado, cenario):
        with patch.object(svc, '_buscar_vendas_hubsoft', return_value=[]):
            resp = logado.get(reverse('integracoes:inconsistencias'))
        assert resp.status_code == 200

    def test_mostra_os_grupos_e_o_aviso_de_titularidade(self, logado, cenario):
        vs = [venda(origem='WHATSAPP ATIVO', cpf='1', nome='Cliente Fora'),
              venda(origem='TRANSFERENCIA DE TITULARIDADE', cpf='2')]
        with patch.object(svc, '_buscar_vendas_hubsoft', return_value=vs):
            html = logado.get(reverse('integracoes:inconsistencias'),
                              {'atualizar': '1'}).content.decode()

        assert 'WHATSAPP ATIVO' in html
        assert 'Cliente Fora' in html
        assert 'titularidade' in html.lower()

    def test_exige_login(self, client, cenario):
        resp = client.get(reverse('integracoes:inconsistencias'))
        assert resp.status_code in (302, 403)
