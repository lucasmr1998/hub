"""Fundação das rotinas de escrita HubSoft (Fase 1):
guard de dry run por tenant, mapa de vencimento, varredura de prospectos e
helpers do cliente do painel. Nada aqui toca rede nem abre navegador.
"""
import pytest

from apps.integracoes.models import PerfilConversaoHubsoft, IntegracaoAPI
from apps.integracoes.services.hubsoft_painel import (
    _derivar_api_base, _jwt_exp, HubsoftPainelService, HubsoftPainelError,
)
from apps.automacao.varreduras import _prospectos_por_criterio
from apps.comercial.leads.models import LeadProspecto


def _perfil(tenant, **kw):
    base = dict(nome='padrao', dry_run_forcado=True, cpf_allowlist=[], vencimentos_map={})
    base.update(kw)
    return PerfilConversaoHubsoft.all_tenants.create(tenant=tenant, **base)


class TestDryRunEfetivo:
    def test_pedido_sempre_dry_run(self, db, tenant_a):
        p = _perfil(tenant_a, dry_run_forcado=False)
        assert p.dry_run_efetivo(True, '11144477735') is True

    def test_forcado_so_allowlist_executa(self, db, tenant_a):
        p = _perfil(tenant_a, dry_run_forcado=True, cpf_allowlist=['111.444.777-35'])
        # CPF na allowlist (compara so digitos) executa de verdade
        assert p.dry_run_efetivo(False, '11144477735') is False
        # CPF fora da allowlist vira dry run
        assert p.dry_run_efetivo(False, '99999999999') is True

    def test_nao_forcado_executa(self, db, tenant_a):
        p = _perfil(tenant_a, dry_run_forcado=False)
        assert p.dry_run_efetivo(False, '99999999999') is False


class TestIdVencimento:
    def test_mapa_traduz_dia(self, db, tenant_a):
        p = _perfil(tenant_a, vencimentos_map={'10': 4, '5': 9})
        assert p.id_vencimento(10) == 4
        assert p.id_vencimento('10') == 4
        assert p.id_vencimento(5) == 9

    def test_dia_nao_mapeado_none(self, db, tenant_a):
        p = _perfil(tenant_a, vencimentos_map={'10': 4})
        assert p.id_vencimento(99) is None
        assert p.id_vencimento(None) is None


class TestVarreduraProspectos:
    def _lead(self, tenant, tel, **kw):
        return LeadProspecto.all_tenants.create(
            tenant=tenant, nome_razaosocial=f'Lead {tel}', telefone=tel, **kw)

    def test_filtra_por_vendedor(self, db, tenant_a):
        self._lead(tenant_a, '5511900000001', id_vendedor_rp=125)
        self._lead(tenant_a, '5511900000002', id_vendedor_rp=999)
        r = _prospectos_por_criterio(tenant_a, {'vendedor_id': '125'})
        assert [x['lead'].telefone for x in r] == ['5511900000001']

    def test_filtra_por_status_e_com_id_hubsoft(self, db, tenant_a):
        self._lead(tenant_a, '5511900000003', status_api='pendente', id_hubsoft='500')
        self._lead(tenant_a, '5511900000004', status_api='pendente', id_hubsoft='')
        self._lead(tenant_a, '5511900000005', status_api='lead_novo', id_hubsoft='501')
        r = _prospectos_por_criterio(tenant_a, {'status_api': 'pendente', 'com_id_hubsoft': 'true'})
        assert [x['lead'].telefone for x in r] == ['5511900000003']

    def test_sem_marcador_exclui(self, db, tenant_a):
        self._lead(tenant_a, '5511900000006', dados_custom={'_conversao_iniciada': '2026'})
        self._lead(tenant_a, '5511900000007', dados_custom={})
        r = _prospectos_por_criterio(tenant_a, {'sem_marcador': '_conversao_iniciada'})
        assert [x['lead'].telefone for x in r] == ['5511900000007']

    def test_isolamento_tenant(self, db, tenant_a, tenant_b):
        self._lead(tenant_a, '5511900000008', id_vendedor_rp=1)
        self._lead(tenant_b, '5511900000009', id_vendedor_rp=1)
        r = _prospectos_por_criterio(tenant_a, {'vendedor_id': '1'})
        assert [x['lead'].telefone for x in r] == ['5511900000008']


