"""Nó `responder_webhook` — define a resposta HTTP de um fluxo disparado por webhook.

É o "Respond to Webhook" do n8n: coloque-o no fluxo e, quando o webhook roda (síncrono),
a view devolve o `status`+`corpo` definidos aqui em vez da resposta padrão. O corpo é
resolvido (`{{...}}`) e promovido em `_resposta_webhook`, que a `webhook_receber` lê.
"""
import json

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
             'ajuda': 'JSON ou texto. Aceita {{...}} (ex: {{nodes.<nó>.campo}}). Quando o '
                      'corpo é um objeto/lista JSON válido, cada valor é resolvido '
                      'preservando o tipo (bool/número/lista) e o JSON final é escapado '
                      'corretamente (aceita texto com quebra de linha/aspas sem quebrar '
                      'o parse do outro lado).'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        try:
            status = int(config.get('status') or 200)
        except (ValueError, TypeError):
            status = 200
        corpo = self._resolver_corpo(config.get('corpo', ''), contexto)
        return NodeResult(
            output={'status': status, 'corpo': corpo},
            promote={'_resposta_webhook': {'status': status, 'corpo': corpo}},
            branch='sucesso',
        )

    @staticmethod
    def _resolver_corpo(bruto, contexto):
        """Resolve o `corpo`, escapando JSON de verdade quando o template já é
        um objeto/lista JSON (o caso recomendado pra responder um contrato
        estruturado, ex: bot de vendas falando com o Matrix).

        Achado montando esse fluxo: o caminho antigo (`str(contexto.resolver(...))`)
        faz substituição de TEXTO — um valor interpolado com quebra de linha ou
        aspas (comum em texto de pergunta/mensagem) quebra o `json.loads` que
        `webhook_receber` faz do outro lado, em silêncio (cai pro fallback
        text/plain). Quando `bruto` é JSON válido, resolve `{{...}}` nas FOLHAS
        (`Contexto.resolver` em dict/lista preserva tipo — bool/número/lista
        passam crus) e serializa com `json.dumps` (escapa de verdade). Texto
        puro ou JSON inválido cai no caminho antigo, sem mudança de
        comportamento (compatibilidade com fluxos existentes)."""
        if isinstance(bruto, str) and bruto.strip()[:1] in ('{', '['):
            try:
                template = json.loads(bruto)
            except (ValueError, TypeError):
                template = None
            if template is not None:
                resolvido = contexto.resolver(template)
                return json.dumps(resolvido, ensure_ascii=False)
        return str(contexto.resolver(bruto) or '')
