"""Nó `adicionar_item_oportunidade` — vincula o plano escolhido pelo cliente
(`lead.id_plano_rp`) como ItemOportunidade na oportunidade.

Migração da automação do funil (Fase 1): porta a lógica pro motor novo via
`services/acoes.py` (autossuficiente — não importa do motor antigo do CRM, que roda
2 clientes vivos e não pode ser tocado). Precisa de `oportunidade` no contexto.

Ação local (ORM), sem integração externa → sem seletor de credencial.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import adicionar_item_oportunidade


@registrar
class AdicionarItemOportunidadeNode(BaseNode):
    tipo = "adicionar_item_oportunidade"
    label = "Adicionar item da oportunidade"
    icone = "bi-bag-plus"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'quantidade', 'label': 'Quantidade', 'tipo': 'numero',
             'placeholder': '1',
             'ajuda': 'Quantidade do item vinculado. Vazio = 1. O produto vem de lead.id_plano_rp.'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        quantidade = contexto.resolver(config.get('quantidade', '')) or 1
        try:
            item, criado, motivo = adicionar_item_oportunidade(
                contexto.tenant, oportunidade=contexto.oportunidade, quantidade=quantidade)
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(
            output={'criado': criado,
                    'motivo': motivo or None,
                    'produto': item.produto.nome if criado and item else None,
                    'valor_unitario': str(item.valor_unitario) if criado and item else None},
            branch='sucesso')
