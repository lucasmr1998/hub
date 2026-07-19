"""Extrai e valida CPF de uma string."""
import re


def extrair_cpf(texto: str) -> str | None:
    """Extrai sequência de 11 dígitos que possa ser CPF."""
    if not texto:
        return None
    digitos = re.sub(r'\D', '', texto)
    if len(digitos) == 11:
        return digitos
    # Buscar 11 dígitos consecutivos
    match = re.search(r'\d{11}', digitos)
    return match.group() if match else None


def validar_cpf(cpf: str) -> bool:
    """Valida CPF pelos dígitos verificadores."""
    if not cpf:
        return False
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    # Primeiro dígito
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto

    # Segundo dígito
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto

    return int(cpf[9]) == dv1 and int(cpf[10]) == dv2


def formatar_cpf(cpf: str) -> str:
    """Formata como XXX.XXX.XXX-XX."""
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
