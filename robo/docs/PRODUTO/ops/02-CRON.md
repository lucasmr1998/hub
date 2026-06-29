# 15. Servicos Periodicos e Cron Jobs

**Ultima atualizacao:** 30/05/2026
**Status:** ✅ **Dispatcher central em deploy** — ver [dispatcher-cron.md](dispatcher-cron.md)

> **Mudanca de arquitetura (30/05/2026):** abandonado o desenho de "1 cron por job no host" (que nunca foi implementado em Easypanel). Adotado **1 unico cron** que dispara o `dispatcher_cron` (apps/cron), que le os jobs da tabela `cron_jobs` no banco e despacha cada um na hora certa. Painel de gestao em `/aurora-admin/cron/`.
>
> Doc da nova arquitetura: **[dispatcher-cron.md](dispatcher-cron.md)**.
> O conteudo abaixo descreve o estado **anterior** (legado) e o gap descoberto em 30/05/2026 — mantido como referencia historica.

---

## ⚠️ Estado real em prod (forensics 30/05/2026, ANTES do dispatcher)

A doc descreve a configuracao **ideal** (Linux VPS com crontab/systemd). O ambiente real (Easypanel/Docker) **nao implementa nenhum scheduler**:

- `Dockerfile`/`entrypoint.sh`: rodam migrate + seeds + collectstatic + nginx + daphne. **Sem cron daemon, sem supervisor, sem worker.**
- `docker-compose.yml`: 3 servicos (web + db + nginx). **Sem sidecar de cron.**
- Os `.timer`/`.service` em `apps/integracoes/systemd/` sao para VPS, **nao aplicados no Easypanel**.
- N8N tem 28 workflows ativos, mas apenas 3-4 com `scheduleTrigger`, **nenhum cobrindo os management commands do Hubtrix**.
- `.github/workflows/ci.yml` so tem CI de PR/push — **sem `schedule:`**.

Forensics em tabelas de log (30/05/2026):

| Job | Ultimo registro | Diagnostico |
|---|---|---|
| `executar_automacoes_cron` (motor marketing) | 27/04/2026 | **APOSENTADO em 29/06/2026** (comando e tabelas deletados; substituido pela engine unificada `apps/automacao/`) |
| `executar_recontato` (recontato Hubtrix) | 07/05/2026 (atendimento_log_fluxo) | **morto ha ~3 semanas** |
| `sincronizar_clientes` (HubSoft) | 21/05/2026 (logs_integracao) | **morto ha 9 dias** |
| `notificar_sla_*`, `alertar_sla_vendedor` | nunca | **nunca rodou** |
| `mover_perdidos`, `taguear_leads` | (verificar via crm_historico_estagio) | provavelmente parado |

**O que mantem o sistema funcional em prod hoje:**
- Vero N8N (webhook-triggered, nao cron) atende WhatsApp da TR Carrion.
- Agentes humanos clicam no inbox manualmente.
- Audit log (`log_sistema`) registra por gatilho de view (nao cron).

**Implicacao:** features que dependem de cron estao **silently degraded**. Ex: o `encerrar_inativos` (deploy de 30/05/2026) esta em prod mas nao executa ate cron ser resolvido.

---

## Visao Geral (desenho ideal — NAO refletindo a realidade atual)

O sistema utiliza servicos periodicos para processar automacoes, sincronizar dados com HubSoft, mover leads no CRM e executar delays dos fluxos de atendimento. Nao usa Celery. Tudo deveria rodar via **crontab** (Linux) ou **Task Scheduler** (Windows) + **systemd timer** para o sync HubSoft.

⚠️ Em producao (Easypanel/Docker) essa configuracao **NAO esta aplicada**. Solucao pendente.

---

## Servicos Criticos (producao)

### 1. executar_automacoes_cron (❌ APOSENTADO 29/06/2026)

> **APOSENTADO em 29/06/2026.** O motor de automacao de marketing (`apps/marketing/automacoes/`) foi aposentado: codigo deletado, 8 tabelas `automacoes_*` dropadas em prod. O comando `executar_automacoes_cron`, a funcao `executar_pendentes` e os models `ExecucaoPendente`/`LogExecucao` **nao existem mais**. Substituido pela engine unificada `apps/automacao/` (estilo n8n), em prod porem dormente (execucao gated por `AUTOMACAO_WIRING_ATIVO`). Doc: [modulos/automacao/](../modulos/automacao/README.md). A descricao abaixo fica como referencia historica.

**O que fazia:** Coracao do motor de automacoes. Processava delays pendentes, detectava leads sem contato, tarefas vencidas e disparava automacoes por segmento.

