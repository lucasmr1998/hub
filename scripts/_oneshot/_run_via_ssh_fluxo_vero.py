"""Roda _criar_fluxo_vero_tr_carrion.py em prod via SSH+docker exec."""
from pathlib import Path
import paramiko

BASE = Path(__file__).parent.parent
env = {}
for line in (BASE / '.env.prod_readonly').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

script_body = (BASE / 'scripts' / '_criar_fluxo_vero_tr_carrion.py').read_text(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(env['PROD_SSH_HOST'], port=int(env.get('PROD_SSH_PORT', '22')),
               username=env['PROD_SSH_USER'], password=env['PROD_SSH_PASSWORD'],
               timeout=20, look_for_keys=False, allow_agent=False)

container = 'projetos_hub.1.fkvaakc3lztoi6fwsd8aq53is'
stdin, stdout, stderr = client.exec_command(
    f"docker exec -i {container} python manage.py shell"
)
stdin.write(script_body)
stdin.channel.shutdown_write()
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
rc = stdout.channel.recv_exit_status()
print(out)
if err:
    print("STDERR:", err)
print(f"\nExit code: {rc}")
client.close()
