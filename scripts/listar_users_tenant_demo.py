"""
Read-only: lista usuarios do tenant 'demo' em producao.
Objetivo: identificar qual(is) usuario(s) reset de senha deve atingir.
"""
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

ENV_PATH = Path(__file__).resolve().parent.parent / ".env.prod_readonly"


def load_env():
    env = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def main():
    env = load_env()
    conn = psycopg2.connect(
        host=env["PROD_DB_HOST"], port=int(env["PROD_DB_PORT"]),
        dbname=env["PROD_DB_NAME"], user=env["PROD_DB_USER"],
        password=env["PROD_DB_PASSWORD"],
    )
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Todos os tenants com 'demo' no nome
            cur.execute("""
                SELECT id, nome, slug FROM sistema_tenant
                WHERE nome ILIKE '%demo%' OR slug ILIKE '%demo%'
                ORDER BY id
            """)
            tenants = cur.fetchall()
            print(f"Tenants com 'demo': {len(tenants)}")
            for t in tenants:
                print(f"  id={t['id']} nome={t['nome']!r} slug={t['slug']!r}")

            if not tenants:
                print("Nenhum tenant 'demo' encontrado.")
                return

            tenant_ids = [t['id'] for t in tenants]

            # Descobrir tabela correta do PerfilUsuario
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_name ILIKE '%perfilusuario%'
                ORDER BY table_name
            """)
            tab = [r['table_name'] for r in cur.fetchall()]
            print(f"\nTabelas PerfilUsuario: {tab}")

            if not tab:
                print("Sem tabela PerfilUsuario encontrada. Tentando via Tenant direto em auth_user...")
                cur.execute("""
                    SELECT u.id, u.username, u.email, u.is_active, u.is_superuser, u.last_login
                    FROM auth_user u
                    WHERE u.username ILIKE '%demo%' OR u.email ILIKE '%demo%'
                    ORDER BY u.id
                """)
                for r in cur.fetchall():
                    print(f"  id={r['id']} user={r['username']!r} email={r['email']!r} "
                          f"ativo={r['is_active']} super={r['is_superuser']} last={r['last_login']}")
                return
            perfil_tbl = tab[0]

            # Usuarios via PerfilUsuario
            cur.execute(f"""
                SELECT u.id, u.username, u.email, u.first_name, u.last_name,
                       u.is_active, u.is_superuser, u.date_joined,
                       u.last_login, pu.tenant_id, t.nome AS tenant_nome
                FROM auth_user u
                JOIN {perfil_tbl} pu ON pu.user_id = u.id
                JOIN sistema_tenant t ON t.id = pu.tenant_id
                WHERE pu.tenant_id = ANY(%s)
                ORDER BY pu.tenant_id, u.username
            """, (tenant_ids,))
            users = cur.fetchall()
            print(f"\nUsuarios nesses tenants: {len(users)}")
            for u in users:
                flags = []
                if u['is_superuser']: flags.append('superuser')
                if not u['is_active']: flags.append('inativo')
                flags_str = f" [{', '.join(flags)}]" if flags else ''
                print(f"  id={u['id']} tenant={u['tenant_id']} "
                      f"username={u['username']!r} email={u['email']!r}{flags_str}")
                print(f"     nome={(u['first_name'] or '') + ' ' + (u['last_name'] or '')!r}")
                print(f"     joined={u['date_joined']} last_login={u['last_login']}")

            # Tambem procurar usuarios com username/email contendo 'demo' (outros tenants)
            cur.execute(f"""
                SELECT u.id, u.username, u.email, u.is_superuser, pu.tenant_id, t.nome AS tenant_nome
                FROM auth_user u
                LEFT JOIN {perfil_tbl} pu ON pu.user_id = u.id
                LEFT JOIN sistema_tenant t ON t.id = pu.tenant_id
                WHERE (u.username ILIKE '%demo%' OR u.email ILIKE '%demo%')
                  AND (pu.tenant_id IS NULL OR NOT (pu.tenant_id = ANY(%s)))
                ORDER BY u.id
            """, (tenant_ids,))
            outros = cur.fetchall()
            if outros:
                print(f"\nUsuarios com 'demo' no username/email mas em OUTROS tenants: {len(outros)}")
                for u in outros:
                    print(f"  id={u['id']} username={u['username']!r} email={u['email']!r} "
                          f"tenant={u['tenant_id']} ({u['tenant_nome']!r})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
