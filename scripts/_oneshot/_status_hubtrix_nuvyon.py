"""Status do lado Hubtrix da Nuvyon (tenant 12) em prod: modulos, users,
integracoes, pipeline, regras, viabilidade, catalogo, atividade."""
import sys
import psycopg2
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
conn = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()


def q(label, sql, params=()):
    print(f'\n=== {label} ===')
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if not rows:
            print('  (vazio)')
        for r in rows:
            print('  ' + ' | '.join(f'{c}={v}' for c, v in zip(cols, r)))
        return rows
    except Exception as e:
        conn.rollback()
        print(f'  ERRO: {e}')
        return []


# tenant
t = q('TENANT', "SELECT id, nome, slug, ativo, plano_comercial, plano_marketing, plano_cs FROM sistema_tenant WHERE slug='nuvyon';")
if not t:
    sys.exit('tenant nuvyon nao encontrado')
TID = t[0][0]

q('USUARIOS + PERFIL', """
SELECT u.username, u.email, u.is_active, pp.nome AS perfil
FROM sistema_permissao_usuario pu
JOIN auth_user u ON u.id=pu.user_id
LEFT JOIN sistema_perfil_permissao pp ON pp.id=pu.perfil_id
WHERE pu.tenant_id=%s ORDER BY u.username;""", (TID,))

q('PERFIS DE PERMISSAO (seedados)', """
SELECT nome, (SELECT COUNT(*) FROM sistema_perfil_permissao_funcionalidades f WHERE f.perfilpermissao_id=p.id) AS n_func
FROM sistema_perfil_permissao p WHERE p.tenant_id=%s ORDER BY nome;""", (TID,))

q('INTEGRACOES', """
SELECT id, nome, tipo, ativa, base_url FROM integracoes_api WHERE tenant_id=%s ORDER BY id;""", (TID,))

q('PIPELINES', """
SELECT id, nome, padrao, ativo FROM crm_pipelines WHERE tenant_id=%s;""", (TID,))

q('ESTAGIOS', """
SELECT pe.id, pe.nome, pe.ordem, pe.is_final_ganho, pe.is_final_perdido, pe.ativo
FROM crm_pipeline_estagios pe WHERE pe.tenant_id=%s ORDER BY pe.ordem;""", (TID,))

q('REGRAS DE AUTOMACAO', """
SELECT id, nome, ativo, total_disparos,
  (estagio_id IS NULL) AS regra_acao_pura
FROM crm_regras_pipeline_estagio WHERE tenant_id=%s ORDER BY id;""", (TID,))

q('CIDADES VIABILIDADE (count)', """
SELECT COUNT(*) AS total FROM viabilidade_cidadeviabilidade WHERE tenant_id=%s;""", (TID,))

q('CATALOGO PLANOS (count)', """
SELECT COUNT(*) AS planos FROM crm_produtos WHERE tenant_id=%s;""", (TID,))

q('EQUIPES / FILAS INBOX', """
SELECT 'equipe' AS tipo, nome FROM inbox_equipes WHERE tenant_id=%s
UNION ALL SELECT 'fila', nome FROM inbox_filas WHERE tenant_id=%s;""", (TID, TID))

q('ATIVIDADE — leads/conversas/oportunidades', """
SELECT
 (SELECT COUNT(*) FROM leads_prospectos WHERE tenant_id=%s) AS leads,
 (SELECT COUNT(*) FROM inbox_conversas WHERE tenant_id=%s) AS conversas,
 (SELECT COUNT(*) FROM crm_oportunidades WHERE tenant_id=%s) AS oportunidades,
 (SELECT COUNT(*) FROM crm_vendas WHERE tenant_id=%s) AS vendas;""", (TID, TID, TID, TID))

cur.close()
conn.close()
