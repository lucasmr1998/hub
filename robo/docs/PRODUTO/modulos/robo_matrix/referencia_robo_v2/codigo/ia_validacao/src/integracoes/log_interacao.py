"""Cliente HTTP pra persistir logs de interação no Django.

Dispara POSTs em thread daemon — nunca bloqueia a resposta da API IA.
Erros são silenciados (log local) pra não derrubar o atendimento.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


_cliente: httpx.Client | None = None


def _get_cliente(base_url: str) -> httpx.Client:
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(10.0, connect=3.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )
    return _cliente


def _enviar_log(base_url: str, payload: dict[str, Any]) -> None:
    """Faz o POST efetivo. Executado em thread daemon."""
    try:
        cliente = _get_cliente(base_url)
        cliente.post('/ia_validador/api/ia/log-interacao/', json=payload, timeout=10.0)
    except Exception as e:
        logger.debug('Falha enviar log-interacao: %s', e)


def registrar_log(
    base_url: str,
    *,
    endpoint: str,
    cellphone: str = '',
    lead_id: int | str | None = None,
    question_id: str = '',
    answer: str = '',
    mensagem_resposta: str = '',
    payload_in: dict | None = None,
    payload_out: dict | None = None,
    duracao_ms: int | None = None,
    valido: bool | None = None,
    transbordou: bool = False,
    motivo: str = '',
) -> None:
    """Agenda um log pro Django em background (não bloqueia).

    Sempre seguro chamar — exceções são silenciadas.
    """
    if not base_url:
        return
    payload = {
        'endpoint': endpoint,
        'cellphone': cellphone or '',
        'lead_id': lead_id,
        'question_id': question_id or '',
        'answer': (answer or '')[:5000],
        'mensagem_resposta': (mensagem_resposta or '')[:5000],
        'payload_in':  payload_in  or {},
        'payload_out': payload_out or {},
        'duracao_ms':  duracao_ms,
        'valido':      valido,
        'transbordou': bool(transbordou),
        'motivo':      (motivo or '')[:200],
    }
    try:
        t = threading.Thread(
            target=_enviar_log, args=(base_url, payload), daemon=True,
        )
        t.start()
    except Exception as e:
        logger.debug('Falha agendar thread de log: %s', e)


class TimerLog:
    """Contexto pra medir duração de uma chamada.

    Uso:
        with TimerLog() as t:
            ... lógica ...
        registrar_log(..., duracao_ms=t.duracao_ms)
    """

    def __init__(self) -> None:
        self.inicio: float = 0.0
        self.duracao_ms: int = 0

    def __enter__(self) -> 'TimerLog':
        self.inicio = time.time()
        return self

    def __exit__(self, *args) -> None:
        self.duracao_ms = int((time.time() - self.inicio) * 1000)
