"""Puxa logs detalhados do ultimo atendimento do fluxo 23."""
from pathlib import Path
import paramiko

env = {}
for line in Path('C:/Users/lucas/Desktop/hub/.env.prod_readonly').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

code = """
from apps.comercial.atendimento.models import (
    FluxoAtendimento, AtendimentoFluxo, LogFluxoAtendimento, NodoFluxoAtendimento
)
from apps.integracoes.models import IntegracaoAPI

# 1. Checa chave OpenAI
i = IntegracaoAPI.objects.get(id=13)
key_preview = (i.api_key[:8] + '...') if i.api_key else '(vazio)'
print(f'== Integracao OpenAI id=13 ==')
print(f'  api_key: {key_preview}')
print(f'  ativa: {i.ativa}')
print()

# 2. Ultimo atendimento do fluxo 23
fluxo = FluxoAtendimento.objects.get(id=23)
ats = AtendimentoFluxo.objects.filter(fluxo=fluxo).order_by('-id')[:3]
for at in ats:
    print(f'== Atendimento #{at.id} ==')
    print(f'  status: {at.status}')
    print(f'  inicio: {at.data_inicio}')
    print(f'  nodo_atual: {at.nodo_atual_id}')
    print(f'  variaveis: {at.variaveis_contexto if hasattr(at, \"variaveis_contexto\") else \"N/A\"}')
    logs = LogFluxoAtendimento.objects.filter(atendimento=at).order_by('id')[:50]
    print(f'  -- {logs.count()} logs --')
    for log in logs:
        nodo_info = ''
        if log.nodo_id:
            try:
                n = NodoFluxoAtendimento.objects.get(id=log.nodo_id)
                nodo_info = f'{n.tipo}/{n.subtipo} (id={n.id})'
            except Exception:
                nodo_info = f'nodo_id={log.nodo_id}'
        print(f'    [{log.criado_em.strftime(\"%H:%M:%S\")}] {nodo_info} acao={log.acao}')
        if log.dados:
            print(f'       dados: {str(log.dados)[:300]}')
    print()
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(env['PROD_SSH_HOST'], port=int(env.get('PROD_SSH_PORT','22')), username=env['PROD_SSH_USER'], password=env['PROD_SSH_PASSWORD'], timeout=20, look_for_keys=False, allow_agent=False)
stdin, stdout, stderr = c.exec_command('docker exec -i projetos_hub.1.fkvaakc3lztoi6fwsd8aq53is python manage.py shell')
stdin.write(code); stdin.channel.shutdown_write()
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err: print('STDERR:', err)
c.close()
