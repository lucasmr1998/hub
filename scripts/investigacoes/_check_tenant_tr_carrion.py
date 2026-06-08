"""Checa via SSH read-only se tenant tr-carrion existe em prod (rollback OK?)."""
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

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(env['PROD_SSH_HOST'], port=int(env.get('PROD_SSH_PORT', '22')),
               username=env['PROD_SSH_USER'], password=env['PROD_SSH_PASSWORD'],
               timeout=20, look_for_keys=False, allow_agent=False)

stdin_data = """from apps.sistema.models import Tenant
from django.contrib.auth.models import User
t = Tenant.objects.filter(slug='tr-carrion').first()
print('Tenant tr-carrion:', t.id if t else 'NAO EXISTE (rollback OK)')
t2 = Tenant.objects.filter(cnpj='07.580.957/0001-01').first()
print('Tenant CNPJ:', t2.id if t2 else 'NAO EXISTE')
u = User.objects.filter(username='lucas.carrion').first()
print('User lucas.carrion:', u.id if u else 'NAO EXISTE')
print('Max tenant id:', Tenant.objects.all().order_by('-id').values_list('id', flat=True).first())
"""

stdin, stdout, stderr = client.exec_command(
    "docker exec -i projetos_hub.1.fkvaakc3lztoi6fwsd8aq53is python manage.py shell"
)
stdin.write(stdin_data)
stdin.channel.shutdown_write()
print("STDOUT:", stdout.read().decode('utf-8', errors='replace'))
err_data = stderr.read().decode('utf-8', errors='replace')
if err_data:
    print("STDERR:", err_data)
client.close()
