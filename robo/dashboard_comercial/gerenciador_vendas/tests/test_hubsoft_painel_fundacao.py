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
