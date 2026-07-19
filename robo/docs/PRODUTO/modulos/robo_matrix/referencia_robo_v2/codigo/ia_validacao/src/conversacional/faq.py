"""Passo 3 — Resposta a perguntas do cliente (FAQ) + emenda da próxima etapa.

Quando o cliente faz uma dúvida no meio do fluxo, geramos UMA mensagem
que: (a) responde a dúvida a partir do FAQ_BASE (sem inventar), e
(b) retoma naturalmente a próxima pergunta do fluxo. Assim o cliente tira
a dúvida sem precisar transbordar pra atendente.
"""
from __future__ import annotations

import logging

from src.conversacional.cliente_llm import chat_texto
from src.conversacional.config import conv_config, FAQ_BASE

logger = logging.getLogger(__name__)


_SYSTEM_RESPOSTA = (
    f"Você é {conv_config.PERSONA_NOME}, atendente virtual da "
    f"{conv_config.PERSONA_EMPRESA} no WhatsApp, durante um cadastro de venda.\n\n"
    "Você vai gerar UMA mensagem curta que faz DUAS coisas em sequência:\n"
    "1. Responde a dúvida do cliente usando SOMENTE os fatos fornecidos.\n"
    "   Se a resposta não estiver nos fatos, diga gentilmente que um "
    "atendente confirma esse detalhe — NÃO invente.\n"
    "2. Em seguida, retoma com NATURALIDADE a próxima pergunta do cadastro "
    "(fornecida abaixo), PRESERVANDO opções numeradas e formatos exigidos.\n\n"
    "REGRAS:\n"
    "- Não invente valores, prazos ou promessas fora dos fatos.\n"
    "- Seja concisa (WhatsApp). Emojis com moderação.\n"
    "- Preserve opções numeradas (1, 2, 3) e formatos exatamente.\n"
    "- Mantenha negrito do WhatsApp (*texto*) quando útil.\n\n"
    "Responda APENAS com a mensagem final, sem aspas nem explicação."
)


def responder_e_emendar(
    pergunta_cliente: str,
    proxima_pergunta_base: str,
    *,
    primeiro_nome: str = '',
) -> str | None:
    """Responde a dúvida + emenda a próxima pergunta. None se falhar/desligado."""
    if not conv_config.PASSO3_FAQ or not pergunta_cliente.strip():
        return None

    user = (
        f'FATOS DISPONÍVEIS:\n{FAQ_BASE}\n\n'
        f'Primeiro nome do cliente: {primeiro_nome or "—"}\n\n'
        f'DÚVIDA DO CLIENTE: "{pergunta_cliente}"\n\n'
        f'PRÓXIMA PERGUNTA DO CADASTRO (retomar após responder):\n'
        f'"""{proxima_pergunta_base}"""'
    )
    return chat_texto(_SYSTEM_RESPOSTA, user, temperatura=0.4, max_tokens=450)
