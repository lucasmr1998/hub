"""Nós HubSoft cliente-scoped (read): atendimentos, OS, extrato de conexão,
renegociações (listar + simular)."""
from .base import registrar
from .hubsoft_base import HubsoftNode, _txt, _int, _faltando

_BUSCA_EXTRATO = ['login', 'ipv4', 'ipv6_wan', 'ipv6_lan', 'mac']

_CAMPOS_IDENT = [
    {'nome': 'cpf_cnpj', 'label': 'CPF/CNPJ', 'tipo': 'texto', 'placeholder': '{{lead.cpf_cnpj}}'},
    {'nome': 'id_cliente', 'label': 'ID cliente (HubSoft)', 'tipo': 'numero'},
    {'nome': 'codigo_cliente', 'label': 'Código cliente', 'tipo': 'numero'},
]


def _ident_falta(config):
    if not any(str(config.get(c, '')).strip() for c in ('cpf_cnpj', 'id_cliente', 'codigo_cliente')):
        return ['informe `cpf_cnpj`, `id_cliente` ou `codigo_cliente`.']
    return []


def _kwargs_ident(contexto, config):
    kw = {}
    cpf = _txt(contexto, config, 'cpf_cnpj')
    if cpf:
        kw['cpf_cnpj'] = cpf
    idc = _int(contexto.resolver(config.get('id_cliente', '')), None)
    if idc:
        kw['id_cliente'] = idc
    cod = _int(contexto.resolver(config.get('codigo_cliente', '')), None)
    if cod:
        kw['codigo_cliente'] = cod
    return kw


@registrar
class HubsoftListarAtendimentosCliente(HubsoftNode):
    tipo = "hubsoft_listar_atendimentos_cliente"
    label = "HubSoft: atendimentos do cliente"
    icone = "bi-headset"
    saida_chave = "atendimentos"

    def _campos_extra(self) -> list:
        return _CAMPOS_IDENT + [{'nome': 'limit', 'label': 'Limite', 'tipo': 'numero', 'placeholder': '20'}]

    def validar_config(self, config) -> list:
        return _ident_falta(config)

    def _chamar(self, svc, config, contexto):
        return svc.listar_atendimentos_cliente(
            limit=_int(contexto.resolver(config.get('limit', '')), 20), **_kwargs_ident(contexto, config))


@registrar
class HubsoftListarOsCliente(HubsoftNode):
    tipo = "hubsoft_listar_os_cliente"
    label = "HubSoft: ordens de serviço do cliente"
    icone = "bi-wrench"
    saida_chave = "ordens_servico"

    def _campos_extra(self) -> list:
        return _CAMPOS_IDENT + [{'nome': 'limit', 'label': 'Limite', 'tipo': 'numero', 'placeholder': '20'}]

    def validar_config(self, config) -> list:
        return _ident_falta(config)

    def _chamar(self, svc, config, contexto):
        return svc.listar_os_cliente(
            limit=_int(contexto.resolver(config.get('limit', '')), 20), **_kwargs_ident(contexto, config))


@registrar
class HubsoftExtratoConexao(HubsoftNode):
    tipo = "hubsoft_extrato_conexao"
    label = "HubSoft: extrato de conexão"
    icone = "bi-router"
    saida_chave = "registros"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'busca', 'label': 'Buscar por', 'tipo': 'select', 'opcoes': _BUSCA_EXTRATO},
            {'nome': 'termo_busca', 'label': 'Termo (ex: login PPPoE)', 'tipo': 'texto', 'obrigatorio': True},
            {'nome': 'limit', 'label': 'Limite (1-50)', 'tipo': 'numero', 'placeholder': '20'},
            {'nome': 'data_inicio', 'label': 'Data início (YYYY-MM-DD)', 'tipo': 'texto'},
            {'nome': 'data_fim', 'label': 'Data fim (YYYY-MM-DD)', 'tipo': 'texto'},
        ]

    def validar_config(self, config) -> list:
        return _faltando(config, ('termo_busca',))

    def _chamar(self, svc, config, contexto):
        kw = {
            'busca': _txt(contexto, config, 'busca') or 'login',
            'termo_busca': _txt(contexto, config, 'termo_busca'),
            'limit': _int(contexto.resolver(config.get('limit', '')), 20),
        }
        di, df = _txt(contexto, config, 'data_inicio'), _txt(contexto, config, 'data_fim')
        if di:
            kw['data_inicio'] = di
        if df:
            kw['data_fim'] = df
        return svc.verificar_extrato_conexao(**kw)


