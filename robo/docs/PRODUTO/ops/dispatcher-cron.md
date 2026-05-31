# Dispatcher Cron — Arquitetura

**Status:** Em producao a partir de 30/05/2026
**App:** `apps/cron/`
**Pagina admin:** `/aurora-admin/cron/`

---

## Por que existe

Ate 30/05/2026 o sistema descrevia em `02-CRON.md` que rodava crontabs/systemd timers no host, mas a infra real (Easypanel/Docker) **nao implementava nada**. Resultado: todos os management commands periodicos estavam parados ha semanas/meses (forensics em 30/05).

Solucao: **1 unico cron** no Easypanel que dispara o `dispatcher_cron`, que por sua vez le os jobs cadastrados no banco e dispara cada um na hora certa.

Beneficios sobre cadastrar 5-15 services no Easypanel:
- Adicionar/pausar/editar job sem mexer em infra (Django admin ou painel `/aurora-admin/cron/`).
- Botao "Executar agora" sob demanda.
- Logs centralizados em `cron_execucoes` (stdout, stderr, return code, duracao) — pesquisaveis.
- "Painel de saude": ve em uma tela quem rodou, quem falhou, quem nao roda ha muito tempo.

---

## Modelos

`apps/cron/models.py`:

- **`CronJob`** — declara um job:
  - `nome`, `descricao`, `command` (manage.py command), `args`, `schedule` (cron 5 campos), `ativo`, `timeout_segundos`.
  - `last_run_at`, `last_status` (`nunca`/`running`/`success`/`erro`/`timeout`).
  - Tabela: `cron_jobs`.

- **`ExecucaoCron`** — log de 1 execucao:
  - `cron_job` FK, `inicio`, `fim`, `duracao_segundos`, `status`, `return_code`, `stdout`, `stderr`, `disparado_por`.
  - Tabela: `cron_execucoes`. Indice `(cron_job, -inicio)`.

Cross-tenant (sem TenantMixin) — cron e infra global.

---

## Dispatcher

`apps/cron/management/commands/dispatcher_cron.py`

Algoritmo (cada execucao, agendada pra 1× por minuto):

1. **Advisory lock** Postgres (`pg_try_advisory_lock(7384921)`) pra evitar 2 dispatchers em paralelo. Se ja tem outro rodando, sai sem fazer nada.
2. Le todos os `CronJob` com `ativo=True`.
3. Pra cada um, parseia `schedule` (parser inline em `services.py:cron_match`) e checa se a expressao bate com o minuto atual.
4. Se bater, checa se ja teve `ExecucaoCron` nesse mesmo minuto (proteccao contra double-fire por overlap de dispatcher).
5. Pra cada candidato, dispara via `subprocess.run([python, 'manage.py', command, *args])` com timeout = `job.timeout_segundos`. Stdout/stderr/return_code capturados.
6. Cria `ExecucaoCron` antes (status='running') e atualiza ao fim. Atualiza `CronJob.last_run_at` e `last_status`.

Parser de cron: aceita `*`, `N`, `*/N`, `N-M`, `N,M,P` em cada campo. Dia-da-semana segue padrao classico (Domingo=0). Implementado em ~50 linhas em `services.py` — sem dep externa.

---

## Como rodar em prod

**Roda dentro do proprio container do service `hub`**, como processo em
background ao lado do daphne. O `entrypoint.sh` sobe um `dispatcher_loop` em
background:

```bash
python manage.py dispatcher_loop --intervalo 60 &
exec daphne ...
```

O `dispatcher_loop` (apps/cron/management/commands/dispatcher_loop.py) e um
wrapper que chama `dispatcher_cron` a cada N segundos num loop infinito.
Cada iteracao e isolada (exception nao mata o loop).

**Por que nao um service Easypanel separado:** simplicidade operacional. 1
service, 1 deploy, 1 conjunto de env vars. O advisory lock do
`dispatcher_cron` ja protege contra duplicacao caso o hub tenha multiplas
replicas no futuro.

