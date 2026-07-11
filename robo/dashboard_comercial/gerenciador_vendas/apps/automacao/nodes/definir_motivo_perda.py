"""Nó `definir_motivo_perda`: vincula um `MotivoPerda` cadastrado à oportunidade.

Ação de domínio único: resolve o motivo por nome (case-insensitive) via
`services/acoes.py`. Normalmente alimentado pelo output de um agente IA
(`motivo_nome` como template). Precisa de `oportunidade` no contexto.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import definir_motivo_perda


@registrar
class DefinirMotivoPerdaNode(BaseNode):
    tipo = "definir_motivo_perda"
    label = "Definir motivo de perda"
    icone = "bi-tag"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'motivo_nome', 'label': 'Motivo', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{var.motivo_ia}}',
             'ajuda': 'Nome do motivo de perda cadastrado no tenant. Normalmente vem do agente IA.'},
            {'nome': 'texto', 'label': 'Detalhe (texto livre)', 'tipo': 'textarea'},
            {'nome': 'somente_se_vazio', 'label': 'Só se ainda não tiver motivo', 'tipo': 'booleano',
             'ajuda': 'Padrão ligado: não sobrescreve motivo já definido na oportunidade.'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('motivo_nome') or '').strip() else ['`motivo_nome` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        motivo_nome = str(contexto.resolver(config.get('motivo_nome', '')) or '')
        texto = str(contexto.resolver(config.get('texto', '')) or '')
        somente_se_vazio = bool(config.get('somente_se_vazio', True))
        try:
            motivo, alterou = definir_motivo_perda(
                contexto.tenant, oportunidade=contexto.oportunidade, motivo_nome=motivo_nome,
                texto=texto, somente_se_vazio=somente_se_vazio)
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(output={'alterou': alterou, 'motivo': motivo.nome}, branch='sucesso')