@registrar
class HubsoftListarRenegociacoes(HubsoftNode):
    tipo = "hubsoft_listar_renegociacoes"
    label = "HubSoft: listar renegociações"
    icone = "bi-cash-coin"
    saida_chave = "renegociacoes"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'cpf_cnpj', 'label': 'CPF/CNPJ', 'tipo': 'texto', 'placeholder': '{{lead.cpf_cnpj}}'},
            {'nome': 'status', 'label': 'Status', 'tipo': 'texto'},
            {'nome': 'data_inicio', 'label': 'Data início (YYYY-MM-DD)', 'tipo': 'texto'},
            {'nome': 'data_fim', 'label': 'Data fim (YYYY-MM-DD)', 'tipo': 'texto'},
        ]

    def _chamar(self, svc, config, contexto):
        kw = {}
        for c in ('cpf_cnpj', 'status', 'data_inicio', 'data_fim'):
            v = _txt(contexto, config, c)
            if v:
                kw[c] = v
        res = svc.listar_renegociacoes(**kw)
        return res.get('renegociacoes', []) if isinstance(res, dict) else res


@registrar
class HubsoftSimularRenegociacao(HubsoftNode):
    tipo = "hubsoft_simular_renegociacao"
    label = "HubSoft: simular renegociação"
    icone = "bi-calculator"
    saida_chave = "simulacao"

    def _campos_extra(self) -> list:
        return [
            {'nome': 'ids_faturas', 'label': 'IDs das faturas (vírgula)', 'tipo': 'texto',
             'obrigatorio': True, 'placeholder': '123,124'},
            {'nome': 'quantidade_parcelas', 'label': 'Qtd parcelas', 'tipo': 'numero', 'obrigatorio': True},
            {'nome': 'vencimento', 'label': '1º vencimento (YYYY-MM-DD)', 'tipo': 'texto', 'obrigatorio': True},
            {'nome': 'cpf_cnpj', 'label': 'CPF/CNPJ', 'tipo': 'texto', 'placeholder': '{{lead.cpf_cnpj}}'},
            {'nome': 'id_cliente', 'label': 'ID cliente (HubSoft)', 'tipo': 'numero'},
        ]

    def validar_config(self, config) -> list:
        erros = _faltando(config, ('ids_faturas', 'quantidade_parcelas', 'vencimento'))
        if not (str(config.get('cpf_cnpj', '')).strip() or str(config.get('id_cliente', '')).strip()):
            erros.append('informe `cpf_cnpj` ou `id_cliente`.')
        return erros

    def _chamar(self, svc, config, contexto):
        bruto = _txt(contexto, config, 'ids_faturas').replace(';', ',')
        ids = [int(x.strip()) for x in bruto.split(',') if x.strip().isdigit()]
        kw = {
            'ids_faturas': ids,
            'quantidade_parcelas': _int(contexto.resolver(config.get('quantidade_parcelas', '')), 1),
            'vencimento': _txt(contexto, config, 'vencimento'),
        }
        cpf = _txt(contexto, config, 'cpf_cnpj')
        if cpf:
            kw['cpf_cnpj'] = cpf
        idc = _int(contexto.resolver(config.get('id_cliente', '')), None)
        if idc:
            kw['id_cliente'] = idc
        return svc.simular_renegociacao(**kw)
