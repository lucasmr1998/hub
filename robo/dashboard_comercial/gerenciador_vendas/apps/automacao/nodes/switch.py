"""Nó `switch` — roteador de N saídas (modelo "Rules" do n8n).

Cada regra é uma condição completa `esquerda [operador] direita` + um nome de saída.
Avalia as regras EM ORDEM; a primeira que casa define o ramo. Nada casou → `default`.
É a generalização N-via do `if` — reusa o mesmo `_comparar` (mesmos operadores), e as
saídas são **dinâmicas** (vêm dos nomes das regras, via `BaseNode.saidas_de`).
"""
from .base import BaseNode, NodeResult, registrar
from .if_node import _comparar


@registrar
class SwitchNode(BaseNode):
    tipo = "switch"
    label = "Switch (roteador)"
    icone = "bi-signpost-split"
    categoria = "core"
    grupo = "Fluxo"
    subgrupo = "Roteamento"
    saidas = ["default"]          # base; as reais vêm das regras (saidas_dinamicas)
    saidas_dinamicas = True
    campo_saidas = "regras"
    is_trigger = False

    def campos_config(self) -> list:
        return [
            {'nome': 'regras', 'label': 'Regras de roteamento', 'tipo': 'regras', 'obrigatorio': True,
             'ajuda': 'Cada regra: valor [operador] comparar → nome da saída. Avalia em ordem; a '
                      'primeira que casa define o caminho. O que não casar segue por "default".'},
        ]

    def validar_config(self, config) -> list:
        validas = [r for r in (config.get('regras') or [])
                   if isinstance(r, dict) and str(r.get('saida') or '').strip()]
        if not validas:
            return ['Defina ao menos uma regra com nome de saída.']
        return []

    def executar(self, config, entrada, contexto) -> NodeResult:
        for regra in (config.get('regras') or []):
            if not isinstance(regra, dict):
                continue
            saida = str(regra.get('saida') or '').strip()
            if not saida:
                continue
            operador = regra.get('operador') or 'igual'
            esquerda = contexto.resolver(regra.get('esquerda', ''))
            direita = contexto.resolver(regra.get('direita', ''))
            if _comparar(esquerda, operador, direita):
                return NodeResult(output={'saida': saida}, branch=saida)
        return NodeResult(output={'saida': None}, branch='default')
