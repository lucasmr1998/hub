"""Higiene de PII do capturador de template (hubsoft_capturar_template).

`_neutralizar_pii` e a parte sensivel: o payload capturado vem de uma conversao
real de teste (com CPF/nome/endereco de uma pessoa) e NAO pode guardar esse PII no
perfil. Aqui garantimos que a identidade/endereco saem e a estrutura + objetos da
empresa ficam.
"""
from apps.integracoes.management.commands.hubsoft_capturar_template import _neutralizar_pii


def _payload():
    return {
        'cpf_cnpj': '11144477735', 'nome_razaosocial': 'Maria Teste',
        'nome_fantasia': 'Maria Teste', 'telefone_primario': '86999990001',
        'telefone_secundario': '86988880002', 'email_principal': 'maria@ex.com',
        'rg': '123456', 'data_nascimento': '1990-05-15', 'id_prospecto': 4242,
        'nome_pai': 'Jose', 'nome_mae': 'Ana',
        'cliente_endereco_numeros': [
            {'tipo': 'cadastral', 'cep': '64000000', 'endereco': 'Rua X',
             'numero': '10', 'bairro': 'Centro', 'complemento': 'ap 1',
             'referencia': 'perto da praca', 'latitude': -5.0, 'id_endereco_numero': 7},
        ],
        'cliente_servico_endereco_instalacao': {
            'cep': '64000000', 'endereco': 'Rua X', 'numero': '10', 'bairro': 'Centro'},
        'cliente_servico': {'servico': {'id_servico': 250}, 'forma_cobranca': {'id_forma_cobranca': 140}},
    }


def test_neutraliza_identidade():
    p = _neutralizar_pii(_payload())
    assert p['cpf_cnpj'] == ''
    assert p['nome_razaosocial'] == '' and p['nome_fantasia'] == ''
    assert p['telefone_primario'] == '' and p['telefone_secundario'] == ''
    assert p['email_principal'] == '' and p['rg'] == ''
    assert p['data_nascimento'] is None and p['id_prospecto'] is None
    assert p['nome_pai'] is None and p['nome_mae'] is None


def test_neutraliza_endereco_mantendo_estrutura():
    p = _neutralizar_pii(_payload())
    end = p['cliente_endereco_numeros'][0]
    assert end['cep'] == '' and end['endereco'] == '' and end['numero'] == '' and end['bairro'] == ''
    assert end['complemento'] is None and end['referencia'] is None
    # estrutura nao-PII preservada
    assert end['tipo'] == 'cadastral' and end['latitude'] == -5.0 and end['id_endereco_numero'] == 7
    inst = p['cliente_servico_endereco_instalacao']
    assert inst['cep'] == '' and inst['bairro'] == ''


def test_preserva_objetos_da_empresa():
    p = _neutralizar_pii(_payload())
    # o que importa pro template continua intacto
    assert p['cliente_servico']['servico']['id_servico'] == 250
    assert p['cliente_servico']['forma_cobranca']['id_forma_cobranca'] == 140


def test_nao_muta_o_original():
    orig = _payload()
    _neutralizar_pii(orig)
    # deepcopy: nem topo nem aninhado do original sao tocados
    assert orig['cpf_cnpj'] == '11144477735'
    assert orig['cliente_endereco_numeros'][0]['cep'] == '64000000'
