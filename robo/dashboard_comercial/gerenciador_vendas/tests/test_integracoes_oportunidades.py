"""Aba Oportunidades: matriz funil x funil contra o export de CRM (tarefa 221).

O que importa nos testes:
  - a etapa do HubSoft vira ganho/aberto/perdido pelo mesmo criterio da sessao
  - o cruzamento e id_prospecto (card) x id_hubsoft (nosso lead)
  - card que nao casa mas cuja pessoa existe aqui com OUTRO id = duplicado
  - a celula "eles aberto / nos perdido" e a divergencia destacada
  - o parser tolera header repetido e coluna faltando, e pula linha sem id
"""
import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.integracoes.services import oportunidades as svc
from apps.integracoes.models import ImportacaoCRMHubsoft
from apps.sistema.middleware import set_current_tenant
from apps.comercial.crm.models import Pipeline, PipelineEstagio, OportunidadeVenda
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory,
)


class TestSituacaoDeles:
    @pytest.mark.parametrize('etapa,esperado', [
        ('CADASTRO APROVADO', 'ganho'),
        ('ASSUNTOS COMERCIAIS', 'aberto'),
        ('LOJA VIRTUAL NUVYON', 'aberto'),
        ('CAPTAÇÃO DE CLIENTE', 'aberto'),
        ('ANALISE DE VIABILIDADE', 'aberto'),
        ('DESISTENCIA/OUTROS MOTIVOS', 'perdido'),
        ('DESISTENCIA/SEM RETORNO', 'perdido'),
        ('CREDITO NEGADO', 'perdido'),
        ('VIABILIDADE NEGATIVA', 'perdido'),
        ('', 'aberto'),
    ])
    def test_mapa(self, etapa, esperado):
        assert svc.situacao_deles(etapa) == esperado

    def test_ignora_caixa_e_espaco(self):
        assert svc.situacao_deles('  cadastro aprovado  ') == 'ganho'


class TestNormId:
    @pytest.mark.parametrize('entrada,esperado', [
        ('24291', '24291'),
        ('24291.0', '24291'),
        (' 24291 ', '24291'),
        (24291, '24291'),
        (24291.0, '24291'),
        ('', ''),
        (None, ''),
    ])
    def test_norm(self, entrada, esperado):
        assert svc._norm_id(entrada) == esperado


