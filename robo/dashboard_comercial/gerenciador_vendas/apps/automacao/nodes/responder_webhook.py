"""Nó `responder_webhook` — define a resposta HTTP de um fluxo disparado por webhook.

É o "Respond to Webhook" do n8n: coloque-o no fluxo e, quando o webhook roda (síncrono),
a view devolve o `status`+`corpo` definidos aqui em vez da resposta padrão. O corpo é
resolvido (`{{...}}`) e promovido em `_resposta_webhook`, que a `webhook_receber` lê.
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class ResponderWebhookNode(BaseNode):
    tipo = "responder_webhook"
    label = "Responder ao Webhook"
    icone = "bi-reply"
    categoria = "core"
    grupo = "Core"
    subgrupo = "Webhook"
    saidas = ["sucesso"]

    def campos_config(self) -> list:
        return [
            {'nome': 'status', 'label': 'Status HTTP', 'tipo': 'numero', 'placeholder': '200'},
            {'nome': 'corpo', 'label': 'Corpo da resposta', 'tipo': 'textarea',
             'placeholder': '{"ok": true}',
             'ajuda': 'JSON ou texto. Aceita {{...}} (ex: {{nodes.<nó>.campo}}).'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        try:
            status = int(config.get('status') or 200)
        except (ValueError, TypeError):
            status = 200
        corpo = str(contexto.resolver(config.get('corpo', '')) or '')
        return NodeResult(
            output={'status': status, 'corpo': corpo},
            promote={'_resposta_webhook': {'status': status, 'corpo': corpo}},
            branch='sucesso',
        )
