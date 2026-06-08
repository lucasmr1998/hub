"""Inventaria o que ja existe DENTRO do tenant=9 (Gigamax) em prod."""
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


print('=== Tenant Gigamax em prod (detalhe) ===')
print(query("SELECT id, nome, slug, criado_em, ativo FROM sistema_tenant WHERE id = 9;"))

# Tabelas tenant-aware com count por tenant=9
tabelas = [
    'sistema_perfil_usuario',
    'sistema_perfil_permissao',
    'sistema_permissao_usuario',
    'configuracao_sistema',
    'vendas_web_configuracaoempresa',
    'integracoes_api',
    'crm_configuracaocrm',
    'crm_pipelineestagio',
    'crm_produtoservico',
    'crm_opcaovencimentocrm',
    'tipos_notificacao',
    'canais_notificacao',
    'inbox_canal',
    'inbox_equipe',
    'inbox_configuracao',
    'logs_sistema',
    'leads_prospecto',
]

print('\n=== Conteudo do tenant=9 em prod ===')
for tabela in tabelas:
    out = query(f"SELECT '{tabela}' AS tabela, COUNT(*) AS qtd FROM {tabela} WHERE tenant_id = 9;")
    # Pega so a linha de dados
    lines = [l for l in out.split('\n') if l.strip() and '|' in l and '---' not in l and 'tabela' not in l]
    for l in lines:
        parts = [p.strip() for p in l.split('|')]
        if len(parts) >= 2 and parts[1].isdigit() and int(parts[1]) > 0:
            print(f'  {parts[0]:40s} {parts[1]:>5}')

client.close()
