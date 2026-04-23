"""
Read-only: inspeciona as conexoes de saida do nodo 523 (questao curso FATEPI v3),
e tambem do nodo 524 (ia_classificador) pra entender roteamento pos-classificacao.

Uso: python scripts/inspecionar_conexoes_523.py
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
            # Descobre nome correto da tabela de conexoes
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_name LIKE '%conex%'
                ORDER BY table_name
            """)
            print("Tabelas com 'conex':", [r['table_name'] for r in cur.fetchall()])

            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='atendimento_conexaonodo' ORDER BY ordinal_position
            """)
            cols = [r['column_name'] for r in cur.fetchall()]
            print(f"\nColunas atendimento_conexaonodo: {cols}\n")

            # Nodos 521..535 pra ter contexto visual
            cur.execute("""
                SELECT id, tipo, subtipo, ordem,
                       configuracao->>'titulo' AS titulo
                FROM atendimento_nodofluxo
                WHERE fluxo_id=6 AND tenant_id=7 AND id BETWEEN 519 AND 545
                ORDER BY ordem, id
            """)
            print("Nodos do fluxo 6 (519-545):")
            for r in cur.fetchall():
                titulo = (r['titulo'] or '')[:60]
                print(f"  id={r['id']} ordem={r['ordem']} tipo={r['tipo']:18s} subtipo={r['subtipo'] or '':18s} | {titulo}")

            # Conexoes saindo de 523
            print("\n=== CONEXOES SAINDO DE 523 (questao curso) ===")
            cur.execute("""
                SELECT c.*, no.tipo AS origem_tipo, nd.tipo AS destino_tipo,
                       nd.configuracao->>'titulo' AS destino_titulo
                FROM atendimento_conexaonodo c
                JOIN atendimento_nodofluxo no ON no.id=c.nodo_origem_id
                JOIN atendimento_nodofluxo nd ON nd.id=c.nodo_destino_id
                WHERE c.nodo_origem_id=523
                ORDER BY c.id
            """)
            for r in cur.fetchall():
                print(f"  {dict(r)}")

            # Conexoes saindo de 524 (classificador pos-fallback)
            print("\n=== CONEXOES SAINDO DE 524 (ia_classificador) ===")
            cur.execute("""
                SELECT c.*, nd.tipo AS destino_tipo,
                       nd.configuracao->>'titulo' AS destino_titulo
                FROM atendimento_conexaonodo c
                JOIN atendimento_nodofluxo nd ON nd.id=c.nodo_destino_id
                WHERE c.nodo_origem_id=524
                ORDER BY c.id
            """)
            for r in cur.fetchall():
                print(f"  {dict(r)}")

            # Config do 523 (ia_campos_extrair, ia_categorias, validacao)
            print("\n=== CONFIG NODO 523 ===")
            cur.execute("""
                SELECT jsonb_pretty(configuracao)::text AS cfg
                FROM atendimento_nodofluxo WHERE id=523 AND fluxo_id=6
            """)
            cfg = cur.fetchone()['cfg']
            # Trunca chaves grandes
            for line in cfg.split('\n'):
                if len(line) > 200:
                    print(line[:200] + '...')
                else:
                    print(line)

            # Logs recentes de atendimentos no nodo 529 (curso invalido) pra confirmar padrao
            print("\n=== ULTIMOS ATENDIMENTOS QUE PASSARAM PELO NODO 529 ===")
            cur.execute("""
                SELECT af.id, af.status, af.nodo_atual_id,
                       af.dados_respostas->>'521' AS resp_521,
                       af.dados_respostas->'variaveis'->>'validacao_curso' AS validacao,
                       af.dados_respostas->>'523' AS resp_523
                FROM atendimentos_fluxo af
                WHERE af.tenant_id=7 AND af.fluxo_id=6
                  AND af.dados_respostas ? '523'
                ORDER BY af.id DESC LIMIT 10
            """)
            for r in cur.fetchall():
                print(f"  at={r['id']} status={r['status']} nodo_atual={r['nodo_atual_id']} "
                      f"validacao={r['validacao']!r}")
                if r['resp_523']:
                    resp = r['resp_523'][:120]
                    print(f"    resp_523={resp}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
