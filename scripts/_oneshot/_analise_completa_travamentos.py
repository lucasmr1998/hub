"""Analise completa de travamentos no atendimento TR Carrion (New World Telecom)."""
import sys
import psycopg2
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

env_path = Path(__file__).resolve().parents[1] / '.env.prod_readonly'
env = {}
for line in env_path.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip()

conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()
TID = 11

ESTADOS_VALIDOS = {
    'aguarda_cep','aguarda_complemento','aguarda_confirmacao_cep',
    'aguarda_confirmacao_final','aguarda_cpf','aguarda_data_nasc',
    'aguarda_decisao_correcao','aguarda_decisao_pos_concluido',
    'aguarda_doc_rg_frente','aguarda_doc_rg_verso','aguarda_email',
    'aguarda_humano','aguarda_nome','aguarda_numero','aguarda_plano',
    'concluido','inicio',
}

print('=' * 70)
print('1) CLIENTE ESPERANDO AGORA (ultima msg = contato, status aberta)')
print('=' * 70)
cur.execute("""
SELECT c.id, c.contato_nome, c.contato_telefone, c.modo_atendimento,
       c.agente_id, c.fila_id, c.ultima_mensagem_em,
       EXTRACT(EPOCH FROM (NOW() - c.ultima_mensagem_em))/3600 AS horas,
       o.dados_custom->>'atendimento_estado' AS estado,
       m.tipo_conteudo
FROM inbox_conversas c
LEFT JOIN crm_oportunidades o ON o.id = c.oportunidade_id
JOIN LATERAL (
    SELECT remetente_tipo, tipo_conteudo FROM inbox_mensagens
    WHERE conversa_id = c.id ORDER BY data_envio DESC LIMIT 1
) m ON true
WHERE c.tenant_id = %s
  AND c.status = 'aberta'
  AND m.remetente_tipo = 'contato'
ORDER BY c.modo_atendimento, c.ultima_mensagem_em DESC;
""", (TID,))
rows = cur.fetchall()
bot_mudo = []
humano_espera = []
for r in rows:
    if r[3] in ('bot', 'finalizado_bot'):
        bot_mudo.append(r)
    else:
        humano_espera.append(r)

print(f'\n  >> BOT MUDO ({len(bot_mudo)}) — cliente falou, bot nao respondeu:')
for r in bot_mudo:
    estado = r[8] or '?'
    flag = ' [ESTADO INVALIDO]' if estado not in ESTADOS_VALIDOS else ''
    print(f'    c#{r[0]:4d} {(r[1] or "")[:18]:18s} tel={r[2]:14s} modo={r[3]:13s} '
          f'estado={estado:22s} parado={r[7]:.1f}h tipo_ult={r[9]}{flag}')

print(f'\n  >> AGUARDANDO VENDEDORA ({len(humano_espera)}) — modo humano, em fila:')
for r in humano_espera:
    print(f'    c#{r[0]:4d} {(r[1] or "")[:18]:18s} tel={r[2]:14s} '
          f'agente={r[4]} fila={r[5]} parado={r[7]:.1f}h')

print('\n' + '=' * 70)
print('2) OPORTUNIDADES COM ESTADO INVALIDO (bot travaria na proxima msg)')
print('=' * 70)
cur.execute("""
SELECT o.id, l.nome_razaosocial, l.telefone,
       o.dados_custom->>'atendimento_estado' AS estado,
       o.dados_custom->>'atendimento_atualizado_em' AS em,
       c.id, c.status, c.modo_atendimento
FROM crm_oportunidades o
JOIN leads_prospectos l ON l.id = o.lead_id
LEFT JOIN inbox_conversas c ON c.oportunidade_id = o.id
WHERE o.tenant_id = %s
  AND o.dados_custom ? 'atendimento_estado'
  AND o.dados_custom->>'atendimento_estado' NOT IN (
    'aguarda_cep','aguarda_complemento','aguarda_confirmacao_cep',
    'aguarda_confirmacao_final','aguarda_cpf','aguarda_data_nasc',
    'aguarda_decisao_correcao','aguarda_decisao_pos_concluido',
    'aguarda_doc_rg_frente','aguarda_doc_rg_verso','aguarda_email',
    'aguarda_humano','aguarda_nome','aguarda_numero','aguarda_plano',
    'concluido','inicio'
  )
ORDER BY o.dados_custom->>'atendimento_atualizado_em' DESC;
""", (TID,))
rows = cur.fetchall()
print(f'  Total: {len(rows)}')
for r in rows:
    print(f'    oport={r[0]} {(r[1] or "")[:18]:18s} tel={r[2]:14s} '
          f'estado={r[3]!r} conv=#{r[5]} status={r[6]} modo={r[7]} em={str(r[4])[:16]}')

print('\n' + '=' * 70)
print('3) DISTRIBUICAO POR ESTADO DO ATENDIMENTO (todas oport ativas)')
print('=' * 70)
cur.execute("""
SELECT o.dados_custom->>'atendimento_estado' AS estado, COUNT(*)
FROM crm_oportunidades o
WHERE o.tenant_id = %s AND o.ativo = true
  AND o.dados_custom ? 'atendimento_estado'
GROUP BY 1 ORDER BY 2 DESC;
""", (TID,))
for r in cur.fetchall():
    estado = r[0] or '(vazio)'
    flag = '' if estado in ESTADOS_VALIDOS else ' <-- INVALIDO'
    print(f'    {estado:25s} {r[1]:3d}{flag}')

print('\n' + '=' * 70)
print('4) HANDOFF PREMATURO — foram pra aguarda_humano mas cliente mandou')
print('   algo valido antes (suspeita de muito_erro com resposta correta)')
print('=' * 70)
# Conversas que receberam o texto de handoff do bot
cur.execute("""
SELECT c.id, c.contato_nome, c.contato_telefone, m_handoff.data_envio,
       (SELECT conteudo FROM inbox_mensagens
        WHERE conversa_id = c.id AND remetente_tipo='contato'
          AND data_envio < m_handoff.data_envio
        ORDER BY data_envio DESC LIMIT 1) AS msg_cliente_antes
FROM inbox_conversas c
JOIN LATERAL (
    SELECT data_envio FROM inbox_mensagens
    WHERE conversa_id = c.id AND remetente_tipo='bot'
      AND conteudo LIKE 'Tudo bem!%%Vou anotar suas informa%%'
    ORDER BY data_envio DESC LIMIT 1
) m_handoff ON true
WHERE c.tenant_id = %s
  AND c.data_abertura >= NOW() - INTERVAL '7 days'
ORDER BY m_handoff.data_envio DESC;
""", (TID,))
rows = cur.fetchall()
print(f'  Conversas que receberam handoff (7d): {len(rows)}')
import re
for r in rows:
    msg = (r[4] or '').strip()
    # Heuristica: msg do cliente antes do handoff parecia valida?
    suspeita = ''
    if re.search(r'\d{8}', msg.replace('-', '').replace('.', '')):
        suspeita = ' <-- tinha CEP/numero valido!'
    elif msg.lower() in ('sim', 'nao', 'não', 'ok'):
        suspeita = ' <-- resposta sim/nao'
    print(f'    c#{r[0]:4d} {(r[1] or "")[:16]:16s} tel={r[2]:14s} '
          f'ult_cliente={msg[:30]!r}{suspeita}')

cur.close()
conn.close()
