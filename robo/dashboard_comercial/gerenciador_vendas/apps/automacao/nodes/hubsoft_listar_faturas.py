"""Nó `hubsoft_listar_faturas` — lista faturas (boletos) de um cliente no HubSoft.

Read-only (enriquecimento/cobrança): traz as faturas pro contexto
(`{{nodes.<id>.faturas}}`) — status, valor, datas, linha digitável, PIX, PDF.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.hubsoft import listar_faturas


@registrar
class HubsoftListarFaturasNode(BaseNode):
    tipo = "hubsoft_listar_faturas"
    label = "HubSoft: listar faturas"
    icone = "bi-receipt"
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "HubSoft"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'cpf_cnpj', 'label': 'CPF/CNPJ', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.cpf_cnpj}}'},
            {'nome': 'apenas_pendente', 'label': 'Só pendentes', 'tipo': 'booleano'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('cpf_cnpj') or '').strip() else ['`cpf_cnpj` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        cpf = str(contexto.resolver(config.get('cpf_cnpj', '')) or '').strip()
        if not cpf:
            return NodeResult(status='erro', branch='erro', erro='CPF/CNPJ vazio.')
        apenas_pendente = bool(config.get('apenas_pendente'))
        try:
            faturas = listar_faturas(contexto.tenant, cpf, apenas_pendente=apenas_pendente)
        except Exception as exc:
            return NodeResult(status='erro', branch='erro', erro=str(exc))
        return NodeResult(output={'faturas': faturas, 'total': len(faturas or [])}, branch='sucesso')
