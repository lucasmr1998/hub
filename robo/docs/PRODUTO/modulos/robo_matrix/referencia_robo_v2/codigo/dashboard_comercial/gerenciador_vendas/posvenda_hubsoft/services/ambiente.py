"""Prepara as variáveis de ambiente que o webdriver portado espera.

O webdriver original lê `ROBOVENDAS_DB_*` (fila), `HUBSOFT_DB_*` (banco read-only
do HubSoft p/ resolver plano/cliente) e `USUARIO`/`SENHA` (login do painel) do
`.env`. Aqui derivamos `ROBOVENDAS_DB_*` direto do `DATABASES['default']` do Django
(que já aponta para `robovendas_v2`), e o resto das envs novas do v2. Assim o
webdriver opera sobre o banco isolado SEM configuração duplicada.
"""
import os

from django.conf import settings


def preparar_ambiente_webdriver():
    """Injeta no os.environ o que os módulos webdriver/ esperam. Idempotente."""
    db = settings.DATABASES['default']
    # Fila = banco do próprio projeto (robovendas_v2)
    os.environ.setdefault('ROBOVENDAS_DB_HOST', str(db.get('HOST', '')))
    os.environ.setdefault('ROBOVENDAS_DB_PORT', str(db.get('PORT', '5432')))
    os.environ['ROBOVENDAS_DB_NAME'] = str(db.get('NAME', ''))   # sempre robovendas_v2
    os.environ.setdefault('ROBOVENDAS_DB_USER', str(db.get('USER', '')))
    os.environ.setdefault('ROBOVENDAS_DB_PASSWORD', str(db.get('PASSWORD', '')))

    # Banco read-only do HubSoft (HUBSOFT_DB_*) já vem do .env.production direto
    # no os.environ (carregado pelo settings) — o webdriver lê de lá.

    # Login do painel HubSoft p/ o Selenium (HUBSOFT_PAINEL_* → USUARIO/SENHA)
    if os.environ.get('USUARIO') is None:
        os.environ['USUARIO'] = os.environ.get('HUBSOFT_PAINEL_USUARIO', '')
    if os.environ.get('SENHA') is None:
        os.environ['SENHA'] = os.environ.get('HUBSOFT_PAINEL_SENHA', '')
