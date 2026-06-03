# Auditoria de Logs do Sistema

> **Tarefa Workspace #153** — relatorio do estado atual + gaps + plano de acao priorizado. **Nao implementa nada** — so mapeia.

Gerado: 03/06/2026.

---

## 1. Infraestrutura de log existente

### 1.1 Tabelas/models de log

| Tabela | Total prod | Volume 24h | O que registra |
|--------|-----------:|-----------:|----------------|
| `log_sistema` | 1.887 | 158 INFO/WARNING | Auditoria de acao de usuario (categoria, acao, entidade, mensagem). Decorator `@auditar` + funcao `registrar_acao()`. |
| `logs_integracao` | 348 | 55 | Cada chamada a API externa (HubSoft hoje). Inclui payload, resposta, status_code, tempo_resposta_ms. |
| `cron_execucoes` | 414 | ~144/hora | Cada execucao de CronJob (stdout, stderr, return_code, duracao). |
| `inbox_historico_transferencia` | 15 | poucos | Atribuicao/transferencia de conversa pra agente/fila. |
| `historico_contato` | 258 | poucos | Tentativas de contato com leads. |
| `atendimentos_fluxo` | 100 | varia | Execucoes do motor de atendimento bot (engine.py). |
| `automacoes_logexecucao` | 57 | varia | Execucao de regras de automacao do CRM. |
| `prospectos` (bot Selenium) | 0+ | depende | Status de conversao prospect -> cliente HubSoft (existe campo log mas pouco usado). |

### 1.2 Mecanismos de log

| Mecanismo | Onde mora | Uso atual |
|-----------|-----------|-----------|
| `@auditar(categoria, acao, entidade)` | `apps.sistema.utils` | 140+ usos em 15 views/services. Cobre auth/CRM/leads/inbox/integracoes/marketing/admin/cs. |
| `registrar_acao(...)` | mesmo modulo | Chamada direta dentro de servicos pra log com payload custom. |
| `logger.info/warning/error` (Python logging) | espalhado | Sem persistencia no DB — vai pro stdout do container apenas. Roda na maioria dos services. |
| `LogIntegracao` model | `apps.integracoes.models` | Setado por `HubsoftService._post`/`_get` automaticamente em toda chamada. |
| `LogWebhookN8N` middleware | `apps.integracoes.middleware` | Captura status_code, duracao de webhooks N8N. Persiste em `LogWebhookN8N`. |
| `ExecucaoCron` | `apps.cron.models` | Setado pelo dispatcher antes/depois de cada job. |

---

## 2. Estado por dominio funcional (cobertura)

Codigo verde = bem coberto. Amarelo = parcial. Vermelho = sem cobertura.

### 2.1 ✓ Autenticacao
- Login/logout/falhas: `apps.sistema.signals` registra `auth` em `log_sistema`. **Coberto.**

### 2.2 ✓ Integracoes externas
- HubSoft API: `HubsoftService._post` salva `LogIntegracao` por chamada. **Coberto.**
- Webhooks N8N: middleware captura status. **Coberto.**
- uazapi: ⚠️ chamadas diretas em scripts/bot **NAO sao registradas** em `LogIntegracao`.

### 2.3 ✓ Cron
- Todas execucoes capturadas em `cron_execucoes`. Painel admin mostra historico colorido. **Coberto.**

### 2.4 ⚠️ Conversao Lead -> Prospect (HubSoft cadastrar_prospecto)
- Sucesso: `LogIntegracao` da chamada API + `LeadProspecto.status_api='processado'` + `id_hubsoft`.
- Falha: agora categorizado em `status_api` (`cpf_invalido`, `vendedor_invalido`, `regra_negocio`) + `motivo_rejeicao` (b0ce863).
- **GAP**: nao tem **historico** de mudancas de `status_api` (so o estado atual). Se um lead foi `pendente`->`incompleto`->`pendente`->`processado`, perdemos o caminho.

### 2.5 ⚠️ Conversao Prospect -> Cliente (bot Selenium)
- Sucesso: registrado em `prospectos` table.
- Falha: idem (status='erro', erro_processamento, tentativas).
- **GAP**: tabela `prospectos` ainda esta zerada em prod — bot rodou manual sem usar essa pipeline. Quando ativarmos cron `converter_prospect_cliente`, sera coberto.

