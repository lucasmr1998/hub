"""Wrapper fino do OpenAI pra camada conversacional.

Centraliza a criação do client + chamada de chat com JSON estruturado,
modelo configurável e tratamento de erro silencioso (retorna None em vez
de derrubar o atendimento).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

from src.conversacional.config import conv_config

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get('OPENAI_API_KEY', '').strip()
        if not key:
            try:
                from src.config import config as _cfg
                key = (_cfg.OPENAI_API_KEY or '').strip()
            except Exception:
                pass
        if not key:
            raise RuntimeError('OPENAI_API_KEY não configurado')
        _client = OpenAI(api_key=key)
    return _client


def chat_json(
    system: str,
    user: str,
    *,
    modelo: str | None = None,
    temperatura: float = 0.3,
    max_tokens: int = 600,
) -> dict[str, Any] | None:
    """Chama o LLM forçando resposta JSON. Retorna dict ou None em erro."""
    modelo = modelo or conv_config.MODELO_CONVERSA
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=modelo,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            temperature=temperatura,
            max_tokens=max_tokens,
            timeout=conv_config.TIMEOUT,
        )
        conteudo = resp.choices[0].message.content or '{}'
        return json.loads(conteudo)
    except json.JSONDecodeError as e:
        logger.warning('chat_json: resposta não-JSON (%s): %s', modelo, e)
        return None
    except Exception as e:
        logger.warning('chat_json falhou (%s): %s', modelo, e)
        return None


def chat_texto(
    system: str,
    user: str,
    *,
    modelo: str | None = None,
    temperatura: float = 0.5,
    max_tokens: int = 400,
) -> str | None:
    """Chama o LLM esperando texto livre. Retorna str ou None em erro."""
    modelo = modelo or conv_config.MODELO_CONVERSA
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            temperature=temperatura,
            max_tokens=max_tokens,
            timeout=conv_config.TIMEOUT,
        )
        return (resp.choices[0].message.content or '').strip()
    except Exception as e:
        logger.warning('chat_texto falhou (%s): %s', modelo, e)
        return None
