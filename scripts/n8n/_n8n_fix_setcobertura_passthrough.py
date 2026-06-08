"""Ajusta SetCoberturaViab: repassa TODOS os campos do endereco (ViaCEP) como antes,
so adicionando nome_cidade quando ha projeto. Resposta ao Matrix volta a ser identica
a de antes (so a fonte da decisao muda). Backup, desativa, PUT, reativa.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
byname = {nd['name']: nd for nd in nodes}

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_nuvyon_FIXSET_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

novo = (
    "const viab = $input.first().json;\n"
    "const addr = $('CheckErrorCEP1').first().json;\n"
    "const p = (viab && viab.resultado) ? viab.resultado.projetos : null;\n"
    "const found = Array.isArray(p) && p.length > 0;\n"
    "const out = { ...addr };\n"               # repassa TUDO do ViaCEP (como antes)
    "if (found) { out.nome_cidade = addr.localidade; } else { delete out.nome_cidade; }\n"
    "return [{ json: out }];"
)
sc = byname['SetCoberturaViab']
sc['parameters']['jsCode'] = novo
print('SetCoberturaViab atualizado (passthrough completo).')

so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
try:
    n.deactivate_workflow(WID)
except Exception as e:
    print('deactivate:', str(e)[:150])
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': sl})
r = n.activate_workflow(WID)
print('reativado:', r.get('active') if isinstance(r, dict) else r)
