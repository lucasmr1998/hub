"""
Garantia anti-regressao: o ciclo encrypt -> decrypt tem que funcionar
em PROCESSOS DIFERENTES (mesmo SECRET_KEY).

Esse era o bug original que quebrou todas as APIs: chave Fernet aleatoria
por processo -> token encriptado em processo A nao decripta em processo B.
Em testes single-process tudo passava — o bug so aparecia em producao
(gunicorn worker A escreveu, worker B leu).
"""
import os
import subprocess
import sys

from django.test import SimpleTestCase

from apps.sistema.encrypted_fields import _get_key, EncryptedCharField
from cryptography.fernet import Fernet


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class EncryptedFieldsCrossProcessTest(SimpleTestCase):
    """
    Valida persistencia de chave entre processos. Sem esse teste, o bug
    de 'chave aleatoria por processo' pode voltar silenciosamente.
    """

    def test_key_estavel_entre_processos(self):
        """
        A chave derivada precisa ser identica em processos diferentes,
        senao decrypt quebra.
        """
        key_processo_atual = _get_key()

        script = '''
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
django.setup()
from apps.sistema.encrypted_fields import _get_key
import sys
sys.stdout.buffer.write(_get_key())
'''
        result = subprocess.run(
            [sys.executable, '-c', script],
            cwd=PROJECT_DIR,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=f'stderr: {result.stderr.decode()}')
        key_processo_outro = result.stdout
        self.assertEqual(
            key_processo_atual, key_processo_outro,
            msg='Chave divergiu entre processos! Decrypt vai quebrar em prod.',
        )

    def test_decrypt_em_processo_separado(self):
        """Token encriptado aqui tem que decriptar em outro processo Python."""
        token_original = 'sk-live-meu-token-super-secreto-12345'
        f = Fernet(_get_key())
        ciphertext = f.encrypt(token_original.encode()).decode()

        script = f'''
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
django.setup()
from apps.sistema.encrypted_fields import _get_key
from cryptography.fernet import Fernet
f = Fernet(_get_key())
print(f.decrypt({ciphertext!r}.encode()).decode())
'''
        result = subprocess.run(
            [sys.executable, '-c', script],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=f'stderr: {result.stderr}')
        self.assertIn(token_original, result.stdout)


class EncryptedFieldsRoundTripTest(SimpleTestCase):
    """Smoke test do ciclo basico encrypt -> get_prep_value -> from_db_value."""

    def test_round_trip_charfield(self):
        field = EncryptedCharField(max_length=255)
        original = 'minha-api-key-confidencial'
        ciphertext = field.get_prep_value(original)
        self.assertNotEqual(ciphertext, original)
        self.assertTrue(ciphertext.startswith('gAAAA'))
        decrypted = field.from_db_value(ciphertext, None, None)
        self.assertEqual(decrypted, original)

    def test_decrypt_invalido_retorna_none(self):
        """Se vier ciphertext de outra chave, retorna None (nao mascara o lixo)."""
        field = EncryptedCharField(max_length=255)
        # Ciphertext valido mas encriptado com OUTRA chave.
        outra_chave = Fernet.generate_key()
        f = Fernet(outra_chave)
        ciphertext_alheio = f.encrypt(b'segredo').decode()
        result = field.from_db_value(ciphertext_alheio, None, None)
        self.assertIsNone(result)
