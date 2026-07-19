"""Motor de fluxo — decide a PRÓXIMA pergunta. PRÓPRIO do conversacional.

Substitui a dependência de onboarding.decidir_proximo_passo. Dado o estado
(dados coletados do lead ou NewService), encontra a próxima etapa pendente,
aplicando as regras de skip. Não tem efeitos colaterais (só leitura).

A decisão de ROTEAMENTO de alto nível (menu de cliente existente,
retomar/recomeçar, encerrar) fica no orquestrador — aqui é só a sequência
de coleta.
"""
from __future__ import annotations

from src.conversacional.fluxo import (
    Etapa, SEQUENCIA_VENDA, SEQUENCIA_NEW_SERVICE,
)

# Valores de nome que o api_8 cria automaticamente (placeholder do WhatsApp).
NOMES_GENERICOS = {'Lead WhatsApp', 'Cliente', 'Lead', 'Contato', '', None}


def nome_eh_generico(nome) -> bool:
    """Nome placeholder/incompleto = ainda não coletado de verdade.

    Réplica isolada da lógica do onboarding (função pura estável).
    """
    if not nome:
        return True
    s = str(nome).strip()
    if not s or s in NOMES_GENERICOS:
        return True
    if len(s) < 3:
        return True
    if len(s.split()) < 2:   # 1 palavra = display name do WhatsApp
        return True
    return False


def _campo_vazio(dados: dict, campo: str) -> bool:
    """True se o campo ainda precisa ser coletado."""
    valor = dados.get(campo)
    if campo == 'nome_razaosocial':
        return nome_eh_generico(valor)
    if isinstance(valor, bool):
        return False        # bool definido (True/False) = preenchido
    return not valor        # None / '' = vazio


def sequencia_para(em_new_service: bool) -> list[Etapa]:
    return SEQUENCIA_NEW_SERVICE if em_new_service else SEQUENCIA_VENDA


def proxima_etapa(dados: dict, em_new_service: bool = False) -> Etapa | None:
    """Primeira etapa pendente da sequência. None = tudo coletado."""
    for etapa in sequencia_para(em_new_service):
        if etapa.skip and etapa.skip(dados):
            continue
        if _campo_vazio(dados, etapa.campo):
            return etapa
    return None


def proxima_pergunta_id(dados: dict, em_new_service: bool = False) -> str:
    """question_id da próxima pergunta pendente (ou '' se completou)."""
    e = proxima_etapa(dados, em_new_service)
    return e.question_id if e else ''


def campos_preenchidos(dados: dict, em_new_service: bool = False) -> list[str]:
    """Lista de campos da sequência já preenchidos (pra resumo/retomada)."""
    out = []
    for etapa in sequencia_para(em_new_service):
        if etapa.skip and etapa.skip(dados):
            continue
        if not _campo_vazio(dados, etapa.campo):
            out.append(etapa.campo)
    return out


def fluxo_completo(dados: dict, em_new_service: bool = False) -> bool:
    """True se não há mais nenhuma etapa pendente."""
    return proxima_etapa(dados, em_new_service) is None
