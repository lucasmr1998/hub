"""Nó `checklist_progresso`: resumo do andamento do checklist pra uma entidade
(lead ou oportunidade) do `Contexto`, quantos itens obrigatórios faltam,
percentual, completo ou não.

Ponte fina pro `services/checklist.progresso` (motor de verdade); sem IA, sem
lógica própria além de resolver `checklist`/`entidade` da config.
"""
from .base import BaseNode, NodeResult, registrar
from .checklist_base import campo_checklist, campo_entidade, carregar_checklist, entidade_de
from ..models import Checklist
from ..services.checklist import progresso


@registrar
class ChecklistProgressoNode(BaseNode):
    tipo = "checklist_progresso"
    label = "Checklist: progresso"
    icone = "bi-percent"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Checklist"
    saidas = ["completo", "incompleto", "erro"]

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

        resumo = progresso(checklist, entidade_tipo, entidade.pk)
        return NodeResult(output=resumo, branch='completo' if resumo['completo'] else 'incompleto')
