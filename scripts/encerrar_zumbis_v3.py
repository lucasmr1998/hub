"""
Encerra 5 atendimentos zumbis do fluxo v3 FATEPI (tenant=7, fluxo=6):
ids 132..136 (status='iniciado' + nodo_atual_id=NULL apos refactor v3).

UPDATE autorizado em 23/04/2026.
Transacional. Abort se rowcount != 5.
"""
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

ENV_PATH = Path(__file__).resolve().parent.parent / ".env.prod_readonly"
ZUMBIS = [132, 133, 134, 135, 136]


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
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Antes
            cur.execute("""
                SELECT id, status, nodo_atual_id FROM atendimentos_fluxo
                WHERE id = ANY(%s) AND tenant_id=7 AND fluxo_id=6
                ORDER BY id
            """, (ZUMBIS,))
            antes = cur.fetchall()
            print("ANTES:")
            for r in antes:
                print(f"  id={r['id']} status={r['status']!r} nodo_atual_id={r['nodo_atual_id']}")

            if len(antes) != 5:
                raise RuntimeError(f"Esperado 5 linhas, encontrado {len(antes)}")

            # UPDATE
            cur.execute("""
                UPDATE atendimentos_fluxo
                SET status = 'abandonado'
                WHERE id = ANY(%s)
                  AND tenant_id = 7 AND fluxo_id = 6
                  AND status = 'iniciado'
                  AND nodo_atual_id IS NULL
            """, (ZUMBIS,))
            print(f"\nrowcount: {cur.rowcount}")
            if cur.rowcount != 5:
                raise RuntimeError(f"Esperado rowcount=5, veio {cur.rowcount}. Abort.")

            # Depois
            cur.execute("""
                SELECT id, status, nodo_atual_id FROM atendimentos_fluxo
                WHERE id = ANY(%s) AND tenant_id=7 AND fluxo_id=6
                ORDER BY id
            """, (ZUMBIS,))
            print("\nDEPOIS:")
            for r in cur.fetchall():
                print(f"  id={r['id']} status={r['status']!r} nodo_atual_id={r['nodo_atual_id']}")

        conn.commit()
        print("\nCOMMIT. 5 zumbis marcados como 'abandonado'.")
    except Exception as e:
        conn.rollback()
        print(f"\nROLLBACK. Erro: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
