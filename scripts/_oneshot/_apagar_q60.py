"""Apaga a copia antiga/baguncada q60Omy70nfmGgBQt (substituida por kIGvBSkGBUDpO2V4).
Backup completo antes. Confirma que esta inativa antes de deletar.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'q60Omy70nfmGgBQt'
n = N8N()
w = n.get_workflow(WID)
print(f'Alvo: {w["name"]}  active={w.get("active")} nodes={len(w["nodes"])}')

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_q60_DELETADO_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

if w.get('active'):
    print('Estava ativo -> desativando antes de apagar.')
    n.deactivate_workflow(WID)

r = n.delete_workflow(WID)
print('DELETE ok. resp id:', r.get('id') if isinstance(r, dict) else r)

# confirma sumico
ids = [x['id'] for x in n.list_workflows().get('data', [])]
print('q60 ainda existe?', WID in ids)
