"""Loop daemon que converte prospects pendentes em clientes via Selenium.

Roda dentro do container `hubtrix-bot-nuvyon` (EasyPanel). Substitui o
legado `gestao_leads/main_leads.py` que apontava pro DB antigo de Megalink.

Fluxo a cada ciclo (default 60s):
  1. SELECT leads_prospectos do tenant Nuvyon com:
       - status_api = 'processado'
       - id_hubsoft preenchido
       - sem ClienteHubsoft vinculado
       - dados_custom['bot_conversao']['status'] != 'sucesso' nem 'manual'
       - tentativas < MAX_TENTATIVAS
       - backoff respeitado (5min/30min/2h conforme tentativa)
  2. Pra cada lead encontrado:
       - Marca lock (dados_custom['bot_conversao']['lock_em'] = agora)
       - Chama main_refatorado.main(nome, id_prospecto, tenant_slug='nuvyon')
       - Atualiza dados_custom: sucesso ou falha + tentativas + ultimo_erro
  3. Sleep e repete

Env vars (em runtime do container, NAO arquivo .env):
  HUBTRIX_DB_HOST, HUBTRIX_DB_PORT, HUBTRIX_DB_NAME, HUBTRIX_DB_USER, HUBTRIX_DB_PASSWORD
  SECRET_KEY                  # mesma do Django pra decrypt
  DEFAULT_TENANT_SLUG=nuvyon
  POLL_INTERVAL_SEC=60        # default
  MAX_TENTATIVAS=3            # default
  DRY_RUN=0                   # 1 = só loga, nao executa Selenium
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Garante imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from credenciais import hubtrix_db_config
from main_refatorado import main as conversor_main


POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL_SEC', '60'))
MAX_TENTATIVAS = int(os.environ.get('MAX_TENTATIVAS', '3'))
TENANT_SLUG = os.environ.get('DEFAULT_TENANT_SLUG', 'nuvyon')
DRY_RUN = os.environ.get('DRY_RUN', '0') == '1'

# Backoff por tentativa: 0=primeira tem 0s espera, 1=5min, 2=30min
BACKOFF_MINUTOS = [0, 5, 30]


def _agora_iso():
    return datetime.now(timezone.utc).isoformat()


def _conn():
    cfg = hubtrix_db_config()
    return psycopg2.connect(**cfg)


def buscar_prospects_pendentes(conn) -> list[dict]:
    """Leads candidatos a conversao por bot."""
    sql = """
    SELECT
        lp.id, lp.nome_razaosocial, lp.id_hubsoft,
        lp.dados_custom, lp.tenant_id
    FROM leads_prospectos lp
    JOIN sistema_tenant t ON t.id = lp.tenant_id
    LEFT JOIN clientes_hubsoft ch ON ch.lead_id = lp.id
    WHERE t.slug = %s
      AND t.ativo = TRUE
      AND lp.status_api = 'processado'
      AND lp.id_hubsoft IS NOT NULL AND lp.id_hubsoft <> ''
      AND ch.id IS NULL
    ORDER BY lp.id ASC
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (TENANT_SLUG,))
        return cur.fetchall()


def filtrar_elegiveis(prospects: list[dict]) -> list[dict]:
    """Aplica regras de tentativas e backoff."""
    elegiveis = []
    agora = datetime.now(timezone.utc)
    for p in prospects:
        bc = (p['dados_custom'] or {}).get('bot_conversao') or {}
        status = bc.get('status')
        if status in ('sucesso', 'manual'):
            continue
        tentativas = int(bc.get('tentativas') or 0)
        if tentativas >= MAX_TENTATIVAS:
            continue
        # Backoff
        ultimo = bc.get('ultimo_em')
        if ultimo and tentativas > 0:
            try:
                ult_dt = datetime.fromisoformat(ultimo.replace('Z', '+00:00'))
                espera = BACKOFF_MINUTOS[min(tentativas, len(BACKOFF_MINUTOS) - 1)]
                if agora - ult_dt < timedelta(minutes=espera):
                    continue
            except (ValueError, TypeError):
                pass
        # Lock antigo (>15min) — assume morto
        lock = bc.get('lock_em')
        if lock:
            try:
                lock_dt = datetime.fromisoformat(lock.replace('Z', '+00:00'))
                if agora - lock_dt < timedelta(minutes=15):
                    print(f'[skip] lead {p["id"]} em lock recente ({lock_dt})')
                    continue
            except (ValueError, TypeError):
                pass
        elegiveis.append(p)
    return elegiveis


