"""Nó `hubsoft_consultar_cliente` — consulta um cliente no HubSoft por CPF/CNPJ.

Read-only (enriquecimento): traz os dados do cliente pro contexto do fluxo
(`{{nodes.<id>.cliente.…}}`). Provedor HubSoft sob Integrações.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.hubsoft import consultar_cliente


@registrar
class HubsoftConsultarClienteNode(BaseNode):
    tipo = "hubsoft_consultar_cliente"
    label = "HubSoft: consultar cliente"
    icone = "bi-search"
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "HubSoft"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'cpf_cnpj', 'label': 'CPF/CNPJ', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.cpf_cnpj}}'},
            {'nome': 'incluir_contrato', 'label': 'Incluir contrato', 'tipo': 'booleano'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('cpf_cnpj') or '').strip() else ['`cpf_cnpj` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        cpf = str(contexto.resolver(config.get('cpf_cnpj', '')) or '').strip()
        if not cpf:
            return NodeResult(status='erro', branch='erro', erro='CPF/CNPJ vazio.')
        incluir = bool(config.get('incluir_contrato'))
        try:
            dados = consultar_cliente(contexto.tenant, cpf, incluir_contrato=incluir)
        except Exception as exc:
            return NodeResult(status='erro', branch='erro', erro=str(exc))
        return NodeResult(output={'cliente': dados}, branch='sucesso')
