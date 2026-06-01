# Cron — Inatividade do atendente (inbox)

**Comando:** `python manage.py cron_inatividade_atendente`
**Periodicidade recomendada:** a cada 5 minutos
**Doc da feature:** [modulos/inbox/reatribuicao-inatividade.md](../modulos/inbox/reatribuicao-inatividade.md)

## O que faz a cada execucao

1. **Heartbeat:** marca offline agentes que nao pingaram ha mais de `--heartbeat-timeout-min` minutos (default 5). Garante que selecao de "outro agente online" reflete realidade.
2. **Nivel A:** realoca conversas atribuidas mas nao assumidas ha > `tempo_max_sem_assumir_min` (configurado por fila).
3. **Nivel B:** notifica admin quando agente assumiu mas nao respondeu ha > `tempo_max_sem_responder_min`.

Trabalho zero se nenhuma fila tem features ativas — a maioria dos tenants nao vai sentir impacto.

## Setup no EasyPanel (produção)

### Opcao A: Service tipo "Scheduled Task"

1. Abrir o projeto `projetos` no EasyPanel
2. Adicionar service novo:
   - **Type:** App
   - **Name:** `cron_inatividade`
   - **Source:** Git (mesmo repo do app principal) OU "Built image" reusando a imagem do `hub`
   - **Command:** `python manage.py cron_inatividade_atendente`
   - **Schedule (cron):** `*/5 * * * *` (a cada 5 min)
   - **Env vars:** importar do app principal (DB, settings)
3. Marcar como "Restart Always: No" + tipo `Scheduled`

### Opcao B: Cron do host via SSH

Se EasyPanel nao expoe scheduler, rodar no host:

```bash
# Editar crontab do usuario que tem acesso ao docker
crontab -e

# Adicionar
*/5 * * * * docker exec $(docker ps --format '{{.Names}}' | grep projetos_hub | head -1) python manage.py cron_inatividade_atendente >> /var/log/cron_inatividade.log 2>&1
```

## Flags

| Flag | Default | Uso |
|---|---|---|
| `--dry-run` | off | Simula sem alterar nada (recomendado pra primeiro teste) |
| `--tenant <slug>` | todos | Restringe a 1 tenant |
| `--fila-id <id>` | todas | Restringe a 1 fila |
| `--heartbeat-timeout-min <N>` | 5 | Minutos sem heartbeat pra marcar offline |

## Saida esperada (terminal)

```
[Cron Inatividade Atendente]

[tr-carrion] filas: 1

[nuvyon] filas: 1

Concluido: offline_auto=3  realocadas=1  alertadas=2  ja_alertadas=4
```

- `offline_auto` — agentes que viraram offline por falta de heartbeat
- `realocadas` — conversas nivel A reatribuidas
- `alertadas` — admins notificados nivel B
- `ja_alertadas` — conversas nivel B onde alerta ja existia (idempotencia funcionando)

## Validacao pos-setup

1. Roda 1x manual com `--dry-run`:
   ```bash
   docker exec <container> python manage.py cron_inatividade_atendente --dry-run
   ```
2. Confirma saida sem erro
3. Aguardar 15 min e rodar `--dry-run` de novo — outputs devem variar conforme atividade dos agentes
4. Apos 24h ativo, conferir `inbox_historico_transferencia` em prod pra ver registros tipo `realocar_inativo` e `alerta_admin`

## Troubleshooting

| Sintoma | Causa | Fix |
|---|---|---|
| `offline_auto=N` muito alto sempre | Heartbeat do JS nao roda — verificar se navegador do agente esta com inbox aberto | Checar Console (F12) — deveria haver POST `/inbox/api/agente/heartbeat/` a cada 60s |
| `realocadas=0` mesmo com filas ativas | Nenhuma conversa cumpre filtro OU horario da fila esta fora | Rodar com `--dry-run` + verificar Conversa.assumida=False ha > tempo_max_sem_assumir_min |
| `alertadas=0` sempre | Idempotencia segurando — apos 1x notificar, nao notifica de novo ate agente responder | Esperado. Reset acontece quando agente envia mensagem |
| Cron nao roda no horario | Container nao ativo OU schedule errado | `docker ps` + ver schedule no EasyPanel |
