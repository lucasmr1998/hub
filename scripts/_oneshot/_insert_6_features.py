"""Script efêmero pra inserir 6 features novas no Workspace. Usa SSH + docker exec psql."""
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
client.connect(creds['PROD_SSH_HOST'], port=int(creds['PROD_SSH_PORT']),
               username=creds['PROD_SSH_USER'], password=creds['PROD_SSH_PASSWORD'], timeout=30)

stdin, stdout, _ = client.exec_command("docker ps --filter name=projetos_hubbanco --format '{{.Names}}' | head -1")
db = stdout.read().decode().strip()

tarefas = [
    {
        'titulo': 'Win/Loss analysis — motivos categorizados de oportunidades',
        'descricao': 'Hoje Oportunidade tem status ganha/perdida mas sem motivo categorizado. Sem isso, decisao de pricing e abordagem de vendas vira palpite, nao dado.',
        'prioridade': 'media',
        'objetivo': 'Transformar perda e ganho de oportunidades em dado acionavel pra time de vendas e pricing.',
        'passos': '1. Adicionar motivo_perda + motivo_ganho em Oportunidade. Migration. 2. Choices: preco, concorrente, timing, sem_orcamento, viabilidade_tecnica, sem_resposta, outro. 3. Modal pede motivo ao mudar status. 4. Dashboard /crm/relatorios/win-loss/ com pizza + tabela.',
        'criterios': 'Migration aplicada. Modal funciona. Dashboard renderiza com pizza + filtro periodo.',
    },
    {
        'titulo': 'CSAT pos-atendimento via IA',
        'descricao': 'Hoje nao ha como medir satisfacao em atendimentos resolvidos. Detectar detratores automaticamente.',
        'prioridade': 'media',
        'objetivo': 'Medir satisfacao por atendimento e detectar detratores via IA.',
        'passos': '1. Model AvaliacaoAtendimento (conversa OneToOne, nota 1-5, comentario, sentimento). 2. Signal: status=resolvida agenda envio em 30min. 3. Bot envia 1-5 estrelas via WhatsApp. 4. IA classifica sentimento de comentario aberto. 5. Dashboard /inbox/csat/ com CSAT medio + lista detratores. 6. Notificacao pro gerente em detrator.',
        'criterios': 'Migration aplicada. Avaliacao envia automaticamente. Dashboard mostra historico.',
    },
    {
        'titulo': 'Resumo automatico de conversa via IA',
        'descricao': 'Conversas longas dificultam transferencia. Botao Resumir gera 3-5 bullets via LLM.',
        'prioridade': 'media',
        'objetivo': 'Reduzir tempo de onboarding em conversas transferidas. Materializar copiloto de IA.',
        'passos': '1. View api_resumir_conversa pega ultimas 50 mensagens, monta prompt. 2. Chama LLM via mesmo provider do assistente. 3. Botao Resumir no header do Inbox. 4. Modal mostra bullets. 5. Cache 1h por conversa.',
        'criterios': 'Botao funciona, resumo aparece em < 5s, conteudo coerente.',
    },
    {
        'titulo': 'AI-suggested next action por lead/oportunidade',
        'descricao': 'Vendedor olha pipeline e nao sabe priorizar. Sugestao IA contextual com botao Aplicar.',
        'prioridade': 'media',
        'objetivo': 'Materializar copiloto de IA no momento de decidir o que fazer.',
        'passos': '1. Campo proxima_acao_sugerida JSONField em Oportunidade e LeadProspecto. 2. Cron sugerir_proxima_acao.py: leads sem atividade 24h chamam LLM. 3. UI: card de sugestao no detalhe com botoes Aplicar e Ignorar. 4. Aplicar gera TarefaCRM. Ignorar regenera em 3 dias.',
        'criterios': 'Crontab gera sugestoes. UI exibe. Aplicar cria TarefaCRM.',
    },
    {
        'titulo': 'Detector de churn preditivo (rule-based)',
        'descricao': 'ISP perde 3-5% clientes/mes. Antecipar via score 0-100 baseado em sinais ja coletados.',
        'prioridade': 'alta',
        'objetivo': 'Reduzir churn por antecipacao. Direcionar acao preventiva antes do cancelamento.',
        'passos': '1. Service churn_score.py com calcular_score. Sinais: sem atividade 30d (+20), 2+ tickets nao resolvidos (+30), inadimplente (+25), NPS detrator (+25), idade cliente. 2. Threshold 60 = alto risco. 3. Cron atualizar_churn_score.py diario. 4. Alerta pro gerente CS. 5. Dashboard /cs/retencao/churn/ com lista priorizada. 6. Badge no detalhe.',
        'criterios': 'Crontab roda diario. Dashboard funciona. Alertas acionam.',
    },
    {
        'titulo': 'Score de risco para inadimplencia',
        'descricao': 'Antes de aprovar venda, sem triagem de risco. Score interno (sem Serasa).',
        'prioridade': 'media',
        'objetivo': 'Reduzir inadimplencia detectando perfis de risco antes da venda.',
        'passos': '1. Service risco_inadimplencia.py. Sinais: cliente novo (+15), plano valor > 200 (+10), boleto vs Pix (+10), historico atrasos (+30), cancelado e voltou (+20). 2. Score 0-100. 3. Modal de aprovacao mostra score visualmente. 4. Risco > 70 bloqueia aprovacao por vendedor (so gerente). 5. Logar aprovacoes em LogSistema.',
        'criterios': 'Modal mostra score. Aprovacao com risco > 70 bloqueada.',
    },
]


def insert_tarefa(t):
    sql = f"""INSERT INTO workspace_tarefa (
        tenant_id, projeto_id, titulo, descricao, status, prioridade,
        ordem, objetivo, contexto, passos, entregavel, criterios_aceite, log_execucao,
        nivel_delegacao, criado_em, atualizado_em
    ) VALUES (
        3, 4, $$ {t['titulo']} $$, $$ {t['descricao']} $$, 'pendente', '{t['prioridade']}',
        0, $$ {t['objetivo']} $$, '', $$ {t['passos']} $$, '', $$ {t['criterios']} $$, '',
        0, NOW(), NOW()
    ) RETURNING id;"""
    sftp = client.open_sftp()
    with sftp.open('/tmp/insert_one.sql', 'w') as f:
        f.write(sql)
    sftp.close()
    stdin, stdout, stderr = client.exec_command(
        f"docker cp /tmp/insert_one.sql {db}:/tmp/insert.sql && docker exec {db} psql -U admin_hub -d hub -f /tmp/insert.sql"
    )
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err


for t in tarefas:
    out, err = insert_tarefa(t)
    print(f"=== {t['titulo'][:50]} ===")
    print(out.strip())
    if err:
        print("ERR:", err[:300])
    print()

# Confirmação final
stdin, stdout, _ = client.exec_command(
    f"docker exec {db} psql -U admin_hub -d hub -c \"SELECT id, titulo, status, prioridade FROM workspace_tarefa WHERE tenant_id = 3 ORDER BY id DESC LIMIT 8;\""
)
print("=== Estado final ===")
print(stdout.read().decode('utf-8', errors='replace'))

client.close()
