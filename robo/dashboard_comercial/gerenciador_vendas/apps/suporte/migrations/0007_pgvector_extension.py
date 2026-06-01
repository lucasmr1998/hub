"""Habilita pgvector + refresh do collation (glibc mudou ao trocar imagem Postgres).

Idempotente nos dois statements. ALTER DATABASE REFRESH COLLATION VERSION
nao roda em transacao do Django porque depende do nome do DB; entao usamos
RunPython com autocommit (ou simplesmente skip se nao for postgres).
"""
from django.db import migrations, connection


def _refresh_collation_e_extension(apps, schema_editor):
    # Skipa se nao for Postgres (ex: SQLite em algum cenario de teste futuro)
    if schema_editor.connection.vendor != 'postgresql':
        return
    # CREATE EXTENSION precisa de superuser; em prod o user do EasyPanel e admin do DB.
    with schema_editor.connection.cursor() as cur:
        cur.execute('CREATE EXTENSION IF NOT EXISTS vector;')
        # REFRESH COLLATION VERSION precisa do nome do DB atual.
        cur.execute('SELECT current_database();')
        dbname = cur.fetchone()[0]
        # Statement nao pode ter parametros; nome do DB e seguro (vem do servidor).
        cur.execute(f'ALTER DATABASE "{dbname}" REFRESH COLLATION VERSION;')


def _noop_reverse(apps, schema_editor):
    # Nao desfazemos: extension fica, collation refresh nao tem volta.
    return


class Migration(migrations.Migration):

    atomic = False  # ALTER DATABASE nao pode rodar em transacao

    dependencies = [
        ('suporte', '0006_perguntasemresposta'),
    ]

    operations = [
        migrations.RunPython(_refresh_collation_e_extension, reverse_code=_noop_reverse),
    ]
