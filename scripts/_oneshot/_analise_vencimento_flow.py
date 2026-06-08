"""Read-only: mapeia TODOS os pontos de vencimento no flow_103_v4.
- nos redirect que setam id_vencimento_prospect (3620050)
- todas as option edges que apontam pra eles (source URA, num, label, dia, id)
- agrupado por URA de origem
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

SRC = Path('robo/docs/context/clientes/nuvyon/implementacoes/flow_103_hubtrix_v4.json')
flow = json.loads(SRC.read_text(encoding='utf-8'))['flow']
V_ID = 3620050

# nos redirect de vencimento
venc_nodes = {}
for o in flow:
    d = o.get('data')
    if isinstance(d, dict) and isinstance(d.get('variables'), list) and V_ID in d['variables']:
        i = d['variables'].index(V_ID)
        vals = d.get('values', [])
        idv = vals[i] if i < len(vals) else None
        # dia geralmente eh o proximo var (3620062)
        dia = vals[1] if len(vals) > 1 else None
        venc_nodes[o['id']] = {'id_venc': idv, 'dia': dia, 'component': d.get('component'),
                               'vars': d['variables'], 'vals': vals, 'ident': d.get('identifier')}

print('NOS REDIRECT DE VENCIMENTO:')
for nid, v in venc_nodes.items():
    print(f"  node {nid} ({v['ident']}): id_venc={v['id_venc']} dia={v['dia']} comp={v['component']} vars={v['vars']} vals={v['vals']}")

# option edges que apontam pra esses nos
print('\nOPTION EDGES -> nos de vencimento (agrupado por URA origem):')
from collections import defaultdict
by_src = defaultdict(list)
for o in flow:
    if o.get('edge') and o.get('target') in venc_nodes and o.get('data', {}).get('cnt', {}).get('type') == 'option':
        op = o['data']['opt']
        by_src[o['source']].append((op.get('number_option'), o.get('value'), op.get('description'),
                                    o['target'], venc_nodes[o['target']]['dia'], venc_nodes[o['target']]['id_venc'], o['id']))

for src, opts in by_src.items():
    # nome da URA origem
    ura = next((x for x in flow if x.get('id') == src), {})
    msg = (ura.get('data', {}) or {}).get('message', '') if isinstance(ura.get('data'), dict) else ''
    print(f"\n  URA origem {src} ({(ura.get('data') or {}).get('identifier','?') if isinstance(ura.get('data'),dict) else '?'}): {msg[:60]!r}")
    for num, val, desc, tgt, dia, idv, eid in sorted(opts, key=lambda x: (x[0] or 0)):
        print(f"    opt {num} | {val!r} desc={desc} -> node {tgt} (dia {dia}, id {idv}) [edge {eid}]")
