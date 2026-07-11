"""Nó `marcar_dados_custom`: grava um par chave/valor em `dados_custom` da
oportunidade. Sem `valor`, grava o timestamp atual (marcador de "processado em").
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import marcar_dados_custom


@registrar
class MarcarDadosCustomNode(BaseNode):
    tipo = "marcar_dados_custom"
    label = "Marcar dado customizado"
    icone = "bi-bookmark-plus"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'chave', 'label': 'Chave', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': 'analise_perda'},
            {'nome': 'valor', 'label': 'Valor', 'tipo': 'texto', 'ajuda': 'Vazio = data/hora atual'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('chave') or '').strip() else ['`chave` é obrigatória.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        chave = str(contexto.resolver(config.get('chave', '')) or '')
        valor = contexto.resolver(config.get('valor', ''))
        try:
            valor_gravado = marcar_dados_custom(
                contexto.tenant, oportunidade=contexto.oportunidade, chave=chave, valor=valor)
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(output={'chave': chave, 'valor': valor_gravado}, branch='sucesso')
