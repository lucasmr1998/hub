"""Atualiza T6 com mudanca de mensagens (5 cliente + 3 atendente) + criterio de
validacao manual de amostra antes do --apply."""
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

T6_ID = 146

NOVOS_PASSOS = (
    '1. Pre-req: adicionar campo motivo_perda_origem (charfield: humano/llm_backfill/bot) '
    'em crm_oportunidades. Migration adjacente.\n'
    '2. Management command apps/comercial/crm/management/commands/backfill_motivos_perda.py.\n'
    '3. Flags obrigatorios: --tenant <slug> (sem isso recusa rodar), --dry-run (default True; '
    'precisa --apply explicito), --confidence-min 0.7 (default), '
    '--max-msgs-cliente 5 (default), --max-msgs-atendente 3 (default).\n'
    '4. Pra cada oportunidade sem motivo, busca mensagens da conversa associada. Filtra: '
    'pega as **ultimas 5 mensagens do CLIENTE** + **ultimas 3 mensagens do ATENDENTE/BOT**, '
    'ordenadas cronologicamente. Foco no sinal do cliente, reduz ruido do bot.\n'
    '5. Prompt LLM (gpt-4o-mini ou Claude Haiku) classifica entre os MotivoPerda do tenant '
    '+ retorna confidence score 0-1 + breve justificativa.\n'
    '6. Se confidence >= confidence_min: salva motivo_perda_ref_id + motivo_perda_categoria + '
    'motivo_perda_origem=llm_backfill + motivo_perda (texto curto com justificativa do LLM).\n'
    '7. Se confidence < confidence_min: salva motivo_perda_categoria="outro" + motivo_perda '
    '(texto livre com justificativa) + origem=llm_backfill.\n'
    '8. Log resumo no fim: distribuicao por motivo + total por confidence bucket.\n'
    '9. **GATE de qualidade**: apos --dry-run, gerar relatorio com 10 amostras random (oportunidade '
    '+ motivo classificado + justificativa) pra revisao humana. Sem aprovacao escrita, NAO rodar --apply.\n'
    '10. Antes de rodar com --apply em tenant cliente final, avisar usuarios via Slack/email.\n'
    '11. Ordem de execucao: aurora-hq -> demo -> (parar e avaliar amostra) -> tenants externos '
    'somente apos OK contratual + revisao da amostra.'
)

NOVOS_CRITERIOS = (
    '- Campo motivo_perda_origem existe e e populado em todas as escritas\n'
    '- --tenant <slug> obrigatorio (sem ele, comando recusa rodar)\n'
    '- --dry-run e o default; --apply precisa ser explicito\n'
    '- --max-msgs-cliente (default 5) e --max-msgs-atendente (default 3) configuraveis via flag\n'
    '- LLM le SOMENTE ultimas N msgs do cliente + N msgs do atendente, nao a conversa inteira\n'
    '- LLM retorna confidence + justificativa curta; texto livre motivo_perda fica com a justificativa\n'
    '- Confidence baixo (<0.7) vai pra motivo_perda_categoria=outro com texto livre da justificativa\n'
    '- motivo_perda_origem=llm_backfill em 100% das escritas do comando\n'
    '- Log final mostra: total processado, por motivo, por confidence bucket (>=0.7, <0.7)\n'
    '- Relatorio --dry-run inclui amostra random de 10 classificacoes (id, motivo, justificativa) pra revisao\n'
    '- Revisao escrita da amostra antes do --apply (logado no PR ou na propria tarefa Workspace)\n'
    '- Rodado primeiro em aurora-hq + demo, amostra revisada manualmente antes de outros\n'
    '- Tenants com cliente final (TR Carrion, FATEPI, Nuvyon) so apos OK contratual + aviso aos usuarios\n'
    '- Rollback funcional: UPDATE motivo_perda_ref_id=NULL WHERE motivo_perda_origem=llm_backfill reverte tudo'
)


def main():
    conn = psycopg2.connect(
        host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
        dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
        password=env['PROD_DB_PASSWORD'], connect_timeout=10,
    )
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SELECT id, titulo FROM workspace_tarefa WHERE id=%s;", (T6_ID,))
    r = cur.fetchone()
    if not r:
        print(f'[ERRO] T6 id={T6_ID} nao encontrada')
        return
    print(f'Atualizando: {r[1][:80]}')

    try:
        cur.execute("""UPDATE workspace_tarefa
            SET passos=%s, criterios_aceite=%s, atualizado_em=NOW()
            WHERE id=%s;""",
            (NOVOS_PASSOS, NOVOS_CRITERIOS, T6_ID))
        conn.commit()
        print('[OK] T6 atualizada: passos (5 cliente + 3 atendente) + gate de revisao manual antes do --apply.')
    except Exception as e:
        conn.rollback()
        print(f'[ERRO] {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
