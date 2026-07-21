"""Testes do WidgetQueryBuilder.

Por ora cobre o transform `normalizar_cidade`, que agrupa variantes de grafia
da mesma cidade. Ele nao toca banco (opera sobre labels/data ja agregados),
entao da pra exercitar sem fixture de tenant.
"""
import pytest

from apps.relatorios.query_builder import WidgetQueryBuilder


def _normalizar(pares):
    """Roda o transform sobre [(label, valor), ...] e devolve o mesmo formato."""
    builder = WidgetQueryBuilder.__new__(WidgetQueryBuilder)  # sem __init__: o transform e puro
    labels = [p[0] for p in pares]
    data = [float(p[1]) for p in pares]
    labels, data = builder._aplicar_transform('normalizar_cidade', 'cidade', None, labels, data)
    return list(zip(labels, data))


class TestNormalizarCidade:
    def test_junta_variacoes_de_caixa(self):
        assert _normalizar([('Mococa', 61), ('MOCOCA', 3)]) == [('Mococa', 64.0)]

    def test_junta_sufixo_de_uf_em_qualquer_separador(self):
        """O caso real da Nuvyon: "Mococa sp" virava fatia separada e o painel
        parecia dizer que Mococa tinha 2 leads quando tinha 65."""
        resultado = _normalizar([
            ('Mococa', 61), ('MOCOCA', 3), ('Mococa sp', 2),
            ('Mococa/SP', 4), ('Mococa - SP', 1), ('Mococa, SP', 1),
        ])
        assert resultado == [('Mococa', 72.0)]

    def test_ignora_acento_ao_agrupar_mas_exibe_a_grafia_mais_comum(self):
        resultado = _normalizar([('Sumaré', 22), ('Sumare', 1)])
        assert resultado == [('Sumaré', 23.0)], 'deve somar e manter o acento'

    def test_nao_amputa_cidade_que_termina_em_duas_letras(self):
        """Regressao: com `[a-z]{2}` no lugar da lista de UFs, um nome que
        acabasse em duas letras que nao sao estado seria cortado."""
        resultado = dict(_normalizar([('Cotia', 5), ('Bauru', 3)]))
        assert 'Cotia' in resultado and 'Bauru' in resultado

    def test_ordena_por_valor_desc(self):
        resultado = _normalizar([('Mococa', 10), ('Salto', 90), ('Itu', 50)])
        assert [lb for lb, _ in resultado] == ['Salto', 'Itu', 'Mococa']

    def test_descarta_vazio_e_travessao(self):
        resultado = _normalizar([('Salto', 5), ('', 3), ('—', 2), ('   ', 1)])
        assert resultado == [('Salto', 5.0)]

    def test_normaliza_espacos_duplicados_e_das_pontas(self):
        assert _normalizar([('  Casa   Branca ', 4), ('Casa Branca', 6)]) == [('Casa Branca', 10.0)]

    @pytest.mark.parametrize('bruto,esperado', [
        ('SAO JOSE DO RIO PARDO', 'Sao Jose do Rio Pardo'),
        ('monte santo de minas', 'Monte Santo de Minas'),
    ])
    def test_titulariza_quando_a_grafia_vem_toda_em_um_caso_so(self, bruto, esperado):
        """Preposicao fica minuscula. Nome ja em caixa mista e preservado."""
        assert _normalizar([(bruto, 1)]) == [(esperado, 1.0)]

    def test_preserva_grafia_mista_do_usuario(self):
        assert _normalizar([('São José do Rio Pardo', 28)]) == [('São José do Rio Pardo', 28.0)]
