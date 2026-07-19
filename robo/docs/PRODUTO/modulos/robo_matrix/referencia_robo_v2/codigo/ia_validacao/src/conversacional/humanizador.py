"""Passo 1 — Humanização das mensagens.

Recebe a mensagem 'base' que o sistema determinístico geraria e reescreve
de forma mais natural e calorosa, SEM alterar o conteúdo essencial
(opções numeradas, formatos exigidos). Se a humanização falhar, devolve
a mensagem original — zero risco.
"""
from __future__ import annotations

import logging

from src.conversacional.cliente_llm import chat_texto
from src.conversacional.config import conv_config

logger = logging.getLogger(__name__)


_SYSTEM_HUMANIZAR = (
    f"Você é {conv_config.PERSONA_NOME}, atendente virtual da "
    f"{conv_config.PERSONA_EMPRESA} (provedora de internet) no WhatsApp.\n"
    "Sua tarefa: reescrever a mensagem do sistema de forma mais NATURAL, "
    "calorosa e humana, como uma vendedora simpática conversaria.\n\n"
    "REGRAS RÍGIDAS (não quebrar):\n"
    "1. PRESERVE todas as opções numeradas exatamente (ex: '1) Casa', "
    "'2) Empresa') — números e rótulos não mudam.\n"
    "2. PRESERVE formatos exigidos (ex: 'Formato: 01/01/2000', exemplos de CPF).\n"
    "3. NÃO invente informações, valores, prazos ou promessas.\n"
    "4. NÃO faça mais de uma pergunta — mantenha o foco da mensagem original.\n"
    "5. Pode usar emojis com moderação e o primeiro nome do cliente se fornecido.\n"
    "6. Seja CONCISA — WhatsApp, não e-mail. No máximo ~2 frases além das opções.\n"
    "7. Mantenha o formato de negrito do WhatsApp (*texto*) quando fizer sentido.\n\n"
    "Responda APENAS com a mensagem reescrita, sem aspas, sem explicação."
)


def humanizar_pergunta(
    mensagem_base: str,
    *,
    primeiro_nome: str = '',
    contexto: str = '',
) -> str:
    """Reescreve a mensagem de forma natural. Fallback = mensagem original."""
    if not conv_config.PASSO1_HUMANIZAR or not mensagem_base.strip():
        return mensagem_base

    partes_user = [f'Mensagem do sistema:\n"""{mensagem_base}"""']
    if primeiro_nome:
        partes_user.append(f'\nPrimeiro nome do cliente: {primeiro_nome}')
    if contexto:
        partes_user.append(f'\nContexto da conversa: {contexto}')

    resultado = chat_texto(
        _SYSTEM_HUMANIZAR,
        '\n'.join(partes_user),
        temperatura=0.6,
        max_tokens=350,
    )
    if not resultado:
        return mensagem_base
    # Guard-rail: se a humanização "perdeu" as opções numeradas que existiam
    # no original, volta pro original (segurança pro extractor determinístico).
    import re as _re
    opcoes_orig = set(_re.findall(r'(?m)^\s*\*?(\d)\)', mensagem_base))
    if opcoes_orig:
        opcoes_novas = set(_re.findall(r'(\d)\)', resultado))
        if not opcoes_orig.issubset(opcoes_novas):
            logger.info('Humanização perdeu opções — usando original')
            return mensagem_base
    return resultado
