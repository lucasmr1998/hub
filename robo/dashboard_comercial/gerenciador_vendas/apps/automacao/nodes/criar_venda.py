"""Nó `criar_venda` — cria registro de Venda (pendente-ERP) pro lead (via service).

Convergência do motor de marketing (`_acao_criar_venda`). Idempotente: não
duplica venda pro mesmo lead. Evento típico: `docs_validados`.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import criar_venda


@registrar
class CriarVendaNode(BaseNode):
    tipo = "criar_venda"
    label = "Criar venda"
    icone = "bi-bag-check"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Vendas"
    saidas = ["sucesso", "erro"]

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.lead is None:
            return NodeResult(status='erro', branch='erro', erro='Sem lead no contexto.')
        try:
            venda, criada = criar_venda(contexto.tenant, lead=contexto.lead)
        except Exception as e:
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(
            output={'venda_id': venda.pk if venda is not None else None, 'criada': criada},
            branch='sucesso',
        )
