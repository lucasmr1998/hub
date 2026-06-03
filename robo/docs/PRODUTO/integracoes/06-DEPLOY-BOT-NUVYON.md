# Deploy do Bot Selenium (`hubtrix-bot-nuvyon`)

Container dedicado que converte prospects HubSoft em clientes via Selenium UI
(passo que a API HubSoft não expõe). **Escopo atual: só Nuvyon.**

> Pra TR Carrion e outros tenants, basta duplicar o serviço com outro
> `DEFAULT_TENANT_SLUG` ou rodar o mesmo container com `--tenant` por lead.

---

## Arquitetura

```
[ projetos_hub ]  ──DB──►  Hubtrix Postgres (leads_prospectos, clientes_hubsoft)
                              ▲ ▲
                              │ │ leitura: pega pendentes
                              │ │ escrita: marca status no dados_custom
                              │ │
                          [ hubtrix-bot-nuvyon ]  ─Selenium─►  HubSoft UI
                          (este container)
```

- **Imagem**: `python:3.11-slim` + chromium do Debian (`web_driver_conversao_lead/Dockerfile`)
- **Entry point**: `bot_runner.py` (loop infinito, poll a cada `POLL_INTERVAL_SEC`)
- **Idempotência**: marca `dados_custom.bot_conversao.status` no lead, com tentativas/backoff
- **Backoff**: 0 / 5min / 30min entre tentativas (até `MAX_TENTATIVAS=3`)
- **Lock**: marca `lock_em` no lead pra evitar dois workers pegarem o mesmo (15min TTL)

---

## Passos pra criar o serviço no EasyPanel

### 1. App → Create → Service

- **Name**: `hubtrix-bot-nuvyon`
- **Type**: Docker (build from Dockerfile)
- **Source**:
  - Git: este repo
  - Branch: `main`
  - **Build path**: `web_driver_conversao_lead/`
  - Dockerfile: `Dockerfile` (default)

### 2. Environment vars

Copiar de `.env.hubtrix` local (gitignored) — preencher manualmente no painel:

| Variável | Valor |
|---|---|
| `HUBTRIX_DB_HOST` | `projetos_banco_hub` (host interno EasyPanel) ou IP externo |
| `HUBTRIX_DB_PORT` | `5432` (interno) ou `5433` (externo) |
| `HUBTRIX_DB_NAME` | `hub` |
| `HUBTRIX_DB_USER` | `admin_hub` |
| `HUBTRIX_DB_PASSWORD` | (mesmo da app Django) |
| `SECRET_KEY` | **mesma** SECRET_KEY do Django prod (pra decrypt Fernet) |
| `DEFAULT_TENANT_SLUG` | `nuvyon` |
| `POLL_INTERVAL_SEC` | `60` |
| `MAX_TENTATIVAS` | `3` |
| `DRY_RUN` | `0` (deixar `1` no primeiro deploy pra validar log antes de tocar Selenium) |

### 3. Resources

- **Memory**: 1 GB (Chrome em headless precisa de pelo menos 512MB)
- **CPU**: 1 vCPU
- **`/dev/shm`**: aumentar pra **1 GB** (default Docker é 64 MB → Chrome crasha)

  No EasyPanel, em **Advanced → Mounts**, adicionar:
  ```
  Type:        tmpfs
  Target:      /dev/shm
  Size:        1g
  ```

### 4. Restart Policy

- **Restart**: `always` (loop infinito Python; se cair, sobe de novo)

### 5. Deploy

- Clicar **Deploy**.
- Esperar build (~3-5 min na primeira vez; depois ~30s com cache).

### 6. Smoke test

Com `DRY_RUN=1` no env:

1. Verificar logs do container — deve mostrar a cada 60s:
   ```
   ==== bot_runner iniciado tenant=nuvyon poll=60s max=3 dry=True ====
   [ts] pendentes=N elegiveis=M
   [DRY_RUN] processaria lead X ...
   ```
2. Confirmar que `pendentes` ≥ 1 (Pedro Paulo #463 deve aparecer).
3. **Trocar `DRY_RUN=0`** no env e re-deploy.
4. Aguardar próximo ciclo. Deve abrir Chrome headless, logar no HubSoft, converter prospect.
5. Validar:
   - DB: `SELECT id, dados_custom->'bot_conversao' FROM leads_prospectos WHERE id=463;`
     → deve ter `status: 'sucesso'`, `tentativas: 1`
   - HubSoft: cliente novo criado, vinculado ao Lead 463.

---

## Observabilidade

- Logs do container são acessíveis em **EasyPanel → hubtrix-bot-nuvyon → Logs**.
- Padrão de log:
  ```
  [2026-06-03T20:00:00Z] pendentes=3 elegiveis=1
  >>> lead 463 'Pedro Paulo' id_hs=22633
      OK lead 463 convertido
  ```
- Erros transient (Selenium timeout, HubSoft 502) caem no backoff automático.
- Erros persistentes após 3 tentativas marcam `status='manual'` — appearecerão filtrando
  `dados_custom->>'bot_conversao'->>'status' = 'manual'` em prod.

---

## Reverter

- EasyPanel → hubtrix-bot-nuvyon → **Stop**. Lead permanece processável manualmente.
- Resetar tentativas de um lead específico:
  ```sql
  UPDATE leads_prospectos
  SET dados_custom = dados_custom - 'bot_conversao'
  WHERE id = 463;
  ```

---

## Próximos passos (não bloqueantes)

- **Métrica no aurora-admin**: card "Conversões automáticas 24h" no dashboard
- **Alerta**: integrar `dados_custom.bot_conversao.status='manual'` com `monitor_sistema`
- **Multi-tenant**: quando TR Carrion entrar no fluxo, separar em outro serviço (`hubtrix-bot-tr-carrion`) com env `DEFAULT_TENANT_SLUG=tr-carrion`