**App:** `apps/marketing/automacoes/` (deletado)
**Comando:** `python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings` (removido)
**Frequencia:** A cada 5 minutos

**Argumentos:**
| Argumento | Descricao |
|-----------|-----------|
| `--dry-run` | Simula sem executar |
| `--tenant SLUG` | Roda apenas para um tenant |

**O que executa (por tenant):**

1. **Processar delays pendentes** — Busca `ExecucaoPendente` com `data_agendada <= agora` e retoma a execucao do grafo de onde parou
2. **Lead sem contato** — Detecta leads sem `HistoricoContato` ha X dias, dispara evento `lead_sem_contato` (com protecao contra duplicatas via `LogExecucao`)
3. **Tarefa vencida** — Detecta `TarefaCRM` pendente com `data_vencimento < agora`, dispara evento `tarefa_vencida`
4. **Disparo por segmento** — Para regras com `evento=disparo_segmento` e segmento FK, itera leads do segmento e dispara automacao (respeita rate limit e cooldown)

**Crontab:**
```bash
*/5 * * * * cd /path/to/project && python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings >> /var/log/automacoes.log 2>&1
```

---

### 2. sincronizar_clientes

**O que faz:** Sincroniza clientes do HubSoft para o sistema local. Cria/atualiza registros em `ClienteHubsoft` e `ServicoClienteHubsoft`. Detecta alteracoes e marca `houve_alteracao=True`.

**App:** `apps/integracoes/`
**Comando:** `python manage.py sincronizar_clientes --settings=gerenciador_vendas.settings`
**Frequencia:** A cada 1 minuto (via systemd timer)

**Argumentos:**
| Argumento | Descricao |
|-----------|-----------|
| `--lead-id INT` | Sincroniza apenas um lead |
| `--todos` | Forca sync completo |
| `--dry-run` | Simula sem salvar |

**Dependencias:** `IntegracaoAPI` (tipo=hubsoft), `HubsoftService`

**Systemd timer** (`apps/integracoes/systemd/robovendas-sync-clientes.timer`):
```ini
[Timer]
OnBootSec=60
OnUnitActiveSec=60
AccuracySec=5
Persistent=true
```

---

### 3. processar_pendentes

**O que faz:** Processa leads com `status_api='pendente'` e envia para o HubSoft via API. Atualiza `status_api` para 'processado' ou 'erro' e preenche `id_hubsoft` em caso de sucesso.

**App:** `apps/integracoes/`
**Comando:** `python manage.py processar_pendentes --settings=gerenciador_vendas.settings`
**Frequencia:** A cada 30 minutos

**Argumentos:**
| Argumento | Descricao |
|-----------|-----------|
| `--lead-id INT` | Processa apenas um lead |
| `--dry-run` | Simula sem enviar |

**Crontab:**
```bash
*/30 * * * * cd /path/to/project && python manage.py processar_pendentes --settings=gerenciador_vendas.settings >> /var/log/hubsoft_pendentes.log 2>&1
```

---

### 3.1 sincronizar_catalogo_hubsoft

**Funcao:** Sincroniza catalogos do HubSoft (planos, vencimentos, vendedores, origens, meios de pagamento, grupos, motivos, tipos, status, tecnologias) para todas as `IntegracaoAPI(tipo='hubsoft', ativa=True)`.

**Comando:**
```bash
python manage.py sincronizar_catalogo_hubsoft --categoria=todos --apenas-automatico --settings=gerenciador_vendas.settings_local
```

**Frequencia recomendada:** 1x ao dia (ex: 03:00 da manha).

**Flag `--apenas-automatico`:** essencial em cron. Roda so as categorias com modo de sync `automatico` em `IntegracaoAPI.modos_sync`. Categorias em `manual` ou `desativado` sao puladas — assim cada tenant controla via `/configuracoes/integracoes/<pk>/` aba "Modos de sincronizacao" o que vai rodar.

**Mapeamento categoria → feature:**
- `servicos` → feature `sincronizar_planos`
- `vencimentos` → feature `sincronizar_vencimentos`
- `vendedores` + 8 catalogos secundarios → feature `sincronizar_vendedores` (modo grupo)

**Output esperado (sucesso):**
```
>> megalink / Hubsoft (id=12)
  servicos              total= 142  criados=  3  atualizados= 12  inalterados=127
  vencimentos           total=  10  criados=  0  atualizados=  0  inalterados= 10
  vendedores            total=  45  criados=  1  atualizados=  2  inalterados= 42
  ...
```

**Falhas comuns:** token expirado (renovacao automatica), HTTP 5xx do HubSoft (logado em `LogIntegracao`, segue pra proxima categoria).

