"""Nó `hubsoft_converter_prospecto` (Fase 2b): controle de fluxo e idempotencia.

Sem rede nem navegador — o service do painel e stubado (buscar_cep canned), entao o
teste exercita o montar_payload_conversao REAL + as 3 camadas de guarda:
idempotencia local (status_api / espelho), guard de dry run e o pre-check de CPF.
"""
import pytest

from apps.integracoes.models import IntegracaoAPI, PerfilConversaoHubsoft, ClienteHubsoft
from apps.integracoes.services.hubsoft_painel import HubsoftPainelService
from apps.automacao.nodes.base import tipo_por_slug
from apps.automacao.nodes.context import Contexto
from apps.comercial.leads.models import LeadProspecto


_TEMPLATE = {
    'tipo_pessoa': 'pf', 'data_nascimento': 'ORIG',
    'cpf_cnpj': 'ORIG', 'nome_razaosocial': 'ORIG', 'nome_fantasia': 'ORIG',
    'telefone_primario': 'ORIG', 'telefone_secundario': 'ORIG',
    'email_principal': 'ORIG', 'rg': 'ORIG', 'id_prospecto': 0,
    'cliente_endereco_numeros': [{'tipo': 'cadastral', 'cep': 'ORIG'}],
    'cliente_servico_endereco_instalacao': {'tipo': 'ORIG', 'cep': 'ORIG'},
    'cliente_servico': {
        'servico': {'id_servico': 100, 'valor': 99.9},
        'valor': 99.9, 'vencimento': {'id_vencimento': 1},
        'vendedor': {'id': 111, 'name': 'Template'}, 'id_usuario_vendedor': 111,
    },
}

NO = tipo_por_slug('hubsoft_converter_prospecto')


def _perfil(tenant, **kw):
    base = dict(nome='padrao', template_conversao=_TEMPLATE, vendedor_id_conversao=1613,
                grupo_servico_obj={'id': 29, 'descricao': 'Varejo'}, vencimentos_map={'10': 4},
                dry_run_forcado=True, cpf_allowlist=[])
    base.update(kw)
    return PerfilConversaoHubsoft.all_tenants.create(tenant=tenant, **base)


def _lead(tenant, **kw):
    base = dict(nome_razaosocial='Fulano de Tal', telefone='86999990001',
                cpf_cnpj='111.444.777-35', email='f@ex.com', rg='123',
                id_hubsoft='777', cep='64000000', rua='Rua A', numero_residencia='10',
                bairro='Centro', id_dia_vencimento=10)
    base.update(kw)
    return LeadProspecto.all_tenants.create(tenant=tenant, **base)


def _stub_svc(tenant, perfil, monkeypatch):
    integ = IntegracaoAPI.all_tenants.create(
        tenant=tenant, tipo='hubsoft_painel', nome='Painel',
        base_url='https://x.hubsoft.com.br', client_id='op', client_secret='pw',
        username='', password='')
    svc = HubsoftPainelService(integ, perfil)
    svc.buscar_cep = lambda cep: {'cep': {
        'cidade_completo': {'id_cidade': 5, 'nome': 'Teresina', 'estado': {'sigla': 'PI'}},
        'pais': {'id_pais': 1, 'nome': 'Brasil'}}}
    monkeypatch.setattr(
        'apps.integracoes.services.hubsoft_painel.hubsoft_painel_do_tenant',
        lambda *a, **k: svc)
    return svc


def _ctx(tenant, lead):
    return Contexto(tenant=tenant, lead=lead)


class TestGuardasBasicas:
    def test_sem_lead_erro(self, db, tenant_a):
        r = NO.executar({'perfil': 'padrao'}, {}, Contexto(tenant=tenant_a))
        assert r.branch == 'erro' and 'lead' in r.erro.lower()

    def test_lead_sem_id_hubsoft_erro(self, db, tenant_a):
        _perfil(tenant_a)
        lead = _lead(tenant_a, id_hubsoft='')
        r = NO.executar({'perfil': 'padrao'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'erro' and 'id_hubsoft' in r.erro

    def test_perfil_inexistente_erro(self, db, tenant_a):
        lead = _lead(tenant_a)
        r = NO.executar({'perfil': 'nao_existe'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'erro' and 'perfil' in r.erro.lower()


class TestIdempotencia:
    def test_status_api_convertido_no_op(self, db, tenant_a):
        _perfil(tenant_a)
        lead = _lead(tenant_a, status_api='convertido_cliente')
        r = NO.executar({'perfil': 'padrao'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'sucesso'
        assert r.output['ja_convertido'] and r.output['motivo'] == 'status_api'

    def test_espelho_cliente_no_op(self, db, tenant_a):
        _perfil(tenant_a)
        lead = _lead(tenant_a)
        ClienteHubsoft.all_tenants.create(
            tenant=tenant_a, lead=lead, id_cliente=999888,
            nome_razaosocial='Fulano', cpf_cnpj='11144477735')
        r = NO.executar({'perfil': 'padrao'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'sucesso' and r.output['motivo'] == 'espelho_cliente_hubsoft'


class TestDryRun:
    def test_dry_run_monta_payload_sem_escrever(self, db, tenant_a, monkeypatch):
        perfil = _perfil(tenant_a)
        lead = _lead(tenant_a)
        svc = _stub_svc(tenant_a, perfil, monkeypatch)
        # criar_cliente NAO pode ser chamado no dry run
        svc.criar_cliente = lambda *a, **k: (_ for _ in ()).throw(AssertionError('POST no dry run!'))

        r = NO.executar({'perfil': 'padrao', 'dry_run': True}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'dry_run'
        assert r.output['dry_run'] is True
        p = r.output['payload']
        assert p['id_prospecto'] == 777
        assert p['cpf_cnpj'] == '11144477735'
        assert p['cliente_servico']['id_vencimento'] == 4
        # endereco enriquecido com a cidade do buscar_cep
        assert p['cliente_endereco_numeros'][0]['cidade']['nome'] == 'Teresina'
        # CPF mascarado no resumo (LGPD)
        assert r.output['resumo']['cpf'].endswith('735') and '*' in r.output['resumo']['cpf']

    def test_allowlist_libera_escrita_real(self, db, tenant_a, monkeypatch):
        perfil = _perfil(tenant_a, cpf_allowlist=['111.444.777-35'])
        lead = _lead(tenant_a)
        svc = _stub_svc(tenant_a, perfil, monkeypatch)
        chamado = {}
        svc.cpf_ja_cadastrado = lambda cpf, **k: False
        svc.criar_cliente = lambda payload, **k: (
            chamado.update(payload=payload),
            {'status': 'success', 'cliente': {'id_cliente': 4242}})[1]

        r = NO.executar({'perfil': 'padrao', 'dry_run': False}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'sucesso'
        assert r.output['dry_run'] is False
        assert r.output['resumo']['id_cliente_novo'] == 4242
        assert chamado['payload']['id_prospecto'] == 777

    def test_cpf_ja_cadastrado_no_painel_no_op(self, db, tenant_a, monkeypatch):
        perfil = _perfil(tenant_a, cpf_allowlist=['111.444.777-35'])
        lead = _lead(tenant_a)
        svc = _stub_svc(tenant_a, perfil, monkeypatch)
        svc.cpf_ja_cadastrado = lambda cpf, **k: True
        svc.criar_cliente = lambda *a, **k: (_ for _ in ()).throw(AssertionError('nao deveria criar'))

        r = NO.executar({'perfil': 'padrao', 'dry_run': False}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'sucesso' and r.output['motivo'] == 'cpf_ja_cadastrado'
