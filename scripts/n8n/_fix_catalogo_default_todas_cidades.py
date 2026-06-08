"""Faz o catalogo do bot retornar planos pra QUALQUER cidade coberta:
troca o default de grupo de `null` (catalogo vazio) para `'B'` nos geradores,
alinhando com ValidarEscolhaPlano que ja usa `|| 'B'`. Backup antes.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'Df1BgcXdg3HAUZwf'
NODES = ['GerarCatalogoPlanos', 'GerarCatalogoPlanos2']
ANTIGO = "const grupo = GRUPO_POR_CIDADE[cidadeNorm] || null;"
NOVO = "const grupo = GRUPO_POR_CIDADE[cidadeNorm] || 'B';"

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
        print(f'AVISO: {nm} nao existe'); continue
    code = nd['parameters'].get('jsCode', '')
    if ANTIGO not in code:
        if NOVO in code:
            print(f'SKIP {nm}: ja usa default B')
        else:
            print(f'AVISO {nm}: linha de grupo nao encontrada')
        continue
    nd['parameters']['jsCode'] = code.replace(ANTIGO, NOVO, 1)
    print(f'OK {nm}: default de grupo agora = B (era null)')
    mudou = True

if not mudou:
    print('\nNada a fazer.'); sys.exit(0)

so = w.get('settings', {})
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
res = n.update_workflow(WID, {'name': w['name'], 'nodes': w['nodes'],
    'connections': w['connections'], 'settings': sl})
print('PUT ok. nodes:', len(res.get('nodes', w['nodes'])))

w2 = n.get_workflow(WID)
for nm in NODES + ['ValidarEscolhaPlano']:
    c = {nd['name']: nd for nd in w2['nodes']}[nm]['parameters'].get('jsCode', '')
    has_null = "|| null;" in c
    has_b = "|| 'B';" in c
    print(f'  {nm}: default_B={has_b} ainda_null={has_null}')
