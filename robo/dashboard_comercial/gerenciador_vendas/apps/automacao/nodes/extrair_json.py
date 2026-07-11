"""Nó `extrair_json` — parseia um JSON embutido em texto livre (ex: resposta
de um agente IA) e expõe os campos pro resto do fluxo.

Sem rede, sem ORM. Tolerante a cerca de código markdown (```json ... ```) e a
texto ao redor do objeto (recorta entre a primeira '{' e a última '}').
"""
import json
import re

from .base import BaseNode, NodeResult, registrar

_CERCA_RE = re.compile(r'```(?:json)?', re.IGNORECASE)


def _extrair_bloco_json(texto):
    """Remove cercas de código e recorta do primeiro '{' ao último '}'.

    Tolerante a texto ao redor (ex: "Aqui está: {...} Obrigado"). Sem chaves
    no texto (ex: JSON de lista pura `[...]`), devolve o texto limpo inteiro.
    """
    t = _CERCA_RE.sub('', texto).strip()
    ini, fim = t.find('{'), t.rfind('}')
    if ini != -1 and fim != -1 and fim > ini:
        return t[ini:fim + 1]
    return t


@registrar
class ExtrairJsonNode(BaseNode):
    tipo = "extrair_json"
    label = "Extrair JSON"
    icone = "bi-braces"
    categoria = "core"
    grupo = "Transformação"
    subgrupo = "JSON"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'origem', 'label': 'Origem', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{nodes.agente.resposta}}',
             'ajuda': 'Texto contendo JSON (aceita cerca de código).'},
            {'nome': 'salvar_em', 'label': 'Salvar em', 'tipo': 'texto',
             'ajuda': 'Opcional: promove os campos pra var.<nome>.'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('origem') or '').strip() else ['`origem` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        bruto = contexto.resolver(config.get('origem', ''))
        if isinstance(bruto, (dict, list)):
            parsed = bruto
        else:
            texto = str(bruto or '').strip()
            if not texto:
                return NodeResult(status='erro', branch='erro', erro='`origem` vazia.')
            try:
                parsed = json.loads(_extrair_bloco_json(texto))
            except (TypeError, ValueError) as exc:
                return NodeResult(status='erro', branch='erro', erro=f'JSON inválido: {exc}')

        output = parsed if isinstance(parsed, dict) else {'valor': parsed}
        salvar_em = (config.get('salvar_em') or '').strip()
        promote = {salvar_em: parsed} if salvar_em else None
        return NodeResult(output=output, promote=promote, branch='sucesso')
