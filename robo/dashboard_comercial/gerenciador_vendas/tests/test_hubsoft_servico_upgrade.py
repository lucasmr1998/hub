"""Fases 3 e 4: novo serviço e upgrade via painel HubSoft.

Cobre o builder compartilhado montar_payload_adicionar_servico (golden: novo servico
vs migracao) e o fluxo dos nos hubsoft_adicionar_servico / hubsoft_migrar_plano
(idempotencia + dry run), com o service stubado (zero rede).
"""
import pytest

from apps.integracoes.models import (
    IntegracaoAPI, PerfilConversaoHubsoft, ClienteHubsoft, ServicoClienteHubsoft,
)
from apps.integracoes.services.hubsoft_painel import HubsoftPainelService
from apps.automacao.nodes.base import tipo_por_slug
from apps.automacao.nodes.context import Contexto
from apps.comercial.leads.models import LeadProspecto

NO_ADD = tipo_por_slug('hubsoft_adicionar_servico')
NO_MIG = tipo_por_slug('hubsoft_migrar_plano')

_FORMA = {'id_forma_cobranca': 140, 'descricao': 'BANCO ITAU', 'ativo': True}
_SERVICO = {'id_servico': 250, 'descricao': 'Plano 500MB', 'valor': 129.9, 'display': 'Plano 500MB'}
_CLIENTE_PAINEL = {'cliente': {'enderecos': [
    {'pivot': {'tipo': 'cadastral'}, 'id_endereco_numero': 55,
     'endereco_numero': {'id_endereco_numero': 55, 'endereco': 'Rua A'}}]}}


def _perfil(tenant, **kw):
    base = dict(nome='padrao', vendedor_id_novo_servico=1385,
                grupo_servico_obj={'id': 29, 'descricao': 'Varejo'},
                forma_cobranca_obj=_FORMA, forma_cobranca_id=140,
                status_servico_novo_id=6, status_servico_migrado_id=11,
                validade_meses=12, vencimentos_map={'10': 4},
                dry_run_forcado=True, cpf_allowlist=[])
    base.update(kw)
    return PerfilConversaoHubsoft.all_tenants.create(tenant=tenant, **base)


def _lead(tenant, **kw):
    base = dict(nome_razaosocial='Fulano', telefone='86999990001', cpf_cnpj='111.444.777-35',
                id_plano_rp='250', id_dia_vencimento=10)
    base.update(kw)
    return LeadProspecto.all_tenants.create(tenant=tenant, **base)


def _espelho(tenant, lead, id_cliente=9001):
    return ClienteHubsoft.all_tenants.create(
        tenant=tenant, lead=lead, id_cliente=id_cliente,
        nome_razaosocial='Fulano', cpf_cnpj='11144477735')


def _servico_espelho(tenant, cli, id_servico, id_cs=7001, cancelado=False):
    return ServicoClienteHubsoft.all_tenants.create(
        tenant=tenant, cliente=cli, id_cliente_servico=id_cs, id_servico=id_servico,
        nome=f'Plano {id_servico}',
        status_prefixo='servico_cancelado' if cancelado else 'servico_habilitado')


def _stub(tenant, perfil, monkeypatch, *, edit=None):
    integ = IntegracaoAPI.all_tenants.create(
        tenant=tenant, tipo='hubsoft_painel', nome='Painel',
        base_url='https://x.hubsoft.com.br', client_id='op', client_secret='pw',
        username='', password='')
    svc = HubsoftPainelService(integ, perfil)
    svc.buscar_plano_por_id = lambda i, **k: dict(_SERVICO, id_servico=int(i))
    svc.get_cliente = lambda i, **k: _CLIENTE_PAINEL
    svc.obter_servico_edit = lambda i, **k: (edit if edit is not None else {'id_vencimento': 9})
    monkeypatch.setattr(
        'apps.integracoes.services.hubsoft_painel.hubsoft_painel_do_tenant',
        lambda *a, **k: svc)
    return svc


def _ctx(tenant, lead):
    return Contexto(tenant=tenant, lead=lead)


# ---------------------------------------------------------------------------
# Golden do builder compartilhado
# ---------------------------------------------------------------------------
class TestBuilderServico:
    def _svc(self, tenant):
        integ = IntegracaoAPI.all_tenants.create(
            tenant=tenant, tipo='hubsoft_painel', nome='P', base_url='https://x.hubsoft.com.br',
            client_id='o', client_secret='s', username='', password='')
        return HubsoftPainelService(integ, _perfil(tenant))

    def test_novo_servico(self, db, tenant_a):
        from datetime import datetime
        svc = self._svc(tenant_a)
        p = svc.montar_payload_adicionar_servico(
            id_cliente=9001, endereco_item={'id_endereco_numero': 55, 'endereco_numero': {}},
            servico_obj=_SERVICO, forma_cobranca_obj=_FORMA, valor=129.9, id_vencimento=4,
            agora=datetime(2026, 7, 24, 12, 0, 0))
        assert p['id_cliente'] == 9001
        assert p['id_usuario_vendedor'] == 1385
        assert p['servico']['id_servico'] == 250
        assert p['forma_cobranca']['id_forma_cobranca'] == 140
        assert p['grupos'] == [{'id': 29, 'descricao': 'Varejo'}]
        assert p['servico_status']['id_servico_status'] == 6
        assert p['servico_status']['habilitado'] is False
        # endereco em 4 papeis
        assert [e['tipo'] for e in p['cliente_servico_endereco']] == \
            ['instalacao', 'cadastral', 'cobranca', 'fiscal']
        # novo servico NAO tem campos de migracao
        assert 'id_cliente_servico_antigo' not in p
        assert p['data_venda'].startswith('2026-07-24')

    def test_migracao_acrescenta_campos(self, db, tenant_a):
        svc = self._svc(tenant_a)
        p = svc.montar_payload_adicionar_servico(
            id_cliente=9001, endereco_item={'id_endereco_numero': 55, 'endereco_numero': {}},
            servico_obj=_SERVICO, forma_cobranca_obj=_FORMA, valor=129.9, id_vencimento=9,
            migracao={'id_cliente_servico_antigo': 7001})
        assert p['id_cliente_servico_antigo'] == 7001
        assert p['executar_migracao_imediata'] is True
        assert p['id_servico_status'] == 11
        assert p['servico_status']['id_servico_status'] == 11
        assert p['servico_status']['habilitado'] is True
        assert p['migrar_durante_troca_servico']['atendimentosOS'] is True


