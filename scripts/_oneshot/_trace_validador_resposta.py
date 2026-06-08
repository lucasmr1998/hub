"""Read-only: rastreia o que o webhook QuestionValidator (nuvyion) devolve.
Segue as conexoes do QuestionValidator e imprime os nos respondToWebhook
e os Set/Code que montam o payload de resposta. Pra avaliar contrato (flat vs wrapped).
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
nodes = {nd['name']: nd for nd in w['nodes']}
conns = w['connections']

# BFS a partir de QuestionValidator
start = 'QuestionValidator'
visited, queue, order = set(), [start], []
while queue:
    cur = queue.pop(0)
    if cur in visited:
        continue
    visited.add(cur); order.append(cur)
    for out in conns.get(cur, {}).get('main', []) or []:
        for c in (out or []):
            queue.append(c['node'])

print(f'Alcancaveis a partir de {start}: {len(order)} nos\n')

# respondToWebhook nodes alcancaveis
print('== respondToWebhook alcancaveis ==')
for name in order:
    nd = nodes.get(name, {})
    if 'respondToWebhook' in nd.get('type', ''):
        p = nd.get('parameters', {})
        print(f'\n-- {name} ({nd["type"]}) --')
        print(json.dumps(p, ensure_ascii=False, indent=2)[:1500])

# Set/Code nodes com 'response'/'answerIsCorrect'/'cep' no payload
print('\n\n== Set/Code que montam resposta (response/answerIsCorrect/cep) ==')
for name in order:
    nd = nodes.get(name, {})
    t = nd.get('type', '')
    raw = json.dumps(nd.get('parameters', {}), ensure_ascii=False)
    if ('set' in t.lower() or 'code' in t.lower()) and any(k in raw for k in ('answerIsCorrect','response','givesServiceToCity','isAClient','json_resultado')):
        print(f'\n-- {name} ({t}) --')
        print(json.dumps(nd.get('parameters', {}), ensure_ascii=False, indent=2)[:2000])
