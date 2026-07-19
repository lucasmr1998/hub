"""Cliente HTTP para as MENSAGENS DO ROBÔ configuráveis (app Django ia_validador).

Busca chave→texto do Django + cache em memória (TTL 1h), igual ao regras_client.
O engine resolve cada mensagem via `mensagens_client.texto(chave, default)`:
- se houver override ativo e não-vazio no banco → usa o override;
- senão → usa o texto PADRÃO embutido no código (nada quebra se apagar).

Cache invalidado quando uma mensagem é editada na ferramenta (POST
/admin/invalidar-cache/ na API IA chama tanto regras quanto mensagens).
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

from src.config import config

logger = logging.getLogger(__name__)


class MensagensClient:
    """Cache em memória das mensagens do robô (chave → {texto, ativo})."""

    def __init__(self, base_url: str, ttl_segundos: int = 3600):
        self.base_url = base_url.rstrip('/')
        self.ttl = ttl_segundos
        self._cache: dict[str, dict] = {}
        self._ultima_carga: float = 0
        self._lock = threading.Lock()
        self._http = httpx.Client(timeout=10.0)

    def _precisa_recarregar(self) -> bool:
        return (time.time() - self._ultima_carga) > self.ttl or not self._cache

    def _recarregar_se_necessario(self):
        with self._lock:
            if not self._precisa_recarregar():
                return
            try:
                r = self._http.get(f'{self.base_url}/ia_validador/api/mensagens-robo/')
                r.raise_for_status()
                d = r.json()
                self._cache = {m['chave']: m for m in d.get('mensagens', [])}
                self._ultima_carga = time.time()
                logger.info('Cache de mensagens do robô atualizado: %d', len(self._cache))
            except Exception as e:  # noqa: BLE001
                logger.warning('Falha ao carregar mensagens do Django: %s', e)

    def invalidar_cache(self):
        with self._lock:
            self._cache.clear()
            self._ultima_carga = 0
        logger.info('Cache de mensagens do robô invalidado por sinal externo')

    def texto(self, chave: str, default: str = '') -> str:
        """Texto configurado da chave; cai no `default` se vazio/ausente/erro."""
        try:
            self._recarregar_se_necessario()
            m = self._cache.get(chave)
            if m and m.get('ativo', True):
                t = (m.get('texto') or '').strip()
                if t:
                    return t
        except Exception:  # noqa: BLE001
            pass
        return default


mensagens_client = MensagensClient(base_url=config.ROBOVENDAS_API_URL)
