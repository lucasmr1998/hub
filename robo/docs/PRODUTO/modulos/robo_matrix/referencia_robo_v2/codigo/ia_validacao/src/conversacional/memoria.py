"""Memória de conversa da camada conversacional (ISOLADA).

Cada telefone tem um registro próprio com:
  - histórico de turnos (cliente disse / bot respondeu)
  - última pergunta feita (pra saber o que o cliente está respondendo)
  - tentativas por pergunta (pra escalar a resposta de erro / transbordar)
  - flags de sessão (sessao_iniciada, retomada_resolvida)
  - timestamps (criado / atualizado)

Store próprio em memória (não compartilha com o contexto do determinístico).
Thread-safe. TTL configurável — sessão "nova" quando expira.

Para produção multi-worker, trocar o _store por Redis sem mudar a API.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turno:
    """Um par pergunta-resposta da conversa."""
    cliente: str          # o que o cliente disse
    bot: str              # o que o bot respondeu
    pergunta_id: str      # qual etapa estava em jogo
    ts: float


@dataclass
class EstadoConversa:
    telefone: str
    historico: list[Turno] = field(default_factory=list)
    ultima_pergunta_id: str = ''
    tentativas: dict[str, int] = field(default_factory=dict)
    flags: dict[str, Any] = field(default_factory=dict)
    criado: float = 0.0
    atualizado: float = 0.0


class MemoriaConversa:
    def __init__(self, ttl_segundos: int = 3600, max_turnos: int = 30):
        self._store: dict[str, EstadoConversa] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_segundos
        self._max_turnos = max_turnos

    # ── ciclo de vida ────────────────────────────────────────────────
    def _expirar(self, agora: float) -> None:
        mortos = [t for t, e in self._store.items()
                  if agora - e.atualizado > self._ttl]
        for t in mortos:
            self._store.pop(t, None)

    def obter(self, telefone: str) -> EstadoConversa:
        """Retorna o estado da conversa. Cria se não existir."""
        with self._lock:
            agora = time.time()
            self._expirar(agora)
            est = self._store.get(telefone)
            if est is None:
                est = EstadoConversa(telefone=telefone, criado=agora, atualizado=agora)
                self._store[telefone] = est
            return est

    def sessao_nova(self, telefone: str) -> bool:
        """True se é a PRIMEIRA mensagem de uma sessão (sem histórico ainda).

        Usado pra decidir se mostra retomar/recomeçar. Como o estado expira
        pelo TTL, um cliente que volta depois de 1h+ é tratado como sessão
        nova — comportamento desejado.
        """
        est = self.obter(telefone)
        return len(est.historico) == 0 and not est.flags.get('sessao_iniciada')

    def marcar_sessao_iniciada(self, telefone: str) -> None:
        est = self.obter(telefone)
        est.flags['sessao_iniciada'] = True
        est.atualizado = time.time()

    # ── turnos / histórico ───────────────────────────────────────────
    def registrar_turno(self, telefone: str, cliente: str, bot: str,
                         pergunta_id: str = '') -> None:
        est = self.obter(telefone)
        est.historico.append(Turno(cliente=cliente, bot=bot,
                                    pergunta_id=pergunta_id, ts=time.time()))
        est.historico = est.historico[-self._max_turnos:]
        est.atualizado = time.time()

    def historico_texto(self, telefone: str, ultimos: int = 6) -> str:
        """Histórico recente formatado pra dar contexto ao LLM."""
        est = self.obter(telefone)
        linhas = []
        for t in est.historico[-ultimos:]:
            if t.cliente:
                linhas.append(f'Cliente: {t.cliente}')
            if t.bot:
                linhas.append(f'Bot: {t.bot}')
        return '\n'.join(linhas)

    # ── última pergunta (o que o cliente está respondendo) ───────────
    def ultima_pergunta(self, telefone: str) -> str:
        return self.obter(telefone).ultima_pergunta_id

    def set_ultima_pergunta(self, telefone: str, pergunta_id: str) -> None:
        est = self.obter(telefone)
        est.ultima_pergunta_id = pergunta_id or ''
        est.atualizado = time.time()

    # ── tentativas (pra escalar erro / transbordar) ──────────────────
    def incrementar_tentativa(self, telefone: str, pergunta_id: str) -> int:
        est = self.obter(telefone)
        est.tentativas[pergunta_id] = est.tentativas.get(pergunta_id, 0) + 1
        est.atualizado = time.time()
        return est.tentativas[pergunta_id]

    def tentativas_de(self, telefone: str, pergunta_id: str) -> int:
        return self.obter(telefone).tentativas.get(pergunta_id, 0)

    def resetar_tentativa(self, telefone: str, pergunta_id: str) -> None:
        est = self.obter(telefone)
        est.tentativas.pop(pergunta_id, None)
        est.atualizado = time.time()

    # ── flags livres ─────────────────────────────────────────────────
    def get_flag(self, telefone: str, chave: str, default=None):
        return self.obter(telefone).flags.get(chave, default)

    def set_flag(self, telefone: str, chave: str, valor) -> None:
        est = self.obter(telefone)
        est.flags[chave] = valor
        est.atualizado = time.time()

    def limpar(self, telefone: str) -> None:
        """Esquece a conversa (ex: cliente encerrou)."""
        with self._lock:
            self._store.pop(telefone, None)


# Instância única da camada conversacional (separada do determinístico)
memoria = MemoriaConversa()
