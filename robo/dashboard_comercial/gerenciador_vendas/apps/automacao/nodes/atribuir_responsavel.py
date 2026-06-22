"""Nó `atribuir_responsavel` — atribui vendedor à oportunidade (via service).

Convergência do motor de marketing (`_acao_atribuir_responsavel`). Modo
`round-robin` (agente menos carregado) ou `fixo` (por username).
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import atribuir_responsavel


@registrar
class AtribuirResponsavelNode(BaseNode):
    tipo = "atribuir_responsavel"
    label = "Atribuir responsável"
    icone = "bi-person-check"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'modo', 'label': 'Modo', 'tipo': 'select', 'opcoes': ['round-robin', 'fixo']},
            {'nome': 'username', 'label': 'Usuário (modo fixo)', 'tipo': 'texto',
             'fonte': 'responsaveis', 'ajuda': 'Só no modo fixo: o responsável.'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        modo = str(contexto.resolver(config.get('modo', '')) or 'round-robin').strip() or 'round-robin'
        username = str(contexto.resolver(config.get('username', '')) or '').strip()
        try:
            user = atribuir_responsavel(
                contexto.tenant, oportunidade=contexto.oportunidade, lead=contexto.lead,
                modo=modo, username=username,
            )
        except Exception as e:
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(output={'responsavel': user.get_full_name() or user.username}, branch='sucesso')
