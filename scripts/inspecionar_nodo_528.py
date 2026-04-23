"""Read-only: configuracao do nodo 528 (condicao) + suas saidas."""
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
            for nid in (525, 528, 537):
                print(f"\n=== NODO {nid} ===")
                cur.execute("""
                    SELECT id, tipo, subtipo, ordem,
                           jsonb_pretty(configuracao)::text AS cfg
                    FROM atendimento_nodofluxo
                    WHERE id=%s AND fluxo_id=6 AND tenant_id=7
                """, (nid,))
                r = cur.fetchone()
                if not r:
                    print("  (nao encontrado)")
                    continue
                print(f"  tipo={r['tipo']} subtipo={r['subtipo']} ordem={r['ordem']}")
                print(r['cfg'])

                cur.execute("""
                    SELECT c.id, c.tipo_saida, c.nodo_destino_id,
                           nd.tipo AS destino_tipo,
                           nd.configuracao->>'titulo' AS destino_titulo
                    FROM atendimento_conexaonodo c
                    JOIN atendimento_nodofluxo nd ON nd.id=c.nodo_destino_id
                    WHERE c.nodo_origem_id=%s
                    ORDER BY c.id
                """, (nid,))
                print(f"  Saidas de {nid}:")
                for row in cur.fetchall():
                    titulo = (row['destino_titulo'] or '')[:50]
                    print(f"    tipo_saida={row['tipo_saida']!r} -> nodo {row['nodo_destino_id']} ({row['destino_tipo']}) | {titulo}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
