"""Extrai data de nascimento."""
import re
from datetime import date, datetime


def extrair_data_nascimento(texto: str) -> dict:
    """Retorna {data, idade, valido, motivo}. Formato data: YYYY-MM-DD."""
    if not texto:
        return {'data': None, 'idade': None, 'valido': False, 'motivo': 'vazio'}

    # Padrões: DD/MM/YYYY, DD-MM-YYYY, DDMMYYYY, DD MM YYYY, DD/MM/YY
    digitos = re.sub(r'\D', '', texto)

    candidatos = []
    if len(digitos) == 8:
        # DDMMYYYY
        candidatos.append((digitos[:2], digitos[2:4], digitos[4:]))
    elif len(digitos) == 6:
        # DDMMYY → assume 19xx ou 20xx
        ano = int(digitos[4:])
        ano_completo = 1900 + ano if ano > 25 else 2000 + ano
        candidatos.append((digitos[:2], digitos[2:4], str(ano_completo)))

    # Tentar parse de cada candidato
    for dd, mm, yyyy in candidatos:
        try:
            d = date(int(yyyy), int(mm), int(dd))
            hoje = date.today()
            idade = hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))
            if idade < 0 or idade > 120:
                return {'data': None, 'idade': None, 'valido': False, 'motivo': 'idade_invalida'}
            if idade < 18:
                return {'data': d.isoformat(), 'idade': idade, 'valido': False, 'motivo': 'menor_de_idade'}
            return {'data': d.isoformat(), 'idade': idade, 'valido': True, 'motivo': ''}
        except ValueError:
            continue

    return {'data': None, 'idade': None, 'valido': False, 'motivo': 'formato_invalido'}
