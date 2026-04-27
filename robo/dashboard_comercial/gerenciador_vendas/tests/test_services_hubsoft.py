"""
Testes unitarios do HubsoftService.

Mocka a camada HTTP (requests.request) — nao bate em prod. Cobre os
caminhos felizes + erros importantes pra prevenir regressao em
mudancas de shape ou nomes de campo.

Espelha a estrutura de tests/test_services_sgp.py (27 testes do SGP).
"""
from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.utils import timezone

from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.integracoes.models import LogIntegracao

from tests.factories import IntegracaoAPIFactory, LeadProspectoFactory


def _mock_response(status=200, json_data=None, text=''):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    if json_data is None:
        resp.json.side_effect = ValueError('no json')
    else:
        resp.json.return_value = json_data
    return resp


@pytest.fixture
def integ(db):
    return IntegracaoAPIFactory(
        tipo='hubsoft',
        base_url='https://api.teste.hubsoft.com.br',
        client_id='cli',
        client_secret='sec',
        username='user',
        password='pwd',
        access_token='tok-cache-123',
        token_expira_em=timezone.now() + timedelta(hours=1),
    )


@pytest.fixture
def svc(integ):
    return HubsoftService(integ)


# ============================================================================
# Construtor
# ============================================================================

@pytest.mark.django_db
class TestHubsoftServiceConstrutor:
    def test_aceita_integracao_hubsoft(self, integ):
        s = HubsoftService(integ)
        assert s.integracao == integ
        assert s.base_url == 'https://api.teste.hubsoft.com.br'

    def test_rejeita_integracao_outro_tipo(self):
        i = IntegracaoAPIFactory(tipo='sgp')
        with pytest.raises(HubsoftServiceError, match='não é do tipo hubsoft'):
            HubsoftService(i)

    def test_strip_trailing_slash_da_base_url(self, db):
        i = IntegracaoAPIFactory(tipo='hubsoft', base_url='https://x.com/')
        assert HubsoftService(i).base_url == 'https://x.com'


# ============================================================================
# _payload_seguro (mascaramento)
# ============================================================================

@pytest.mark.django_db
class TestPayloadSeguro:
    def test_mascara_password(self):
        out = HubsoftService._payload_seguro({'username': 'u', 'password': 'p'})
        assert out['username'] == 'u'
        assert out['password'] == '***REDACTED***'

    def test_mascara_client_secret(self):
        out = HubsoftService._payload_seguro({'client_secret': 'x', 'foo': 'y'})
        assert out['client_secret'] == '***REDACTED***'
        assert out['foo'] == 'y'

    def test_mascara_token_e_access_token(self):
        out = HubsoftService._payload_seguro({'token': 'a', 'access_token': 'b'})
        assert out['token'] == '***REDACTED***'
        assert out['access_token'] == '***REDACTED***'

    def test_nao_mexe_em_outros_campos(self):
        original = {'cpf_cnpj': '11111111111', 'plano': 1}
        out = HubsoftService._payload_seguro(original)
        assert out == original


# ============================================================================
# Token / autenticacao
# ============================================================================

@pytest.mark.django_db
class TestObterToken:
    def test_reutiliza_token_cacheado(self, svc):
        # token_expira_em ja foi setado pra +1h na fixture
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            t = svc.obter_token()
            assert t == 'tok-cache-123'
            mock.assert_not_called()

    def test_renova_quando_expirado(self, svc):
        svc.integracao.token_expira_em = timezone.now() - timedelta(minutes=5)
        svc.integracao.save()
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'access_token': 'novo-tok', 'expires_in': 3600,
            })
            t = svc.obter_token()
            assert t == 'novo-tok'
            mock.assert_called_once()
            # Verifica que o body NAO contem o password em claro no log
            log = LogIntegracao.objects.get(endpoint='/oauth/token')
            assert log.payload_enviado['password'] == '***REDACTED***'
            assert log.payload_enviado['client_secret'] == '***REDACTED***'

    def test_token_falha_http(self, svc):
        svc.integracao.token_expira_em = None
        svc.integracao.save()
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(401, json_data={'error': 'invalid_grant'})
            with pytest.raises(HubsoftServiceError, match='HTTP 401'):
                svc.obter_token()


# ============================================================================
# Catalogos (H2)
# ============================================================================

@pytest.mark.django_db
class TestCatalogos:
    def test_listar_servicos(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success',
                'servicos': [{'id_servico': 1, 'descricao': 'P1'}],
            })
            servicos = svc.listar_servicos()
            assert len(servicos) == 1
            assert servicos[0]['id_servico'] == 1

    def test_listar_vencimentos(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success',
                'vencimentos': [{'id_vencimento': 22, 'dia_vencimento': 1}],
            })
            v = svc.listar_vencimentos()
            assert v[0]['dia_vencimento'] == 1

    def test_sincronizar_catalogo_cacheado_chave_invalida(self, svc):
        with pytest.raises(HubsoftServiceError, match='desconhecido'):
            svc.sincronizar_catalogo_cacheado('inexistente')

    def test_sincronizar_catalogo_vendedores_dry_run(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success',
                'vendedores': [{'id': 1, 'name': 'A'}, {'id': 2, 'name': 'B'}],
            })
            r = svc.sincronizar_catalogo_cacheado('vendedores', dry_run=True)
            assert r['total'] == 2
            assert r['criados'] == 2
            assert r['dry_run'] is True
            # Nao escreve em dry_run
            svc.integracao.refresh_from_db()
            assert (svc.integracao.configuracoes_extras or {}).get('cache') is None

    def test_sincronizar_configuracoes_captura_erro_por_catalogo(self, svc):
        # Primeiro endpoint OK (servicos), os demais retornam 500 — wrapper nao deve falhar
        call_count = {'n': 0}

        def fake(*args, **kwargs):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return _mock_response(200, json_data={'status': 'success', 'servicos': []})
            return _mock_response(500, json_data={'status': 'error', 'msg': 'down'})

        with patch('apps.integracoes.services.hubsoft.requests.request', side_effect=fake):
            r = svc.sincronizar_configuracoes(dry_run=True)
            assert 'servicos' in r
            # Deve ter 'erro' em pelo menos um catalogo
            erros = [k for k, v in r.items() if isinstance(v, dict) and 'erro' in v]
            assert len(erros) >= 1


# ============================================================================
# Cliente / Prospecto
# ============================================================================

@pytest.mark.django_db
class TestConsultarCliente:
    def test_envia_cpf_so_digitos(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'clientes': [],
            })
            svc.consultar_cliente('123.456.789-09')
            _, kwargs = mock.call_args
            assert kwargs['params']['termo_busca'] == '12345678909'
            assert kwargs['params']['busca'] == 'cpf_cnpj'

    def test_status_nao_success_levanta(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'error', 'msg': 'cliente nao encontrado',
            })
            with pytest.raises(HubsoftServiceError, match='retornou erro'):
                svc.consultar_cliente('11111111111')


@pytest.mark.django_db
class TestCadastrarProspecto:
    def test_envia_payload_correto_e_bearer(self, svc):
        lead = LeadProspectoFactory(
            tenant=svc.integracao.tenant,
            nome_razaosocial='Teste',
            cpf_cnpj='11111111111',
            telefone='5589994034399',
            email='t@x.com',
        )
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'prospecto': {'id_prospecto': 42},
            })
            r = svc.cadastrar_prospecto(lead)
            assert r['prospecto']['id_prospecto'] == 42
            args, kwargs = mock.call_args
            assert kwargs['headers']['Authorization'] == 'Bearer tok-cache-123'
            assert kwargs['json']['cpf_cnpj'] == '11111111111'
            # DDI 55 removido
            assert kwargs['json']['telefone'] == '89994034399'

    def test_status_nao_success_levanta(self, svc):
        lead = LeadProspectoFactory(tenant=svc.integracao.tenant, cpf_cnpj='11111111111')
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'error', 'msg': 'CPF invalido',
            })
            with pytest.raises(HubsoftServiceError, match='rejeitou prospecto'):
                svc.cadastrar_prospecto(lead)


# ============================================================================
# Financeiro (H3)
# ============================================================================

