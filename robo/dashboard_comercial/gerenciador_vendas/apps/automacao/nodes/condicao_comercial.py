"""Nó `condicao_comercial` — avalia uma condição da engine comercial (CRM) sobre a
oportunidade do contexto. Saídas true/false.

Convergência: reusa o REGISTRY de condições de
`apps.comercial.crm.services.automacao_condicoes` — **todas** as condições (tag,
status_api, viabilidade, serviço HubSoft, converteu venda, score externo,
conversa…) ficam disponíveis num só nó, escolhidas pelo campo `tipo_condicao`.
Sem 2ª cópia da lógica de avaliação.
"""
from .base import BaseNode, NodeResult, registrar

_OPERADORES = ['igual', 'diferente', 'existe', 'nao_existe', 'todas_iguais', 'nenhuma_com']


def _tipos_condicao():
    try:
        from apps.comercial.crm.services import automacao_condicoes
        return [slug for slug, _ in automacao_condicoes.todos_tipos()]
    except Exception:
        return []


@registrar
class CondicaoComercialNode(BaseNode):
    tipo = "condicao_comercial"
    label = "Condição comercial (CRM)"
    icone = "bi-funnel"
    categoria = "comercial"
    grupo = "Fluxo"
    subgrupo = "Lógica"
    saidas = ["true", "false"]

    def campos_config(self) -> list:
        return [
            {'nome': 'tipo_condicao', 'label': 'Condição', 'tipo': 'select',
             'opcoes': _tipos_condicao(), 'obrigatorio': True},
            {'nome': 'operador', 'label': 'Operador', 'tipo': 'select',
             'opcoes': _OPERADORES, 'obrigatorio': True},
            {'nome': 'valor', 'label': 'Valor', 'tipo': 'texto'},
            {'nome': 'campo', 'label': 'Campo (só p/ "Campo do lead")', 'tipo': 'texto',
             'ajuda': 'Nome do atributo do lead, ex: cidade.'},
        ]

    def validar_config(self, config) -> list:
        erros = []
        if not (config.get('tipo_condicao') or '').strip():
            erros.append('`tipo_condicao` é obrigatório.')
        if not (config.get('operador') or '').strip():
            erros.append('`operador` é obrigatório.')
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        from apps.comercial.crm.services import automacao_condicoes

        oportunidade = contexto.oportunidade
        if oportunidade is None or not getattr(oportunidade, 'pk', None):
            return NodeResult(output={'resultado': False, 'erro': 'sem oportunidade no contexto'},
                              branch='false')
        cond = automacao_condicoes.tipo_por_slug((config.get('tipo_condicao') or '').strip())
        if cond is None:
            return NodeResult(output={'resultado': False, 'erro': 'condição desconhecida'},
                              branch='false')

        operador = (config.get('operador') or 'igual').strip()
        valor = contexto.resolver(config.get('valor', ''))
        campo = (config.get('campo') or '').strip()
        try:
            dados = {}
            cond.coletar_contexto(oportunidade, dados)
            resultado = bool(cond.avaliar(operador, valor, campo, dados))
        except Exception as exc:  # noqa: BLE001 — condição que estoura vira false (não derruba)
            return NodeResult(output={'resultado': False, 'erro': str(exc)}, branch='false')

        return NodeResult(output={'resultado': resultado}, branch='true' if resultado else 'false')