---

## Servicos de Manutencao (diario/semanal)

### 4. taguear_leads

**O que faz:** Auto-atribui tags do CRM baseado na completude dos dados do lead:
- "Comercial" → lead tem plano ou dia de vencimento selecionado
- "Endereco" → lead tem endereco completo (rua, numero, bairro, CEP)
- "Documental" → lead tem CPF preenchido

**App:** `apps/comercial/crm/`
**Comando:** `python manage.py taguear_leads --settings=gerenciador_vendas.settings`
**Frequencia:** Diario (recomendado: 2h da manha)

**Argumentos:**
| Argumento | Descricao |
|-----------|-----------|
| `--dry-run` | Simula sem salvar |
| `--resetar` | Remove tags existentes antes de reatribuir |
| `--estagio TIPO` | Filtra por tipo de estagio |

**Crontab:**
```bash
0 2 * * * cd /path/to/project && python manage.py taguear_leads --settings=gerenciador_vendas.settings
```

---

### 5. mover_perdidos

**O que faz:** Move automaticamente oportunidades do estagio "Qualificacao" para "Perdido" se nao houver validacao de documentacao em X horas (padrao: 48h).

**App:** `apps/comercial/crm/`
**Comando:** `python manage.py mover_perdidos --settings=gerenciador_vendas.settings`
**Frequencia:** A cada 2 horas

**Argumentos:**
| Argumento | Descricao |
|-----------|-----------|
| `--dry-run` | Simula sem mover |
| `--horas INT` | Limite de horas sem atividade (padrao: 48) |

**Cria:** Registro em `HistoricoPipelineEstagio` para auditoria.

**Crontab:**
```bash
0 */2 * * * cd /path/to/project && python manage.py mover_perdidos --settings=gerenciador_vendas.settings
```

---

### 6. popular_crm

**O que faz:** Popula o pipeline do CRM com leads existentes, usando regras de prioridade para definir o estagio:
- P1: HubSoft `servico_habilitado` → "cliente"
- P2: HubSoft `aguardando_instalacao` → "fechamento"
- P3: `documentacao_validada=True` → "fechamento"
- P4: `status_api='processado'` → "negociacao"
- P5: `status_api='processamento_manual'` → "qualificacao"
- P6: Demais → "novo"

**App:** `apps/comercial/crm/`
**Comando:** `python manage.py popular_crm --settings=gerenciador_vendas.settings`
**Frequencia:** Unica vez ou semanal para backfill

**Argumentos:**
| Argumento | Descricao |
|-----------|-----------|
| `--dry-run` | Simula sem criar |
| `--limpar` | Remove oportunidades existentes antes |
| `--criar-perfis` | Cria PerfilVendedor para users sem perfil CRM |

---

## Engine de Pendentes (Delays)

### Automacoes (Marketing) (❌ APOSENTADO 29/06/2026)

> **APOSENTADO em 29/06/2026.** `executar_pendentes` e o model `ExecucaoPendente` viviam em `apps/marketing/automacoes/engine.py`, app aposentado (codigo deletado, tabelas dropadas). A engine unificada `apps/automacao/` assume os delays agora. Descricao abaixo e historica.

**Funcao (removida):** `executar_pendentes(tenant=None)` em `apps/marketing/automacoes/engine.py`

**Como funcionava:**
1. Buscava `ExecucaoPendente` com `status='pendente'` e `data_agendada <= agora`
2. Para cada pendente:
   - Restaurava contexto do JSON serializado
   - Se `nodo` (modo fluxo): retomava traversal do grafo a partir das saidas do no de delay
   - Se `acao` (modo legado): executava a acao diretamente
   - Marcava como `executado` ou `erro`
3. Chamada pelo cron `executar_automacoes_cron`

**Idempotente:** Cada pendente era marcado apos execucao, nao re-executava.

### Atendimento (Fluxos de Bot)

**Funcao:** `executar_pendentes_atendimento(tenant=None)` em `apps/comercial/atendimento/engine.py`

**Como funciona:**
1. Busca `ExecucaoFluxoAtendimento` com `status='pendente'` e `data_agendada <= agora`
2. Para cada pendente:
   - Reconstroi contexto da conversa
   - Retoma traversal do grafo a partir do no de delay
   - Marca como `executado` ou `erro`

**Nota:** Deve ser integrado ao cron principal ou ter cron separado.

---

## Comandos de Setup (unica vez)