@pytest.mark.django_db
class TestFinanceiro:
    def test_listar_faturas_exige_identificacao(self, svc):
        with pytest.raises(HubsoftServiceError, match='cpf_cnpj.*id_cliente.*codigo_cliente'):
            svc.listar_faturas_cliente()

    def test_listar_faturas_apenas_pendente(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'faturas': [{'id_fatura': 1}],
            })
            f = svc.listar_faturas_cliente(cpf_cnpj='11111111111', apenas_pendente=True)
            _, kwargs = mock.call_args
            assert kwargs['params']['apenas_pendente'] == 'sim'
            assert len(f) == 1

    def test_simular_renegociacao_id_cliente(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'faturas_que_foram_geradas': [],
            })
            svc.simular_renegociacao(
                ids_faturas=[100, 200], quantidade_parcelas=3,
                vencimento='2026-05-01', id_cliente=42,
            )
            _, kwargs = mock.call_args
            assert kwargs['json']['tipo_dados_cliente'] == 'id_cliente'
            assert kwargs['json']['dados_cliente'] == 42
            assert kwargs['json']['ids_faturas'] == [100, 200]
            assert kwargs['json']['quantidade_parcelas'] == 3

    def test_simular_renegociacao_validacoes(self, svc):
        with pytest.raises(HubsoftServiceError, match='ids_faturas'):
            svc.simular_renegociacao(ids_faturas=[], quantidade_parcelas=1, vencimento='2026-01-01', id_cliente=1)
        with pytest.raises(HubsoftServiceError, match='vencimento'):
            svc.simular_renegociacao(ids_faturas=[1], quantidade_parcelas=1, vencimento='', id_cliente=1)
        with pytest.raises(HubsoftServiceError, match='quantidade_parcelas'):
            svc.simular_renegociacao(ids_faturas=[1], quantidade_parcelas=0, vencimento='2026-01-01', id_cliente=1)
        with pytest.raises(HubsoftServiceError, match='id_cliente OU cpf_cnpj'):
            svc.simular_renegociacao(ids_faturas=[1], quantidade_parcelas=1, vencimento='2026-01-01')


# ============================================================================
# Operacional (H4)
# ============================================================================

@pytest.mark.django_db
class TestOperacional:
    def test_extrato_conexao_envia_busca_e_termo(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'registros': [{'username': 'u'}],
            })
            r = svc.verificar_extrato_conexao(busca='login', termo_busca='hubsoft')
            _, kwargs = mock.call_args
            assert kwargs['params']['busca'] == 'login'
            assert kwargs['params']['termo_busca'] == 'hubsoft'
            assert len(r) == 1

    def test_extrato_exige_termo(self, svc):
        with pytest.raises(HubsoftServiceError, match='termo_busca'):
            svc.verificar_extrato_conexao(termo_busca='')

    def test_desbloqueio_confianca_envia_id_e_dias_como_string(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'status': 'success', 'msg': 'ok'})
            svc.desbloqueio_confianca(11000, dias_desbloqueio=2)
            _, kwargs = mock.call_args
            assert kwargs['json']['id_cliente_servico'] == '11000'
            assert kwargs['json']['dias_desbloqueio'] == '2'

    def test_reset_mac_addr(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'status': 'success'})
            svc.reset_mac_addr(11000)
            _, kwargs = mock.call_args
            assert kwargs['json']['id_cliente_servico'] == '11000'

    def test_suspender_servico_passa_tipo(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'status': 'success'})
            svc.suspender_servico(123, tipo_suspensao='suspenso_solicitacao_cliente')
            args, kwargs = mock.call_args
            assert '/cliente_servico/suspender/123' in args[1]
            assert kwargs['json']['tipo_suspensao'] == 'suspenso_solicitacao_cliente'

    def test_ativar_servico_endpoint_correto(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'status': 'success'})
            svc.ativar_servico(456)
            args, _ = mock.call_args
            assert '/cliente_servico/ativar/456' in args[1]


# ============================================================================
# Viabilidade (H5)
# ============================================================================

