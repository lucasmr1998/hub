"""Testa IDs sequenciais de origem_cliente. Manda CPF invalido proposital
pra NAO criar prospect real — apenas detecta qual ID a API aceita.

Erros esperados:
  - 'origem cliente invalido' = ID errado, segue testando
  - 'cpf' / 'checksum' = ID aceito! Para e mostra.
  - 'origem cliente obrigatoria' = ID nao enviado (bug script)
"""
import os, django, json, copy
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.comercial.leads.models import LeadProspecto
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

lead = LeadProspecto.all_tenants.get(pk=463)  # Pedro Paulo Nuvyon
integ = IntegracaoAPI.all_tenants.filter(tenant=lead.tenant, tipo='hubsoft', ativa=True).first()
svc = HubsoftService(integ)

# Forca CPF invalido pra parar antes de criar
lead.cpf_cnpj = '11111111111'   # repetidos — checksum invalido
lead.id_vendedor_rp = 743        # ja sabemos que esse passou
lead.id_origem_servico = None    # opcional

aceitos_origem = []
print(f'{"id":>3} {"status":<6}  msg')
for id_origem in range(1, 31):
    lead.id_origem = id_origem
    try:
        resp = svc.cadastrar_prospecto(lead)
        # Se aceitar: CRIOU prospect (ruim)
        print(f'{id_origem:>3} SUCCESS  prospect CRIADO! id_prospecto={resp.get("prospecto",{}).get("id_prospecto")}')
        aceitos_origem.append(id_origem)
        # Para imediatamente — nao quer criar mais
        break
    except HubsoftServiceError as e:
        msg = str(e)[:200].lower()
        if 'origem' in msg and ('invalido' in msg or 'inválido' in msg) and 'cliente' in msg:
            print(f'{id_origem:>3} reject  origem_cliente invalido')
        elif 'cpf' in msg or 'checksum' in msg:
            print(f'{id_origem:>3} CPF!    {str(e)[:140]}')
            aceitos_origem.append(id_origem)
            # CPF rejeitou = origem foi aceita, podemos parar
            break
        else:
            print(f'{id_origem:>3} other   {str(e)[:140]}')
    except Exception as e:
        print(f'{id_origem:>3} EXC     {type(e).__name__}: {str(e)[:140]}')

print(f'\n>>> IDs aceitos (provavelmente validos): {aceitos_origem}')
