"""Adiciona o ramo de esgotamento ao fluxo de follow-up TR Carrion (tYckyds4TqPpFOWd):
schedule -> Buscar Esgotados (count>=2, ultimo toque >=10min) -> HTTP transferir_fila
-> Marcar Aguarda Humano. Reusa cred Postgres do fluxo e a cred httpHeaderAuth do
orquestrador (X-N8N-Webhook-Secret). Backup antes. NAO ativa.
"""
import sys, json, uuid, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'tYckyds4TqPpFOWd'
n = N8N()

# cred httpHeaderAuth do orquestrador (sem ecoar o segredo)
orq = n.get_workflow('Df1BgcXdg3HAUZwf')
header_cred = None
for nd in orq['nodes']:
    c = (nd.get('credentials') or {}).get('httpHeaderAuth')
    if c:
        header_cred = c; break
assert header_cred, 'cred httpHeaderAuth nao encontrada no orquestrador'
print('httpHeaderAuth cred:', header_cred.get('name'), '(id oculto)')

w = n.get_workflow(WID)
nodes = w['nodes']; conns = w['connections']
byname = {nd['name']: nd for nd in nodes}
pg_cred = byname['Buscar Stale']['credentials']  # mesma cred Postgres
sched_name = next(nd['name'] for nd in nodes if nd.get('type','').endswith('scheduleTrigger'))
print('schedule node:', sched_name)

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_followup_RAMO_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

def nid(): return str(uuid.uuid4())

q_esgotados = (
    "SELECT telefone, dados\n"
    "FROM vero_session\n"
    "WHERE atualizado_em < NOW() - INTERVAL '5 minutes'\n"
    "  AND atualizado_em > NOW() - INTERVAL '7 days'\n"
    "  AND nodo_atual NOT IN ('inicio', 'concluido', 'aguarda_humano')\n"
    "  AND COALESCE((dados->>'_followup_count')::int, 0) >= 2\n"
    "  AND (dados->>'_followup_enviado_em')::timestamp < NOW() - INTERVAL '10 minutes'\n"
    "LIMIT 50;"
)
n_esgotados = {'parameters': {'operation': 'executeQuery', 'query': q_esgotados, 'options': {}},
    'type': 'n8n-nodes-base.postgres', 'typeVersion': 2.5, 'position': [240, 480],
    'id': nid(), 'name': 'Buscar Esgotados', 'credentials': pg_cred}

http_body = ('={\n  "tenant_slug": "tr-carrion",\n'
             '  "telefone": {{ JSON.stringify($json.telefone) }}\n}')
n_http = {'parameters': {'method': 'POST',
    'url': 'https://app.hubtrix.com.br/api/public/n8n/conversa/transferir-fila/',
    'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
    'sendHeaders': True, 'headerParameters': {'parameters': [
        {'name': 'Content-Type', 'value': 'application/json'}]},
    'sendBody': True, 'specifyBody': 'json', 'jsonBody': http_body, 'options': {}},
    'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [460, 480],
    'id': nid(), 'name': 'Transferir Fila', 'credentials': {'httpHeaderAuth': header_cred}}

q_aguarda = ("UPDATE vero_session SET nodo_atual = 'aguarda_humano'\n"
             "WHERE telefone = '{{ $('Buscar Esgotados').item.json.telefone }}';")
n_aguarda = {'parameters': {'operation': 'executeQuery', 'query': q_aguarda, 'options': {}},
    'type': 'n8n-nodes-base.postgres', 'typeVersion': 2.5, 'position': [680, 480],
    'id': nid(), 'name': 'Marcar Aguarda Humano', 'credentials': pg_cred}

nodes.extend([n_esgotados, n_http, n_aguarda])

# conexoes: schedule -> Buscar Esgotados (alem do Buscar Stale ja existente)
conns.setdefault(sched_name, {}).setdefault('main', [[]])
conns[sched_name]['main'][0].append({'node': 'Buscar Esgotados', 'type': 'main', 'index': 0})
conns['Buscar Esgotados'] = {'main': [[{'node': 'Transferir Fila', 'type': 'main', 'index': 0}]]}
conns['Transferir Fila'] = {'main': [[{'node': 'Marcar Aguarda Humano', 'type': 'main', 'index': 0}]]}

so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes, 'connections': conns, 'settings': sl})
print('PUT ok. (INATIVO)')

w2 = n.get_workflow(WID)
print('active:', w2.get('active'), '| nodes:', len(w2['nodes']))
print('schedule -> ', [c['node'] for c in w2['connections'][sched_name]['main'][0]])
print('Buscar Esgotados -> ', [c['node'] for c in w2['connections'].get('Buscar Esgotados',{}).get('main',[[]])[0]])
print('Transferir Fila -> ', [c['node'] for c in w2['connections'].get('Transferir Fila',{}).get('main',[[]])[0]])
