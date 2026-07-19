"""Extrai e valida telefone brasileiro."""
import re


def extrair_telefone(texto: str) -> str | None:
    """Retorna telefone com DDI/DDD (55 + 2 dígitos + 9 dígitos)."""
    if not texto:
        return None
    digitos = re.sub(r'\D', '', texto)
    # Sem DDI: 10 ou 11 dígitos
    if len(digitos) == 11:
        return '55' + digitos
    if len(digitos) == 10:
        return '55' + digitos
    # Com DDI 55
    if len(digitos) in (12, 13) and digitos.startswith('55'):
        return digitos
    return None
