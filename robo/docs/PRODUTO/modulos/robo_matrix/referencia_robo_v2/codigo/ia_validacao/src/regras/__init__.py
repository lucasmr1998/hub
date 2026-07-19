"""Pacote regras: lookup + execução de regras de validação.

- client.py: busca regras no Django via HTTP + cache em memória (TTL 1h)
- engine.py: aplica extractor da regra + dispara ações em background
"""
from .client import regras_client
from .engine import validar_por_regra

__all__ = ['regras_client', 'validar_por_regra']
