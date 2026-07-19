"""Definição das etapas do fluxo — PRÓPRIA da camada conversacional.

Espelha as sequências do onboarding determinístico, mas é independente:
mudar isto NÃO afeta o /ia/proximo-passo. Cada etapa sabe seu campo no
alvo (lead ou NewService), o question_id da regra (pra carregar a config
de validação do Django) e uma condição opcional de "pular".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Etapa:
    campo: str               # campo no lead/NewService
    question_id: str         # id da RegraValidacao (config de validação)
    skip: Callable[[dict], bool] | None = None   # True = pular esta etapa


# ── Condições de skip ─────────────────────────────────────────────────
def _skip_tipo_residencia(dados: dict) -> bool:
    """tipo_residencia só faz sentido pra residencial (casa)."""
    ti = (dados.get('tipo_imovel') or '').strip()
    return bool(ti and ti != 'casa')


# ── Fluxo de VENDA (lead novo) ────────────────────────────────────────
SEQUENCIA_VENDA: list[Etapa] = [
    Etapa('cpf_cnpj',            'coleta_cpf'),
    Etapa('nome_razaosocial',    'coleta_nome'),
    Etapa('data_nascimento',     'coleta_data_nascimento'),
    Etapa('email',               'coleta_email'),
    Etapa('tipo_imovel',         'tipo_imovel'),
    Etapa('cep',                 'coleta_cep'),
    Etapa('endereco_confirmado', 'confirmacao_endereco'),
    Etapa('cidade',              'coleta_cidade'),   # só se ViaCEP não preencheu
    Etapa('bairro',              'coleta_bairro'),
    Etapa('rua',                 'coleta_rua'),
    Etapa('numero_residencia',   'coleta_numero'),
    Etapa('tipo_residencia',     'coleta_tipo_residencia', _skip_tipo_residencia),
    Etapa('ponto_referencia',    'coleta_ponto_referencia'),
    Etapa('id_plano_rp',         'escolha_plano'),
    Etapa('plano_confirmado',    'confirmacao_plano'),
    Etapa('id_dia_vencimento',   'dia_vencimento'),
    Etapa('dados_confirmados',   'confirmacao_dados'),
    Etapa('doc_selfie_recebida', 'documentacao_selfie'),
    Etapa('doc_frente_recebida', 'documentacao_frente_doc'),
    Etapa('doc_verso_recebida',  'documentacao_verso_doc'),
    Etapa('turno_instalacao',    'escolha_turno'),
    Etapa('data_instalacao',     'escolha_data'),
]


# ── Fluxo de NOVO SERVIÇO (cliente Hubsoft já existe) ────────────────
# Sem dados pessoais (já temos): começa do tipo de imóvel.
SEQUENCIA_NEW_SERVICE: list[Etapa] = [
    Etapa('tipo_imovel',         'tipo_imovel'),
    Etapa('cep',                 'coleta_cep'),
    Etapa('endereco_confirmado', 'confirmacao_endereco'),
    Etapa('cidade',              'coleta_cidade'),
    Etapa('bairro',              'coleta_bairro'),
    Etapa('rua',                 'coleta_rua'),
    Etapa('numero_residencia',   'coleta_numero'),
    Etapa('tipo_residencia',     'coleta_tipo_residencia', _skip_tipo_residencia),
    Etapa('ponto_referencia',    'coleta_ponto_referencia'),
    Etapa('id_plano_rp',         'escolha_plano'),
    Etapa('plano_confirmado',    'confirmacao_plano'),
    Etapa('id_dia_vencimento',   'dia_vencimento'),
    Etapa('dados_confirmados',   'confirmacao_dados'),
    Etapa('doc_selfie_recebida', 'documentacao_selfie'),
    Etapa('doc_frente_recebida', 'documentacao_frente_doc'),
    Etapa('doc_verso_recebida',  'documentacao_verso_doc'),
    Etapa('turno_instalacao',    'escolha_turno'),
    Etapa('data_instalacao',     'escolha_data'),
]


# question_id → campo (pra resolver rápido o alvo de cada pergunta)
def mapa_qid_para_campo() -> dict[str, str]:
    m: dict[str, str] = {}
    for seq in (SEQUENCIA_VENDA, SEQUENCIA_NEW_SERVICE):
        for e in seq:
            m.setdefault(e.question_id, e.campo)
    return m
