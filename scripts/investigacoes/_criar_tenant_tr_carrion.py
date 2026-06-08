"""
Cria tenant T R Carrion em producao com admin pessoal do Lucas.

Como rodar (EasyPanel console do container Django):
    python manage.py shell < scripts/_criar_tenant_tr_carrion.py

Ou interativo (preferido — copia/cola no shell):
    python manage.py shell
    >>> exec(open('scripts/_criar_tenant_tr_carrion.py').read())

Idempotente: aborta se ja existir tenant com mesmo slug/CNPJ ou user com mesmo username.
"""
import secrets
import string
from django.contrib.auth.models import User
from django.db import transaction
from apps.sistema.models import (
    Tenant, PerfilUsuario, PermissaoUsuario, PerfilPermissao,
    Funcionalidade, ConfiguracaoEmpresa,
)

# ============================================================================
# DADOS DO TENANT (do cartao CNPJ)
# ============================================================================

TENANT_DATA = {
    'nome': 'T R Carrion',
    'slug': 'tr-carrion',
    'cnpj': '07.580.957/0001-01',
    'modulo_comercial': True,
    'plano_comercial': 'starter',
    'modulo_marketing': False,
    'modulo_cs': False,
    'modulo_workspace': False,
    'ativo': True,
    'em_trial': False,
}

ADMIN_DATA = {
    'username': 'lucas.carrion',
    'email': 'lucasmr1998@live.com',
    'first_name': 'Lucas',
    'last_name': 'Carrion (Admin)',
}

EMPRESA_DATA = {
    'nome_empresa': 'T R CARRION UNIPESSOAL LTDA',
}

# Senha aleatoria forte (12 chars: letras + digitos + alguns simbolos seguros)
ALFABETO_SENHA = string.ascii_letters + string.digits + '!@#$%&*'
SENHA_GERADA = ''.join(secrets.choice(ALFABETO_SENHA) for _ in range(12))


# ============================================================================
# CHECAGENS PRE-EXECUCAO
# ============================================================================

print("=" * 70)
print("CRIACAO DE TENANT EM PRODUCAO — T R CARRION")
print("=" * 70)

erros = []
if Tenant.objects.filter(slug=TENANT_DATA['slug']).exists():
    erros.append(f"Tenant com slug '{TENANT_DATA['slug']}' ja existe.")
if Tenant.objects.filter(cnpj=TENANT_DATA['cnpj']).exists():
    erros.append(f"Tenant com CNPJ '{TENANT_DATA['cnpj']}' ja existe.")
if User.objects.filter(username=ADMIN_DATA['username']).exists():
    erros.append(f"Usuario '{ADMIN_DATA['username']}' ja existe.")

if erros:
    print("\nERROS DE PRE-VERIFICACAO:")
    for e in erros:
        print(f"  [ERRO] {e}")
    print("\nAbortando. Resolva os conflitos acima e tente novamente.")
    raise SystemExit(1)

print("[OK] Pre-checagens passaram.")


# ============================================================================
# CRIACAO (transacao atomica)
# ============================================================================

with transaction.atomic():
    # 1. Tenant
    tenant = Tenant.objects.create(**TENANT_DATA)
    print(f"[OK] Tenant criado: id={tenant.id}, slug='{tenant.slug}'")

    # 2. ConfiguracaoEmpresa
    config = ConfiguracaoEmpresa.objects.create(tenant=tenant, ativo=True, **EMPRESA_DATA)
    print(f"[OK] ConfiguracaoEmpresa criada: id={config.id}")

    # 3. User admin (Lucas)
    user = User.objects.create_user(
        username=ADMIN_DATA['username'],
        email=ADMIN_DATA['email'],
        password=SENHA_GERADA,
        first_name=ADMIN_DATA['first_name'],
        last_name=ADMIN_DATA['last_name'],
    )
    print(f"[OK] User criado: id={user.id}, username='{user.username}'")

    # 4. PerfilUsuario (vincula user -> tenant)
    perfil_user = PerfilUsuario.objects.create(user=user, tenant=tenant)
    print(f"[OK] PerfilUsuario criado: id={perfil_user.id}")

    # 5. Cria os 11 perfis de permissao padrao pra esse tenant
    #    Reusa a logica do seed_perfis_padrao
    from apps.sistema.management.commands.seed_perfis_padrao import PERFIS

    todas_funcs = {f.codigo: f for f in Funcionalidade.objects.all()}
    perfis_criados = []
    perfil_admin = None

    for nome_perfil, cfg in PERFIS.items():
        perfil, criado = PerfilPermissao.objects.get_or_create(
            tenant=tenant,
            nome=nome_perfil,
            defaults={'descricao': cfg['descricao']},
        )
        if criado:
            if cfg['funcionalidades'] == '__all__':
                perfil.funcionalidades.set(Funcionalidade.objects.all())
            else:
                funcs = [todas_funcs[c] for c in cfg['funcionalidades'] if c in todas_funcs]
                perfil.funcionalidades.set(funcs)
            perfis_criados.append(nome_perfil)
        if nome_perfil == 'Admin':
            perfil_admin = perfil

    print(f"[OK] PerfisPermissao criados: {len(perfis_criados)} ({', '.join(perfis_criados)})")

    # 6. Atribui perfil Admin ao user (acesso total)
    if not perfil_admin:
        raise RuntimeError("Perfil 'Admin' nao foi criado — checa seed_perfis_padrao.py")

    PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil_admin)
    print(f"[OK] PermissaoUsuario criada: {user.username} -> Admin")


# ============================================================================
# RESUMO FINAL
# ============================================================================

print()
print("=" * 70)
print("TENANT CRIADO COM SUCESSO")
print("=" * 70)
print(f"Tenant ID:     {tenant.id}")
print(f"Nome:          {tenant.nome}")
print(f"Slug:          {tenant.slug}")
print(f"CNPJ:          {tenant.cnpj}")
print(f"Modulos:       Comercial Starter")
print()
print("CREDENCIAIS DO ADMIN (anote agora — nao tem como recuperar a senha):")
print(f"  URL:         https://app.hubtrix.com.br/")
print(f"  Username:    {user.username}")
print(f"  Email:       {user.email}")
print(f"  Senha:       {SENHA_GERADA}")
print(f"  Perfil:      Admin (acesso total)")
print("=" * 70)