def _xlsx(headers, linhas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for l in linhas:
        ws.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestParsePlanilha:
    def test_parseia_e_normaliza(self):
        buf = _xlsx(
            # header duplicado de proposito (a planilha real tem), e sem coluna `tag`
            ['id_prospecto', 'crm_etapa', 'nome_cartao', 'prospecto_cpf_cnpj',
             'prospecto_telefone', 'data_cadastro_prospecto', 'data_cadastro_prospecto'],
            [
                [24291, 'CADASTRO APROVADO', 'EDER', '111.222.333-44', '(35) 99267-1522', 'x', 'y'],
                ['', 'ASSUNTOS COMERCIAIS', 'SEM ID', '', '', '', ''],  # sem id: pulada
            ])
        cards = svc.parse_planilha(buf)
        assert len(cards) == 1
        c = cards[0]
        assert c['id_prospecto'] == '24291'
        assert c['situacao'] == 'ganho'
        assert c['cpf'] == '11122233344'
        assert c['telefone'] == '35992671522'
        assert c['tag'] == ''          # coluna ausente vira vazio, sem quebrar

    def test_planilha_vazia(self):
        assert svc.parse_planilha(_xlsx(['id_prospecto'], [])) == []


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    pipeline = Pipeline.all_tenants.create(
        tenant=tenant, nome='Vendas', slug='vendas', tipo='vendas', padrao=True)
    est = {
        'aberto': PipelineEstagio.all_tenants.create(
            tenant=tenant, pipeline=pipeline, nome='Novo', slug='novo', tipo='novo', ordem=1),
        'ganho': PipelineEstagio.all_tenants.create(
            tenant=tenant, pipeline=pipeline, nome='Ganho', slug='ganho', tipo='cliente',
            ordem=2, is_final_ganho=True),
        'perdido': PipelineEstagio.all_tenants.create(
            tenant=tenant, pipeline=pipeline, nome='Perdido', slug='perdido', tipo='perdido',
            ordem=3, is_final_perdido=True),
    }

    def lead(id_hubsoft='', cpf='', tel='', situacao='aberto'):
        l = LeadProspectoFactory.build(
            tenant=tenant, cpf_cnpj=cpf, telefone=tel, id_hubsoft=id_hubsoft)
        l._skip_crm_signal = True
        l._skip_automacao = True
        l.save()
        OportunidadeVenda.all_tenants.create(
            tenant=tenant, pipeline=pipeline, lead=l, estagio=est[situacao],
            titulo=f'Op {l.pk}', responsavel=user)
        return l

    def importar(cards):
        return ImportacaoCRMHubsoft.all_tenants.create(
            tenant=tenant, nome_arquivo='crm.xlsx', total=len(cards), cards=cards)

    return {'tenant': tenant, 'user': user, 'lead': lead, 'importar': importar}


def card(idp, etapa, cpf='', tel='', nome='Fulano'):
    return {
        'id_prospecto': str(idp), 'crm': 'CRM - VENDAS', 'crm_etapa': etapa,
        'situacao': svc.situacao_deles(etapa), 'status_prospecto': 'Pré-Cadastro',
        'nome_cartao': nome, 'nome_prospecto': nome, 'cpf': cpf, 'telefone': tel,
        'tag': 'WHATSAPP EMPRESA', 'usuario': 'Katia', 'data_cadastro_cartao': '18/07/2026',
    }


class TestMontarAba:
    def test_sem_import(self, cenario):
        assert svc.montar_aba(cenario['tenant']) == {'tem_import': False}

    def test_casado_duplicado_e_so_deles(self, cenario):
        # A: casa por id_prospecto (id_hubsoft do lead == card) -> so conta cobertura
        cenario['lead'](id_hubsoft='100', cpf='11111111111', tel='11988887777')
        # B: casa tambem -> cobertura
        cenario['lead'](id_hubsoft='200', cpf='22222222222', tel='11988886666')
        # C: pessoa existe com id_hubsoft 301, mas o card dela e 300 -> duplicado
        cenario['lead'](id_hubsoft='301', cpf='33333333333', tel='11988885555')

        cenario['importar']([
            card('100', 'CADASTRO APROVADO', cpf='11111111111'),
            card('200', 'ASSUNTOS COMERCIAIS', cpf='22222222222'),
            card('300', 'ASSUNTOS COMERCIAIS', cpf='33333333333'),   # duplicado de C
            card('999', 'CAPTAÇÃO DE CLIENTE', tel='11900000000'),   # so deles
        ])

        d = svc.montar_aba(cenario['tenant'])
        assert d['tem_import'] is True
        assert d['total'] == 4
        assert d['casados'] == 2                    # 100 e 200
        assert d['total_duplicados'] == 1           # o card 300
        assert d['total_so_deles'] == 1             # o card 999
        assert d['so_nossos'] == 1                  # o lead C (301) nao esta na planilha
        # matriz/divergencia sairam: a comparacao de situacao morreu
        assert 'matriz' not in d
        assert 'concordancia_pct' not in d
        # lista unificada: 1 duplicado + 1 so deles = 2 (os casados nao entram)
        assert d['total_problemas'] == 2
        cats = {p['categoria'] for p in d['problemas']}
        assert cats == {'Duplicado', 'Só existe lá'}

    def test_casa_por_telefone_quando_sem_cpf(self, cenario):
        cenario['lead'](id_hubsoft='500', cpf='', tel='11977776666', situacao='ganho')
        cenario['importar']([card('501', 'CADASTRO APROVADO', tel='11977776666')])
        d = svc.montar_aba(cenario['tenant'])
        # 501 != 500 por id, mas a pessoa existe por telefone com outro id_hubsoft
        assert d['total_duplicados'] == 1
        assert d['total_so_deles'] == 0

    def test_id_zero_vira_bucket_e_nao_infla_a_matriz(self, cenario):
        cenario['lead'](id_hubsoft='100', cpf='11111111111', situacao='ganho')
        cenario['importar']([
            card('100', 'CADASTRO APROVADO', cpf='11111111111'),
            card('0', 'ASSUNTOS COMERCIAIS', nome='MARCIA 5511'),   # sem prospecto
            card('0', 'ASSUNTOS COMERCIAIS', nome='SANDRA ??'),     # sem prospecto
        ])
        d = svc.montar_aba(cenario['tenant'])
        assert d['total_sem_prospecto'] == 2
        assert d['total'] == 1              # cobertura so sobre os com prospecto
        assert d['total_cards'] == 3        # o cru inclui os id=0
        assert d['casados'] == 1
        assert d['total_so_deles'] == 0     # os id=0 NAO caem aqui
        assert d['cobertura_pct'] == 100


class TestUploadEView:
    @pytest.fixture
    def logado(self, client, cenario):
        client.force_login(cenario['user'])
        return client

    def test_upload_cria_import(self, logado, cenario):
        buf = _xlsx(['id_prospecto', 'crm_etapa'],
                    [[24291, 'CADASTRO APROVADO'], [24292, 'ASSUNTOS COMERCIAIS']])
        arquivo = SimpleUploadedFile(
            'crm.xlsx', buf.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp = logado.post(reverse('integracoes:oportunidades_upload'), {'planilha': arquivo})
        assert resp.status_code == 302
        imp = ImportacaoCRMHubsoft.all_tenants.filter(tenant=cenario['tenant']).first()
        assert imp is not None
        assert imp.total == 2

    def test_upload_rejeita_nao_xlsx(self, logado, cenario):
        arquivo = SimpleUploadedFile('lista.csv', b'a,b,c', content_type='text/csv')
        logado.post(reverse('integracoes:oportunidades_upload'), {'planilha': arquivo})
        assert not ImportacaoCRMHubsoft.all_tenants.filter(tenant=cenario['tenant']).exists()

    def test_pagina_mostra_a_aba_oportunidades(self, logado, cenario):
        cenario['lead'](id_hubsoft='100', cpf='11111111111', situacao='ganho')
        cenario['importar']([card('100', 'CADASTRO APROVADO', cpf='11111111111')])
        cenario['importar']([card('301', 'ASSUNTOS COMERCIAIS', cpf='11111111111')])  # duplicado
        with patch_vendas():
            html = logado.get(reverse('integracoes:inconsistencias'),
                              {'tab': 'oportunidades'}).content.decode()
        assert 'aba-oportunidades' in html
        assert 'Inconsistências' in html
        assert 'Estão aqui' in html          # KPI de cobertura
        assert 'Matriz funil x funil' not in html   # a matriz saiu


def patch_vendas():
    """A aba Vendas chama a API do HubSoft; nos testes da aba Oportunidades ela
    nao interessa, entao devolve lista vazia."""
    from unittest.mock import patch
    from apps.integracoes.services import inconsistencias as inc
    return patch.object(inc, '_buscar_vendas_hubsoft', return_value=[])
