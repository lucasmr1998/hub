"""Atualiza T6 (id=146) no Workspace com mitigacoes de seguranca/privacidade."""
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

NOVO_CONTEXTO = (
    'TR Carrion (80), FATEPI (53), Demo (13), Nuvyon (10) - todas zeradas. LLM classifica '
    'pela conversa final. Custo ~$0.05. Reusa infra de RAG/OpenAI ja deployada. Depende de '
    'T2 estar deployada.\n\n'
    'ATENCAO LGPD: o LLM precisa ler ultimas mensagens das conversas dos clientes. Conteudo '
    'sai pro provider externo (OpenAI/Anthropic). Antes de rodar em tenants com clientes '
    'finais (TR Carrion, FATEPI, Nuvyon), validar autorizacao contratual. Aurora HQ e Demo '
    'sao internos, sem bloqueio.\n\n'
    'Risco operacional: oportunidades antigas vao aparecer classificadas do nada pros '
    'vendedores. Avisar antes de rodar em tenant com operacao ativa.'
)

NOVOS_PASSOS = (
    '1. Pre-req: adicionar campo motivo_perda_origem (charfield: humano/llm_backfill/bot) '
    'em crm_oportunidades. Migration adjacente.\n'
    '2. Management command apps/comercial/crm/management/commands/backfill_motivos_perda.py.\n'
    '3. Flags obrigatorios: --tenant <slug> (sem isso, recusa rodar), --dry-run (default True; '
    'precisa --apply explicito pra persistir), --confidence-min 0.7 (default).\n'
    '4. Pra cada oportunidade sem motivo: pega ultimas 10 msgs da conversa associada.\n'
    '5. Prompt LLM (gpt-4o-mini ou Claude Haiku) classifica entre os MotivoPerda do tenant '
    '+ retorna confidence score 0-1.\n'
    '6. Se confidence >= confidence_min: salva motivo_perda_ref_id + motivo_perda_categoria + '
    'motivo_perda_origem=llm_backfill.\n'
    '7. Se confidence < confidence_min: salva motivo_perda_categoria="outro" + motivo_perda '
    '(texto livre com a explicacao do LLM) + origem=llm_backfill.\n'
    '8. Log resumo no fim: distribuicao por motivo + total por confidence bucket.\n'
    '9. Antes de rodar com --apply em tenant cliente final, **avisar usuarios** via Slack/email.\n'
    '10. Ordem de execucao: aurora-hq -> demo -> (parar e avaliar amostra) -> tenants externos '
    'somente apos OK contratual.'
)

NOVOS_CRITERIOS_ACEITE = (
    '- Campo motivo_perda_origem existe e e populado em todas as escritas\n'
    '- --tenant <slug> obrigatorio (sem ele, comando recusa rodar)\n'
    '- --dry-run e o default; --apply precisa ser explicito\n'
    '- --dry-run imprime distribuicao + amostras sem persistir nada\n'
    '- Confidence baixo (<0.7) vai pra motivo_perda_categoria=outro com texto livre\n'
    '- motivo_perda_origem=llm_backfill em 100% das escritas do comando\n'
    '- Log final mostra: total processado, por motivo, por confidence bucket (>=0.7, <0.7)\n'
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
        print(f'[ERRO] tarefa id={T6_ID} nao encontrada')
        return
    print(f'Atualizando tarefa id={r[0]}: {r[1][:80]}')

    try:
        cur.execute("""UPDATE workspace_tarefa
            SET contexto=%s, passos=%s, criterios_aceite=%s, atualizado_em=NOW()
            WHERE id=%s;""",
            (NOVO_CONTEXTO, NOVOS_PASSOS, NOVOS_CRITERIOS_ACEITE, T6_ID))
        conn.commit()
        print(f'[OK] T6 atualizada — contexto/passos/criterios_aceite com 5 mitigacoes.')
    except Exception as e:
        conn.rollback()
        print(f'[ERRO] {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