@pytest.mark.django_db
class TestViabilidade:
    def test_consultar_endereco(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'resultado': {'projetos': []},
            })
            r = svc.consultar_viabilidade_endereco(
                endereco='Rua X', numero='10', bairro='Centro',
                cidade='Teresina', estado='pi',
            )
            _, kwargs = mock.call_args
            assert kwargs['json']['tipo_busca'] == 'endereco'
            assert kwargs['json']['endereco']['estado'] == 'PI'  # uppercased
            assert isinstance(r, dict)

    def test_consultar_coords(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'resultado': {'projetos': []},
            })
            svc.consultar_viabilidade_coords(latitude=-5.0, longitude=-42.0)
            _, kwargs = mock.call_args
            assert kwargs['json']['tipo_busca'] == 'coordenadas'
            assert kwargs['json']['latitude'] == -5.0

    def test_listar_planos_por_cep_so_digitos(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'servicos': [{'id_servico': 1, 'valor': 100}],
            })
            r = svc.listar_planos_por_cep('64000-000')
            _, kwargs = mock.call_args
            assert kwargs['params']['cep'] == '64000000'
            assert r[0]['id_servico'] == 1

    def test_listar_planos_por_cep_vazio_levanta(self, svc):
        with pytest.raises(HubsoftServiceError, match='cep'):
            svc.listar_planos_por_cep('')


# ============================================================================
# Atendimento / OS leitura (H6 reduzido)
# ============================================================================

@pytest.mark.django_db
class TestAtendimentoLeitura:
    def test_listar_atendimentos_cliente(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'atendimentos': [{'id_atendimento': 5}],
            })
            r = svc.listar_atendimentos_cliente(cpf_cnpj='11111111111')
            assert r[0]['id_atendimento'] == 5

    def test_listar_os_aceita_id_cliente(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'ordens_servico': [],
            })
            svc.listar_os_cliente(id_cliente=42)
            _, kwargs = mock.call_args
            assert kwargs['params']['busca'] == 'id_cliente'
            assert kwargs['params']['termo_busca'] == '42'

    def test_busca_cliente_exige_um_id(self, svc):
        with pytest.raises(HubsoftServiceError, match='cpf_cnpj.*id_cliente.*codigo_cliente'):
            svc.listar_atendimentos_cliente()


# ============================================================================
# Helpers de normalizacao
# ============================================================================

@pytest.mark.django_db
class TestNormalizacao:
    def test_somente_numeros_remove_pontuacao(self):
        assert HubsoftService._somente_numeros('123.456.789-09') == '12345678909'
        assert HubsoftService._somente_numeros(None) == ''

    def test_normalizar_telefone_remove_ddi_55(self):
        # 13 digitos com 55 prefixo -> remove
        assert HubsoftService._normalizar_telefone('5589994034399') == '89994034399'
        # Numero ja sem DDI -> mantem
        assert HubsoftService._normalizar_telefone('89994034399') == '89994034399'

    def test_detectar_tipo_pessoa(self):
        assert HubsoftService._detectar_tipo_pessoa('11111111111') == 'pf'
        assert HubsoftService._detectar_tipo_pessoa('11.222.333/0001-44') == 'pj'
        assert HubsoftService._detectar_tipo_pessoa('') == 'pf'


# ============================================================================
# _request — log e mascaramento end-to-end
# ============================================================================

@pytest.mark.django_db
class TestRequestLogging:
    def test_log_de_sucesso_eh_registrado(self, svc):
        with patch('apps.integracoes.services.hubsoft.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'status': 'success', 'clientes': [],
            })
            svc.consultar_cliente('11111111111')
            log = LogIntegracao.objects.filter(
                endpoint='/api/v1/integracao/cliente',
            ).order_by('-data_criacao').first()
            assert log is not None
            assert log.sucesso is True
            assert log.status_code == 200
            assert log.metodo == 'GET'
            assert log.tempo_resposta_ms >= 0

    def test_falha_de_rede_levanta_e_loga(self, svc):
        import requests as rq
        with patch('apps.integracoes.services.hubsoft.requests.request',
                   side_effect=rq.ConnectionError('boom')):
            with pytest.raises(HubsoftServiceError, match='Falha de conexão'):
                svc.consultar_cliente('11111111111')
        log = LogIntegracao.objects.filter(sucesso=False).order_by('-data_criacao').first()
        assert log is not None
        assert 'boom' in log.mensagem_erro