# ---------------------------------------------------------------------------
# Nó novo serviço
# ---------------------------------------------------------------------------
class TestNoAdicionarServico:
    def test_sem_espelho_erro(self, db, tenant_a):
        _perfil(tenant_a)
        lead = _lead(tenant_a)
        r = NO_ADD.executar({'perfil': 'padrao'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'erro' and 'espelho' in r.erro.lower()

    def test_idempotencia_plano_ativo(self, db, tenant_a):
        _perfil(tenant_a)
        lead = _lead(tenant_a)
        cli = _espelho(tenant_a, lead)
        _servico_espelho(tenant_a, cli, id_servico=250)
        r = NO_ADD.executar({'perfil': 'padrao', 'id_servico': '250'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'sucesso' and r.output['motivo'] == 'plano_ativo'

    def test_dry_run_monta_payload(self, db, tenant_a, monkeypatch):
        perfil = _perfil(tenant_a)
        lead = _lead(tenant_a)
        _espelho(tenant_a, lead)
        svc = _stub(tenant_a, perfil, monkeypatch)
        svc.adicionar_servico = lambda *a, **k: (_ for _ in ()).throw(AssertionError('POST no dry run!'))
        r = NO_ADD.executar({'perfil': 'padrao', 'id_servico': '250', 'dry_run': True}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'dry_run'
        p = r.output['payload']
        assert p['id_cliente'] == 9001
        assert p['servico']['id_servico'] == 250
        assert p['cliente_servico_endereco'][0]['id_endereco_numero'] == 55
        assert p['id_vencimento'] == 4

    def test_allowlist_faz_post(self, db, tenant_a, monkeypatch):
        perfil = _perfil(tenant_a, cpf_allowlist=['111.444.777-35'])
        lead = _lead(tenant_a)
        _espelho(tenant_a, lead)
        svc = _stub(tenant_a, perfil, monkeypatch)
        chamado = {}
        svc.adicionar_servico = lambda payload, **k: (
            chamado.update(p=payload), {'status': 'success', 'cliente_servico': {'id_cliente_servico': 7777}})[1]
        r = NO_ADD.executar({'perfil': 'padrao', 'id_servico': '250', 'dry_run': False}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'sucesso'
        assert r.output['resumo']['id_cliente_servico'] == 7777
        assert chamado['p']['id_cliente'] == 9001


# ---------------------------------------------------------------------------
# Nó upgrade
# ---------------------------------------------------------------------------
class TestNoMigrarPlano:
    def test_id_novo_invalido_erro(self, db, tenant_a):
        _perfil(tenant_a)
        lead = _lead(tenant_a)
        _espelho(tenant_a, lead)
        r = NO_MIG.executar({'perfil': 'padrao', 'id_servico_novo': 'abc'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'erro' and 'id_servico_novo' in r.erro

    def test_idempotencia_ja_no_destino(self, db, tenant_a):
        _perfil(tenant_a)
        lead = _lead(tenant_a)
        cli = _espelho(tenant_a, lead)
        _servico_espelho(tenant_a, cli, id_servico=300)
        r = NO_MIG.executar({'perfil': 'padrao', 'id_servico_novo': '300'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'sucesso' and r.output['motivo'] == 'plano_destino_ativo'

    def test_ambiguidade_servico_antigo_erro(self, db, tenant_a, monkeypatch):
        perfil = _perfil(tenant_a)
        lead = _lead(tenant_a)
        cli = _espelho(tenant_a, lead)
        _servico_espelho(tenant_a, cli, id_servico=100, id_cs=1)
        _servico_espelho(tenant_a, cli, id_servico=200, id_cs=2)
        _stub(tenant_a, perfil, monkeypatch)
        r = NO_MIG.executar({'perfil': 'padrao', 'id_servico_novo': '300'}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'erro' and 'antigo' in r.erro.lower()

    def test_dry_run_infere_antigo_e_monta_migracao(self, db, tenant_a, monkeypatch):
        perfil = _perfil(tenant_a)
        lead = _lead(tenant_a)
        cli = _espelho(tenant_a, lead)
        _servico_espelho(tenant_a, cli, id_servico=100, id_cs=7001)
        svc = _stub(tenant_a, perfil, monkeypatch, edit={'id_vencimento': 9})
        svc.adicionar_servico = lambda *a, **k: (_ for _ in ()).throw(AssertionError('POST no dry run!'))
        r = NO_MIG.executar({'perfil': 'padrao', 'id_servico_novo': '300', 'dry_run': True}, {}, _ctx(tenant_a, lead))
        assert r.branch == 'dry_run'
        p = r.output['payload']
        assert p['id_cliente_servico_antigo'] == 7001
        assert p['executar_migracao_imediata'] is True
        assert p['servico']['id_servico'] == 300
        assert p['id_vencimento'] == 9
        assert p['id_servico_status'] == 11
