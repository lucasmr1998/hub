"""Verifica dependências (FKs) do tenant Gigamax local pra User e outros."""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'robo', 'dashboard_comercial', 'gerenciador_vendas'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'gerenciador_vendas.settings_local'
django.setup()

from django.contrib.auth.models import User
from apps.sistema.models import PerfilUsuario, PerfilPermissao, PermissaoUsuario

TENANT_ID = 9

# Usuários do tenant
print('=== Users do tenant Gigamax (via PerfilUsuario) ===')
perfis = PerfilUsuario.objects.filter(tenant_id=TENANT_ID).select_related('user')
for p in perfis:
    user = p.user
    print(f'  user_id={user.id} | username={user.username} | email={user.email or "—"} | first_name={user.first_name!r}')

print('\n=== Perfis de permissao customizados ===')
for p in PerfilPermissao.objects.filter(tenant_id=TENANT_ID):
    print(f'  id={p.id} | nome={p.nome}')

print('\n=== PermissaoUsuario ===')
for pu in PermissaoUsuario.objects.filter(tenant_id=TENANT_ID).select_related('user', 'perfil'):
    print(f'  user={pu.user.username} | perfil={pu.perfil.nome if pu.perfil else "—"}')

# Integracoes
print('\n=== IntegracaoAPI do tenant ===')
from apps.integracoes.models import IntegracaoAPI
for i in IntegracaoAPI.all_tenants.filter(tenant_id=TENANT_ID):
    print(f'  id={i.id} | nome={i.nome} | tipo={i.tipo} | ativa={i.ativa}')

# Verificar prod tem esses usuarios
print('\n=== Conferindo se usuarios existem em prod (via SSH) ===')
print('Esta verificacao precisa ser feita por outro script — esse roda local.')