**Pra desligar:** ou mata o processo no container, ou desabilita cada
`CronJob` individualmente no painel `/aurora-admin/cron/`.

---

## Como adicionar um novo job

**Via Django admin** (`/admin/cron/cronjob/add/`) ou **via data migration**:

```python
CronJob.objects.create(
    nome='meu_job_novo',
    command='meu_comando',
    args='--tenant aurora-hq',
    schedule='*/30 * * * *',
    ativo=True,
    timeout_segundos=600,
    descricao='Faz X.',
)
```

Pronto. O dispatcher pega automatico no proximo tick.

---

## Painel de gestao

URL: **`/aurora-admin/cron/`** (apenas superusers).

**Lista** (`cron/lista.html`):
- KPIs: jobs ativos, total, execucoes 24h, erros 24h.
- Banner vermelho se o dispatcher nao executa ha mais de 3min ("Dispatcher inativo").
- Tabela com cada job: nome, schedule humanizado, command, ultimo run, status, botao Pausar/Ativar, link Detalhes.

**Detalhe** (`cron/detalhe.html`):
- Form editavel: schedule, args, timeout, descricao.
- Botoes: Pausar/Ativar, Executar agora (sincrono, ate `timeout_segundos`).
- Historico das ultimas 50 execucoes: timestamp, status colorido, duracao, return_code, disparado_por, stdout/stderr expandivel.

---

## Jobs iniciais (seed)

Migration `0002_seed_jobs_iniciais`:

| Nome | Schedule | Timeout | Default |
|---|---|---|---|
| `encerrar_inativos` | `*/15 * * * *` | 600s | Ativo |
| `processar_pendentes` | `*/30 * * * *` | 1200s | Ativo |
| `sincronizar_clientes` | `* * * * *` | 300s | Ativo |

Os 3 nascem **ativos** pra reativar o sistema que estava parado ha mais de um mes.

---

## Operacao

### Quando algo der errado

1. Abre `/aurora-admin/cron/`. Banner mostra se o dispatcher esta saudavel.
2. Clica no job com falha → ve `stderr` da ultima execucao.
3. "Executar agora" pra retentar manualmente.
4. Se precisar parar tudo: pausa o job (ou desabilita o service `hub-dispatcher` no Easypanel).

### Adicionar timeout maior pra um job lento

Edit no painel (`/aurora-admin/cron/<id>/`) campo "Timeout (s)".

### Migrar um cron de outra forma pra esse sistema

Se hoje algum cron roda fora desse dispatcher (ex: cron-job.org chamando endpoint, GitHub Actions schedule, etc.):

1. Garante que o command Django existe e funciona standalone.
2. Adiciona um `CronJob` apontando pra ele.
3. Desativa o cron externo.

---

## Limitacoes conhecidas

1. **Granularidade minima: 1 minuto.** Pra rodar a cada 10s precisaria de outro padrao (loop em thread, queue worker).
2. **Single-process.** Todos os jobs sao subprocess do mesmo container do dispatcher. Se um job pesado consome muita RAM, pode afetar o dispatcher e jobs em paralelo. Mitigacao: timeout + ajustar processo Easypanel se preciso.
3. **Sem retry automatico.** Se falhar, o erro fica registrado em `ExecucaoCron.stderr`. O proximo tick agendado tentara de novo. Pra retry imediato, "Executar agora" no painel.
4. **Sem alertas externos.** O banner do painel mostra dispatcher inativo, mas nao envia email/slack. Adicionar via `notificar_sla_*` se quiser (apos esses crons voltarem a rodar).

---

## Migracao a partir do estado anterior

A doc antiga em `02-CRON.md` descrevia crontab/systemd timers que **nunca foram aplicados em Easypanel**. Os arquivos `.timer` e `.service` em `apps/integracoes/systemd/` e em `prod/` continuam no repo mas **estao deprecated** — manter so como referencia historica de como rodar num VPS sem container.

Apos esse dispatcher entrar em prod, a fonte da verdade pra o que roda periodicamente vira a tabela `cron_jobs` no banco.
