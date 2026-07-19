"""Extrai e valida CEP."""
import re
import httpx


def extrair_cep(texto: str) -> str | None:
    if not texto:
        return None
    digitos = re.sub(r'\D', '', texto)
    if len(digitos) == 8:
        return digitos
    match = re.search(r'\d{8}', digitos)
    return match.group() if match else None


def validar_cep(cep: str) -> bool:
    """Validação básica de formato."""
    cep = re.sub(r'\D', '', cep or '')
    return len(cep) == 8


def consultar_cep_viacep(cep: str) -> dict | None:
    """Consulta ViaCEP e retorna dados ou None."""
    cep = re.sub(r'\D', '', cep or '')
    if not validar_cep(cep):
        return None
    try:
        r = httpx.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=8)
        if r.status_code == 200:
            data = r.json()
            if not data.get('erro'):
                return data
    except Exception:
        pass
    return None


def formatar_cep(cep: str) -> str:
    cep = re.sub(r'\D', '', cep or '')
    return f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep
