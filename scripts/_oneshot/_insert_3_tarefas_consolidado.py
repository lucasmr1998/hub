"""
Insere 3 tarefas relacionadas ao ClienteConsolidado + config churn.
"""
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


def insert_tarefa(titulo, descricao, prioridade, objetivo, contexto, passos, criterios):
    sql = f"""INSERT INTO workspace_tarefa (
  tenant_id, projeto_id, titulo, descricao, status, prioridade,
  ordem, objetivo, contexto, passos, entregavel, criterios_aceite, log_execucao,
  nivel_delegacao, criado_em, atualizado_em
) VALUES (
  3, 4,
  $${titulo}$$, $${descricao}$$, 'pendente', '{prioridade}',
  0,
  $${objetivo}$$, $${contexto}$$, $${passos}$$,
  $${criterios}$$,
  $${criterios}$$,
  '',
  0, NOW(), NOW()
) RETURNING id;"""

    sftp = client.open_sftp()
    with sftp.open('/tmp/insert_t.sql', 'w') as f:
        f.write(sql)
    sftp.close()

    cmd = f"docker cp /tmp/insert_t.sql {db}:/tmp/i.sql && docker exec {db} psql -U admin_hub -d hub -f /tmp/i.sql"
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f"=== {titulo[:60]} ===")
    print(out)
    if err:
        print("ERR:", err[:300])


# Tarefa A — fundação
insert_tarefa(
    titulo='ClienteConsolidado — modelo central + adapter HubSoft',
    descricao='Cria modelo central ClienteConsolidado que normaliza dados de qualquer ERP num schema unico. Adapter HubSoft popula automaticamente a partir do ClienteHubsoft existente. Fundacao pra multi-ERP funcionar em todos scanners (churn, inadimplencia, futuros).',
    prioridade='alta',
    objetivo='Desacoplar scanners (churn, inadimplencia, dashboards) dos modelos nativos por ERP. Permitir que adicionar novo ERP no futuro seja so escrever 1 adapter.',
    contexto='Hoje churn_score e risco_inadimplencia leem direto de ClienteHubsoft. Quando SGP/Voalle/IXC entrarem, escala mal. Solucao: cache normalizado em ClienteConsolidado, adapters por ERP populando.',
    passos='1. Criar model ClienteConsolidado com 8 dimensoes: identidade, pessoa, vinculo Hubtrix, cliente, contratos, financeiro, suporte, tecnologia. unique_together (origem, id_origem). 2. Migration. 3. Service apps/integracoes/services/adapters/hubsoft.py com sync_cliente(c) -> ClienteConsolidado e sync_todos(tenant). 4. Management command consolidar_clientes que itera HubSoft. 5. Crontab 4x/dia. 6. Doc em docs/PRODUTO/integracoes/.',
    criterios='Migration aplicada. Cron roda sem erro. ClienteConsolidado populado pra todos ClienteHubsoft existentes. Schema documentado.',
)

# Tarefa B — refactor scanners
insert_tarefa(
    titulo='Refactor scanners (churn + inadimplencia) pra ler ClienteConsolidado',
    descricao='Depois que ClienteConsolidado existir, refactorar churn_score.py e risco_inadimplencia.py pra trabalhar com a estrutura normalizada em vez de modelos nativos por ERP.',
    prioridade='media',
    objetivo='Scanners ficam ERP-agnosticos. Dashboard de churn agrega clientes de qualquer ERP no mesmo lugar.',
    contexto='Depende da tarefa A estar em producao. Modelo ClienteConsolidado precisa ja estar populado.',
    passos='1. Refactor apps/integracoes/services/churn_score.py: input vira ClienteConsolidado em vez de ClienteHubsoft. 2. Refactor apps/comercial/cadastro/services/risco_inadimplencia.py: usa CPF/CNPJ pra buscar TODOS ClienteConsolidado historicos (cross-ERP). 3. Atualizar management command atualizar_churn_score pra iterar ClienteConsolidado. 4. Mover campos churn_score do ClienteHubsoft pra ClienteConsolidado. 5. Migration de dados: copiar scores existentes. 6. Atualizar dashboards.',
    criterios='Scanners rodam sem mais referenciar ClienteHubsoft diretamente. Dashboard mostra clientes de qualquer origem. Backward compat OK durante transicao.',
)

# Tarefa C — config por tenant
insert_tarefa(
    titulo='Configuracao por tenant dos pesos do scanner de churn',
    descricao='Cada provedor pode ligar/desligar sinais e ajustar pesos do scanner de churn na UI de configuracoes. Defaults sensatos pra novos tenants.',
    prioridade='media',
    objetivo='Scanner deixa de ser heuristica fixa do Hubtrix e vira configuravel por tenant. Cada provedor adapta para sua realidade (ex: tenant sem modulo de NPS desliga sinal NPS).',
    contexto='Independente da tarefa A. Pode rodar em paralelo. Feedback do usuario: cada provedor tem realidade diferente, peso fixo serve mal pra todos.',
    passos='1. Model ConfiguracaoChurnScore (singleton por tenant) com 7+ sinais: cada um com ativo (bool), peso (int), e parametros especificos (ex: dias, qtd minima, % queda). 2. Migration + seed defaults. 3. Tela /configuracoes/churn-score/ com form Django: toggle por sinal + slider de peso + thresholds editaveis. 4. Refactor service churn_score.py pra ler config do tenant. 5. Botao restaurar padroes Hubtrix. 6. Preview interativo: cliente tipico com inadimplencia + 2 tickets daria score X. 7. Permissao apenas Admin/Gerente CS.',
    criterios='Form salva config no DB. Service usa pesos do tenant. Restaurar padroes funciona. Preview mostra score calculado em tempo real.',
)

client.close()
