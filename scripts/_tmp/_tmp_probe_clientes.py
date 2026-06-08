import os, django, json
from collections import Counter
os.environ.setdefault('DJANGO_SETTINGS_MODULE','gerenciador_vendas.settings')
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.sistema.models import Tenant

t = Tenant.objects.get(slug='nuvyon')
integ = IntegracaoAPI.all_tenants.filter(tenant=t, tipo='hubsoft', ativa=True).first()
svc = HubsoftService(integ)

# 1) Tenta endpoint de clientes (lista) — extrair id_origem usado
print('=== Tenta /api/v1/integracao/cliente (pagina 1) ===')
try:
    r = svc._get('/api/v1/integracao/cliente', params={'limit': 50, 'offset': 0}, lead=None)
    keys = list(r.keys())
    print(f'keys: {keys}')
    clientes = r.get('clientes', []) or r.get('data', [])
    print(f'clientes retornados: {len(clientes)}')
    if clientes:
        c = clientes[0]
        print('campos relevantes do 1o cliente:')
        for k in ('id_cliente','codigo_cliente','nome_razaosocial','id_origem','id_origem_cliente','origem','origem_cliente'):
            if k in c: print(f'  {k}: {c[k]!r}')
        # Distribuicao
        origens = Counter()
        for c in clientes:
            v = c.get('id_origem') or c.get('id_origem_cliente')
            if v is None:
                ov = c.get('origem') or c.get('origem_cliente')
                if isinstance(ov, dict): v = ov.get('id_origem') or ov.get('id_origem_cliente')
            origens[str(v)] += 1
        print('\nDistribuicao id_origem:')
        for v, n in origens.most_common(): print(f'  id={v}: {n} clientes')
except HubsoftServiceError as e:
    print(f'ERRO: {str(e)[:200]}')

# 2) Endpoints alternativos de origem_cliente
print('\n=== Outros endpoints candidatos pra origem_cliente ===')
for ep in [
    '/api/v1/integracao/cliente/configuracao/origem_cliente',
    '/api/v1/integracao/cadastro/origem_cliente',
    '/api/v1/integracao/origem-cliente',
    '/api/v1/integracao/configuracao/origem-cliente',
    '/api/v1/integracao/prospecto/configuracao/origem_cliente',
]:
    try:
        r = svc._get(ep, lead=None)
        st = r.get('status')
        if st == 'success':
            data = {k:v for k,v in r.items() if k not in ('status','msg')}
            print(f'[OK] {ep} -> keys={list(data.keys())}')
            for k, v in data.items():
                if isinstance(v, list): print(f'  {k}: {len(v)} itens. Ex: {v[:5]}')
        else:
            print(f'[--] {ep} status={st}')
    except HubsoftServiceError as e:
        print(f'[ER] {ep} {str(e)[:80]}')
