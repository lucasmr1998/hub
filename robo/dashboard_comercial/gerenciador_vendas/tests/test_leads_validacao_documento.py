"""Validacao de CPF/CNPJ no pre-flight do cadastro de prospecto (tarefa 185).

O validador antigo so conhecia CPF: comecava com `len(s) != 11`, entao todo
lead PJ caia em `cpf_invalido` e a venda nunca chegava no HubSoft. Os CNPJs
abaixo sao os casos reais que estavam travados na Nuvyon em 21/07/2026.
"""
import pytest

from apps.comercial.leads.utils import _validar_cnpj, _validar_cpf, validar_documento


# CNPJs reais que o validador antigo reprovava (todos validos de verdade)
CNPJS_TRAVADOS_EM_PROD = [
    ('67559966000134', 'CONSORCIO INFRACON'),
    ('66543964000194', 'MATEUS EDUARDO GUERRA'),
    ('58742188000123', 'Fabio'),
    ('48409090000103', 'GOLD HOUSE CONSTRUTORA'),
    ('30180292000152', 'DOT A DOT TELECOMUNICACAO'),
]


class TestValidarCnpj:
    @pytest.mark.parametrize('cnpj,nome', CNPJS_TRAVADOS_EM_PROD)
    def test_aceita_os_cnpj_que_estavam_travados(self, cnpj, nome):
        assert _validar_cnpj(cnpj) is True, f'{nome} tem CNPJ valido'

    def test_aceita_com_pontuacao(self):
        assert _validar_cnpj('30.180.292/0001-52') is True

    def test_recusa_digito_verificador_errado(self):
        assert _validar_cnpj('30180292000153') is False

    def test_recusa_tamanho_errado(self):
        assert _validar_cnpj('3018029200015') is False
        assert _validar_cnpj('301802920001522') is False

    def test_recusa_todos_digitos_iguais(self):
        assert _validar_cnpj('11111111111111') is False

    def test_recusa_vazio_e_none(self):
        assert _validar_cnpj('') is False
        assert _validar_cnpj(None) is False


class TestValidarDocumento:
    """O despacho por tamanho e o coracao do fix."""

    @pytest.mark.parametrize('cnpj,_nome', CNPJS_TRAVADOS_EM_PROD)
    def test_cnpj_valido_passa(self, cnpj, _nome):
        assert validar_documento(cnpj) is True

    def test_cpf_valido_continua_passando(self):
        assert validar_documento('52998224725') is True

    def test_cpf_realmente_invalido_continua_reprovado(self):
        """Caso real: lead 2520, CPF errado de verdade. O fix nao pode deixar
        passar so porque afrouxou pra PJ."""
        assert validar_documento('37777365794') is False

    def test_cnpj_invalido_e_reprovado(self):
        assert validar_documento('30180292000153') is False

    @pytest.mark.parametrize('doc', ['', None, '123', '1234567890123'])
    def test_lixo_e_reprovado(self, doc):
        assert validar_documento(doc) is False

    def test_nao_confunde_os_dois_algoritmos(self):
        """CPF valido com 11 digitos nao pode ser lido como CNPJ e vice-versa."""
        assert _validar_cpf('52998224725') is True
        assert _validar_cnpj('52998224725') is False
        assert _validar_cnpj('30180292000152') is True
        assert _validar_cpf('30180292000152') is False


class TestPreflightUsaODespacho:
    """Garante que o pre-flight enxerga o CNPJ e roda ate o fim, em vez de
    parar em cpf_invalido."""

    def _lead_pj_completo(self, cnpj='30180292000152'):
        from datetime import date
        from types import SimpleNamespace
        return SimpleNamespace(
            pk=1, tenant_id=1,
            nome_razaosocial='DOT A DOT TELECOMUNICACAO LTDA',
            cpf_cnpj=cnpj, telefone='22999598948', email='pj@exemplo.com',
            cep='13730000', numero_residencia='100', rg='123456789',
            data_nascimento=date(1990, 1, 1), id_vendedor_rp=None,
        )

    def test_cnpj_valido_nao_para_em_cpf_invalido(self, db):
        from apps.comercial.leads.utils import validar_lead_pronto_para_prospect
        status, motivo = validar_lead_pronto_para_prospect(self._lead_pj_completo())
        assert status != 'cpf_invalido', motivo

    def test_cnpj_invalido_para_em_cpf_invalido_e_diz_CNPJ(self, db):
        from apps.comercial.leads.utils import validar_lead_pronto_para_prospect
        status, motivo = validar_lead_pronto_para_prospect(
            self._lead_pj_completo(cnpj='30180292000153'))
        assert status == 'cpf_invalido'
        assert 'CNPJ' in motivo, f'mensagem deve dizer CNPJ, veio: {motivo}'
