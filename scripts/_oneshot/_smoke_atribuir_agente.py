"""Smoke test do executor atribuir_agente — usa banco LOCAL (settings_local).

Cria um lead+oport fake na tenant 11 (TR Carrion) com cidade=Palhoça,
executa a regra manualmente e verifica que o responsavel virou Flavia.
Limpa no fim.
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings_local')
django.setup()

from apps.sistema.models import Tenant
from apps.comercial.leads.models import LeadProspecto
from apps.comercial.crm.models import (
    OportunidadeVenda, Pipeline, PipelineEstagio, RegraPipelineEstagio,
)
from apps.comercial.crm.services.automacao_pipeline import _executar_acoes_regra
from django.contrib.auth.models import User

# Usuario fake "flavia"
flavia, _ = User.objects.get_or_create(
    username='_smoke_flavia', defaults={'first_name': 'Flavia', 'last_name': 'Teste'}
)
tenant, _ = Tenant.objects.get_or_create(
    slug='_smoke_carrion', defaults={'nome': 'Smoke Carrion'}
)
pipeline, _ = Pipeline.all_tenants.get_or_create(
    tenant=tenant, nome='Smoke Pipeline'
)
estagio, _ = PipelineEstagio.all_tenants.get_or_create(
    tenant=tenant, pipeline=pipeline, nome='Smoke Aguardando',
    defaults={'ordem': 1, 'slug': '_smoke_aguardando'},
)

# Lead com cidade=Palhoça
lead, _ = LeadProspecto.all_tenants.get_or_create(
    tenant=tenant, telefone='_smoke_99999',
    defaults={'nome_razaosocial': 'Smoke Lead', 'cidade': 'Palhoça', 'estado': 'SC'},
)

# Oportunidade (sem responsavel)
oport, _ = OportunidadeVenda.all_tenants.get_or_create(
    tenant=tenant, lead=lead,
    defaults={'titulo': 'Smoke Oport', 'pipeline': pipeline, 'estagio': estagio,
              'valor_estimado': 100},
)
OportunidadeVenda.all_tenants.filter(pk=oport.pk).update(responsavel=None)
oport.refresh_from_db()

# Regra: condicao cidade=Palhoça, acao atribuir_agente user_id=flavia
regra, _ = RegraPipelineEstagio.all_tenants.get_or_create(
    tenant=tenant, nome='Smoke Regra Roteamento',
    defaults={
        'estagio': None,
        'condicoes': [{'tipo': 'lead_campo', 'campo': 'cidade',
                       'operador': 'igual', 'valor': 'Palhoça'}],
        'acoes': [{'tipo': 'atribuir_agente', 'config': {'user_id': flavia.id}}],
        'ativo': True, 'prioridade': 1,
    },
)

print(f'ANTES: oport.responsavel_id={oport.responsavel_id}')
_executar_acoes_regra(oport, regra)
oport.refresh_from_db()
print(f'DEPOIS: oport.responsavel_id={oport.responsavel_id}  (esperado={flavia.id})')
assert oport.responsavel_id == flavia.id, 'FALHOU: nao atribuiu'

# Segunda execucao nao deve roubar
print('\nSEGUNDA EXECUCAO (deve manter, nao roubar):')
outro_user, _ = User.objects.get_or_create(username='_smoke_outro')
oport.responsavel = outro_user
oport.save()
_executar_acoes_regra(oport, regra)
oport.refresh_from_db()
print(f'DEPOIS: oport.responsavel_id={oport.responsavel_id}  (esperado={outro_user.id} — nao deve mudar)')
assert oport.responsavel_id == outro_user.id, 'FALHOU: roubou lead!'

print('\nOK — todos os asserts passaram.')

# Cleanup
oport.delete()
lead.delete()
regra.delete()
estagio.delete()
pipeline.delete()
flavia.delete()
outro_user.delete()
tenant.delete()
print('Cleanup concluido.')
