"""Gera flow_103_hubtrix_v5.json a partir do v4: troca os planos Megalink
pelos planos reais da Nuvyon (HubSoft artelecom) mantendo o funil + framing promo.

Destaque (ura_plano): 600MB R$109,90 id_plano_rp=1236
Menu (ura_plano_2): 300/400/500/800 (ids 758/770/707/696)

Opera por id de no/edge com asserts (falha alto se a estrutura divergir).
Nao toca em credenciais, HubSoft, nem na logica de validacao.
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

BASE = Path('robo/docs/context/clientes/nuvyon/implementacoes')
SRC = BASE / 'flow_103_hubtrix_v4.json'
DST = BASE / 'flow_103_hubtrix_v5.json'

doc = json.loads(SRC.read_text(encoding='utf-8'))
flow = doc['flow']
by_id = {}
for o in flow:
    if isinstance(o.get('id'), int):
        by_id.setdefault(o['id'], []).append(o)

def one(nid):
    lst = by_id.get(nid, [])
    assert len(lst) == 1, f'id {nid}: esperava 1 objeto, achei {len(lst)}'
    return lst[0]

# vars de plano
V_ID, V_VALOR, V_TITULO = 3620058, 3620059, 3620063
V_PERGUNTA, V_PROXPASS = 3620075, 3620077

DESTAQUE_MSG = (
    "##1f4e3## Ótima notícia, {#CONTATO.NOME}!\n\n"
    "Promoção exclusiva da Nuvyon, válida somente neste mês, com "
    "condição especial para pagamento até a data de vencimento.\n\n"
    "##1f4f6## 600 Mega de velocidade\n"
    "##1f4b0## Por apenas R$ 109,90/mês (com desconto de pontualidade)\n\n"
    "##1f680## Ideal para filmes e séries sem travar, jogos online e home office."
)
MENU_MSG = "Temos outros planos disponíveis. Escolha o que combina com você:"

# ---- 1. destaque ura_plano (5679) ----
n = one(5679)
assert n['data'].get('identifier') == 'ura_plano', n['data'].get('identifier')
n['data']['message'] = DESTAQUE_MSG

# ---- 2. redirect Contratar (5684) ----
n = one(5684)
assert n['data']['variables'] == [V_ID, V_VALOR, V_TITULO, V_PERGUNTA, V_PROXPASS], n['data']['variables']
n['data']['values'] = [1236, 109.9, "Plano de 600MB", "", "msg_cep"]

# ---- 3. menu ura_plano_2 (5691) ----
n = one(5691)
assert n['data'].get('identifier') == 'ura_plano_2', n['data'].get('identifier')
n['data']['message'] = MENU_MSG

# ---- 4. 5906 (era 620MB) -> 300MB ----
n = one(5906)
assert n['data']['variables'] == [V_ID, V_VALOR, V_TITULO], n['data']['variables']
n['data']['values'] = [758, 78.9, "Plano de 300MB"]
template_node = json.loads(json.dumps(one(5689)))  # snapshot p/ novos nos

# ---- 5. 5689 (era Turbo) -> 800MB ----
n = one(5689)
assert n['data']['variables'] == [V_ID, V_VALOR, V_TITULO], n['data']['variables']
n['data']['values'] = [696, 189.9, "Plano de 800MB"]

# ---- edges das opcoes do menu (source 5691) ----
def edge(src, tgt):
    for o in flow:
        if o.get('edge') and o.get('source') == src and o.get('target') == tgt:
            return o
    raise AssertionError(f'edge {src}->{tgt} nao encontrada')

def set_opt(e, num, label, desc, preco):
    e['value'] = f'{num} - {label}'
    e['data']['opt']['number_option'] = num
    e['data']['opt']['description'] = desc
    e['data']['opt']['extraDescription'] = preco

set_opt(edge(5691, 5906), 1, '300MB', 'Plano de 300MB', '*R$ 78,90/mês*')
set_opt(edge(5691, 5689), 4, '800MB', 'Plano de 800MB', '*R$ 189,90/mês*')
# Nuvyon Energia: REMOVE a opcao do menu (edge 5691->6034).
# No 6034 + sub-flow ficam orfaos (inofensivos, fora do alcance do cliente).
en = edge(5691, 6034)
assert en['data']['opt']['description'] == 'Nuvyon Energia', en['data']['opt']['description']
flow.remove(en)
# voltar: 6 -> 5
ev = edge(5691, 5701)
ev['value'] = '5 - voltar menu'
ev['data']['opt']['number_option'] = 5

# ---- novos ids ----
maxid = max(o['id'] for o in flow if isinstance(o.get('id'), int))
nid_400, nid_500 = maxid + 1, maxid + 2
eid_400, eid_500 = maxid + 3, maxid + 4

edge_template = json.loads(json.dumps(edge(5691, 5689)))

def novo_redirect(nid, ident, refnode, id_plano, valor, titulo, dx):
    o = json.loads(json.dumps(template_node))
    o['id'] = nid
    o['data']['identifier'] = ident
    o['data']['values'] = [id_plano, valor, titulo]
    o['x'] = refnode['x'] + dx
    o['y'] = refnode['y'] + 90
    return o

def novo_edge(eid, tgt, num, label, desc, preco):
    o = json.loads(json.dumps(edge_template))
    o['id'] = eid
    o['source'] = 5691
    o['target'] = tgt
    set_opt(o, num, label, desc, preco)
    return o

ref = one(5689)
flow.append(novo_redirect(nid_400, 'red_nuvyon_400', ref, 770, 89.9, 'Plano de 400MB', -120))
flow.append(novo_edge(eid_400, nid_400, 2, '400MB', 'Plano de 400MB', '*R$ 89,90/mês*'))
flow.append(novo_redirect(nid_500, 'red_nuvyon_500', ref, 707, 99.9, 'Plano de 500MB', 120))
flow.append(novo_edge(eid_500, nid_500, 3, '500MB', 'Plano de 500MB', '*R$ 99,90/mês*'))

DST.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')

# ---- verificacao ----
print('Gerado:', DST)
print('Novos nos (redirect):', nid_400, '(400MB)', nid_500, '(500MB)')
print('Novas edges:', eid_400, eid_500)
print('\nMenu ura_plano_2 (opcoes):')
for o in sorted([x for x in flow if x.get('edge') and x.get('source') == 5691
                 and x.get('data', {}).get('cnt', {}).get('type') == 'option'],
                key=lambda x: x['data']['opt']['number_option']):
    op = o['data']['opt']
    print(f"  {op['number_option']} | {op['description']:18s} {op.get('extraDescription','')} -> tgt {o['target']}")
def find(nid):
    return next(o for o in flow if o.get('id') == nid)

print('\nValores gravados:')
for nid, nome in [(5684, 'destaque/Contratar'), (5906, 'op1 300MB'), (nid_400, 'op2 400MB'),
                  (nid_500, 'op3 500MB'), (5689, 'op4 800MB')]:
    print(f'  {nome:20s} node {nid}: {find(nid)["data"]["values"]}')
