"""
Campos criptografados compatíveis com Django 5.2.
Usa Fernet (AES-128-CBC) via biblioteca cryptography.
"""
import base64
import os

from cryptography.fernet import Fernet
from django.db import models


def _get_key():
    """Retorna a chave Fernet. Gera uma se não existir no env."""
    key = os.environ.get('FIELD_ENCRYPTION_KEY', '')
    if not key:
        key = Fernet.generate_key().decode()
        os.environ['FIELD_ENCRYPTION_KEY'] = key
    if isinstance(key, str):
        key = key.encode()
    # Fernet exige 32 bytes base64-encoded. Se a chave não tiver formato correto, derivar.
    try:
        Fernet(key)
        return key
    except Exception:
        import hashlib
        derived = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        return derived


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
        except Exception:
            return value  # Retorna sem decriptar se falhar (dados antigos não criptografados)


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
        except Exception:
            return value
