"""Implementa viabilidade HubSoft no validador Nuvyon (kIGvBSkGBUDpO2V4):
- substitui SelecionarCidade1 (Postgres cidade_atendida) por: TokenHubsoftViab ->
  ViabilidadeHubsoft -> SetCoberturaViab (Code) -> If (reusa If/Merge1/Edit Fields).
- givesServiceToCity passa a vir de 'existe projeto na viabilidade'.
- de quebra: repointa TokenHubsoft3 + 'Consulta dados cliente' (isAClient) p/ artelecom.
Creds lidas de .env.nuvyon_hubsoft (nao hardcoda secret). Backup, desativa, PUT, reativa.
"""
import sys, json, uuid, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
ART = 'https://api.artelecom.hubsoft.com.br'

env = {}
for l in Path('.env.nuvyon_hubsoft').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
token_body = json.dumps({
    'client_id': env['HUBSOFT_CLIENT_ID'], 'client_secret': env['HUBSOFT_CLIENT_SECRET'],
    'username': env['HUBSOFT_USERNAME'], 'password': env['HUBSOFT_PASSWORD'],
    'grant_type': env['HUBSOFT_GRANT_TYPE'],
}, ensure_ascii=False, indent=1)

n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
conns = w['connections']
byname = {nd['name']: nd for nd in nodes}

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_nuvyon_IMPLVIAB_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

# asserts de estrutura esperada
assert 'SelecionarCidade1' in byname and 'CheckErrorCEP1' in byname and 'If' in byname
assert conns['CheckErrorCEP1']['main'][0] == [
    {'node': 'SelecionarCidade1', 'type': 'main', 'index': 0},
    {'node': 'Merge1', 'type': 'main', 'index': 1}], conns['CheckErrorCEP1']['main'][0]

posx, posy = byname['SelecionarCidade1']['position']

viab_body = ('={\n "tipo_busca": "endereco",\n "raio": 1000,\n "endereco": {\n'
             '  "numero": "S/N",\n'
             '  "endereco": "{{ $(\'CheckErrorCEP1\').item.json.logradouro }}",\n'
             '  "bairro": "{{ $(\'CheckErrorCEP1\').item.json.bairro }}",\n'
             '  "cidade": "{{ $(\'CheckErrorCEP1\').item.json.localidade }}",\n'
             '  "estado": "{{ $(\'CheckErrorCEP1\').item.json.uf }}"\n },\n'
             ' "detalhar_portas": false\n}')

set_code = (
    "const viab = $input.first().json;\n"
    "const addr = $('CheckErrorCEP1').first().json;\n"
    "const p = (viab && viab.resultado) ? viab.resultado.projetos : null;\n"
    "const found = Array.isArray(p) && p.length > 0;\n"
    "const out = { cep: addr.cep, logradouro: addr.logradouro, bairro: addr.bairro,"
    " localidade: addr.localidade, uf: addr.uf };\n"
    "if (found) { out.nome_cidade = addr.localidade; }\n"
    "return [{ json: out }];"
)

tok_node = {
    'parameters': {'method': 'POST', 'url': f'{ART}/oauth/token', 'sendBody': True,
                   'specifyBody': 'json', 'jsonBody': token_body, 'options': {}},
    'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2,
    'position': [posx, posy - 120], 'id': str(uuid.uuid4()), 'name': 'TokenHubsoftViab'}
viab_node = {
    'parameters': {'method': 'POST',
                   'url': f'{ART}/api/v1/integracao/mapeamento/viabilidade/consultar',
                   'sendBody': True, 'specifyBody': 'json', 'jsonBody': viab_body,
                   'sendHeaders': True, 'headerParameters': {'parameters': [
                       {'name': 'Authorization', 'value': '=Bearer {{ $json.access_token }}'}]},
                   'options': {}},
    'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2,
    'position': [posx + 180, posy - 120], 'id': str(uuid.uuid4()), 'name': 'ViabilidadeHubsoft'}
set_node = {
    'parameters': {'jsCode': set_code},
    'type': 'n8n-nodes-base.code', 'typeVersion': 2,
    'position': [posx + 360, posy - 120], 'id': str(uuid.uuid4()), 'name': 'SetCoberturaViab'}
nodes.extend([tok_node, viab_node, set_node])

# rewire
conns['CheckErrorCEP1']['main'][0] = [
    {'node': 'TokenHubsoftViab', 'type': 'main', 'index': 0},
    {'node': 'Merge1', 'type': 'main', 'index': 1}]
conns['TokenHubsoftViab'] = {'main': [[{'node': 'ViabilidadeHubsoft', 'type': 'main', 'index': 0}]]}
conns['ViabilidadeHubsoft'] = {'main': [[{'node': 'SetCoberturaViab', 'type': 'main', 'index': 0}]]}
conns['SetCoberturaViab'] = {'main': [[{'node': 'If', 'type': 'main', 'index': 0}]]}
conns.pop('SelecionarCidade1', None)  # orfa o no Postgres

# isAClient -> artelecom
byname['TokenHubsoft3']['parameters']['url'] = f'{ART}/oauth/token'
byname['TokenHubsoft3']['parameters']['jsonBody'] = token_body
byname['Consulta dados cliente']['parameters']['url'] = f'{ART}/api/v1/integracao/cliente'

# PUT (desativa -> update -> reativa)
so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
try:
    n.deactivate_workflow(WID); print('Desativado p/ editar.')
except Exception as e:
    print('deactivate:', str(e)[:200])
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes, 'connections': conns, 'settings': sl})
print('PUT ok. nodes agora:', len(nodes))
try:
    r = n.activate_workflow(WID); print('Reativado:', r.get('active') if isinstance(r, dict) else r)
except Exception as e:
    print('ATIVACAO FALHOU:', str(e)[:400])

w2 = n.get_workflow(WID)
print('active:', w2.get('active'))
nn = {x['name'] for x in w2['nodes']}
print('novos presentes:', {'TokenHubsoftViab','ViabilidadeHubsoft','SetCoberturaViab'} <= nn)
print('CheckErrorCEP1.main[0] ->', [c['node'] for c in w2['connections']['CheckErrorCEP1']['main'][0]])
print('isAClient url:', next(x for x in w2['nodes'] if x['name']=='Consulta dados cliente')['parameters']['url'])