class TestClientePainelHelpers:
    def test_derivar_api_base(self):
        assert _derivar_api_base('https://artelecom.hubsoft.com.br') == 'https://api.artelecom.hubsoft.com.br'
        assert _derivar_api_base('https://api.artelecom.hubsoft.com.br/') == 'https://api.artelecom.hubsoft.com.br'

    def test_jwt_exp(self):
        import base64, json
        payload = base64.urlsafe_b64encode(json.dumps({'exp': 1893456000}).encode()).decode().rstrip('=')
        token = f'aaa.{payload}.bbb'
        assert _jwt_exp(token) == 1893456000
        assert _jwt_exp('token-invalido') is None

    def test_service_recusa_tipo_errado(self, db, tenant_a):
        integ = IntegracaoAPI.all_tenants.create(
            tenant=tenant_a, tipo='hubsoft', nome='API oficial',
            client_id='', client_secret='', username='', password='')
        with pytest.raises(HubsoftPainelError):
            HubsoftPainelService(integ)


# Template minimo mas representativo do payload de conversao capturado no painel.
# Valores 'ORIG' marcam o que a rotina DEVE sobrepor; o resto o overlay preserva.
_TEMPLATE_CONVERSAO = {
    'tipo_pessoa': 'pf',
    'data_nascimento': 'ORIG',
    'cpf_cnpj': 'ORIG', 'nome_razaosocial': 'ORIG', 'nome_fantasia': 'ORIG',
    'telefone_primario': 'ORIG', 'telefone_secundario': 'ORIG',
    'email_principal': 'ORIG', 'rg': 'ORIG', 'id_prospecto': 0,
    'nacionalidade': 'BRASILEIRO', 'valor': 99.9,
    'cliente_endereco_numeros': [
        {'tipo': 'cadastral', 'cep': 'ORIG', 'endereco': 'ORIG', 'numero': 'ORIG'},
        {'tipo': 'cobranca', 'cep': 'ORIG', 'endereco': 'ORIG', 'numero': 'ORIG'},
    ],
    'cliente_servico_endereco_instalacao': {'tipo': 'ORIG', 'cep': 'ORIG', 'endereco': 'ORIG'},
    'cliente_servico': {
        'servico': {'id_servico': 100, 'valor': 99.9, 'display': 'Plano do Template'},
        'valor': 99.9,
        'vencimento': {'id_vencimento': 1, 'dia_vencimento': '1'},
        'grupos': [{'id': 1, 'descricao': 'Grupo do Template'}],
        'vendedor': {'id': 111, 'name': 'Vendedor do Template', 'email': 'v@erp'},
        'id_usuario_vendedor': 111,
        'data_venda': 'ORIG',
    },
}

_ENDERECO = {
    'cep': '64000000', 'endereco': 'Rua das Flores', 'numero': '10',
    'bairro': 'Centro', 'cidade': {'id_cidade': 5, 'nome': 'Teresina'},
}


