"""Le o v6 e troca o webhook_aurora (var 3620089 no no var_servidor):
  .../webhook/atendimento-v2  ->  .../webhook/nuvyion
Gera v7. So o #2 (validador). NAO mexe nos endpoints de lead (#1 fica pra decidir).
Destino do validador: https://automation-n8n.v4riem.easypanel.host/webhook/nuvyion
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

B = Path('robo/docs/context/clientes/nuvyon/implementacoes')
SRC = B / 'flow_103_hubtrix_v6.json'
DST = B / 'flow_103_hubtrix_v7.json'

doc = json.loads(SRC.read_text(encoding='utf-8'))
flow = doc['flow']

OLD = 'https://automation-n8n.v4riem.easypanel.host/webhook/atendimento-v2'
NEW = 'https://automation-n8n.v4riem.easypanel.host/webhook/nuvyion'

vs = [o for o in flow if isinstance(o.get('data'), dict) and o['data'].get('identifier') == 'var_servidor']
assert len(vs) == 1, f'var_servidor: achei {len(vs)}'
d = vs[0]['data']
assert 3620089 in d['variables'], 'var 3620089 (webhook_aurora) nao encontrada'
i = d['variables'].index(3620089)
assert d['values'][i] == OLD, f'valor inesperado: {d["values"][i]!r}'
d['values'][i] = NEW

DST.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
print('Gerado:', DST)
print('webhook_aurora agora:', d['values'][i])
# sanity: nenhum atendimento-v2 sobrando
n = json.dumps(doc, ensure_ascii=False).count('webhook/atendimento-v2')
print('ocorrencias de atendimento-v2 restantes:', n, '(esperado 0)')
print('ocorrencias de webhook/nuvyion:', json.dumps(doc, ensure_ascii=False).count('webhook/nuvyion'))
