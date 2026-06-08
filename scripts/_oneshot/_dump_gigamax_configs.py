"""
Gera dump filtrado do tenant Gigamax (id=9) no DB local.
- Inclui apenas configs (não dados operacionais)
- Pula models que já existem em prod (Tenant, User, PerfilUsuario, ConfiguracaoEmpresa)
- Remapeia user_id 18 (local) -> 19 (prod) em PermissaoUsuario
- Salva em /tmp/gigamax_configs_dump.json

Pra aplicar em prod, usar scripts/_apply_gigamax_configs.py (separado).
"""
import os
import sys
import json
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'robo', 'dashboard_comercial', 'gerenciador_vendas'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'gerenciador_vendas.settings_local'
django.setup()

from django.core import serializers
from django.apps import apps as django_apps

TENANT_LOCAL = 9
USER_LOCAL = 18
USER_PROD = 19

# Models a migrar — explícito pra evitar surpresas
# (app_label.ModelName, descrição)
MODELOS = [
    ('sistema.PerfilPermissao', 'Perfil customizado'),
    ('sistema.PermissaoUsuario', 'Permissão do user (REMAP user_id)'),
    ('integracoes.IntegracaoAPI', 'Integrações API (HubSoft, SGP)'),
    ('crm.ConfiguracaoCRM', 'Config CRM'),
    ('crm.OpcaoVencimentoCRM', 'Opções de vencimento'),
    ('crm.ProdutoServico', 'Catálogo de produtos/serviços'),
    # SKIP TipoNotificacao e CanalNotificacao — ja seedados automaticamente em prod
    ('clube.RoletaConfig', 'Config Roleta CS'),
]

print('=== Dump Gigamax (local tenant=9) ===\n')

todos_objs = []

for label, desc in MODELOS:
    Model = django_apps.get_model(label)

    # all_tenants se disponível, senão objects
    manager = getattr(Model, 'all_tenants', Model.objects)
    qs = manager.filter(tenant_id=TENANT_LOCAL)
    qtd = qs.count()
    print(f'  {label:35s} {qtd:>4} — {desc}')
    todos_objs.extend(list(qs))

print(f'\nTotal de objetos: {len(todos_objs)}')

# Serializa
serialized = serializers.serialize('python', todos_objs, indent=2)

# Remapeamento de user_id 18 -> 19
print(f'\n=== Remapeando user_id {USER_LOCAL} -> {USER_PROD} em PermissaoUsuario ===')
remap_count = 0
for obj in serialized:
    if obj['model'] == 'sistema.permissaousuario':
        if obj['fields'].get('user') == USER_LOCAL:
            obj['fields']['user'] = USER_PROD
            remap_count += 1
print(f'  {remap_count} registro(s) remapeado(s)')

# Remapeamento de Funcionalidades por codigo (M2M de PerfilPermissao)
# IDs do local podem nao existir em prod — recuperar pelo codigo
print('\n=== Remapeando funcionalidades de PerfilPermissao por codigo ===')
from apps.sistema.models import Funcionalidade
codigos_locais_por_id = {f.id: f.codigo for f in Funcionalidade.objects.all()}

# Coletar codigos dos perfis
codigos_necessarios = set()
for obj in serialized:
    if obj['model'] == 'sistema.perfilpermissao':
        for fid in obj['fields'].get('funcionalidades', []):
            if fid in codigos_locais_por_id:
                codigos_necessarios.add(codigos_locais_por_id[fid])
print(f'  Codigos de funcionalidade necessarios: {len(codigos_necessarios)}')

# Salvar lista pra remapear depois em prod
import json as _json
codigos_path = os.path.join(os.path.dirname(__file__), 'gigamax_perfil_funcionalidades.json')
with open(codigos_path, 'w', encoding='utf-8') as f:
    _json.dump({
        'perfil_nome': 'Admin',  # vamos remapear pelo nome do perfil
        'tenant_id_prod': 9,
        'codigos': sorted(codigos_necessarios),
    }, f, indent=2)
print(f'  Salvos em: {codigos_path}')

# Remover M2M funcionalidades do dump (vai ser preenchido depois)
remov_m2m = 0
for obj in serialized:
    if obj['model'] == 'sistema.perfilpermissao' and 'funcionalidades' in obj['fields']:
        obj['fields']['funcionalidades'] = []
        remov_m2m += 1
print(f'  M2M funcionalidades zerado em {remov_m2m} PerfilPermissao')

# Sanity check: nenhum tenant_id != 9
print('\n=== Sanity check: todos com tenant_id=9? ===')
fora = [
    obj for obj in serialized
    if obj['fields'].get('tenant') and obj['fields']['tenant'] != TENANT_LOCAL
]
if fora:
    print(f'  [!] {len(fora)} objetos fora — REVISAR')
    for o in fora[:5]:
        print(f'    {o["model"]} pk={o["pk"]} tenant={o["fields"].get("tenant")}')
else:
    print('  [OK] todos os objetos com tenant_id=9')

# Salvar
out_path = '/tmp/gigamax_configs_dump.json'
# Em Windows, usar caminho absoluto Windows
if os.name == 'nt':
    out_path = os.path.join(os.path.dirname(__file__), 'gigamax_configs_dump.json')

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(serialized, f, indent=2, default=str, ensure_ascii=False)

print(f'\n=== Dump salvo em: {out_path} ===')
print(f'Tamanho: {os.path.getsize(out_path):,} bytes')

# Resumo final
print('\n=== Resumo do que vai pra prod ===')
por_model = {}
for obj in serialized:
    por_model[obj['model']] = por_model.get(obj['model'], 0) + 1
for model, qtd in sorted(por_model.items()):
    print(f'  {model:45s} {qtd}')
