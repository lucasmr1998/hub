"""Configurações da aplicação carregadas de .env"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    OPENAI_TIMEOUT = int(os.getenv('OPENAI_TIMEOUT', '20'))

    # Servidor
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '8090'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Persona
    PERSONA_NOME = os.getenv('PERSONA_NOME', 'Aurora')
    PERSONA_EMPRESA = os.getenv('PERSONA_EMPRESA', 'Megalink')

    # Cache
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    USAR_CACHE = os.getenv('USAR_CACHE', 'false').lower() == 'true'
    # Cache de inferência pergunta→regra via OpenAI (validador v2)
    USAR_CACHE_INFERENCIA = os.getenv('USAR_CACHE_INFERENCIA', 'true').lower() == 'true'

    # Externos
    ROBOVENDAS_API_URL = os.getenv('ROBOVENDAS_API_URL', '')

    # Diretórios
    FLUXOS_DIR = BASE_DIR / 'fluxos'
    LOGS_DIR = BASE_DIR / 'logs'

    @classmethod
    def validar(cls):
        """Retorna lista de erros de configuração."""
        erros = []
        if not cls.OPENAI_API_KEY or cls.OPENAI_API_KEY.startswith('sk-COLOQUE'):
            erros.append('OPENAI_API_KEY não configurada')
        return erros


config = Config()
