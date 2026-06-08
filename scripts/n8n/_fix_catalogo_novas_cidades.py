"""Adiciona Palhoca/Novo Hamburgo/Francisco Beltrao ao grupo A do catalogo
hardcoded do bot (nodes GerarCatalogoPlanos, GerarCatalogoPlanos2,
ValidarEscolhaPlano). Backup antes. Idempotente.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'Df1BgcXdg3HAUZwf'
NODES = ['GerarCatalogoPlanos', 'GerarCatalogoPlanos2', 'ValidarEscolhaPlano']
ANCHOR = "'piratininga': 'A',"
NOVO = ANCHOR + "\n  'palhoca': 'A', 'novo hamburgo': 'A', 'francisco beltrao': 'A',"

n = N8N()
w = n.get_workflow(WID)
by_name = {nd['name']: nd for nd in w['nodes']}

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_orquestrador_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

mudou = False
for nm in NODES:
    nd = by_name.get(nm)
    if not nd:
        print(f'AVISO: node {nm} nao existe'); continue
    code = nd['parameters'].get('jsCode', '')
    if "'palhoca'" in code:
        print(f'SKIP {nm}: ja tem palhoca'); continue
    if ANCHOR not in code:
        print(f'AVISO {nm}: ancora nao encontrada'); continue
    nd['parameters']['jsCode'] = code.replace(ANCHOR, NOVO, 1)
    print(f'OK {nm}: 3 cidades adicionadas ao grupo A')
    mudou = True

if not mudou:
    print('\nNada a fazer.'); sys.exit(0)

settings_orig = w.get('settings', {})
settings_limpo = {k: settings_orig[k] for k in (
    'executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in settings_orig}
res = n.update_workflow(WID, {'name': w['name'], 'nodes': w['nodes'],
    'connections': w['connections'], 'settings': settings_limpo})
print('PUT ok. nodes:', len(res.get('nodes', w['nodes'])))

# Verifica
w2 = n.get_workflow(WID)
key = "'palhoca'"
for nm in NODES:
    c = {nd['name']: nd for nd in w2['nodes']}[nm]['parameters'].get('jsCode', '')
    print(f'  {nm}: tem palhoca={key in c}')
