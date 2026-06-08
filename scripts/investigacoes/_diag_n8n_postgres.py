"""
Diagnostico de conectividade do container N8N pro banco_n8n.
Testa varios hostnames + descobre o IP atual do banco_n8n no overlay easypanel.
"""
import os
import paramiko
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(
    hostname=env['PROD_SSH_HOST'],
    port=int(env['PROD_SSH_PORT']),
    username=env['PROD_SSH_USER'],
    password=env['PROD_SSH_PASSWORD'],
    timeout=15,
)

def run(cmd, label=None):
    print(f'\n=== {label or cmd} ===')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out: print(out.rstrip())
    if err: print('STDERR:', err.rstrip())

# 1. Achar containers
run("docker ps --format '{{.Names}}\t{{.Image}}' | grep -iE 'n8n|banco_n8n'", "Containers n8n e banco_n8n")

# 2. Descobrir nome do servico/IP do banco_n8n
run("docker service ls | grep -iE 'banco_n8n|n8n'", "Services swarm")

# 3. Inspecionar redes do container n8n e banco_n8n
run("""docker ps --format '{{.Names}}' | grep -i 'n8n' | head -5 | while read c; do
  echo "--- $c ---"
  docker inspect "$c" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}'
done""", "IPs e redes dos containers n8n")

# 4. Inspecionar banco_n8n
run("""docker ps --format '{{.Names}}' | grep -i 'banco_n8n' | head -5 | while read c; do
  echo "--- $c ---"
  docker inspect "$c" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}'
done""", "IPs e redes dos containers banco_n8n")

# 5. Achar container do n8n e testar resolucao DNS
run("""N8N=$(docker ps --format '{{.Names}}' | grep -i 'automation_n8n' | head -1)
echo "N8N container: $N8N"
echo ""
echo "--- getent hosts banco_n8n ---"
docker exec "$N8N" getent hosts banco_n8n 2>&1 || echo "getent nao disponivel"
echo ""
echo "--- getent hosts projetos_banco_n8n ---"
docker exec "$N8N" getent hosts projetos_banco_n8n 2>&1
echo ""
echo "--- nslookup banco_n8n (se tiver) ---"
docker exec "$N8N" nslookup banco_n8n 2>&1 | head -10 || echo "nslookup ausente"
echo ""
echo "--- nslookup projetos_banco_n8n ---"
docker exec "$N8N" nslookup projetos_banco_n8n 2>&1 | head -10
""", "Resolucao DNS de dentro do N8N")

# 6. Testar conectividade com node (n8n roda em node, garantido)
run("""N8N=$(docker ps --format '{{.Names}}' | grep -i 'automation_n8n' | head -1)
for HOST in banco_n8n projetos_banco_n8n 10.11.0.42; do
  echo "--- TCP test to $HOST:5432 ---"
  docker exec "$N8N" node -e "
    const net = require('net');
    const sock = net.connect({host: '$HOST', port: 5432, timeout: 5000});
    sock.on('connect', () => { console.log('OK connected to $HOST:5432'); process.exit(0); });
    sock.on('error', e => { console.log('FAIL', e.code, e.message); process.exit(1); });
    sock.on('timeout', () => { console.log('TIMEOUT'); process.exit(1); });
  " 2>&1
done
""", "Teste TCP 5432 do N8N pra cada candidato")

# 7. IP do banco_n8n em todas as redes
run("""B=$(docker ps --format '{{.Names}}' | grep -i 'banco_n8n' | head -1)
echo "banco_n8n container: $B"
docker inspect "$B" --format '{{json .NetworkSettings.Networks}}' | python3 -m json.tool 2>&1 || echo "sem python3"
""", "Detalhe completo da rede do banco_n8n")

ssh.close()
