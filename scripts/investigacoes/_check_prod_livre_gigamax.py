"""Verifica em prod se os IDs que vamos importar (tenant=9, user=18, perfil=57) estão livres."""
import paramiko
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

creds = {}
with open('.env.prod_readonly', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        creds[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    creds['PROD_SSH_HOST'], port=int(creds['PROD_SSH_PORT']),
    username=creds['PROD_SSH_USER'], password=creds['PROD_SSH_PASSWORD'],
    timeout=30,
)

stdin, stdout, _ = client.exec_command(
    "docker ps --filter name=projetos_hubbanco --format '{{.Names}}' | head -1"
)
db = stdout.read().decode().strip()


def query(sql):
    safe = sql.replace('"', '\\"')
    cmd = f'docker exec {db} psql -U admin_hub -d hub -c "{safe}"'
    stdin, stdout, _ = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace')


# Tenant id=9 livre?
print('=== sistema_tenant onde id=9 ou slug=gigamax ===')
print(query("SELECT id, nome, slug FROM sistema_tenant WHERE id = 9 OR slug = 'gigamax';"))

# User id=18 livre?
print('=== auth_user onde id=18 ou username=admin_gigamax ===')
print(query("SELECT id, username, email FROM auth_user WHERE id = 18 OR username = 'admin_gigamax';"))

# PerfilPermissao id=57 livre?
print('=== sistema_perfil_permissao onde id=57 ===')
print(query("SELECT id, nome, tenant_id FROM sistema_perfil_permissao WHERE id = 57;"))

# IntegracaoAPI ids 11 e 12 livres?
print('=== integracoes_api onde id IN (11, 12) ===')
print(query("SELECT id, nome, tipo, tenant_id FROM integracoes_api WHERE id IN (11, 12);"))

# Próximo user id disponivel
print('=== Maior id em auth_user (próximo livre = +1) ===')
print(query("SELECT MAX(id) AS maior_user_id FROM auth_user;"))

# Próximo perfil id
print('=== Maior id em sistema_perfil_permissao ===')
print(query("SELECT MAX(id) AS maior_perfil_id FROM sistema_perfil_permissao;"))

# Próximo integracao id
print('=== Maior id em integracoes_api ===')
print(query("SELECT MAX(id) AS maior_integ_id FROM integracoes_api;"))

client.close()
