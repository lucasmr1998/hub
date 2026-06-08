import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','gerenciador_vendas.settings')
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.sistema.models import Tenant

t = Tenant.objects.get(slug='nuvyon')
integ = IntegracaoAPI.all_tenants.filter(tenant=t, tipo='hubsoft', ativa=True).for_each = None
integ = IntegracaoAPI.all_tenants.filter(tenant=t, tipo='hubsoft', ativa=True).first()
svc = HubsoftService(integ)

print('=== GET /api/v1/integracao/prospecto (lista) ===')
try:
    r = svc._get('/api/v1/integracao/prospecto', params={'limit': 30}, lead=None)
    print('keys:', list(r.keys()))
    prospectos = r.get('prospectos') or r.get('data') or []
    print(f'prospectos: {len(prospectos)}')
    if prospectos:
        print('Primeiro:')
        p = prospectos[0]
        for k in ('id_prospecto','nome_razaosocial','cpf_cnpj','id_origem','id_origem_cliente','id_origem_servico','id_vendedor','origem','origem_cliente','servico'):
            if k in p: print(f'  {k}: {p[k]!r}')
        print('Distribuicao id_origem nos prospectos:')
        from collections import Counter
        cn = Counter(str(p.get('id_origem') or p.get('id_origem_cliente')) for p in prospectos)
        for v,n in cn.most_common(): print(f'  id={v}: {n}')
except HubsoftServiceError as e:
    print(f'ERRO: {e}')

# Tambem tenta GET /prospecto/create
print('\n=== GET /api/v1/integracao/prospecto/create ===')
try:
    r = svc._get('/api/v1/integracao/prospecto/create', lead=None)
    print('keys:', list(r.keys()))
    print(json.dumps(r, indent=2, ensure_ascii=False)[:1500])
except HubsoftServiceError as e:
    print(f'ERRO: {e}')