def atualizar_dados_custom(conn, lead_id: int, patch: dict):
    """Merge no JSONB dados_custom['bot_conversao']."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dados_custom FROM leads_prospectos WHERE id = %s",
            (lead_id,),
        )
        row = cur.fetchone()
        dc = (row[0] or {}) if row else {}
        bc = dc.get('bot_conversao') or {}
        bc.update(patch)
        dc['bot_conversao'] = bc
        cur.execute(
            "UPDATE leads_prospectos SET dados_custom = %s WHERE id = %s",
            (Json(dc), lead_id),
        )
    conn.commit()


def processar_lead(conn, lead: dict) -> tuple[bool, str | None]:
    """Roda o conversor pra 1 lead. Retorna (sucesso, erro_msg)."""
    lead_id = lead['id']
    nome = lead['nome_razaosocial'] or ''
    id_prospecto = lead['id_hubsoft']

    # Lock
    atualizar_dados_custom(conn, lead_id, {
        'lock_em': _agora_iso(),
        'status': 'tentando',
    })

    if DRY_RUN:
        print(f'[DRY_RUN] processaria lead {lead_id} {nome!r} id_hubsoft={id_prospecto}')
        return False, 'dry_run'

    try:
        # Chama o conversor in-process. Retorna True/False.
        ok = conversor_main(
            nome_filtro=nome,
            id_prospecto=str(id_prospecto),
            tenant_slug=TENANT_SLUG,
        )
        return bool(ok), None if ok else 'conversor retornou False'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}\n{traceback.format_exc()[:500]}'


def processar_todos():
    """Um ciclo: busca pendentes, processa todos."""
    try:
        conn = _conn()
    except Exception as e:
        print(f'[FATAL] sem DB: {e}', flush=True)
        return

    try:
        prospects = buscar_prospects_pendentes(conn)
        elegiveis = filtrar_elegiveis(prospects)
        print(f'[{_agora_iso()}] pendentes={len(prospects)} elegiveis={len(elegiveis)}', flush=True)

        for lead in elegiveis:
            print(f'>>> lead {lead["id"]} {lead["nome_razaosocial"]!r} id_hs={lead["id_hubsoft"]}', flush=True)
            sucesso, erro = processar_lead(conn, lead)
            bc_prev = (lead['dados_custom'] or {}).get('bot_conversao') or {}
            tentativas = int(bc_prev.get('tentativas') or 0) + 1
            patch = {
                'tentativas': tentativas,
                'ultimo_em': _agora_iso(),
                'lock_em': None,
            }
            if sucesso:
                patch['status'] = 'sucesso'
                patch['ultimo_erro'] = None
                print(f'    OK lead {lead["id"]} convertido', flush=True)
            else:
                if tentativas >= MAX_TENTATIVAS:
                    patch['status'] = 'manual'
                else:
                    patch['status'] = 'falha'
                patch['ultimo_erro'] = (erro or '')[:500]
                print(f'    FAIL lead {lead["id"]}: {erro[:200] if erro else "?"}', flush=True)
            atualizar_dados_custom(conn, lead['id'], patch)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    print(f'==== bot_runner iniciado tenant={TENANT_SLUG} poll={POLL_INTERVAL}s max={MAX_TENTATIVAS} dry={DRY_RUN} ====', flush=True)
    while True:
        try:
            processar_todos()
        except Exception as e:
            print(f'[loop-error] {type(e).__name__}: {e}', flush=True)
            traceback.print_exc()
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
