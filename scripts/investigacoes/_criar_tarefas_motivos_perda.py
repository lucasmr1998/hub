"""Cria 9 tarefas no Workspace pro projeto 'Hubtrix Desenvolvimento' (Aurora HQ)
referentes a feature 'Motivos de Perda CRM'. Idempotente: nao recria se ja
existem tarefas com mesmo titulo.
"""
import sys
import psycopg2
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO = Path(__file__).resolve().parent.parent
env = {}
for line in (REPO / '.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

PROJETO_ID = 4
RESPONSAVEL_ID = 5
TENANT_ID = 3
ORDEM_INICIAL = 28
PREFIX = '[Motivos de Perda CRM]'

TAREFAS = [
    {
        'codigo': 'T0',
        'titulo': f'{PREFIX} T0 - Migration: flags motivo_perda_obrigatorio + motivo_perda_pede_concorrente em ConfiguracaoCRM',
        'prioridade': 'alta',
        'objetivo': 'Adicionar 2 BooleanFields em ConfiguracaoCRM pra controlar comportamento de Motivo de Perda por tenant.',
        'contexto': 'A operacao de marcar oportunidade como Perdida hoje nao categoriza nenhum motivo (156 oportunidades em prod, 0 com motivo). Antes de impor obrigatoriedade na UX, precisamos de um interruptor por tenant. Pre-requisito de T1, T2, T3, T8.',
        'passos': '1. Adicionar motivo_perda_obrigatorio: BooleanField(default=False) em ConfiguracaoCRM.\n2. Adicionar motivo_perda_pede_concorrente: BooleanField(default=True).\n3. Gerar migration (makemigrations crm).\n4. Aplicar local + validar manage.py check.\n5. Push pra prod.',
        'entregavel': 'Migration em apps/comercial/crm/migrations/, 2 colunas novas em crm_configuracao com defaults seguros (False e True).',
        'criterios_aceite': '- ConfiguracaoCRM.motivo_perda_obrigatorio existe e default=False\n- ConfiguracaoCRM.motivo_perda_pede_concorrente existe e default=True\n- manage.py check sem erros\n- Migration roda idempotente em prod',
    },
    {
        'codigo': 'T8',
        'titulo': f'{PREFIX} T8 - UI toggle das 2 flags no painel /crm/configuracoes/',
        'prioridade': 'alta',
        'objetivo': 'Dar ao admin do tenant o controle das 2 flags introduzidas em T0 via interface, sem precisar tocar DB.',
        'contexto': 'Cliente pode querer ativar/desativar a obrigatoriedade dependendo do momento operacional. UI fica em /crm/configuracoes/ junto com as outras flags ja existentes. Depende de T0.',
        'passos': '1. Adicionar 2 toggles em configuracoes_crm.html.\n2. Handler em views.configuracoes_crm pra persistir.\n3. Feedback no save.',
        'entregavel': 'Secao Motivos de Perda no painel com 2 toggles funcionais.',
        'criterios_aceite': '- Toggles aparecem no painel\n- Mudar toggle salva no DB\n- Feedback visual no save',
    },
    {
        'codigo': 'T2',
        'titulo': f'{PREFIX} T2 - Backend: validacao que rejeita mudanca pra Perdida sem motivo (quando flag=True)',
        'prioridade': 'alta',
        'objetivo': 'API rejeita mudanca de estagio pra Perdida sem motivo quando ConfiguracaoCRM.motivo_perda_obrigatorio=True.',
        'contexto': 'Mesmo com modal frontend (T1/T3), API direta poderia bypassar. Backend e a unica barreira real. Depende de T0.',
        'passos': '1. Localizar handler de mudanca de estagio (views.editar_campo_oportunidade, drag and drop API).\n2. Carregar ConfiguracaoCRM do tenant.\n3. Se estagio destino e Perdida + flag=True + nem motivo_perda nem motivo_perda_ref_id preenchidos -> return 400.\n4. Test unit cobrindo cenario.',
        'entregavel': 'Validacao backend bloqueando salvar oportunidade em Perdida sem motivo. Erro 400 com mensagem util.',
        'criterios_aceite': '- POST /crm/oportunidade/<id>/editar/ com estagio=perdida sem motivo -> 400\n- Com motivo preenchido -> 200\n- Quando flag=False, aceita sem motivo\n- Mensagem de erro orienta a preencher motivo',
    },
    {
        'codigo': 'T1',
        'titulo': f'{PREFIX} T1 - Modal de motivo ao mover card pra Perdida no Kanban',
        'prioridade': 'alta',
        'objetivo': 'Quando vendedor arrasta card pra Perdida no pipeline.html, abrir modal pedindo motivo (catalogado) + concorrente (se aplicavel).',
        'contexto': 'Vendedor arrasta sem feedback, motivo nunca e categorizado. Modal aparece SEMPRE, mas botao Pular so habilitado se motivo_perda_obrigatorio=False. Depende de T0 + T2.',
        'passos': '1. JS no pipeline.html: detecta drag pra Perdida.\n2. Modal: dropdown motivos + texto livre + campo concorrente condicional.\n3. Confirmar so envia API se motivo selecionado.\n4. Botao Pular so aparece se flag=False.\n5. Cancelar reverte o drag.',
        'entregavel': 'Modal funcional no Kanban com dropdown + texto + concorrente + 2 botoes.',
        'criterios_aceite': '- Drag pra Perdida sempre abre modal\n- Confirmar com motivo salva e fecha\n- Pular so visivel se flag=False\n- Cancelar reverte o card\n- Concorrente: campo qual? obrigatorio',
    },
    {
        'codigo': 'T3',
        'titulo': f'{PREFIX} T3 - Modal de motivo em oportunidade_detalhe.html',
        'prioridade': 'media',
        'objetivo': 'Mesma logica do T1 mas na tela de detalhe (mudanca de estagio via select).',
        'contexto': 'Vendedor pode mudar estagio direto na pagina de detalhe. Sem o modal aqui, T1 vira contornavel. Reusa componente.',
        'passos': '1. Listener no select de estagio em oportunidade_detalhe.html.\n2. Se valor e Perdida sem motivo, abrir mesmo modal de T1.\n3. Reverter select se cancelar.',
        'entregavel': 'Modal disparado pela mudanca de estagio no detalhe.',
        'criterios_aceite': '- Mudar select pra Perdida abre modal\n- Cancelar reverte\n- Confirmar salva motivo + estagio',
    },
    {
        'codigo': 'T7',
        'titulo': f'{PREFIX} T7 - Tela dedicada /crm/motivos-perda/ (extrair de configuracoes_crm)',
        'prioridade': 'media',
        'objetivo': 'Tirar o CRUD de Motivos de Perda da tela /crm/configuracoes/ (que tambem tem pipelines, estagios, equipes, metas) e criar tela propria com estatistica de uso.',
        'contexto': 'UI atual reportada como horrivel. Tela dedicada melhora UX, libera espaco, e permite mostrar contador X oportunidades neste motivo (12m).',
        'passos': '1. View motivos_perda em apps/comercial/crm/views.py (CRUD + reordenar).\n2. URLs /crm/motivos-perda/.\n3. Template motivos_perda.html (padrao visual de /suporte/conhecimento/perguntas/).\n4. Annotate Count de uso por motivo.\n5. Confirmacao especial pra excluir motivo em uso.\n6. Link no subnav Comercial.\n7. Remover secao antiga de configuracoes_crm.html.',
        'entregavel': 'Tela /crm/motivos-perda/ com CRUD limpo + contagem + link sidebar + remocao da secao antiga.',
        'criterios_aceite': '- Acessivel via subnav Comercial > Motivos de Perda\n- CRUD funcional\n- Contador de uso visivel\n- Excluir motivo em uso pede confirmacao\n- Bloco antigo removido',
    },
    {
        'codigo': 'T4',
        'titulo': f'{PREFIX} T4 - Link Relatorio Win/Loss no subnav Comercial',
        'prioridade': 'baixa',
        'objetivo': 'Expor o relatorio_win_loss.html que ja existe mas esta escondido (zero usuarios sabem que existe).',
        'contexto': 'Relatorio /crm/relatorios/win-loss/ ja implementado mas sem link na navegacao. Mesmo problema da /suporte/conhecimento/perguntas/ que resolvemos.',
        'passos': '1. Adicionar item no partials/sidebar_subnav.html dentro de Comercial > Relatorios.\n2. Icon bi-bar-chart-line ou bi-trophy.',
        'entregavel': 'Link na sidebar/subnav apontando pro relatorio.',
        'criterios_aceite': '- Link aparece em subnav Comercial > Relatorios\n- Click leva pra /crm/relatorios/win-loss/\n- is-active funciona',
    },
    {
        'codigo': 'T6',
        'titulo': f'{PREFIX} T6 - Backfill historico via LLM dos 156 oportunidades sem motivo',
        'prioridade': 'media',
        'objetivo': 'Analisar via LLM as ultimas mensagens das 156 oportunidades existentes e inferir motivo_perda automaticamente.',
        'contexto': 'TR Carrion (80), FATEPI (53), Demo (13), Nuvyon (10) - todas zeradas. LLM classifica pela conversa final. Custo ~$0.05. Reusa infra de RAG/OpenAI ja deployada. Depende de T2 estar deployada.',
        'passos': '1. Management command apps/comercial/crm/management/commands/backfill_motivos_perda.py.\n2. Pra cada oportunidade sem motivo: pega ultimas 10 msgs da conversa associada.\n3. Prompt LLM pra classificar entre os MotivoPerda do tenant.\n4. Salva motivo_perda_ref_id + motivo_perda_categoria.\n5. --dry-run e --tenant <slug>.\n6. Log resumo no fim.',
        'entregavel': 'Comando funcional. Apos rodar uma vez, oportunidades historicas categorizadas.',
        'criterios_aceite': '- --dry-run mostra sem persistir\n- Sem --dry-run popula motivo_perda_ref\n- Ambiguos vao pra Outro com observacao\n- Log mostra distribuicao no fim',
    },
    {
        'codigo': 'T5',
        'titulo': f'{PREFIX} T5 - Captura automatica de motivo via bot (Vero/Matrix)',
        'prioridade': 'media',
        'objetivo': 'Quando o bot detecta padrao de motivo no ultimo turno do cliente, associa motivo automaticamente ao encerrar oportunidade.',
        'contexto': 'Flow N8N do TR Carrion e Nuvyon ja fecha conversas. Da pra evoluir: ao encerrar, chamar LLM pra inferir motivo. Junto com T6 e T2. Depende de T1+T2 estaveis.',
        'passos': '1. Endpoint publico POST /api/public/n8n/crm/oportunidade/<id>/encerrar-com-motivo/.\n2. Recebe ultima mensagem + tenant via Bearer.\n3. LLM classifica.\n4. Persiste motivo + muda estagio pra Perdida.\n5. Atualizar flows piloto.\n6. Doc no 03-APIS_N8N.md.',
        'entregavel': 'Endpoint funcional + flow piloto integrado.',
        'criterios_aceite': '- Endpoint responde 200 e move estagio\n- Motivo bate com catalogados\n- Baixa confianca vai pra Outro + texto livre\n- 1 flow piloto integrado',
    },
]


def main():
    conn = psycopg2.connect(
        host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
        dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
        password=env['PROD_DB_PASSWORD'], connect_timeout=10,
    )
    conn.autocommit = False
    cur = conn.cursor()

    print(f'Total tarefas: {len(TAREFAS)}  projeto={PROJETO_ID}  responsavel={RESPONSAVEL_ID}  tenant={TENANT_ID}')

    # Idempotente: pula se titulo ja existe no projeto
    cur.execute(
        "SELECT titulo FROM workspace_tarefa WHERE projeto_id=%s AND titulo LIKE %s;",
        (PROJETO_ID, f'{PREFIX}%'),
    )
    ja_existem = {r[0] for r in cur.fetchall()}
    if ja_existem:
        print(f'\nJa existem {len(ja_existem)} tarefas com prefix {PREFIX}, pulando essas.')

    ids = []
    try:
        for i, t in enumerate(TAREFAS):
            if t['titulo'] in ja_existem:
                print(f'  [SKIP-ja-existe] {t["codigo"]}')
                continue
            cur.execute("""INSERT INTO workspace_tarefa
            (titulo, descricao, status, prioridade, data_limite, data_conclusao, ordem,
             objetivo, contexto, passos, entregavel, criterios_aceite, log_execucao,
             nivel_delegacao, criado_em, atualizado_em, projeto_id, responsavel_id, tenant_id)
            VALUES (%s, %s, 'pendente', %s, NULL, NULL, %s,
                    %s, %s, %s, %s, %s, '',
                    0, NOW(), NOW(), %s, %s, %s)
            RETURNING id;""",
                (t['titulo'], t['objetivo'][:300], t['prioridade'], ORDEM_INICIAL + i,
                 t['objetivo'], t['contexto'], t['passos'], t['entregavel'], t['criterios_aceite'],
                 PROJETO_ID, RESPONSAVEL_ID, TENANT_ID))
            novo = cur.fetchone()[0]
            ids.append(novo)
            print(f'  [OK] {t["codigo"]}: id={novo}')
        conn.commit()
        print(f'\nCommit OK. {len(ids)} tarefas inseridas. IDs: {ids}')
    except Exception as e:
        conn.rollback()
        print(f'\n[ERRO] {e}')
        print('ROLLBACK feito.')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
