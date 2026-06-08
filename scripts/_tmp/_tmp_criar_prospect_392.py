"""Cria prospect REAL na Nuvyon Artelecom — lead 392 Yuri Honann."""
import os, django, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.comercial.leads.models import LeadProspecto
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

lead = LeadProspecto.all_tenants.get(pk=392)
integ = IntegracaoAPI.all_tenants.filter(tenant=lead.tenant, tipo='hubsoft', ativa=True).first()
svc = HubsoftService(integ)

# Sobrescreve IDs antigos pelos validos
lead.id_vendedor_rp = 743
lead.id_origem = 15
lead.id_origem_servico = None

# Completa endereco via ViaCEP (lead 392 nao tem rua/bairro)
import requests
if not (lead.rua or '').strip() or not (lead.bairro or '').strip():
    cep_limpo = ''.join(c for c in (lead.cep or '') if c.isdigit())
    if len(cep_limpo) == 8:
        r = requests.get(f'https://viacep.com.br/ws/{cep_limpo}/json/', timeout=10)
        if r.ok:
            j = r.json()
            print(f'ViaCEP: {j}')
            lead.rua = lead.rua or j.get('logradouro') or 'A definir'
            lead.bairro = lead.bairro or j.get('bairro') or 'Centro'
            lead.cidade = lead.cidade or j.get('localidade') or 'Sumare'
            lead.estado = lead.estado or j.get('uf') or 'SP'
# numero "S/N" ja vem do mapeador
print()

# Mostrar payload exato que vai
payload = svc._mapear_lead_para_hubsoft(lead)
print('PAYLOAD:')
print(json.dumps(payload, indent=2, ensure_ascii=False, default=str)[:1500])
print()

try:
    resp = svc.cadastrar_prospecto(lead)
    id_prosp = resp.get('prospecto', {}).get('id_prospecto')
    print(f'🎉 SUCESSO! id_prospecto={id_prosp}')
    LeadProspecto.all_tenants.filter(pk=lead.pk).update(
        status_api='processado',
        id_hubsoft=str(id_prosp) if id_prosp else '',
        id_vendedor_rp=743, id_origem=15,
    )
    print(f'Lead 392 marcado processado, id_hubsoft={id_prosp}')
except HubsoftServiceError as e:
    print(f'❌ FALHOU: {e}')
