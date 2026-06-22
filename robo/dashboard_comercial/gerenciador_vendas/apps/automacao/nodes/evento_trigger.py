"""Nó de gatilho Evento do sistema — dispara quando algo acontece no Hubtrix.

Config: o `evento` (lead_criado, mensagem_recebida, oportunidade_movida…) + `filtros`
(condições nos subcampos do evento; todas precisam bater). O contexto do evento entra
no fluxo (entidades → {{lead.…}}, escalares → {{var.…}}).

A avaliação dos filtros + a assinatura dos signals é feita pelo dispatcher (fase
de wiring). Aqui o nó só carrega a config e, em teste, passa adiante.
"""
from .base import BaseNode, NodeResult, registrar
from ..eventos import opcoes_eventos


@registrar
class EventoTriggerNode(BaseNode):
    tipo = "evento"
    label = "Evento do sistema"
    icone = "bi-broadcast"
    categoria = "core"
    grupo = "Gatilho"
    subgrupo = "Sistema"
    saidas = ["default"]
    is_trigger = True

    def campos_config(self) -> list:
        return [
            {'nome': 'evento', 'label': 'Evento', 'tipo': 'select',
             'opcoes': opcoes_eventos()},
            {'nome': 'filtros', 'label': 'Filtros (todos precisam bater)', 'tipo': 'filtros',
             'ajuda': 'Os campos disponíveis dependem do evento escolhido.'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        return NodeResult(output={'evento': config.get('evento')}, branch='default')
