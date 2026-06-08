"""Ajusta a parte de ENVIO do fluxo de follow-up Vero/TR Carrion (tYckyds4TqPpFOWd):
- scan 30min -> 5min
- Buscar Stale: abandono 5min, intervalo 10min, contador < 2
- Marcar Enviado: corrige telefone (Buscar Stale) + incrementa _followup_count
Backup antes. NAO ativa (falta o ramo de handoff/esgotamento).
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'tYckyds4TqPpFOWd'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
byname = {nd['name']: nd for nd in nodes}

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_followup_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk, '| active=', w.get('active'))

# 1. schedule 30 -> 5
sched = next(nd for nd in nodes if nd.get('type','').endswith('scheduleTrigger'))
iv = sched['parameters']['rule']['interval'][0]
assert iv.get('minutesInterval') == 30, iv
iv['minutesInterval'] = 5
print('schedule:', iv)

# 2. Buscar Stale
busca = byname['Buscar Stale']
busca['parameters']['query'] = (
    "SELECT telefone, nodo_atual, dados, atualizado_em\n"
    "FROM vero_session\n"
    "WHERE atualizado_em < NOW() - INTERVAL '5 minutes'\n"
    "  AND atualizado_em > NOW() - INTERVAL '7 days'\n"
    "  AND nodo_atual NOT IN ('inicio', 'concluido', 'aguarda_humano')\n"
    "  AND COALESCE((dados->>'_followup_count')::int, 0) < 2\n"
    "  AND (dados->>'_followup_enviado_em' IS NULL\n"
    "       OR (dados->>'_followup_enviado_em')::timestamp < NOW() - INTERVAL '10 minutes')\n"
    "LIMIT 50;"
)

# 3. Marcar Enviado (fix telefone + incrementa contador)
marcar = byname['Marcar Enviado']
marcar['parameters']['query'] = (
    "UPDATE vero_session\n"
    "SET dados = jsonb_set(\n"
    "      jsonb_set(COALESCE(dados, '{}'::jsonb),\n"
    "                '{_followup_enviado_em}', to_jsonb(NOW()::text), true),\n"
    "      '{_followup_count}',\n"
    "      to_jsonb(COALESCE((dados->>'_followup_count')::int, 0) + 1), true)\n"
    "WHERE telefone = '{{ $('Buscar Stale').item.json.telefone }}';"
)

so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': sl})
print('PUT ok. (continua INATIVO)')

w2 = n.get_workflow(WID)
print('active:', w2.get('active'))
b2 = next(nd for nd in w2['nodes'] if nd['name'] == 'Buscar Stale')
print('Buscar Stale tem contador<2:', "_followup_count')::int, 0) < 2" in b2['parameters']['query'])
m2 = next(nd for nd in w2['nodes'] if nd['name'] == 'Marcar Enviado')
print('Marcar usa Buscar Stale telefone:', "$('Buscar Stale')" in m2['parameters']['query'])