class TestMontarPayloadConversao:
    def _svc(self, tenant, **perfil_kw):
        from apps.integracoes.services.hubsoft_painel import HubsoftPainelService
        integ = IntegracaoAPI.all_tenants.create(
            tenant=tenant, tipo='hubsoft_painel', nome='Painel',
            base_url='https://artelecom.hubsoft.com.br',
            client_id='operador', client_secret='senha', username='', password='')
        base = dict(nome='padrao', template_conversao=_TEMPLATE_CONVERSAO,
                    vendedor_id_conversao=1613,
                    grupo_servico_obj={'id': 29, 'descricao': 'Varejo'},
                    vencimentos_map={'10': 4})
        base.update(perfil_kw)
        perfil = PerfilConversaoHubsoft.all_tenants.create(tenant=tenant, **base)
        return HubsoftPainelService(integ, perfil)

    def _lead(self, **kw):
        from types import SimpleNamespace
        base = dict(cpf_cnpj='111.444.777-35', nome_razaosocial='Fulano de Tal',
                    telefone='(86) 99999-0001', email='fulano@ex.com', rg='1234567',
                    id_hubsoft='777', data_nascimento='15/05/1990',
                    tipo_pessoa='fisica', id_dia_vencimento=10)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_overlay_identidade_e_endereco(self, db, tenant_a):
        from datetime import datetime
        svc = self._svc(tenant_a)
        p = svc.montar_payload_conversao(
            self._lead(), _ENDERECO, agora=datetime(2026, 7, 24, 12, 0, 0))
        assert p['cpf_cnpj'] == '11144477735'
        assert p['nome_razaosocial'] == 'Fulano de Tal'
        assert p['nome_fantasia'] == 'Fulano de Tal'
        assert p['telefone_primario'] == '86999990001'
        assert p['email_principal'] == 'fulano@ex.com'
        assert p['id_prospecto'] == 777
        assert p['tipo_pessoa'] == 'pf'
        assert p['data_nascimento'] == '1990-05-15'
        # os 2 enderecos recebem o resolvido mas mantem o tipo
        assert [e['tipo'] for e in p['cliente_endereco_numeros']] == ['cadastral', 'cobranca']
        assert all(e['cep'] == '64000000' for e in p['cliente_endereco_numeros'])
        assert p['cliente_servico_endereco_instalacao']['cep'] == '64000000'
        assert p['cliente_servico_endereco_instalacao']['tipo'] == 'cadastral'

    def test_vencimento_grupo_vendedor_e_data(self, db, tenant_a):
        from datetime import datetime
        svc = self._svc(tenant_a)
        cs = svc.montar_payload_conversao(
            self._lead(), _ENDERECO, agora=datetime(2026, 7, 24, 12, 0, 0))['cliente_servico']
        assert cs['vencimento']['id_vencimento'] == 4
        assert cs['id_vencimento'] == 4
        assert cs['grupos'] == [{'id': 29, 'descricao': 'Varejo'}]
        # vendedor: id do perfil, resto do objeto preservado do template
        assert cs['vendedor']['id'] == 1613
        assert cs['vendedor']['name'] == 'Vendedor do Template'
        assert cs['id_usuario_vendedor'] == 1613
        assert cs['data_venda'].startswith('2026-07-24') and cs['data_venda'].endswith('Z')

    def test_nao_troca_servico_sem_override(self, db, tenant_a):
        svc = self._svc(tenant_a)
        p = svc.montar_payload_conversao(self._lead(), _ENDERECO)
        assert p['cliente_servico']['servico']['id_servico'] == 100

    def test_override_de_servico(self, db, tenant_a):
        svc = self._svc(tenant_a)
        novo = {'id_servico': 250, 'valor': 129.9, 'display': 'Plano 500MB'}
        p = svc.montar_payload_conversao(self._lead(), _ENDERECO, servico_obj=novo)
        assert p['cliente_servico']['servico']['id_servico'] == 250
        assert p['cliente_servico']['valor'] == 129.9
        assert p['valor'] == 129.9

    def test_pj_zera_campos_pf(self, db, tenant_a):
        svc = self._svc(tenant_a)
        lead = self._lead(cpf_cnpj='12.345.678/0001-99', tipo_pessoa='juridica')
        p = svc.montar_payload_conversao(lead, _ENDERECO)
        assert p['tipo_pessoa'] == 'pj'
        assert p['data_nascimento'] is None
        assert p['cpf_cnpj'] == '12345678000199'
        assert p['nacionalidade'] is None

    def test_menor_de_18_vira_default(self, db, tenant_a):
        from datetime import datetime
        svc = self._svc(tenant_a)
        lead = self._lead(data_nascimento='15/05/2015')
        p = svc.montar_payload_conversao(
            lead, _ENDERECO, agora=datetime(2026, 7, 24, 12, 0, 0))
        assert p['data_nascimento'] == '1930-01-01'

    def test_template_ausente_levanta(self, db, tenant_a):
        svc = self._svc(tenant_a, template_conversao={})
        with pytest.raises(HubsoftPainelError):
            svc.montar_payload_conversao(self._lead(), _ENDERECO)

    def test_nao_muta_o_template_do_perfil(self, db, tenant_a):
        svc = self._svc(tenant_a)
        svc.montar_payload_conversao(self._lead(), _ENDERECO)
        # o template do perfil segue intacto (deepcopy no montar)
        assert svc.perfil.template_conversao['cpf_cnpj'] == 'ORIG'
        assert svc.perfil.template_conversao['cliente_servico']['vendedor']['id'] == 111
