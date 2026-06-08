"""Cria prospect REAL na Nuvyon Artelecom — Pedro Paulo (lead 463).
Usa id_origem_cliente=15 (descoberto via brute force).
"""
import os, django, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.comercial.leads.models import LeadProspecto
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

lead = LeadProspecto.all_tenants.get(pk=463)
integ = IntegracaoAPI.all_tenants.filter(tenant=lead.tenant, tipo='hubsoft', ativa=True).first()
svc = HubsoftService(integ)

# Configura lead com os IDs validos descobertos
lead.id_vendedor_rp = 743     # hubtrix (validado)
lead.id_origem = 15            # origem_cliente VALIDA (descoberta brute force)
lead.id_origem_servico = None  # opcional, omitir

print(f'=== Tentando cadastrar prospect REAL ===')
print(f'  lead: pk={lead.pk} {lead.nome_razaosocial!r}')
print(f'  cpf: {lead.cpf_cnpj}')
print(f'  id_vendedor={lead.id_vendedor_rp}  id_origem_cliente={lead.id_origem}  id_servico={lead.id_plano_rp}')

try:
    resp = svc.cadastrar_prospecto(lead)
    id_prosp = resp.get('prospecto', {}).get('id_prospecto')
    print(f'\n🎉 SUCESSO! Prospect criado.')
    print(f'   id_prospecto HubSoft: {id_prosp}')
    print(f'\nResposta completa:')
    print(json.dumps(resp, indent=2, ensure_ascii=False)[:2000])
    # PERSISTE no lead — primeiro prospect REAL criado via API
    LeadProspecto.all_tenants.filter(pk=lead.pk).update(
        status_api='processado',
        id_hubsoft=str(id_prosp) if id_prosp else '',
    )
    print(f'\n✓ Lead {lead.pk} marcado status_api=processado, id_hubsoft={id_prosp}')
except HubsoftServiceError as e:
    print(f'\n❌ FALHOU: {e}')
except Exception as e:
    print(f'\n💥 ERRO INESPERADO: {type(e).__name__}: {e}')
