"""Fix: nó Entrada do N8N nao trata localizacao -> vira '(midia)'.
Adiciona deteccao de LocationMessage no conteudo_inbox, montando link Maps.
Backup antes. Idempotente (pula se ja tem degreesLatitude no codigo).
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'Df1BgcXdg3HAUZwf'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
by_name = {nd['name']: nd for nd in nodes}

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_orquestrador_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

ent = by_name['Entrada']['parameters']['assignments']['assignments']
alvo = next((a for a in ent if a.get('name') == 'conteudo_inbox'), None)
if not alvo:
    sys.exit('conteudo_inbox nao encontrado')

val = alvo['value']
if 'degreesLatitude' in val:
    print('Fix ja aplicado.')
    sys.exit(0)

# Insere deteccao de localizacao logo apos a checagem de texto
anchor = "if (txt && typeof txt === 'string') return txt;"
loc_code = (" if (c.degreesLatitude != null && c.degreesLongitude != null) "
            "{ const loc = [c.name, c.address].filter(Boolean).join(' - '); "
            "return '\\ud83d\\udccd ' + (loc ? loc + ' ' : '') + "
            "'https://maps.google.com/?q=' + c.degreesLatitude + ',' + c.degreesLongitude; }")
if anchor not in val:
    sys.exit('ancora nao encontrada no conteudo_inbox')
novo = val.replace(anchor, anchor + loc_code)
alvo['value'] = novo
print('conteudo_inbox atualizado.')

settings_orig = w.get('settings', {})
settings_limpo = {k: settings_orig[k] for k in (
    'executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in settings_orig}
res = n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': settings_limpo})
print('PUT ok. nodes:', len(res.get('nodes', nodes)))

# Verifica
w2 = n.get_workflow(WID)
v2 = next(a['value'] for a in {nd['name']: nd for nd in w2['nodes']}['Entrada']['parameters']['assignments']['assignments'] if a['name']=='conteudo_inbox')
print('Verificacao - tem degreesLatitude:', 'degreesLatitude' in v2)
