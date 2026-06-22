"""Nó `if` — ramifica o fluxo por uma condição. Saídas: `true` / `false`."""
from .base import BaseNode, NodeResult, registrar

OPERADORES = {
    'igual', 'diferente', 'contem', 'nao_contem',
    'maior', 'menor', 'maior_igual', 'menor_igual',
    'vazio', 'nao_vazio',
}


def _num(v):
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _comparar(a, operador, b):
    txt_a = '' if a is None else str(a)
    txt_b = '' if b is None else str(b)
    if operador == 'vazio':
        return not txt_a.strip()
    if operador == 'nao_vazio':
        return bool(txt_a.strip())
    if operador in ('maior', 'menor', 'maior_igual', 'menor_igual'):
        na, nb = _num(a), _num(b)
        if na is None or nb is None:
            return False
        return {
            'maior': na > nb, 'menor': na < nb,
            'maior_igual': na >= nb, 'menor_igual': na <= nb,
        }[operador]
    if operador == 'igual':
        return txt_a.strip() == txt_b.strip()
    if operador == 'diferente':
        return txt_a.strip() != txt_b.strip()
    if operador == 'contem':
        return txt_b in txt_a
    if operador == 'nao_contem':
        return txt_b not in txt_a
    return False


@registrar
class IfNode(BaseNode):
    tipo = "if"
    label = "Condição (If)"
    icone = "bi-signpost-split"
    categoria = "core"
    grupo = "Fluxo"
    subgrupo = "Lógica"
    saidas = ["true", "false"]

    def campos_config(self) -> list:
        return [
            {'nome': 'esquerda', 'label': 'Valor', 'tipo': 'texto',
             'placeholder': '{{var.score}}'},
            {'nome': 'operador', 'label': 'Operador', 'tipo': 'select',
             'opcoes': sorted(OPERADORES), 'obrigatorio': True},
            {'nome': 'direita', 'label': 'Comparar com', 'tipo': 'texto', 'placeholder': '7'},
        ]

    def validar_config(self, config) -> list:
        if config.get('operador') not in OPERADORES:
            return [f"`operador` inválido (use um de: {', '.join(sorted(OPERADORES))})."]
        return []

    def executar(self, config, entrada, contexto) -> NodeResult:
        a = contexto.resolver(config.get('esquerda', ''))
        b = contexto.resolver(config.get('direita', ''))
        resultado = _comparar(a, config.get('operador'), b)
        return NodeResult(output={'resultado': resultado}, branch='true' if resultado else 'false')
