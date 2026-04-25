"""
Campos criptografados compatíveis com Django 5.2.
Usa Fernet (AES-128-CBC) via biblioteca cryptography.

Chave de criptografia derivada de `settings.SECRET_KEY` (estável entre
processos e ambientes — desde que SECRET_KEY nao mude). Permite override
via env var FIELD_ENCRYPTION_KEY pra cenarios de rotacao.
"""
import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


def _get_key() -> bytes:
    """
    Retorna a chave Fernet (32 bytes urlsafe-base64) derivada de uma fonte
    estavel. Ordem de precedencia:
      1. FIELD_ENCRYPTION_KEY no env (usada como esta se for Fernet valida,
         senao derivada via SHA256). Util pra rotacao.
      2. settings.SECRET_KEY (default — sempre disponivel em qualquer processo).

    NUNCA gera chave aleatoria — isso quebrava decrypt entre processos
    porque a chave era perdida no fim de cada processo Python.
    """
    raw = os.environ.get('FIELD_ENCRYPTION_KEY') or settings.SECRET_KEY
    if isinstance(raw, str):
        raw = raw.encode()

    # Se ja vier no formato Fernet (32 bytes urlsafe-base64), usa direto.
    try:
        Fernet(raw)
        return raw
    except Exception:
        pass

    # Senao, deriva via SHA256 -> 32 bytes -> urlsafe-base64.
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())


class EncryptedCharField(models.CharField):
    """CharField que armazena o valor criptografado no banco."""

    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        f = Fernet(_get_key())
        return f.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            f = Fernet(_get_key())
            return f.decrypt(value.encode()).decode()
        except InvalidToken:
            # Valor no banco nao foi encriptado com a chave atual.
            # Pode ser dado legado (texto puro pre-criptografia) ou chave
            # rotacionada. Loga e retorna None pra evitar mandar lixo
            # encriptado pra APIs externas, o que confunde o diagnostico.
            logger.error(
                'EncryptedCharField: falha de decrypt em %s.%s. '
                'Provavel: SECRET_KEY mudou ou dado salvo com chave antiga. '
                'Retornando None pra forcar reentrada do segredo.',
                getattr(getattr(self, 'model', None), '_meta', None) and self.model._meta.label or '?',
                getattr(self, 'name', '?'),
            )
            return None


class EncryptedTextField(models.TextField):
    """TextField que armazena o valor criptografado no banco."""

    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        f = Fernet(_get_key())
        return f.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            f = Fernet(_get_key())
            return f.decrypt(value.encode()).decode()
        except InvalidToken:
            logger.error(
                'EncryptedTextField: falha de decrypt em %s.%s. '
                'Provavel: SECRET_KEY mudou ou dado salvo com chave antiga.',
                getattr(getattr(self, 'model', None), '_meta', None) and self.model._meta.label or '?',
                getattr(self, 'name', '?'),
            )
            return None
