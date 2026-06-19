"""
Validadores server-side dos campos do formulario da landing page.

Cada validador recebe (valor, campo_dict, tenant) e retorna:
    (valor_normalizado, erro: str | None)

Onde campo_dict e {tipo, name, props}. Se erro=None, valor passou.

Validadores sao referenciados em CampoSpec.validador (catalog.py). Quem usa
e a view de submit (views.py:submeter_formulario).
"""
from __future__ import annotations

import re

import requests


def validar_text(valor: str, campo: dict, tenant) -> tuple[str, str | None]:
    props = campo.get('props', {})
    valor = (valor or '').strip()
    if props.get('required') and not valor:
        return valor, f"{props.get('label', 'Campo')} e obrigatorio"
    min_len = int(props.get('min_length', 0))
    max_len = int(props.get('max_length', 5000))
    if valor and len(valor) < min_len:
        return valor, f"{props.get('label')} deve ter pelo menos {min_len} caracteres"
    if valor and len(valor) > max_len:
        return valor[:max_len], f"{props.get('label')} muito longo (max {max_len})"
    return valor, None


def validar_email(valor: str, campo: dict, tenant) -> tuple[str, str | None]:
    props = campo.get('props', {})
    valor = (valor or '').strip().lower()
    if props.get('required') and not valor:
        return valor, 'E-mail obrigatorio'
    if valor and not re.match(r'^[\w\.\-+]+@[\w\.\-]+\.\w{2,}$', valor):
        return valor, 'E-mail invalido'
    return valor, None


def validar_telefone(valor: str, campo: dict, tenant) -> tuple[str, str | None]:
    props = campo.get('props', {})
    # So digitos
    digitos = re.sub(r'\D', '', valor or '')
    # Tira DDI 55 se vier
    if digitos.startswith('55') and len(digitos) > 11:
        digitos = digitos[2:]
    if props.get('required') and not digitos:
        return digitos, 'Telefone obrigatorio'
    if digitos and len(digitos) not in (10, 11):
        return digitos, 'Telefone invalido (use DDD + numero, ex: 11999999999)'
    return digitos, None


def _calcular_digito_cpf(numeros: str, multiplicador: int) -> int:
    total = sum(int(d) * (multiplicador - i) for i, d in enumerate(numeros))
    resto = (total * 10) % 11
    return 0 if resto == 10 else resto


def _validar_cpf(cpf: str) -> bool:
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    d1 = _calcular_digito_cpf(cpf[:9], 10)
    if d1 != int(cpf[9]):
        return False
    d2 = _calcular_digito_cpf(cpf[:10], 11)
    return d2 == int(cpf[10])


def _validar_cnpj(cnpj: str) -> bool:
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    soma1 = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    d1 = (soma1 % 11)
    d1 = 0 if d1 < 2 else 11 - d1
    if d1 != int(cnpj[12]):
        return False
    soma2 = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    d2 = (soma2 % 11)
    d2 = 0 if d2 < 2 else 11 - d2
    return d2 == int(cnpj[13])


def validar_cpf_cnpj(valor: str, campo: dict, tenant) -> tuple[str, str | None]:
    props = campo.get('props', {})
    digitos = re.sub(r'\D', '', valor or '')
    if props.get('required') and not digitos:
        return digitos, 'CPF/CNPJ obrigatorio'
    if not digitos:
        return digitos, None
    tipo = props.get('tipo', 'auto')
    if tipo == 'pf' or (tipo == 'auto' and len(digitos) == 11):
        if not _validar_cpf(digitos):
            return digitos, 'CPF invalido'
    elif tipo == 'pj' or (tipo == 'auto' and len(digitos) == 14):
        if not _validar_cnpj(digitos):
            return digitos, 'CNPJ invalido'
    else:
        return digitos, 'CPF/CNPJ invalido'
    return digitos, None


def validar_cep(valor: str, campo: dict, tenant) -> tuple[str, str | None]:
    props = campo.get('props', {})
    digitos = re.sub(r'\D', '', valor or '')
    if props.get('required') and not digitos:
        return digitos, 'CEP obrigatorio'
    if digitos and len(digitos) != 8:
        return digitos, 'CEP invalido (8 digitos)'
    return digitos, None


def consultar_viacep(cep: str) -> dict:
    """Consulta ViaCEP e retorna {rua, bairro, cidade, uf} ou {} se nao achar."""
    cep = re.sub(r'\D', '', cep or '')
    if len(cep) != 8:
        return {}
    try:
        r = requests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
        if r.status_code != 200:
            return {}
        d = r.json()
        if d.get('erro'):
            return {}
        return {
            'rua': d.get('logradouro', ''),
            'bairro': d.get('bairro', ''),
            'cidade': d.get('localidade', ''),
            'uf': d.get('uf', ''),
        }
    except Exception:
        return {}


def validar_endereco(valor, campo: dict, tenant) -> tuple[dict, str | None]:
    """`valor` esperado e dict (ou JSON string) com chaves rua/numero/bairro/cidade/uf."""
    import json
    if isinstance(valor, str):
        try:
            valor = json.loads(valor) if valor.startswith('{') else {'rua': valor}
        except Exception:
            valor = {}
    if not isinstance(valor, dict):
        valor = {}
    props = campo.get('props', {})
    if props.get('required'):
        if not valor.get('rua') or not valor.get('numero') or not valor.get('cidade'):
            return valor, 'Endereco incompleto (rua, numero e cidade obrigatorios)'
    return valor, None


def validar_select(valor, campo: dict, tenant) -> tuple[str, str | None]:
    props = campo.get('props', {})
    opcoes = props.get('opcoes', []) or []
    if props.get('required') and not valor:
        return valor, f"{props.get('label')} obrigatorio"
    if valor and opcoes and valor not in opcoes:
        return valor, f"Opcao invalida"
    return valor, None


def validar_viabilidade(valor, campo: dict, tenant) -> tuple[dict, str | None]:
    """Campo viabilidade: consulta API HubSoft/SGP via consultar_viabilidade.

    `valor` esperado e dict com chaves cep, logradouro, numero, bairro, cidade, uf.
    Retorna (resultado_dict, erro_str). resultado_dict tem chave 'status':
    'cobertura_ok' | 'fora_cobertura' | 'nao_consultado' | 'erro'.
    """
    if not isinstance(valor, dict):
        return {}, None  # opcional — sem dado, nao valida
    try:
        from apps.comercial.viabilidade.services import consultar_viabilidade
        resultado = consultar_viabilidade(
            tenant,
            cep=valor.get('cep', ''),
            logradouro=valor.get('rua', '') or valor.get('logradouro', ''),
            numero=valor.get('numero', ''),
            bairro=valor.get('bairro', ''),
            cidade=valor.get('cidade', ''),
            uf=valor.get('uf', ''),
        )
        return resultado.to_dict(), None
    except Exception as exc:
        return {'status': 'erro', 'mensagem': str(exc)[:200]}, None


REGISTRY = {
    'validar_text': validar_text,
    'validar_email': validar_email,
    'validar_telefone': validar_telefone,
    'validar_cpf_cnpj': validar_cpf_cnpj,
    'validar_cep': validar_cep,
    'validar_endereco': validar_endereco,
    'validar_select': validar_select,
    'validar_viabilidade': validar_viabilidade,
}


def get_validador(nome: str | None):
    if not nome:
        return None
    return REGISTRY.get(nome)
