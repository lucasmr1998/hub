"""Nó `hubsoft_planos_cep` — lista planos disponíveis pra um CEP (viabilidade).

Read-only: útil em fluxos de qualificação (lead de uma região atendida?). Traz os
planos pro contexto (`{{nodes.<id>.planos}}`).
"""
from .base import BaseNode, NodeResult, registrar
from ..services.hubsoft import listar_planos_por_cep


@registrar
class HubsoftPlanosCepNode(BaseNode):
    tipo = "hubsoft_planos_cep"
    label = "HubSoft: planos por CEP"
    icone = "bi-geo-alt"
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "HubSoft"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'cep', 'label': 'CEP', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.cep}}'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('cep') or '').strip() else ['`cep` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        cep = str(contexto.resolver(config.get('cep', '')) or '').strip()
        if not cep:
            return NodeResult(status='erro', branch='erro', erro='CEP vazio.')
        try:
            planos = listar_planos_por_cep(contexto.tenant, cep)
        except Exception as exc:
            return NodeResult(status='erro', branch='erro', erro=str(exc))
        return NodeResult(output={'planos': planos, 'total': len(planos or [])}, branch='sucesso')
