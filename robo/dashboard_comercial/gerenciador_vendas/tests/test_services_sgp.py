"""
Testes unitarios do SGPService.

Mocka a camada HTTP (requests.request) — nao bate em prod. Cobre os
caminhos felizes + erros importantes pra prevenir regressao em
mudancas de shape ou nomes de campo.
"""
from io import BytesIO
from unittest.mock import patch, MagicMock

import pytest

from apps.integracoes.services.sgp import SGPService, SGPServiceError
from apps.integracoes.models import ClienteSGP

from tests.factories import IntegracaoAPIFactory, LeadProspectoFactory


def _mock_response(status=200, json_data=None, text=''):
    """Helper: cria mock de response com .json() / .status_code / .text."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    if json_data is None:
        resp.json.side_effect = ValueError('no json')
    else:
        resp.json.return_value = json_data
    return resp


@pytest.fixture
def integracao_sgp(db):
    return IntegracaoAPIFactory(
        tipo='sgp',
        base_url='https://provedor.sgp.net.br',
        client_id='aurora',
        access_token='token-fake-123',
    )


@pytest.fixture
def svc(integracao_sgp):
    return SGPService(integracao_sgp)


@pytest.mark.django_db
class TestSGPServiceConstrutor:

    def test_aceita_integracao_sgp(self, integracao_sgp):
        s = SGPService(integracao_sgp)
        assert s.integracao == integracao_sgp
        assert s.base_url == 'https://provedor.sgp.net.br'

    def test_rejeita_integracao_de_outro_tipo(self):
        integ = IntegracaoAPIFactory(tipo='hubsoft')
        with pytest.raises(SGPServiceError, match='não é do tipo sgp'):
            SGPService(integ)

    def test_strip_trailing_slash_da_base_url(self, db):
        integ = IntegracaoAPIFactory(tipo='sgp', base_url='https://x.com/')
        s = SGPService(integ)
        assert s.base_url == 'https://x.com'


@pytest.mark.django_db
class TestValidarCredenciais:

    def test_sucesso_retorna_true(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data=[{'id': 1}])
            assert svc.validar_credenciais() is True

    def test_resposta_nao_lista_levanta(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'erro': 'auth'})
            with pytest.raises(SGPServiceError, match='inválidas|inesperado'):
                svc.validar_credenciais()

    def test_http_403_levanta(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(403, json_data={'detail': 'erro'})
            with pytest.raises(SGPServiceError, match='HTTP 403'):
                svc.validar_credenciais()


@pytest.mark.django_db
class TestConsultarCliente:

    def test_envia_cpfcnpj_so_digitos(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'contratos': []})
            svc.consultar_cliente('123.456.789-09')
            # requests.request chamado com data contendo cpfcnpj limpo
            _, kwargs = mock.call_args
            assert kwargs['data']['cpfcnpj'] == '12345678909'

    def test_cpf_vazio_levanta(self, svc):
        with pytest.raises(SGPServiceError, match='vazio'):
            svc.consultar_cliente('')


@pytest.mark.django_db
class TestSincronizarCliente:

    @pytest.fixture
    def resposta_gdm(self):
        return {
            'contratos': [
                {
                    'clienteId': 215,
                    'cpfCnpj': '06.064.410/0001-82',
                    'razaoSocial': 'GDM TELECOM LTDA',
                    'telefones': ['(86) 99966-1078'],
                    'emails': ['x@y.com'],
                    'endereco_cep': '64325-000',
                    'endereco_logradouro': 'RUA TESTE',
                    'endereco_numero': '100',
                    'endereco_bairro': 'CENTRO',
                    'endereco_cidade': 'ELESBAO VELOSO',
                    'endereco_uf': 'PI',
                    'contratoId': 7232,
                    'contratoStatus': 1,
                },
                {
                    'clienteId': 215,
                    'contratoId': 7233,
                    'contratoStatus': 1,
                    'razaoSocial': 'GDM TELECOM LTDA',
                    'cpfCnpj': '06.064.410/0001-82',
                    'telefones': [],
                    'emails': [],
                },
            ]
        }

    def test_cria_cliente_sgp_com_dados_do_primeiro_contrato(self, svc, resposta_gdm, integracao_sgp):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data=resposta_gdm)
            cliente = svc.sincronizar_cliente(None, cpf_cnpj='06064410000182')

        assert cliente is not None
        assert cliente.id_cliente_sgp == 215
        assert cliente.nome == 'GDM TELECOM LTDA'
        assert cliente.cpf_cnpj == '06064410000182'
        assert cliente.email == 'x@y.com'
        assert cliente.telefone == '(86) 99966-1078'
        assert cliente.cep == '64325000'
        assert cliente.cidade == 'ELESBAO VELOSO'
        assert cliente.uf == 'PI'
        assert cliente.ativo is True  # tem contrato status=1
        assert len(cliente.contratos) == 2
        assert cliente.integracao == integracao_sgp

    def test_idempotente_atualiza_em_vez_de_duplicar(self, svc, resposta_gdm):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data=resposta_gdm)
            svc.sincronizar_cliente(None, cpf_cnpj='06064410000182')
            svc.sincronizar_cliente(None, cpf_cnpj='06064410000182')
        assert ClienteSGP.objects.count() == 1

    def test_resposta_sem_contratos_retorna_none(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'contratos': []})
            cliente = svc.sincronizar_cliente(None, cpf_cnpj='02988460043')
        assert cliente is None
        assert ClienteSGP.objects.count() == 0

    def test_lead_sem_cpf_retorna_none(self, svc):
        cliente = svc.sincronizar_cliente(None, cpf_cnpj=None)
        assert cliente is None


@pytest.mark.django_db
class TestCadastrarProspectoPF:

    def test_envia_payload_sem_prefixo_endereco(self, svc):
        """Bug critico que descobrimos em prod: SGP nao usa prefixo `endereco_`."""
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={
                'precadastro_id': 1, 'new_cliente_id': 2, 'message': 'ok',
            })
            svc.cadastrar_prospecto_pf(
                nome='Lucas', cpf='02988460043', email='x@y.com',
                telefone_celular='53981521653',
                cep='64325000', logradouro='Rua X', numero='1',
                bairro='Centro', cidade='Elesbao', uf='PI',
                plano_id=8, vendedor_id=1, pop_id=1, portador_id=1,
                dia_vencimento=5, forma_cobranca=6,
            )
            _, kwargs = mock.call_args
            data = kwargs['data']
            # Campos diretos, sem prefixo
            assert 'logradouro' in data and 'endereco_logradouro' not in data
            assert 'cep' in data and 'endereco_cep' not in data
            assert data['cpfcnpj'] == '02988460043'
            assert data['plano'] == 8
            assert data['vendedor'] == 1
            assert data['precadastro_ativar'] == 0


@pytest.mark.django_db
class TestCadastrarProspectoParaLead:

    def test_falta_defaults_levanta_erro_claro(self, svc, integracao_sgp):
        lead = LeadProspectoFactory(cpf_cnpj='12345678909', tenant=integracao_sgp.tenant)
        # Sem defaults setados em configuracoes_extras
        with pytest.raises(SGPServiceError, match='defaults faltando'):
            svc.cadastrar_prospecto_para_lead(lead)

    def test_lead_sem_cpf_levanta(self, svc, integracao_sgp):
        integracao_sgp.configuracoes_extras = {
            'plano_id_padrao': 1, 'vendedor_id_padrao': 1, 'pop_id_padrao': 1,
            'portador_id_padrao': 1, 'forma_cobranca_id_padrao': 6,
            'dia_vencimento_padrao': 5,
        }
        integracao_sgp.save()
        lead = LeadProspectoFactory(cpf_cnpj=None, tenant=integracao_sgp.tenant)
        with pytest.raises(SGPServiceError, match='sem CPF'):
            svc.cadastrar_prospecto_para_lead(lead)


@pytest.mark.django_db
class TestListarTitulos:

    def test_exige_cpf_ou_cliente_id(self, svc):
        with pytest.raises(SGPServiceError, match='cpf_cnpj OU cliente_id'):
            svc.listar_titulos()

    def test_envia_filtros_corretos(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data=[])
            svc.listar_titulos(cpf_cnpj='123', status='abertos',
                               data_vencimento_inicio='2026-01-01')
            _, kwargs = mock.call_args
            assert kwargs['data']['cpfcnpj'] == '123'
            assert kwargs['data']['status'] == 'abertos'
            assert kwargs['data']['data_vencimento_inicio'] == '2026-01-01'

    def test_resposta_lista_direta(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data=[{'id': 1}, {'id': 2}])
            r = svc.listar_titulos(cliente_id=215)
            assert len(r) == 2

    def test_resposta_dict_com_chave_titulos(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'titulos': [{'id': 1}]})
            r = svc.listar_titulos(cliente_id=215)
            assert len(r) == 1


@pytest.mark.django_db
class TestVerificarAcesso:

    def test_exige_pelo_menos_um_id(self, svc):
        with pytest.raises(SGPServiceError, match='cliente_id, contrato_id ou cpf_cnpj'):
            svc.verificar_acesso()

    def test_envia_contrato_id(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'status': 1, 'msg': 'Online'})
            svc.verificar_acesso(contrato_id=7232)
            _, kwargs = mock.call_args
            assert kwargs['data']['contrato'] == 7232


@pytest.mark.django_db
class TestGerar2viaFatura:

    def test_exige_titulo_id(self, svc):
        with pytest.raises(SGPServiceError, match='titulo_id obrigatorio'):
            svc.gerar_2via_fatura(0)

    def test_envia_titulo(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'link': 'https://x'})
            r = svc.gerar_2via_fatura(123)
            _, kwargs = mock.call_args
            assert kwargs['data']['titulo'] == 123
            assert r['link'] == 'https://x'


@pytest.mark.django_db
class TestAnexarDocumento:

    def test_exige_cliente_id(self, svc):
        with pytest.raises(SGPServiceError, match='cliente_id obrigatorio'):
            svc.anexar_documento(0, BytesIO(b'fake'))

    def test_usa_put_e_multipart(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'ok': True})
            svc.anexar_documento(215, BytesIO(b'PDFBYTES'),
                                 nome_arquivo='rg.pdf', descricao='RG do cliente')
            args, kwargs = mock.call_args
            # Primeiro positional eh metodo
            assert args[0] == 'PUT'
            assert '/api/suporte/cliente/215/documento/add/' in args[1]
            assert 'file' in kwargs['files']
            assert kwargs['data']['descricao'] == 'RG do cliente'


@pytest.mark.django_db
class TestAceitarContrato:

    def test_exige_contrato_id(self, svc):
        with pytest.raises(SGPServiceError, match='contrato_id obrigatorio'):
            svc.aceitar_contrato(0)

    def test_envia_aceite_sim(self, svc):
        with patch('apps.integracoes.services.sgp.requests.request') as mock:
            mock.return_value = _mock_response(200, json_data={'ok': True})
            svc.aceitar_contrato(7232)
            args, kwargs = mock.call_args
            assert '/api/contrato/termoaceite/7232' in args[1]
            assert kwargs['data']['aceite'] == 'sim'
