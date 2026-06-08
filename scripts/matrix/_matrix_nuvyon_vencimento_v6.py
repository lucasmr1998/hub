"""Le o v5 (que ja tem os planos) e ajusta os vencimentos do menu vivo ura_12 (5626)
-> gera v6 = planos + vencimentos. Mantem ura_9 (6062, morta) intacta.

Dias oferecidos: 5(id9), 10(id4), 15(id5), 20(id6). Remove dia 1.
- node 5636 (era dia1/id28) -> reaproveitado pro dia 20 (id6)
- node 5632 (dia5/id9) e 5633 (dia15/id5): mantidos, so renumera opcao
- +1 no novo pro dia 10 (id4)
Opera por id com asserts.
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

B = Path('robo/docs/context/clientes/nuvyon/implementacoes')
SRC = B / 'flow_103_hubtrix_v5.json'
DST = B / 'flow_103_hubtrix_v6.json'

doc = json.loads(SRC.read_text(encoding='utf-8'))
flow = doc['flow']

V_ID, V_DIA = 3620050, 3620062

def node(nid):
    m = [o for o in flow if o.get('id') == nid and not o.get('edge')]
    assert len(m) == 1, f'node {nid}: achei {len(m)}'
    return m[0]

def edge(src, tgt):
    m = [o for o in flow if o.get('edge') and o.get('source') == src and o.get('target') == tgt]
    assert len(m) == 1, f'edge {src}->{tgt}: achei {len(m)}'
    return m[0]

def set_opt(e, num, dia):
    e['value'] = f'{num} - {dia}'
    e['data']['opt']['number_option'] = num
    e['data']['opt']['description'] = dia

# --- node 5636 (dia1/id28) -> dia20/id6 ---
n5636 = node(5636)
assert n5636['data']['variables'] == [V_ID, V_DIA] and n5636['data']['values'] == [28, 1], n5636['data']['values']
n5636['data']['values'] = [6, 20]
# --- conferir nos mantidos ---
assert node(5632)['data']['values'] == [9, 5], node(5632)['data']['values']    # dia5
assert node(5633)['data']['values'] == [5, 15], node(5633)['data']['values']   # dia15

# template p/ novo no (copia do 5632) e nova edge (copia da 5638)
tpl_node = json.loads(json.dumps(node(5632)))
tpl_edge = json.loads(json.dumps(edge(5626, 5632)))

# --- renumerar edges existentes do menu 5626 ---
set_opt(edge(5626, 5632), 1, 5)    # dia 5
set_opt(edge(5626, 5633), 3, 15)   # dia 15
set_opt(edge(5626, 5636), 4, 20)   # dia 20 (reaproveitado)

# --- novo no + edge p/ dia 10 (id4) ---
maxid = max(o['id'] for o in flow if isinstance(o.get('id'), int))
nid10, eid10 = maxid + 1, maxid + 2

novo = json.loads(json.dumps(tpl_node))
novo['id'] = nid10
novo['data']['identifier'] = 'red_nuvyon_venc10'
novo['data']['values'] = [4, 10]
novo['x'] = tpl_node['x'] + 40
novo['y'] = tpl_node['y'] + 60
flow.append(novo)

nedge = json.loads(json.dumps(tpl_edge))
nedge['id'] = eid10
nedge['source'] = 5626
nedge['target'] = nid10
set_opt(nedge, 2, 10)   # dia 10
flow.append(nedge)

DST.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')

# --- verificacao ---
print('Gerado:', DST, '| novo no dia10:', nid10, '| nova edge:', eid10)
print('\nMenu vivo ura_12 (5626):')
opts = [o for o in flow if o.get('edge') and o.get('source') == 5626
        and o.get('data', {}).get('cnt', {}).get('type') == 'option']
for o in sorted(opts, key=lambda x: x['data']['opt']['number_option']):
    tgt = next(n for n in flow if n.get('id') == o['target'] and not n.get('edge'))
    print(f"  opt {o['data']['opt']['number_option']} | {o['value']!r} -> node {o['target']} vals={tgt['data']['values']} (id_venc={tgt['data']['values'][0]}, dia={tgt['data']['values'][1]})")
