"""
Lista atendimentos zumbis do fluxo v3 FATEPI (tenant=7, fluxo=6):
atendimentos com nodo_atual_id apontando pra nodo inexistente ou NULL,
status ainda nao finalizado.

Read-only. Uso: python scripts/listar_zumbis_v3.py
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
            # Descobre a tabela correta
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_name LIKE '%atendimento%'
                ORDER BY table_name
            """)
            print("Tabelas com 'atendimento':")
            for r in cur.fetchall():
                print("  " + r["table_name"])
            print()

            # Candidatos a zumbi: status ativo + nodo_atual_id NULL OU apontando pra nodo que nao existe
            # Descobre nome da tabela de atendimento (model AtendimentoFluxo)
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public'
                  AND (table_name LIKE '%atendimento%fluxo%' OR table_name LIKE '%atendimentofluxo%')
                ORDER BY table_name
            """)
            candidatas = [r["table_name"] for r in cur.fetchall()]
            print("Candidatas pra tabela de atendimentos:", candidatas)

            # Procura a que tem nodo_atual_id
            tabela = None
            for t in candidatas:
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = %s AND column_name = 'nodo_atual_id'
                """, (t,))
                if cur.fetchone():
                    tabela = t
                    break
            if not tabela:
                print("Nao achei tabela com nodo_atual_id")
                return
            print(f"Usando tabela: {tabela}\n")

            # Colunas disponiveis
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s ORDER BY ordinal_position
            """, (tabela,))
            cols = {r["column_name"] for r in cur.fetchall()}

            # Monta SELECT dinamico usando apenas colunas que existem
            campos_desejados = ['id', 'tenant_id', 'fluxo_id', 'status',
                                'nodo_atual_id', 'questao_atual', 'questoes_respondidas',
                                'data_inicio', 'data_ultima_interacao', 'lead_id']
            campos = [c for c in campos_desejados if c in cols]

            sql_zumbis = f"""
                SELECT {', '.join(campos)}
                FROM {tabela}
                WHERE tenant_id = 7 AND fluxo_id = 6
                  AND status NOT IN ('finalizado', 'abandonado', 'erro', 'cancelado')
                  AND (
                    nodo_atual_id IS NULL
                    OR nodo_atual_id NOT IN (
                        SELECT id FROM atendimento_nodofluxo WHERE fluxo_id = 6
                    )
                  )
                ORDER BY {'data_ultima_interacao DESC NULLS LAST' if 'data_ultima_interacao' in cols else 'id DESC'}
            """
            cur.execute(sql_zumbis)
            rows = cur.fetchall()
            print(f"Zumbis encontrados: {len(rows)}")
            for r in rows:
                print(f"  {dict(r)}")

            cur.execute(f"""
                SELECT status, COUNT(*) as n
                FROM {tabela}
                WHERE tenant_id = 7 AND fluxo_id = 6
                GROUP BY status ORDER BY n DESC
            """)
            print("\nDistribuicao geral do fluxo 6:")
            for r in cur.fetchall():
                print(f"  {r['status']!r}: {r['n']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
