"""Verificacao de integridade do fluxo Vero Orquestrador apos os fixes."""
import sys, json, re
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'Df1BgcXdg3HAUZwf'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
conns = w['connections']
by_name = {nd['name']: nd for nd in nodes}

print('=' * 64)
print('STATUS GERAL')
print('=' * 64)
print(f'  active: {w.get("active")}')
print(f'  nodes:  {len(nodes)}')

print('\n' + '=' * 64)
print('FIX A — cadeia RG (Step -> Registrar -> Restaura -> SmartSkip)')
print('=' * 64)
def saidas(nm):
    return [c['node'] for pl in conns.get(nm, {}).get('main', []) for c in pl]
for http, restaura in [('Registrar RG Frente Hubtrix', 'Restaura Contexto RG Frente'),
                       ('Registrar RG Verso Hubtrix', 'Restaura Contexto RG Verso')]:
    ok1 = saidas(http) == [restaura]
    ok2 = saidas(restaura) == ['SmartSkip']
    exists = restaura in by_name
    print(f'  {http} -> {saidas(http)}  {"OK" if ok1 else "FALHA"}')
    print(f'  {restaura} existe={exists} -> {saidas(restaura)}  {"OK" if ok2 else "FALHA"}')

print('\n' + '=' * 64)
print('FIX B — muito_erro pre-incremento')
print('=' * 64)
code = by_name['DetectarPedidoHumano']['parameters'].get('jsCode', '')
print('  tentativas_anteriores:', 'tentativas_anteriores' in code)
print('  muito_erro = tentativas_anteriores >= 3:',
      'const muito_erro = tentativas_anteriores >= 3' in code)

print('\n' + '=' * 64)
print('CONSISTENCIA — proximo_nodo setado vs estados do switch')
print('=' * 64)
# Coleta todos proximo_nodo setados em Set nodes
proximos = set()
for nd in nodes:
    if nd.get('type') == 'n8n-nodes-base.set':
        for a in nd.get('parameters', {}).get('assignments', {}).get('assignments', []):
            if a.get('name') == 'proximo_nodo':
                val = a.get('value', '')
                # so valores literais (nao expressao)
                if not str(val).startswith('='):
                    proximos.add(val)
                else:
                    # expressao referenciando outro Step — extrai se simples
                    proximos.add(f'(expr) {val[:60]}')

# Estados do switch
sw = by_name['Por Nodo Atual']['parameters']
def walk(o):
    f = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('value2', 'rightValue') and isinstance(v, str):
                f.append(v)
            else:
                f += walk(v)
    elif isinstance(o, list):
        for i in o:
            f += walk(i)
    return f
estados_switch = set(walk(sw))

print('  Estados reconhecidos pelo switch:', len(estados_switch))
literais = {p for p in proximos if not p.startswith('(expr)')}
print(f'\n  proximo_nodo literais setados pelos Steps: {len(literais)}')
faltando = literais - estados_switch
if faltando:
    print('  >> NAO reconhecidos pelo switch (TRAVARIAM):')
    for p in sorted(faltando):
        print(f'       {p!r}')
else:
    print('  >> Todos reconhecidos pelo switch. OK')

exprs = {p for p in proximos if p.startswith('(expr)')}
if exprs:
    print('\n  proximo_nodo via expressao (verificar manualmente):')
    for p in sorted(exprs):
        print(f'       {p}')

print('\n' + '=' * 64)
print('NODOS ORFAOS (sem conexao de entrada, exceto trigger)')
print('=' * 64)
tem_entrada = set()
for src, outs in conns.items():
    for pl in outs.get('main', []):
        for c in pl:
            tem_entrada.add(c['node'])
orfaos = []
for nd in nodes:
    nm = nd['name']
    tipo = nd.get('type', '')
    if 'webhook' in tipo.lower() or 'trigger' in tipo.lower() or 'manualTrigger' in tipo:
        continue
    if nm not in tem_entrada:
        orfaos.append((nm, tipo))
if orfaos:
    for nm, tipo in orfaos:
        print(f'  ORFAO: {nm!r} ({tipo})')
else:
    print('  Nenhum orfao. OK')
