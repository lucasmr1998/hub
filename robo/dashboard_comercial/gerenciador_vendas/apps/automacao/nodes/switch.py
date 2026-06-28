"""Nó `switch` — roteador de N saídas.

Testa um valor (`{{...}}`) contra uma lista de casos; cada caso vira um ramo do
fluxo. O que não casar segue por `default`. Casa **normalizado** (sem espaços, sem
maiúsc.) pra aguentar saída de LLM ("Bug " == "bug"). É o roteador genérico da
engine — as saídas são **dinâmicas** (vêm dos casos, via `BaseNode.saidas_de`).
"""
from .base import BaseNode, NodeResult, registrar


def _norm(valor) -> str:
    return str(valor or '').strip().lower()


@registrar
class SwitchNode(BaseNode):
    tipo = "switch"
    label = "Switch (roteador)"
    icone = "bi-signpost-split"
    categoria = "core"
    grupo = "Fluxo"
    subgrupo = "Roteamento"
    saidas = ["default"]          # base; as reais vêm dos casos (saidas_dinamicas)
    saidas_dinamicas = True
    campo_saidas = "casos"
    is_trigger = False

    def campos_config(self) -> list:
        return [
            {'nome': 'valor', 'label': 'Valor a testar', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{nodes.classificador.resposta}}',
             'ajuda': 'O valor que decide o caminho. Aceita expressões {{...}}.'},
            {'nome': 'casos', 'label': 'Casos (um por linha)', 'tipo': 'textarea', 'obrigatorio': True,
             'placeholder': 'bug\nduvida\nfinanceiro',
             'ajuda': 'Cada linha vira um ramo. Casa por igualdade ignorando maiúsc./espaços. '
                      'O que não casar segue por "default".'},
        ]

    def validar_config(self, config) -> list:
        erros = []
        if not str(config.get('valor') or '').strip():
            erros.append('`valor` é obrigatório.')
        casos = [s for s in self.saidas_de(config) if s != 'default']
        if not casos:
            erros.append('Defina ao menos um caso (uma linha em "Casos").')
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        valor = _norm(contexto.resolver(config.get('valor', '')))
        for caso in self.saidas_de(config):
            if caso == 'default':
                continue
            if _norm(caso) == valor:
                return NodeResult(output={'valor': valor, 'caso': caso}, branch=caso)
        return NodeResult(output={'valor': valor, 'caso': None}, branch='default')
