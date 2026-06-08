import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','gerenciador_vendas.settings')
django.setup()
from apps.comercial.leads.models import LeadProspecto
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.sistema.models import Tenant

t = Tenant.objects.get(slug='nuvyon')
integ = IntegracaoAPI.all_tenants.filter(tenant=t, tipo='hubsoft', ativa=True).first()
svc = HubsoftService(integ)
lead = LeadProspecto.all_tenants.get(pk=463)
lead.id_vendedor_rp = 743
lead.id_origem_servico = None
lead.id_origem = None

payload = svc._mapear_lead_para_hubsoft(lead)
print('PAYLOAD:')
print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))

# Tenta /prospecto/create
print('\n=== POST /api/v1/integracao/prospecto/create ===')
try:
    r = svc._post('/api/v1/integracao/prospecto/create', json=payload, lead=lead)
    print('RESPOSTA:', json.dumps(r, indent=2, ensure_ascii=False)[:2000])
except HubsoftServiceError as e:
    print(f'ERRO: {e}')

# Tenta buscar cliente real existente pra extrair id_origem_cliente usado
print('\n=== Busca cliente real (qualquer) por CPF generico ===')
for cpf_busca in ['00000000000', '11111111111', '01000000000', '03000000000']:
    try:
        r = svc._get('/api/v1/integracao/cliente', params={'busca':'cpf_cnpj','termo_busca':cpf_busca}, lead=None)
        if r.get('status') == 'success':
            clientes = r.get('clientes', [])
            if clientes:
                print(f'  CPF {cpf_busca}: encontrou {len(clientes)} clientes')
                c = clientes[0]
                for k in ('id_cliente','codigo_cliente','nome_razaosocial','id_origem','id_origem_cliente','origem_cliente'):
                    if k in c: print(f'    {k}: {c[k]!r}')
                break
    except HubsoftServiceError as e:
        pass
