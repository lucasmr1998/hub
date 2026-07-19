"""Interpretação de PLANO pelo que o cliente fala — por preço OU velocidade.

Corrige o caso "quero o plano de 99 reais" (cliente cita o PREÇO, não o
número da opção do menu). Determinístico e seguro: reusa a tabela oficial
robovendas.PLANOS (fonte única de verdade dos ids/valores).
"""
from __future__ import annotations

import re

from src.integracoes.robovendas import PLANOS

# Aliases de velocidade → chave canônica em PLANOS.
# Ordenado por especificidade (mais longo primeiro) pra casar "1 giga"
# antes de "1".
_VELOCIDADE_ALIASES: list[tuple[str, str]] = [
    ('2000', '2g'), ('2 giga', '2g'), ('2giga', '2g'), ('2gb', '2g'),
    ('2 gb', '2g'), ('2g', '2g'),
    ('1000', '1g'), ('1 giga', '1g'), ('1giga', '1g'), ('1gb', '1g'),
    ('1 gb', '1g'), ('1g', '1g'), ('giga', '1g'),
    ('620', '620'), ('300', '300'),
]


def _plano_por_chave(chave: str) -> dict | None:
    p = PLANOS.get(chave)
    if not p:
        return None
    return {'id_plano_rp': p['id_plano_rp'], 'valor': p['valor'],
            'titulo': p['titulo'], 'chave': chave}


def resolver_plano(mensagem: str) -> dict | None:
    """Tenta resolver o plano citado. Retorna dados do plano ou None.

    Prioridade: preço (99/99,90) → velocidade (620, 1 giga, 1000...).
    None quando não dá pra ter certeza — aí o fluxo segue pedindo a opção.
    """
    txt = (mensagem or '').lower().strip()
    if not txt:
        return None

    # ── 1) Por PREÇO (ex: "99", "99,90", "de 99 reais", "R$ 129") ──────
    # Conjunto de preços reais → chave (79→300, 99→620, 129→1g, 169→2g)
    precos = {int(p['valor']): chave for chave, p in PLANOS.items()}
    for token in re.findall(r'\d+(?:[.,]\d{1,2})?', txt):
        valor = float(token.replace(',', '.'))
        reais = int(valor)
        if reais in precos:
            # evita confundir com velocidade (620, 300, 1000, 2000 não são preços)
            return _plano_por_chave(precos[reais])

    # ── 2) Por VELOCIDADE (alias textual) ─────────────────────────────
    # normaliza separadores pra casar "1 giga", "620 mega", etc.
    norm = re.sub(r'\s+', ' ', txt)
    for alias, chave in _VELOCIDADE_ALIASES:
        if re.search(rf'(?<!\d){re.escape(alias)}(?!\d)', norm):
            return _plano_por_chave(chave)

    return None
