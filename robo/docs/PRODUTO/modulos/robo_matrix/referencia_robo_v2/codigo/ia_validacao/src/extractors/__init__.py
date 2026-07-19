"""Extractors locais (sem IA) para reduzir custo OpenAI."""

from .cpf import extrair_cpf, validar_cpf
from .cep import extrair_cep, validar_cep, consultar_cep_viacep
from .nome import extrair_nome
from .telefone import extrair_telefone
from .data_nascimento import extrair_data_nascimento

__all__ = [
    'extrair_cpf', 'validar_cpf',
    'extrair_cep', 'validar_cep', 'consultar_cep_viacep',
    'extrair_nome',
    'extrair_telefone',
    'extrair_data_nascimento',
]
