"""Validação de respostas — PRÓPRIA do conversacional.

Reusa apenas os VALIDADORES PUROS estáveis (src.extractors): CPF com
dígito verificador, CEP via ViaCEP, data >= 18, etc. A lógica de opção e
confirmação aproveita a interpretação da IA (analise) — mais inteligente
que matching de texto.

Não persiste — só valida e devolve os campos a salvar. A persistência é
feita pelo orquestrador via _alvo (roteia lead/NewService).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.extractors import (
    extrair_cpf, validar_cpf,
    extrair_cep, consultar_cep_viacep,
    extrair_nome, extrair_data_nascimento,
)

# Lixo a remover de respostas curtas (números/opções) — inclui acentos soltos
_LIXO = ' \t.)(-:,;!?´`\'"‘’“”'


@dataclass
class Resultado:
    valido: bool
    campos: dict[str, Any] = field(default_factory=dict)  # campos a persistir
    motivo: str = ''                                       # código do erro
    extra: dict[str, Any] = field(default_factory=dict)    # ex: dados do CEP


def _opcao_match(resposta: str, opcoes: dict, opcao_ia: str | None) -> str | None:
    """Mapeia a resposta pra uma chave de opção.

    1) Se a IA já extraiu o número da opção, usa direto.
    2) Senão, faz matching: número exato (curto) ou substring (alias longo).
    """
    r = (resposta or '').strip().lower().strip(_LIXO)
    # 1) opção numérica da IA
    if opcao_ia:
        oi = str(opcao_ia).strip().strip(_LIXO)
        for valor, aliases in opcoes.items():
            if oi in [str(a).strip().lower() for a in aliases]:
                return valor
    # 2) matching textual
    for valor, aliases in opcoes.items():
        for alias in aliases:
            al = str(alias).lower().strip()
            if not al:
                continue
            if len(al) <= 3:
                if r == al:
                    return valor
            elif al in r:
                return valor
    return None


def validar(regra: dict, resposta: str, analise: dict | None = None) -> Resultado:
    """Valida a resposta conforme a regra. Devolve campos a persistir."""
    analise = analise or {}
    tipo = regra.get('extractor_tipo', 'texto_livre')
    campo = regra.get('campo_lead_atualizar') or ''
    r = (resposta or '').strip()

    # ── CPF ───────────────────────────────────────────────────────────
    if tipo == 'cpf':
        cpf = extrair_cpf(r)
        if not cpf:
            return Resultado(False, motivo='cpf_nao_identificado')
        if not validar_cpf(cpf):
            return Resultado(False, motivo='cpf_invalido')
        return Resultado(True, campos={campo or 'cpf_cnpj': cpf})

    # ── CEP ───────────────────────────────────────────────────────────
    if tipo == 'cep':
        cep = extrair_cep(r)
        if not cep:
            return Resultado(False, motivo='cep_nao_identificado')
        via = consultar_cep_viacep(cep)
        if not via:
            return Resultado(False, motivo='cep_nao_existe')
        campos = {'cep': cep}
        for k_via, k_lead in (('logradouro', 'rua'), ('bairro', 'bairro'),
                              ('localidade', 'cidade'), ('uf', 'estado')):
            v = (via.get(k_via) or '').strip()
            if v:
                campos[k_lead] = v
        return Resultado(True, campos=campos, extra={'viacep': via})

    # ── NOME ──────────────────────────────────────────────────────────
    if tipo == 'nome':
        res = extrair_nome(r)   # {nome, valido, motivo}
        if not res.get('valido'):
            return Resultado(False, motivo=res.get('motivo') or 'nome_invalido')
        return Resultado(True, campos={campo or 'nome_razaosocial': res['nome']})

    # ── DATA DE NASCIMENTO ────────────────────────────────────────────
    if tipo == 'data_nascimento':
        res = extrair_data_nascimento(r)   # {data, idade, valido, motivo}
        if not res.get('valido'):
            return Resultado(False, motivo=res.get('motivo') or 'data_invalida')
        return Resultado(True, campos={campo or 'data_nascimento': res['data']})

    # ── E-MAIL ────────────────────────────────────────────────────────
    if tipo == 'email':
        m = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', r)
        if not m:
            return Resultado(False, motivo='email_invalido')
        return Resultado(True, campos={campo or 'email': m.group(0).lower()})

    # ── NÚMERO (residência) ───────────────────────────────────────────
    if tipo == 'numero':
        rl = r.strip().lower()
        if rl in ('s/n', 'sn', 'sem numero', 'sem número', 'não tem', 'nao tem'):
            return Resultado(True, campos={campo or 'numero_residencia': 'S/N'})
        m = re.search(r'\d+', r)
        if not m:
            return Resultado(False, motivo='numero_invalido')
        return Resultado(True, campos={campo or 'numero_residencia': m.group(0)})

    # ── CONFIRMAÇÃO (sim/não) ─────────────────────────────────────────
    if tipo == 'confirmacao':
        conf = analise.get('confirmacao')   # 'sim'|'nao'|None (da IA)
        if conf is None:
            # Fallback determinístico mínimo
            rl = r.lower().strip(_LIXO)
            if rl in ('1', 's', 'sim', 'ok', 'isso', 'claro', 'certo'):
                conf = 'sim'
            elif rl in ('2', 'n', 'nao', 'não'):
                conf = 'nao'
        if conf == 'sim':
            return Resultado(True, campos={campo: True} if campo else {},
                             extra={'confirmacao': True})
        if conf == 'nao':
            return Resultado(True, campos={campo: False} if campo else {},
                             extra={'confirmacao': False})
        return Resultado(False, motivo='confirmacao_ambigua')

    # ── OPÇÃO (1/2/3...) ──────────────────────────────────────────────
    if tipo == 'opcao':
        opcoes = (regra.get('extractor_config') or {}).get('opcoes') or {}
        if not opcoes:
            return Resultado(True, campos={campo: r} if campo else {},
                             extra={'opcao': r})
        valor = _opcao_match(r, opcoes, analise.get('opcao_numerica'))
        if valor is None:
            return Resultado(False, motivo='opcao_nao_reconhecida')
        return Resultado(True, campos={campo: valor} if campo else {},
                         extra={'opcao': valor})

    # ── IMAGEM ────────────────────────────────────────────────────────
    # A validação de imagem (IA Vision) é tratada à parte no orquestrador,
    # pois depende de URL + descrição. Aqui só sinaliza.
    if tipo == 'imagem':
        return Resultado(bool(r), motivo='' if r else 'imagem_ausente',
                         extra={'url_imagem': r})

    # ── TEXTO LIVRE / LIVRE ───────────────────────────────────────────
    if tipo in ('texto_livre', 'livre'):
        if tipo == 'texto_livre' and not r:
            return Resultado(False, motivo='resposta_vazia')
        return Resultado(True, campos={campo: r} if campo else {},
                         extra={'valor': r})

    # tipo desconhecido — aceita por segurança
    return Resultado(True, campos={campo: r} if campo else {})
