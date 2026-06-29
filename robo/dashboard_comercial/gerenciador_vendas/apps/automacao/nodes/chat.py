"""Nó `chat` — gatilho de teste estilo n8n.

Marca o fluxo como testável pelo painel "Chat" do editor: cada mensagem digitada
roda o fluxo com `var.conteudo` = a mensagem. Em execução, é só o ponto de entrada
(sem porta de entrada, como todo trigger) e repassa a mensagem adiante.
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class ChatNode(BaseNode):
    tipo = "chat"
    label = "Chat (teste)"
    icone = "bi-chat-dots"
    categoria = "core"
    grupo = "Gatilho"
    subgrupo = "Teste"
    saidas = ["default"]
    is_trigger = True

    def executar(self, config, entrada, contexto) -> NodeResult:
        msg = str((contexto.variaveis or {}).get('conteudo', '') or '')
        return NodeResult(output={'conteudo': msg}, branch='default')
