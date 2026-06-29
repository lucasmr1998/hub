"""Nó de gatilho Webhook — entrada do fluxo.

Um `POST /automacao/webhook/<token>/` inicia o fluxo a partir deste nó; o corpo
JSON entra como `{{var.payload}}` (e também sai deste nó como `{{nodes.<handle>.payload}}`).
O token é gerenciado no fluxo (gerado no save quando há um nó webhook).
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class WebhookTriggerNode(BaseNode):
    tipo = "webhook"
    label = "Webhook"
    icone = "bi-lightning-charge"
    categoria = "core"
    grupo = "Gatilho"
    subgrupo = "Entrada"
    saidas = ["default"]
    is_trigger = True

    def campos_config(self) -> list:
        return [
            {'nome': 'responder', 'label': 'Responder', 'tipo': 'select',
             'opcoes': ['imediato', 'ultimo_no', 'no_resposta'],
             'ajuda': 'Como o webhook responde (estilo n8n): "imediato" = devolve um ok na hora; '
                      '"ultimo_no" = devolve o output do último nó executado; "no_resposta" = use '
                      'um nó "Responder ao Webhook" no fluxo pra definir status/corpo.'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        payload = (contexto.variaveis or {}).get('payload', {})
        return NodeResult(output={'payload': payload}, branch='default')
