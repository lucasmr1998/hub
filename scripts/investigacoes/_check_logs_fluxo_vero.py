"""Puxa logs recentes do fluxo Vero V1 (id=23) em prod."""
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

shell_code = """
from apps.comercial.atendimento.models import (
    FluxoAtendimento, LogFluxoAtendimento, NodoFluxoAtendimento, AtendimentoFluxo
)
fluxo = FluxoAtendimento.objects.get(id=23)
print(f'Fluxo: {fluxo.nome} (status={fluxo.status})')
print()

# Atendimentos (sessoes) recentes
atendimentos = AtendimentoFluxo.objects.filter(fluxo=fluxo).order_by('-id')[:5]
print(f'== Atendimentos recentes ({atendimentos.count()}) ==')
for at in atendimentos:
    print(f'  Atend #{at.id} status={at.status} criado={at.criado_em} lead={getattr(at, \"lead_id\", None)} oport={getattr(at, \"oportunidade_id\", None)}')
print()

# Logs recentes
logs = LogFluxoAtendimento.objects.filter(fluxo=fluxo).order_by('-id')[:40]
print(f'== Ultimos {logs.count()} logs ==')
for log in reversed(list(logs)):
    nodo_info = ''
    if log.nodo_id:
        try:
            n = NodoFluxoAtendimento.objects.get(id=log.nodo_id)
            nodo_info = f'{n.tipo}/{n.subtipo}'
        except Exception:
            nodo_info = f'id={log.nodo_id}'
    print(f'  [{log.criado_em.strftime(\"%H:%M:%S\")}] atend={log.atendimento_id} nodo={nodo_info} acao={log.acao} dados={str(log.dados)[:200]}')
"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(env['PROD_SSH_HOST'], port=int(env.get('PROD_SSH_PORT', '22')),
               username=env['PROD_SSH_USER'], password=env['PROD_SSH_PASSWORD'],
               timeout=20, look_for_keys=False, allow_agent=False)
stdin, stdout, stderr = client.exec_command(
    "docker exec -i projetos_hub.1.fkvaakc3lztoi6fwsd8aq53is python manage.py shell"
)
stdin.write(shell_code)
stdin.channel.shutdown_write()
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)
client.close()