### 2.6 ⚠️ Inbox
- Atribuicao/transferencia: `HistoricoTransferencia`. **Coberto.**
- Mudancas de `modo_atendimento` (bot/humano/finalizado_bot): **NAO REGISTRADO**. Isso foi causa raiz do caso Michele 02/06 (regressao silenciosa humano->bot) — sem auditoria, ficamos descobrindo no log de execucao N8N.
- Envio/recebimento de mensagens: registrado em `inbox_mensagens` (tabela principal), mas nao em log de auditoria.

### 2.7 ⚠️ Imagens/Documentos de lead
- Validacao/rejeicao: `@auditar('leads','validar','imagem')`. **Coberto.**
- **GAP**: criacao da imagem (POST `/api/public/n8n/lead/imagem/`) **nao** chama `registrar_acao`. Saber QUEM/QUANDO criou cada imagem precisa olhar webhook N8N. Foi o que dificultou o diagnostico das 44 imagens broken hoje.

### 2.8 ⚠️ CRM (oportunidades, vendas, estagios)
- `apps.comercial.crm.views` usa `@auditar` em muitas views. **Coberto na UI.**
- Mudancas via signal (ex: `crm_historico_estagio`): **persistido** em tabela propria, mas nao em log de auditoria.
- **GAP**: criacao de venda via signal (regra de automacao) nao cai em `log_sistema`. So aparece em `crm_vendas` mesmo.

### 2.9 ⚠️ Aurora-admin
- `apps.admin_aurora.views` usa `@auditar` em algumas rotas. **Parcial.**
- **GAP**: criar/editar/deletar `CronJob`, `IntegracaoAPI`, `Tenant` no admin **NAO registra** automaticamente. Mudancas sensiveis (ex: desativar integracao Nuvyon) sem rastro.

### 2.10 ❌ Bot Vero (N8N)
- Logs ficam SO no N8N — nao espelhados no Hubtrix.
- **GAP CRITICO**: incidentes (caso Michele, caso Fabiana, caso Juliana de hoje) dependeram de analise manual das execucoes N8N. Sem agregacao no Hubtrix.

### 2.11 ❌ Erros Python (logger.error)
- Espalhados em ~50 lugares. Vai pro **stdout do container** (EasyPanel).
- **GAP CRITICO**: nao tem persistencia no DB. Se container reiniciar, perdemos. Nao aparece em `/aurora-admin/`.

### 2.12 ❌ uazapi (envios e respostas)
- Envios via uazapi nao gravam em `LogIntegracao` (so HubSoft grava).
- **GAP**: incidentes onde bot Vero envia msg errada (caso Michele) nao tem registro do POST `/send/text` que disparou.

### 2.13 ❌ Operacoes administrativas via shell
- Scripts rodando no shell (sync_clientes manual, fix em prod, etc.) **nao tem log**.
- **GAP**: alteracoes feitas via Django shell em prod nao deixam rastro.

---

## 3. Gaps criticos (ordem de prioridade)

### P1 — CRITICO (afeta diagnostico de incidentes)

1. **Bot Vero N8N nao gera log no Hubtrix.** Cada caso grave (Michele, Fabiana, Juliana) custou horas porque tivemos que olhar N8N + DB cruzado. **Solucao**: webhook do Hubtrix recebe POST de cada decisao do bot (modo='humano' detectado, msg enviada, etc.) e salva em `log_sistema` com tipo='bot'.

2. **uazapi nao em `LogIntegracao`.** Envios fora do trilho (caso Michele: bot mandou 4 msgs por cima da Kelle) nao tem registro DB. **Solucao**: wrap das chamadas uazapi (POST /send/text) num service com `LogIntegracao.objects.create`.

3. **Erros Python (logger.error) sem persistencia.** Vai pro stdout do container. Reinicio = perda. **Solucao**: handler customizado que tambem salva em `log_sistema` (nivel=error).

### P2 — ALTO (auditoria de mudancas)

4. **Mudancas de `modo_atendimento` sem auditoria.** Causa raiz do caso Michele foi regressao humano->bot silenciosa. Hoje temos a defesa em profundidade (12d7a61) mas o log AINDA NAO existe. **Solucao**: signal `post_save` em `Conversa` quando `modo_atendimento` muda, grava `log_sistema`.

5. **Mudancas de `status_api` em LeadProspecto sem historico.** Saber a jornada (`pendente->incompleto->pendente->processado`) ajuda diagnostico. **Solucao**: signal grava `log_sistema` ou model `HistoricoStatusLead`.

