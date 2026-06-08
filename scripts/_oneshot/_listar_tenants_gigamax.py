"""Lista tenants no DB local pra encontrar Gigamax."""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'robo', 'dashboard_comercial', 'gerenciador_vendas'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'gerenciador_vendas.settings_local'
django.setup()

from apps.sistema.models import Tenant

print('=== Tenants no DB local ===')
for t in Tenant.objects.all().order_by('id'):
    print(f'  id={t.id} | nome={t.nome!r} | slug={t.slug!r}')

# Tentar achar Gigamax
giga = Tenant.objects.filter(nome__icontains='gigamax').first() or Tenant.objects.filter(slug__icontains='gigamax').first()
if giga:
    print(f'\n=== Gigamax encontrada local ===')
    print(f'id={giga.id} | nome={giga.nome} | slug={giga.slug}')
else:
    print('\n[!] Gigamax nao encontrada por nome/slug.')
