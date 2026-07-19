"""Nó `checklist_proximo_item`: acha a próxima pergunta pendente do checklist
pra uma entidade (lead ou oportunidade) do `Contexto` do fluxo.

Ponte fina entre o checklist configurável (dado) e o grafo (decisão de
arquitetura: o bot de vendas por WhatsApp deixa de ser serviço Python e vira um
FLUXO no editor, montado com os nós que já existem). Este nó SÓ busca o item;
não tem IA nenhuma aqui dentro. Quem decide o que fazer com a pergunta
(formatar a mensagem, chamar o nó `ia_agente` pra conduzir a conversa) é o
grafo, encadeando os nós depois deste.
"""
from .base import BaseNode, NodeResult, registrar
from .checklist_base import campo_checklist, campo_entidade, carregar_checklist, entidade_de
from ..models import Checklist
from ..services.checklist import proximo_item


@registrar
class ChecklistProximoItemNode(BaseNode):
    tipo = "checklist_proximo_item"
    label = "Checklist: próximo item"
    icone = "bi-list-check"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Checklist"
    saidas = ["tem_item", "completo", "erro"]

    def campos_config(self) -> list:
        return [campo_checklist(), campo_entidade()]

    def validar_config(self, config) -> list:
        return [] if (config.get('checklist') or '').strip() else ['`checklist` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        entidade_tipo, entidade = entidade_de(config, contexto)
        if entidade is None:
            return NodeResult(status='erro', branch='erro', erro=f'Sem {entidade_tipo} no contexto.')

        try:
            checklist = carregar_checklist(contexto.tenant, config, contexto)
        except Checklist.DoesNotExist:
            slug = config.get('checklist') or ''
            return NodeResult(status='erro', branch='erro', erro=f'checklist {slug!r} não encontrado.')

        item = proximo_item(checklist, entidade_tipo, entidade.pk)
        if item is None:
            # Nada elegível ficou sem resposta: fim do roteiro pra essa entidade.
            return NodeResult(output={'checklist': checklist.slug}, branch='completo')

        output = {
            'item_id': item.pk,
            'chave': item.chave,
            'pergunta': item.pergunta,
            'tipo_resposta': item.tipo_resposta,
            'opcoes': item.opcoes,
            'ura_titulo': item.ura_titulo,
            'tipo_validacao': item.tipo_validacao,
            'instrucoes_ia': item.instrucoes_ia,
            'ordem': item.ordem,
        }
        return NodeResult(output=output, branch='tem_item')
