"""Extrai e valida nome completo."""
import re


def extrair_nome(texto: str) -> dict:
    """Retorna dict com {nome, valido, motivo}."""
    if not texto:
        return {'nome': '', 'valido': False, 'motivo': 'vazio'}

    # Limpar
    nome = re.sub(r'[^a-zA-ZÀ-ÿ\s\']', ' ', texto).strip()
    nome = re.sub(r'\s+', ' ', nome)

    # Capitalizar
    palavras = nome.split()
    if not palavras:
        return {'nome': '', 'valido': False, 'motivo': 'vazio'}

    # Conectores em minúsculo
    conectores = {'de', 'da', 'do', 'das', 'dos', 'e'}
    formatadas = []
    for i, p in enumerate(palavras):
        pl = p.lower()
        formatadas.append(pl if i > 0 and pl in conectores else pl.capitalize())
    nome_fmt = ' '.join(formatadas)

    # Validações
    if len(palavras) < 2:
        return {'nome': nome_fmt, 'valido': False, 'motivo': 'sobrenome_faltando'}
    if any(len(p) < 2 for p in palavras if p.lower() not in conectores):
        return {'nome': nome_fmt, 'valido': False, 'motivo': 'palavra_muito_curta'}
    if len(nome_fmt) < 5 or len(nome_fmt) > 100:
        return {'nome': nome_fmt, 'valido': False, 'motivo': 'tamanho_invalido'}

    return {'nome': nome_fmt, 'valido': True, 'motivo': ''}