| Comando | App | O que faz |
|---------|-----|-----------|
| `seed_planos` | sistema | Cria planos de assinatura e features |
| `seed_funcionalidades` | sistema | Cria 35 funcionalidades do sistema de permissoes |
| `seed_perfis` | sistema | Cria perfis de usuario base |
| `criar_tenant` | sistema | Cria novo workspace multi-tenant |
| `setup_hubsoft` | integracoes | Configura credenciais HubSoft (le de variaveis de ambiente) |
| `seed_inbox` | inbox | Inicializa sistema de inbox |
| `seed_aurora` | suporte | Popula dados de suporte |
| `gerar_faq` | cs/clube | Gera conteudo FAQ do clube de beneficios |

---

## Comandos de Teste (desenvolvimento)

| Comando | App | O que faz |
|---------|-----|-----------|
| ~~`testar_automacoes`~~ | ~~automacoes~~ | ❌ APOSENTADO 29/06/2026 (comando e engine deletados) |
| `testar_pontuacoes` | cs/clube | Testa sistema de gamificacao |

---

## Configuracao Completa de Producao

### Crontab (Linux)

```bash
# ============================================================
# CRITICOS — nao desligar
# ============================================================

# Engine de automacoes (delays, eventos, segmentos)
# ❌ APOSENTADO 29/06/2026. Comando executar_automacoes_cron removido (motor marketing aposentado).
#   Engine unificada apps/automacao/ assume; quando ativada, ajustar este bloco.
# */5 * * * * cd /opt/aurora && python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings >> /var/log/aurora/automacoes.log 2>&1

# Processar leads pendentes para HubSoft
*/30 * * * * cd /opt/aurora && python manage.py processar_pendentes --settings=gerenciador_vendas.settings >> /var/log/aurora/hubsoft_pendentes.log 2>&1

# ============================================================
# MANUTENCAO — pode ajustar horario
# ============================================================

# Auto-tag de leads por completude de dados
0 2 * * * cd /opt/aurora && python manage.py taguear_leads --settings=gerenciador_vendas.settings >> /var/log/aurora/tags.log 2>&1

# Mover oportunidades estagnadas para "Perdido"
0 */2 * * * cd /opt/aurora && python manage.py mover_perdidos --settings=gerenciador_vendas.settings >> /var/log/aurora/perdidos.log 2>&1
```

### Systemd Timer (sincronizar_clientes)

```bash
# Copiar arquivos
sudo cp apps/integracoes/systemd/robovendas-sync-clientes.timer /etc/systemd/system/
sudo cp apps/integracoes/systemd/robovendas-sync-clientes.service /etc/systemd/system/

# Ativar
sudo systemctl daemon-reload
sudo systemctl enable robovendas-sync-clientes.timer
sudo systemctl start robovendas-sync-clientes.timer

# Verificar
sudo systemctl status robovendas-sync-clientes.timer
```

### Task Scheduler (Windows — desenvolvimento)

Para ambiente de desenvolvimento no Windows, criar tarefas no Agendador de Tarefas:

| Tarefa | Programa | Argumentos | Frequencia |
|--------|----------|------------|------------|
| ~~Aurora Automacoes~~ ❌ APOSENTADO 29/06 | ~~python~~ | ~~`manage.py executar_automacoes_cron`~~ (comando removido) | nao roda |
| Aurora HubSoft Sync | python | `manage.py sincronizar_clientes --settings=gerenciador_vendas.settings_local` | 1 min |
| Aurora Pendentes | python | `manage.py processar_pendentes --settings=gerenciador_vendas.settings_local` | 30 min |
| Aurora HubSoft Catalogos | python | `manage.py sincronizar_catalogo_hubsoft --categoria=todos --apenas-automatico --settings=gerenciador_vendas.settings_local` | 1x ao dia (03:00) |

---

## Monitoramento

Para verificar se os crons estao rodando:

```bash
# Verificar logs
tail -f /var/log/aurora/automacoes.log

# ❌ APOSENTADO 29/06/2026. Os models ExecucaoPendente e LogExecucao foram
#   deletados junto com o motor marketing (tabelas automacoes_* dropadas em prod).
#   As queries abaixo nao funcionam mais; o monitoramento da engine unificada
#   (apps/automacao/) sera definido quando ela sair do estado dormente.
#
# python manage.py shell -c "
# from apps.marketing.automacoes.models import ExecucaoPendente
# print(f'Pendentes: {ExecucaoPendente.objects.filter(status=\"pendente\").count()}')
# "
#
# python manage.py shell -c "
# from apps.marketing.automacoes.models import LogExecucao
# ultimo = LogExecucao.objects.order_by('-data_execucao').first()
# print(f'Ultima execucao: {ultimo.data_execucao if ultimo else \"nunca\"} - {ultimo.resultado[:50] if ultimo else \"\"}')
# "
```
