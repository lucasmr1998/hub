"""
Conecta SSH em prod, identifica container Django e roda o script
_criar_tenant_tr_carrion.py via docker exec.
"""
import os
from pathlib import Path
import paramiko

BASE = Path(__file__).parent.parent

# Carrega .env.prod_readonly manualmente (sem dependencia extra)
env = {}
for line in (BASE / '.env.prod_readonly').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

host = env['PROD_SSH_HOST']
port = int(env.get('PROD_SSH_PORT', '22'))
user = env['PROD_SSH_USER']
password = env['PROD_SSH_PASSWORD']
container_filter = env['PROD_APP_CONTAINER_FILTER']

script_path = BASE / 'scripts' / '_criar_tenant_tr_carrion.py'
script_body = script_path.read_text(encoding='utf-8')

print(f"[1] Conectando em {user}@{host}:{port}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=user, password=password, timeout=20, look_for_keys=False, allow_agent=False)
print("[1] OK conectado.")

def run(cmd, stdin_data=None):
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=False)
    if stdin_data:
        stdin.write(stdin_data)
        stdin.channel.shutdown_write()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err

# Lista containers que batem com o filter
print(f"\n[2] Procurando containers que batem com filter '{container_filter}'...")
rc, out, err = run(f"docker ps --filter 'name={container_filter}' --format '{{{{.Names}}}}|{{{{.Image}}}}|{{{{.Status}}}}'")
print(out)
if err:
    print(f"STDERR: {err}")

# Pra escolher container do app Django (nao DB), pegamos o que NAO tem 'postgres' na imagem
linhas = [l for l in out.strip().splitlines() if l]
candidatos = [l for l in linhas if 'postgres' not in l.lower() and 'redis' not in l.lower() and 'nginx' not in l.lower()]
if not candidatos:
    print("ERRO: nenhum container app encontrado.")
    client.close()
    raise SystemExit(1)

if len(candidatos) > 1:
    print(f"\n[2] Multiplos candidatos. Listando pra voce escolher:")
    for i, c in enumerate(candidatos):
        print(f"  [{i}] {c}")
    print("\nABORTANDO — define o container manualmente.")
    client.close()
    raise SystemExit(1)

container = candidatos[0].split('|')[0]
print(f"\n[2] Container Django identificado: {container}")

# Roda o script via stdin pro python shell do Django
print(f"\n[3] Executando script no container '{container}'...")
print("-" * 70)
rc, out, err = run(
    f"docker exec -i {container} python manage.py shell",
    stdin_data=script_body,
)
print(out)
if err:
    print("STDERR:", err)
print("-" * 70)
print(f"\n[3] Exit code: {rc}")

client.close()
print("\nFINALIZADO.")
