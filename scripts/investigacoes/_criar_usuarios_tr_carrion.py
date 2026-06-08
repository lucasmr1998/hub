"""
Cria 5 usuarios no tenant tr-carrion (id=11) com perfis e equipe.

Senha padrao: Vero@2026
Marca senha_temporaria=True (usuario tera que trocar no primeiro login).

Vendedores ja entram como membros da EquipeInbox 9 (Vendedores Vero).
"""
import psycopg2
import sys
import io
import django
from django.conf import settings
from dotenv import dotenv_values

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Bootstrap Django so pra hashing
if not settings.configured:
    settings.configure(
        SECRET_KEY='temp-for-hash',
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes'],
        PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher'],
        AUTH_USER_MODEL='auth.User',
        USE_TZ=True,
    )
    django.setup()
from django.contrib.auth.hashers import make_password

env = dotenv_values('.env.prod_readonly')
TENANT_ID = 11
PERFIL_ADMIN = 68
PERFIL_VENDEDOR = 58
EQUIPE_ID = 9  # Vendedores Vero
SENHA_PADRAO = 'Vero@2026'

USUARIOS = [
    # (username, first_name, last_name, email, perfil_id, eh_vendedor)
    ('kelle.alves',     'Kelle Cristinaa', 'Alexandre Alves',   'newworldtelecombrasil@gmail.com',  PERFIL_ADMIN,    False),
    ('tiago.carrion',   'Tiago Rafael',    'Carrion',           'nwtelecomoficial@gmail.com',       PERFIL_ADMIN,    False),
    ('flavia.vidoto',   'Flavia Meire',    'Silva Vidoto',      'flaviameire@yahoo.com.br',         PERFIL_VENDEDOR, True),
    ('karina.liporaz',  'Karina Cristina', 'Gonzales Liporaz',  'karinaliporazzz@gmail.com',        PERFIL_VENDEDOR, True),
    ('sthefanny.dutra', 'Sthefanny',       'Nascimento Dutra',  'nascimentosthefanny469@gmail.com', PERFIL_VENDEDOR, True),
]

senha_hash = make_password(SENHA_PADRAO)
print(f'Hash gerado pra senha padrao: {senha_hash[:35]}...')

conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
    database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.autocommit = False
cur = conn.cursor()

try:
    for username, fn, ln, email, perfil_id, eh_vendedor in USUARIOS:
        cur.execute("SELECT id FROM auth_user WHERE username=%s OR email=%s;", (username, email))
        existing = cur.fetchone()
        if existing:
            print(f'  ⚠ {username}: ja existe (id={existing[0]}), pulando criacao')
            user_id = existing[0]
        else:
            cur.execute("""INSERT INTO auth_user
                            (username, email, password, first_name, last_name,
                             is_active, is_staff, is_superuser, date_joined)
                            VALUES (%s, %s, %s, %s, %s, TRUE, FALSE, FALSE, NOW())
                          RETURNING id;""",
                        (username, email, senha_hash, fn, ln))
            user_id = cur.fetchone()[0]
            print(f'  ✓ {username} criado (id={user_id})')

        # PerfilUsuario (1-1 user x tenant)
        cur.execute("SELECT id FROM sistema_perfil_usuario WHERE user_id=%s;", (user_id,))
        if not cur.fetchone():
            cur.execute("""INSERT INTO sistema_perfil_usuario
                            (user_id, tenant_id, telefone, senha_temporaria)
                            VALUES (%s, %s, '', TRUE);""",
                        (user_id, TENANT_ID))
            print(f'    + perfil_usuario criado (senha_temporaria=true)')

        # PermissaoUsuario — vincula com PerfilPermissao
        cur.execute("SELECT id FROM sistema_permissao_usuario WHERE user_id=%s AND tenant_id=%s;",
                    (user_id, TENANT_ID))
        if not cur.fetchone():
            cur.execute("""INSERT INTO sistema_permissao_usuario (user_id, tenant_id, perfil_id)
                            VALUES (%s, %s, %s);""",
                        (user_id, TENANT_ID, perfil_id))
            print(f'    + permissao perfil_id={perfil_id}')

        # Se for vendedor, vira membro da equipe Vendedores Vero
        if eh_vendedor:
            cur.execute("""SELECT id FROM inbox_membros_equipe
                            WHERE tenant_id=%s AND equipe_id=%s AND user_id=%s;""",
                        (TENANT_ID, EQUIPE_ID, user_id))
            if not cur.fetchone():
                cur.execute("""INSERT INTO inbox_membros_equipe
                                (tenant_id, equipe_id, user_id, cargo, adicionado_em)
                                VALUES (%s, %s, %s, 'agente', NOW());""",
                            (TENANT_ID, EQUIPE_ID, user_id))
                print(f'    + membro da equipe 9 (Vendedores Vero)')

    conn.commit()
    print('\n✅ COMMIT OK')
    print(f'\nSenha padrao pra todos: {SENHA_PADRAO}')
    print('Sera solicitada troca no primeiro login (senha_temporaria=True).')
except Exception as e:
    conn.rollback()
    print(f'\n❌ ROLLBACK: {type(e).__name__}: {e}')
    raise
finally:
    cur.close(); conn.close()
