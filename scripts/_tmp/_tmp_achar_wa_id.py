"""Procura nas execucoes do Vero Follow-up os wa_msg_ids enviados pra Michele
e tenta deletar via uazapi.
"""
import os, django, requests, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.sistema.models import Tenant
from pathlib import Path

env={}
for l in Path('/app/.env.n8n').read_text(encoding='utf-8').splitlines() if Path('/app/.env.n8n').exists() else []:
    if l.strip() and not l.startswith('#') and '=' in l: k,v=l.split('=',1); env[k.strip()]=v.strip()
# Caso .env.n8n nao esteja no container, hardcode
N8N_BASE = 'https://automation-n8n.v4riem.easypanel.host'
N8N_KEY = env.get('N8N_API_KEY','')

# uazapi
t = Tenant.objects.get(slug="tr-carrion")
i = IntegracaoAPI.all_tenants.filter(tenant=t, tipo="uazapi", ativa=True).first()
UTOKEN = i.api_key or i.access_token or (i.configuracoes_extras or {}).get("token") or ""
HU = {"token": UTOKEN, "Content-Type":"application/json"}
UBASE = i.base_url.rstrip('/')

TEL_MICHELE = "5511953551590"

# N8N nem sempre tem o key dentro do container; tenta via os.environ tambem
N8N_KEY = N8N_KEY or os.environ.get('N8N_API_KEY','')
print(f'N8N_KEY presente: {bool(N8N_KEY)} len={len(N8N_KEY)}')

if not N8N_KEY:
    print('Sem N8N_API_KEY — nao consegue listar executions. Vou skip + tentar buscar wa_msg_ids direto no uazapi por horario.')
else:
    HN = {'X-N8N-API-KEY': N8N_KEY}
    r = requests.get(f'{N8N_BASE}/api/v1/executions?workflowId=tYckyds4TqPpFOWd&limit=20', headers=HN, timeout=15)
    print(f'execucoes follow-up recentes: {len(r.json().get("data", []))}')
    for ex_meta in r.json().get('data', []):
        eid = ex_meta['id']
        ex = requests.get(f'{N8N_BASE}/api/v1/executions/{eid}?includeData=true', headers=HN, timeout=15).json()
        rd = ex.get('data', {}).get('resultData', {}).get('runData', {})
        # Verifica se rodou pra Michele
        bs = rd.get('Buscar Stale', [{}])[0].get('data', {}).get('main', [[{}]])[0]
        for item in bs:
            tel = item.get('json', {}).get('telefone','')
            if tel and tel.endswith(TEL_MICHELE[-9:]):
                # Pega resposta do Enviar Followup
                env_n = rd.get('Enviar Followup', [{}])
                if env_n:
                    out = env_n[0].get('data', {}).get('main', [[{}]])[0]
                    if out:
                        resp = out[0].get('json', {})
                        msg_id = resp.get('messageId') or resp.get('id') or resp.get('key', {}).get('id')
                        print(f'  ex#{eid} stopped={ex_meta.get("stoppedAt")} msg_id={msg_id!r}')
                        print(f'    resp_keys={list(resp.keys())[:8]}')
                        if 'error' in resp:
                            print(f'    ERROR detalhe: {json.dumps(resp.get("error",{}),ensure_ascii=False)[:300]}')
                        else:
                            print(f'    resp completo: {json.dumps(resp, ensure_ascii=False)[:400]}')
                        # Tenta delete imediatamente
                        if msg_id:
                            for ep, payload in [
                                ('/message/delete', {'id': msg_id, 'fromAll': True}),
                                ('/message/revoke', {'phone': TEL_MICHELE, 'messageid': msg_id}),
                            ]:
                                rd2 = requests.post(UBASE+ep, headers=HU, json=payload, timeout=20)
                                print(f'    DELETE {ep}: {rd2.status_code} {rd2.text[:200]}')
                                if rd2.status_code == 200:
                                    break
