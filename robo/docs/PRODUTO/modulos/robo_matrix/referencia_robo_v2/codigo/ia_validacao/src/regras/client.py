"""Cliente HTTP para o app Django `ia_validador`.

Busca regras do Django + cache em memória (TTL 1h).
Suporta:
- lookup por question_id (rápido)
- inferência por texto da pergunta (chama OpenAI; resultado cacheado também)

Cache invalidado automaticamente quando uma regra é editada no admin Django
(via signal do Django que chama POST /admin/invalidar-cache/ na API IA).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from src.config import config

logger = logging.getLogger(__name__)


class RegrasClient:
    """Cliente com cache em memória das regras de validação."""

    def __init__(self, base_url: str, ttl_segundos: int = 3600):
        self.base_url = base_url.rstrip('/')
        self.ttl = ttl_segundos
        self._cache_regras: dict[str, dict] = {}              # question_id → regra
        self._cache_inferencia: dict[str, tuple[str, float]] = {}  # texto pergunta → (question_id, timestamp)
        self._ultima_carga: float = 0
        self._lock = threading.Lock()
        self._http = httpx.Client(timeout=10.0)

    # ── carga & invalidação ─────────────────────────────────────────

    def _precisa_recarregar(self) -> bool:
        return (time.time() - self._ultima_carga) > self.ttl or not self._cache_regras

    def _recarregar_se_necessario(self):
        with self._lock:
            if not self._precisa_recarregar():
                return
            try:
                r = self._http.get(f'{self.base_url}/ia_validador/api/regras-validacao/')
                r.raise_for_status()
                d = r.json()
                self._cache_regras = {reg['question_id']: reg for reg in d.get('regras', [])}
                self._ultima_carga = time.time()
                logger.info(f'Cache de regras atualizado: {len(self._cache_regras)} regras')
            except Exception as e:
                logger.warning(f'Falha ao carregar regras do Django: {e}')

    def invalidar_cache(self):
        """Força reload na próxima consulta (chamado pelo endpoint /admin/invalidar-cache/)."""
        with self._lock:
            self._cache_regras.clear()
            self._cache_inferencia.clear()
            self._ultima_carga = 0
        logger.info('Cache de regras invalidado por sinal externo')

    # ── lookup ──────────────────────────────────────────────────────

    def obter_por_id(self, question_id: str) -> dict | None:
        """Lookup direto por question_id."""
        if not question_id:
            return None
        self._recarregar_se_necessario()
        regra = self._cache_regras.get(question_id)
        if regra is None and question_id.startswith('confirmacao_plano_'):
            # Títulos de URA específicos por plano (confirmacao_plano_620/1g/
            # 1g_ponto_adc) validam com a MESMA regra confirmacao_plano.
            regra = self._cache_regras.get('confirmacao_plano')
        return regra

    # Keywords pra inferência rápida (ordem importa — mais específico antes)
    KEYWORDS_REGRA = [
        # tuple: (lista de palavras-chave que devem aparecer juntas, question_id)
        # As listas internas exigem TODAS as palavras presentes na pergunta
        (['cpf'], 'coleta_cpf'),
        (['cep'], 'coleta_cep'),
        (['nome', 'completo'], 'coleta_nome'),
        (['data', 'nascimento'], 'coleta_data_nascimento'),
        (['e-mail'], 'coleta_email'),
        (['email'], 'coleta_email'),
        (['rg'], 'coleta_rg'),
        (['número', 'endereço'], 'coleta_numero'),
        (['numero', 'endereço'], 'coleta_numero'),
        (['número', 'residência'], 'coleta_numero'),
        (['numero', 'residencia'], 'coleta_numero'),
        (['ponto', 'referência'], 'coleta_ponto_referencia'),
        (['ponto', 'referencia'], 'coleta_ponto_referencia'),
        (['bairro'], 'coleta_bairro'),
        (['rua'], 'coleta_rua'),
        (['cidade'], 'coleta_cidade'),
        (['casa', 'empresa'], 'tipo_imovel'),
        (['confirme'], 'confirmacao_dados'),
        (['está tudo certo'], 'confirmacao_dados'),
        (['esta tudo certo'], 'confirmacao_dados'),
        (['posso seguir'], 'confirmacao_dados'),
        (['confirma'], 'confirmacao_dados'),
        (['selfie'], 'documentacao_selfie'),
        (['frente'], 'documentacao_frente_doc'),
        (['verso', 'documento'], 'documentacao_verso_doc'),
        (['trás', 'rg'], 'documentacao_verso_doc'),
        (['turno'], 'escolha_turno'),
        (['manhã', 'tarde'], 'escolha_turno'),
        (['data', 'instalação'], 'escolha_data'),
        (['vencimento'], 'dia_vencimento'),
        (['plano'], 'escolha_plano'),
        (['oi'], 'cumprimento'),
        (['olá'], 'cumprimento'),
        (['ola'], 'cumprimento'),
    ]

    def inferir_por_pergunta(self, pergunta: str, openai_inferir_fn=None) -> dict | None:
        """Tenta inferir qual regra aplicar pelo texto da pergunta.

        Cascata:
        1. Cache de inferência (válido por TTL)
        2. Match exato com `pergunta_padrao` da regra
        3. **Keywords-based matching** (rápido e robusto a variações de texto)
        4. Substring match (primeiros 40 chars)
        5. Fallback OpenAI (se configurado)
        """
        if not pergunta or not pergunta.strip():
            return None

        chave = pergunta.strip().lower()
        self._recarregar_se_necessario()

        # 1) Cache de inferência
        cached = self._cache_inferencia.get(chave)
        if cached and (time.time() - cached[1]) < self.ttl:
            qid = cached[0]
            return self._cache_regras.get(qid)

        # 2) Match exato
        for qid, regra in self._cache_regras.items():
            if regra.get('pergunta_padrao', '').strip().lower() == chave:
                self._cache_inferencia[chave] = (qid, time.time())
                return regra

        # 3) Keywords-based — mais robusto a variações de texto
        chave_norm = chave.replace('-', ' ').replace('.', ' ').replace(',', ' ')
        chave_norm = ' '.join(chave_norm.split())
        for keywords, qid in self.KEYWORDS_REGRA:
            if all(kw in chave_norm for kw in keywords):
                regra = self._cache_regras.get(qid)
                if regra:
                    self._cache_inferencia[chave] = (qid, time.time())
                    logger.info(f'Inferência por keywords {keywords} → {qid}')
                    return regra

        # 4) Substring match — primeiros 40 chars da pergunta_padrao
        for qid, regra in self._cache_regras.items():
            pp = regra.get('pergunta_padrao', '').strip().lower()
            if not pp:
                continue
            primeiros = pp[:40]
            if primeiros and primeiros in chave:
                self._cache_inferencia[chave] = (qid, time.time())
                return regra

        # 5) Fallback OpenAI
        if openai_inferir_fn and config.USAR_CACHE_INFERENCIA:
            try:
                opcoes = [(qid, r.get('pergunta_padrao', '')) for qid, r in self._cache_regras.items()]
                qid_escolhido = openai_inferir_fn(pergunta, opcoes)
                if qid_escolhido and qid_escolhido in self._cache_regras:
                    self._cache_inferencia[chave] = (qid_escolhido, time.time())
                    return self._cache_regras[qid_escolhido]
            except Exception as e:
                logger.warning(f'Inferência via OpenAI falhou: {e}')

        return None

    # ── debug ───────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            'regras_em_cache': len(self._cache_regras),
            'inferencias_em_cache': len(self._cache_inferencia),
            'ultima_carga_h_atras': round((time.time() - self._ultima_carga) / 3600, 2) if self._ultima_carga else None,
            'ttl_segundos': self.ttl,
        }


regras_client = RegrasClient(base_url=config.ROBOVENDAS_API_URL)
