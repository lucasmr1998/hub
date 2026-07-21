"""Nó `checklist_respostas`: o que a entidade (lead ou oportunidade) já
respondeu nesse checklist, como um dicionário `chave -> valor`.

Peça que faltava pra um nó adiante usar resposta de turno ANTERIOR. Até aqui o
grafo só enxergava a resposta do turno corrente (`checklist_validar`) e a
CONTAGEM do andamento (`checklist_progresso`), nunca os valores. Sem isso não
dá pra montar, por exemplo, a consulta de viabilidade: ela precisa do CEP, do
número e da cidade, que vieram de perguntas respondidas antes.

Cada resposta vira uma chave do output, então o resto do grafo referencia
direto: `{{nodes.<handle>.cep}}`, `{{nodes.<handle>.cidade}}`.

Ponte fina pro `services/checklist.respostas_da_entidade` (motor de verdade);
sem IA e sem lógica própria além de resolver `checklist`/`entidade` da config.
"""
from .base import BaseNode, NodeResult, registrar
from .checklist_base import campo_checklist, campo_entidade, carregar_checklist, entidade_de
from ..models import Checklist
from ..services.checklist import respostas_da_entidade


@registrar
class ChecklistRespostasNode(BaseNode):
    tipo = "checklist_respostas"
    label = "Checklist: respostas"
    icone = "bi-list-check"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Checklist"
    # `vazio` separado de `sucesso`: entidade que ainda não respondeu nada é
    # caso normal (começo de conversa), não erro. Quem chama decide o que
    # fazer, em vez de seguir com um dicionário vazio e falhar mais adiante.
    saidas = ["sucesso", "vazio", "erro"]

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

        respostas = respostas_da_entidade(checklist, entidade_tipo, entidade.pk)
        # `_total` com underscore pra não colidir com uma chave de item que se
        # chame "total" (nada impede alguém de criar um item com essa chave).
        saida = {**respostas, '_total': len(respostas)}
        return NodeResult(output=saida, branch='sucesso' if respostas else 'vazio')