6. **Operacoes do Aurora-admin (CronJob/IntegracaoAPI/Tenant) sem log.** Desativar integracao Nuvyon hoje sem rastro. **Solucao**: middleware ou signal generico nos models sensiveis.

### P3 — MEDIO (cobertura completa)

7. **Criacao de imagem via webhook N8N nao chama registrar_acao.** Hoje complica audit de "quem criou esse RG". **Solucao**: chamada explicita no endpoint.

8. **Webhook recebidos do N8N nao tem retencao definida.** `LogWebhookN8N` cresce sem limite. **Solucao**: cron de cleanup (retencao 90 dias?).

9. **Scripts shell em prod sem rastro.** Quando rodamos fix manual (`set_password`, `update modos_sync`), nada fica registrado. **Solucao**: convencao de chamar `registrar_acao('admin','shell_script', ...)` no inicio do script.

### P4 — BAIXO (nice-to-have)

10. **Bot Selenium ainda nao registra em `prospectos`** (table criada mas vazia — bot roda manual hoje). **Solucao**: quando ativarmos cron `converter_prospect_cliente`, registra automaticamente.
11. **Dashboard agregado de logs.** Hoje precisa ir no Django admin pra ver `log_sistema`. Sem dashboard de "erros nas ultimas 24h por modulo". **Solucao**: parte da tarefa #150 (dashboard de monitoramento).

---

## 4. Plano de acao priorizado

### Sprint 1 (1-2 dias) — fechar P1

- [ ] Wrap `uazapi.send_text/send_image/send_document` num service que registra `LogIntegracao` (com payload, resposta, status_code, lead_id se possivel)
- [ ] Handler customizado de Python logging: `apps.sistema.logging_handlers.DBLogHandler` que escreve em `log_sistema` para `nivel='error'/'critical'`. Configurar no `settings.LOGGING`
- [ ] Endpoint POST `/api/public/n8n/log/` recebe eventos do N8N (bot Vero) e salva em `log_sistema` com categoria='bot_vero'. Atualizar workflows N8N pra chamar esse endpoint em decisoes-chave (transferir humano, gerar resposta, etc.)

### Sprint 2 (1 dia) — fechar P2

- [ ] Signal `post_save` em `Conversa` quando `modo_atendimento` muda: `log_sistema` (categoria='inbox', acao='mudou_modo', entidade='Conversa', entidade_id=conv.id, mensagem='modo X->Y')
- [ ] Signal `post_save` em `LeadProspecto` quando `status_api` muda: idem (categoria='leads', acao='mudou_status_api')
- [ ] Middleware ou signal generico `post_save` em modelos sensiveis (`CronJob`, `IntegracaoAPI`, `Tenant`, `ConfiguracaoEmpresa`) registra alteracoes em `log_sistema` com categoria='admin'

### Sprint 3 (meio dia) — fechar P3 + P4

- [ ] Adicionar `registrar_acao('leads','criar','imagem')` no endpoint POST `/api/public/n8n/lead/imagem/`
- [ ] CronJob `limpar_logs_antigos` (mensal) que apaga `LogWebhookN8N`, `LogIntegracao` e `log_sistema` (nivel=INFO) com mais de 90 dias
- [ ] Convencao no top de cada script shell: `registrar_acao('admin','shell_script', mensagem='nome do script')`

### Sprint 4 — junto da tarefa #150 (admin + dashboard)

- [ ] Pagina `/aurora-admin/logs/` consolidada com filtros (modulo, nivel, periodo, tenant)
- [ ] Widget no dashboard: erros nas ultimas 24h por modulo, com link pro detalhe
- [ ] Alerta uazapi (tarefa #152) dispara quando nivel='critical' chega no `log_sistema`

---

## 5. Resumo executivo

- **Coberto**: 60% das operacoes criticas tem algum tipo de log (auditoria, integracao, cron, atendimento).
- **Gap critico**: bot Vero N8N + envios uazapi + erros Python soltos. Sao os 3 vetores que mais doem em diagnostico de incidente.
- **Esforco pra fechar**: ~3-4 dias de trabalho dividido em 4 sprints.
- **Beneficio principal**: dashboard de monitoramento (tarefa #150) precisa desses logs estruturados pra ser util.

Implementacao NAO faz parte desta tarefa — abrir tarefas filhas no Workspace conforme cada item for atacado.
