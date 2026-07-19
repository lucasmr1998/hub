# Execution log — Automação (engine unificada)

---

## 2026-06-29 — Aposentar motor de marketing: Fase 0 (gate) + Fase 1 (relocar encanamento)

- **Fase 0 (gate, read-only prod):** 9 regras "ativas" mas **0 execuções/30d**; **0** ações `sincronizar_prospecto_hubsoft` ativas (o risco do nuvyon não existe — nuvyon faz HubSoft via Matrix). Única regra com execuções reais: `aurora-hq` "Novo lead: notificar equipe" (lead_criado, 37x), tenant interno. **Decisão do usuário: pode morrer.** Gate verde — nada funcional depende da execução das regras antigas.
- **Fase 1 (relocar o encanamento, sem deletar):**
  - **`apps/automacao/hub.py`** — `disparar_evento(evento, contexto, tenant)` neutro → só `gatilhos.on_evento` (fallback de tenant, blindado). Não roda regra antiga.
  - **`apps/automacao/signals_dominio.py`** — os 6 signals de domínio (lead_criado, lead_status_pendente, lead_qualificado, oportunidade_movida, docs_validados, indicacao_convertida) relocados do motor antigo; registrados em `automacao/apps.py::ready()`.
  - **Desligado** o `from . import signals` do `marketing/automacoes/apps.py` (evita disparo duplo).
  - **Trocados** os imports de `inbox/signals.py` (3×) + `crm/signals.py` (1×) → `apps.automacao.hub`.
  - **Cron deferido:** os eventos `lead_sem_contato`/`tarefa_vencida`/`disparo_segmento` (gated por regra antiga, 0 fluxo novo consome) morrem com o app na Fase 3; relocar quando um fluxo novo precisar. A engine nova já tem cron próprio (`automacao_retomar`).
  - **Verificado (dev):** signals antigos NÃO carregam, novos carregam, hub ok, `check` limpo → eventos vão **1×** pra engine nova.
- **Fase 2 (desacoplar dados):** FK `EnvioEmail.automacao` → `IntegerField` (migration `emails 0003`; tira o constraint que bloqueava o drop; FK estava morta — `disparar_para_lead` nunca é chamado). Timeline de automação do CRM (`oportunidade_detalhe`) repontada de `LogExecucao` → `ExecucaoFluxo` via adaptador `SimpleNamespace` (template intacto). Fix do `EnvioEmailAdmin.raw_id_fields`. **Gate verde:** nenhuma ref funcional a `marketing.automacoes` fora do app + ferramentas descartáveis (só comentários + settings/urls, que saem na Fase 3).
- **Fase 3 (DEPLOYADA + VERIFICADA EM PROD):** deletado todo o código do motor antigo (engine, views, signals, admin, urls, templates Drawflow, cron + commands, ferramentas de migração `migrar/cutover/migracao_marketing`, testes antigos). O app virou **husk**: `models.py` vazio + `apps.py` + migrations `0001-0006` (tombstone) + **`0007` DeleteModel**. Validado em `aurora_dev` (8 tabelas dropadas, `check` limpo, collection 1196, engine nova verde 35) numa branch separada (`aposentar-marketing-fase3`), mergeada na main sem conflito após o gate. Bônus: corrigida regressão do refactor de memória no `ia_agente` (`getattr`) + 2 testes atualizados. **Husk (não remoção total) porque `emails/0001` depende de `automacoes/0004` no grafo de migrations** — o app fica registrado mas inerte.
- **Go-live EXECUTADO (29/06/2026):** (1) **backup** read-only das 8 tabelas → `_backups/automacoes_legado_prod_20260629.json` (247 linhas, gitignored, PII); (2) **deploy Fases 1-2** → verificado via SSH: container Up, `hub.py`+`signals_dominio.py` presentes, `check` limpo; (3) merge da branch + `push origin main` (`e1d62c3..2206083`, hook de migrations-safety passou) + **deploy do drop**; (4) **verificado em prod:** container novo sem o engine antigo, `check` limpo, **`automacoes_*` = NENHUMA tabela**. Motor de marketing aposentado.
- **Fase 4 (cleanup):** branch `aposentar-marketing-fase3` deletada (mergeada). Pendente menor: permissão órfã `marketing.gerenciar_automacoes` na matriz; drift pré-existente de `notificacoes` (não meu). Cron deferido: `lead_sem_contato`/`tarefa_vencida`/`disparo_segmento` relocar quando um fluxo novo precisar.

---

## 2026-06-29 — Mapa de entrada (WhatsApp → memória) + fluxo de suporte pronto pra prod

- **Como o WhatsApp inicia o fluxo (verificado no código, não chute):**
  ```
  Uazapi → POST /inbox/api/uazapi/webhook/ (inbox/views_uazapi.uazapi_webhook)
         → services.receber_mensagem() → cria Conversa + Mensagem (remetente_tipo='contato')
         → signal inbox/signals.py:192 on_mensagem_recebida → disparar_evento('mensagem_recebida', {'conversa':conversa, 'conteudo':..., ...})  [motor antigo]
         → marketing/automacoes/engine.py:48 → on_evento(evento, contexto, tenant)  [encaminha p/ engine nova]
         → automacao/gatilhos.py:_despachar → acha Fluxo ativo com gatilho_evento='mensagem_recebida' + nó `evento` → _contexto_do_evento → Contexto(conversa=..., var.conteudo=...)
         → roda a partir do nó evento (NÃO do `inicio`) → agente memória 'conversa' lê as mensagens da Conversa → MEMÓRIA OK
  ```
- **Conclusão da dúvida do usuário:** o Uazapi entra **por webhook, mas via inbox** (cria Conversa) — **não** é o webhook cru/stateless. No canal real, a memória `conversa` funciona. O stateless só vale pra fluxo que use o nó-gatilho `webhook` direto (custom). `sessao` memory fica pra esse caso.
- **`gatilho_evento`** é **auto-sincronizado no `Fluxo.save()`** (models.py:52-58) a partir do nó `evento` — não seta à mão.
- **Multi-trigger parcial:** `evento` inicia do **handle do nó evento** (`_enfileirar(trigger_handle)`), `webhook`/`chat` iniciam do `grafo['inicio']`. Então **chat (teste) + evento (prod) coexistem** no mesmo fluxo; só webhook usa o `inicio`.
- **Feito:** "Triagem de Suporte" ganhou nó `evento` (mensagem_recebida) → guard → Classificador (ao lado do chat). `gatilho_evento='mensagem_recebida'`. Falta só `ativo=True` + `AUTOMACAO_WIRING_ATIVO` pra disparar em prod (decisão de go-live).

---

## 2026-06-29 — Reproduzir execução no canvas (estilo n8n) + webhook testável no localhost

- **Webhook no localhost:** `@csrf_exempt`, precisa fluxo `ativo=True`. Validado com curl: `POST /automacao/webhook/<token>/` com body → vira `{{var.payload}}`; nó Responder ao Webhook resolveu o corpo (`{{var.payload.nome}}` → "Ana"). **Limite anotado:** engine tem **um `inicio` só** por fluxo → chat+webhook no mesmo fluxo roda sempre do `inicio` (não há multi-trigger; recomendar 1 gatilho por fluxo até implementar).
- **Persistir estado nas execuções completadas:** `executar_e_persistir` só salvava `estado` quando pausava (`aguardando`). Agora salva `contexto.serializar()` (variaveis+nodes) também em completada/erro → observabilidade.
- **"Ver no fluxo" (estilo n8n):** `execucao_detalhe_api(pk)` devolve grafo+estado+trace; `ExecucoesPanel` ganha botão "↗ ver no fluxo"; `App.abrirExecucao` carrega o grafo no canvas, **pinta o caminho que rodou** (`destacarCaminho(trace)`) e alimenta o **I/O por nó** (`ultimaExec` = variaveis/nodes da execução). Clicar num nó mostra o INPUT (output do nó anterior) e OUTPUT daquela execução. Validado e2e (webhook → execução com `rp.output` persistido).

---

## 2026-06-29 — Nó `responder_webhook` (Respond to Webhook do n8n) + guard de humano no fluxo de suporte

- **Nó `responder_webhook`** (`nodes/responder_webhook.py`): define `status`+`corpo` (resolve `{{...}}`) da resposta HTTP de um fluxo via webhook. Promove `_resposta_webhook`; `webhook_receber` (já roda síncrono via `executar_e_persistir`) lê e devolve isso (JSON se parsear, senão texto) em vez do `{execucao_id, status}` padrão. 3 testes; e2e validado (`{{var.payload.nome}}` → corpo resolvido). Editor: aparece na paleta via catálogo (sem rebuild).
- **Modo de resposta no nó Webhook (estilo n8n):** campo `responder` no nó Webhook — `imediato` (ack), `ultimo_no` (output do último nó executado), `no_resposta` (usa o nó Responder ao Webhook). A `webhook_receber` lê o modo da config do nó de início. Nó de resposta sempre vence se rodou. 3 modos validados.
- **Guard de "humano assumiu" no fluxo de suporte:** nó `if` no topo (`{{var.modo_atendimento}} == humano`) → bot calado; senão segue. Valor `humano` é o canônico de `Conversa.MODO_ATENDIMENTO_CHOICES` (não hardcoded). **Atenção:** o modelo tem `default='humano'` → em prod a conversa nasce humano e o guard calaria o bot por padrão; falta definir **quando a conversa vira `bot`** (decisão de produto, pré-prod).
- **Afinação dos prompts (dados, dev):** Capturador/Financeiro pararam de interrogar — máx 2-3 perguntas, confirmam antes de abrir e avisam o nº do chamado. Validado: conversa fecha em ticket (#7/#8) sem virar questionário.
- **Princípio reforçado pelo usuário (memória):** **nada hardcoded** — valores vêm de config/modelo/dropdown, nunca string mágico no código.

---

## 2026-06-28 — Drag-to-reference + seletor de conta (credential do n8n) + output de integração

- **Drag-to-reference (editor):** o painel INPUT virou **árvore arrastável** (`InputArvore`); cada campo carrega sua referência (`{{nodes.<nó>.campo}}` ou `{{var.campo}}`). Campos de texto/textarea + as regras do switch viram **drop targets** (`propsDrop` insere no cursor). Zero mudança no backend (a referência já era resolvida pelo `contexto.resolver`).
- **Seletor de conta = o "credential" do n8n:** nós de integração ganham o campo **"Conta (Uazapi)"** (`integracao_id`, `fonte: integracoes_uazapi`) — escolhe **qual `IntegracaoAPI`** usar (a credencial é a integração; antes pegava sempre a 1ª ativa). `uazapi_do_tenant(tenant, integracao_id=None)` resolve a escolhida, com fallback pra 1ª ativa. Nova fonte `_integracoes_por_tipo` em `opcoes.py` (genérica por tipo). Backend-driven (dropdown automático, sem rebuild). Vale pros 4 nós WhatsApp (texto/mídia/presença/pergunta).
- **Output de integração enriquecido:** `enviar_texto`/`enviar_midia` devolvem a resposta do uazapi → vai pro `output.resultado` (saneado por `_saneia`, serializável e capado). Agora dá pra referenciar o id/status do envio downstream + ver no painel OUTPUT.
- **⚠️ Nota (não corrigido a pedido):** o chat de teste roda os nós **de verdade** — inclui envio real de WhatsApp. Modo-teste sem outbound foi **deixado de fora** por opção do usuário.
- `check` limpo; `test_automacao_whatsapp` 6/6.

---

## 2026-06-28 — Chat de teste (n8n) + arquitetura conversacional (memória = a conversa)

- **Nó `chat`** (`nodes/chat.py`): gatilho de teste estilo n8n. **Painel "💬 Chat"** no editor (`ChatPanel.tsx`): cada msg roda o fluxo (`var.conteudo`) reusando `testar-fluxo`, extrai a resposta do último agente, mostra trace. **Adicionar o nó chat abre o painel.** **Caminho executado fica verde** (`destacarCaminho` lê o trace). 2 testes.
- **INPUT/OUTPUT por nó (estilo n8n):** o modal do nó pré-preenche **INPUT = output do nó anterior** (upstream via aresta) e **OUTPUT = output do próprio nó**, ambos da última execução; "Executar nó" roda com a última msg do chat.
- **Memória de agente = registry extensível** (`services/memoria.py`, mesmo padrão de nodes/tools). Campo **`Agente.memoria`** (migration `0008`). 1º tipo **`conversa`**: as mensagens da conversa atual — **inbox em prod** (`Mensagem`: contato→user, bot/agente→assistant), **turnos do chat no teste** (`var._memoria_turnos`). **Compartilhada de graça** (todos os agentes leem a mesma conversa) e o **classificador não polui** (não responde → não vira mensagem → fora da memória). Sem tabela nova, sem write-back. Outros tipos (resumo, store) entram no registry depois.
- **Decisão de arquitetura (com o usuário):** "classificar todo `oi` é robótico". Multi-agente mantido (token + prompts focados), mas com **`conversa` como 4ª saída** do classificador → **Conversador** que sonda. Memória compartilhada + persistência = mensagens da conversa do inbox (modelo n8n, backend = nosso inbox).
- **5 agentes (aurora-hq dev):** Classificador (+`conversa`), Conversador, Capturador, Respondedor (RAG), Financeiro — todos `memoria='conversa'`. Fluxo "Triagem de Suporte" religado com **4 ramos** (bug/duvida/financeiro/conversa).
- **Validado (LLM real, multi-turno):** "oi" → `conversa` → Conversador cumprimenta natural; "tô com bug" → `bug` → Capturador pergunta detalhes **lembrando** do oi (não re-cumprimenta, não repete). Memória ponta a ponta. `check` limpo; testes por-arquivo verdes.
- **Status:** arquitetura conversacional **completed** e commitada. RAG só valida em prod (embeddings quebrados no dev). Próximo: **drag-to-reference** no editor (arrastar campo do INPUT → insere `{{nodes.X.campo}}`).

---

## 📌 Resumo geral (estado consolidado — 19-20/06/2026)

> **O que é:** engine de automação unificada estilo n8n, greenfield em `apps/automacao/`, **isolada e dev-only** (migrations só no `aurora_dev`, **nada deployado**, os 3 motores antigos intactos). Objetivo: convergir e aposentar os motores atuais (marketing → atendimento → comercial). A trilha detalhada de cada etapa está nas entradas datadas abaixo.

### Arquitetura
- **Contrato de nó** (`nodes/base.py`): `BaseNode`/`NodeResult` + registry `@registrar`. Cada nó declara `tipo, label, icone, grupo/subgrupo, categoria (gating), saidas, campos_config(), is_trigger`. **Identidade:** o `id` do nó é o **handle** (slug seguro) usado em `{{nodes.<handle>}}`; `data.nome` é só exibição.
- **Contrato híbrido** (`nodes/context.py`): contexto global (tenant obrigatório, fora-de-request) + output por nó endereçável (`{{nodes.id.campo}}`); resolver de template dot-notation próprio. `Contexto.serializar()` por id.
- **Runtime** (`runtime.py`): `executar_fluxo()` percorre o grafo, ramifica por `branch`, pausa/retoma, loop guard, validação. À prova de exceção (nó que estoura vira `erro`).
- **Persistência** (`models.py`): `Fluxo` (grafo JSONField, índice `gatilho_evento`) + `ExecucaoFluxo` (estado serializado + âncora; status inclui `pendente`). Migrations 0001–0004 (dev).
- **3 modelos de execução, um motor só (a "âncora"):** **timer** (delay), **resposta** (conversa: pausa no contato, retoma no signal do inbox ou timeout), **lead** (jornada/enrollment estilo RD/HubSpot — FK `lead` no model, dedup ainda não feito). `execucao.py`: `retomar/retomar_pendentes/retomar_por_resposta`.
- **Camada de gatilho (wiring)** (`gatilhos.py`): `on_evento(evento, contexto, tenant)` — hook **blindado** no `disparar_evento` do marketing acha os fluxos (índice `Fluxo.gatilho_evento`), avalia filtros (reusa `_comparar` do `if`) e **enfileira** execução (`pendente`); o cron `rodar_novos` roda **fora do thread do evento** (deferido, não sobrecarrega). Kill-switch `AUTOMACAO_WIRING_ATIVO` (prod default **off**).

### Nós (10) — por grupo
- **Core:** `http_request` (SSRF + mascaramento)
- **Transformação:** `set_fields`
- **Fluxo:** `if` (true/false), `delay`
- **Gatilho:** `webhook` (✅ funcional), `evento` (✅ funcional via wiring deferido — kill-switch `AUTOMACAO_WIRING_ATIVO`)
- **WhatsApp (Uazapi):** `whatsapp_texto`, `whatsapp_midia`, `whatsapp_presenca`, `whatsapp_pergunta` (envia e aguarda resposta) — reusam `UazapiService` via `services/whatsapp.py`

### Editor, skill, segurança
- **Editor** React Flow (`apps/automacao/editor/`, Vite+TS) servido em **`/automacao/editor/`** (1 app, cache-bust). Paleta n8n-style (busca, categoria→subcategoria, ícones, cor), card com nome+subtítulo+saídas, gatilho com forma especial, modal de nó (INPUT/PARÂMETROS/OUTPUT + Executar), salvar/carregar, construtor de filtros do evento.
- **Skill** `/criar-no-automacao` scaffolda nó (classe+registro+teste+catálogo+gate).
- **Segurança:** CSRF nos endpoints do editor (X-CSRFToken); webhook público com token + rate-limit + cap. Fix: webhook exemptado no `LoginRequiredMiddleware`.

### Como rodar
- Editor: `npm run build` em `apps/automacao/editor/` → `http://localhost:8001/automacao/editor/` (logado). Dev da UI: Vite `:5173`.
- Testar nó/fluxo isolado: `manage.py testar_no` / `testar_fluxo`. Retoma de delays/timeout: `manage.py automacao_retomar` (cron).

### Pendências principais
- ~~Wiring do gatilho de evento~~ **✅ feito (22/06)** — deferido + kill-switch + E2E. Próximo da convergência: mover as **ações do marketing** pra nós da engine nova.
- **Re-hidratar oportunidade/conversa como entidade** em execução deferida (hoje só `lead` via FK; os `var.*` desses eventos já funcionam).
- **Modo jornada/enrollment** (ativar âncora `lead`: 1 por lead/fluxo, dedup, visão por etapa).
- Gating por tenant (categoria existe, não enforced); observabilidade (UI de execuções); decisão de build no deploy; revisão de segurança do signal do inbox antes de prod.

---

## 2026-06-19 — Fase 0: fundação + skill de nós + nó HTTP Request

- **Ação:** Criado o app greenfield `apps/automacao/` (isolado: sem models/migrations/signals/triggers/editor). Entregue em 4 gates validados:
  - **D1 — fundação:** `Contexto` + resolvedor de template `{{...}}` próprio (dot-notation: `{{lead.nome}}`, `{{var.x}}`, `{{nodes.id.campo}}`; full-match preserva tipo bruto; não resolvido fica literal); contrato de nó `BaseNode`/`NodeResult` + registry `@registrar`; command `testar_no`.
  - **D2 — nó de referência `set_fields`** (na unha): escreve/promove variáveis. Vira o template canônico da skill.
  - **D3 — skill `/criar-no-automacao`** (`.claude/skills/`): scaffolda nó (classe + registro + teste + catálogo na doc + gate). Validada com nó de fumaça `noop` (criado, gate verde, descartado).
  - **D4 — nó `http_request` criado pela skill:** guard SSRF (esquema http/https, `getaddrinfo` AF_INET+AF_INET6, bloqueio de IP privado/loopback/link-local/reservado + IPv4-mapped-IPv6, `allow_redirects=False`, cap de tamanho) e mascaramento de `Authorization`/`Cookie`/`Set-Cookie`.
- **Decisão:**
  - Greenfield em vez de generalizar o motor de atendimento (em produção/hotfix) — anti-paralelismo.
  - Contrato **híbrido**: contexto global (tenant obrigatório) + output por nó endereçável; ponte de promoção (`salvar_em`).
  - **Tenancy fora-de-request:** `Contexto.tenant` obrigatório; nenhum nó lê o thread-local (correção do CTO).
  - Serialização por id (não objeto) já no `Contexto.serializar()` — deixa porta aberta pra retoma assíncrona.
  - Parecer do CTO incorporado (4 bloqueadores: resolver novo de template, tenancy, SSRF com redirect+esquema, mascaramento de secrets).
- **Output (arquivos):**
  - `.claude/skills/criar-no-automacao/SKILL.md`
  - `robo/docs/PRODUTO/modulos/automacao/README.md` (+ este log)
  - `apps/automacao/` (`apps.py`, `nodes/{base,context,set_fields,http_request,seguranca}.py`, `management/commands/testar_no.py`)
  - `gerenciador_vendas/settings.py` (+ `'apps.automacao'` no INSTALLED_APPS)
  - `tests/test_automacao_{context,set_fields,http}.py` (29 testes, verdes)
  - Validação manual: GET/POST reais em httpbin + SSRF metadata bloqueado.
- **Status:** completed (Fase 0). Zero impacto em prod até push+deploy; `manage.py check` limpo (boot seguro).

## 2026-06-19 — Runtime (esqueleto do motor, em memória)

- **Ação:** `apps/automacao/runtime.py` — `executar_fluxo(fluxo, contexto)` percorre o grafo (nós + conexões em JSON), executa cada nó, passa output adiante (contrato híbrido), ramifica por branch, pausa (`aguardando`) com `Contexto.serializar()`, e tem loop guard + validação estrutural (`validar_fluxo`). Command `testar_fluxo` pra rodar um fluxo no terminal. Sem models/DB ainda (grafo em memória).
- **Decisão:**
  - **Stack do motor:** Python puro dentro do Django + signals (real-time) + cron (retoma de delays). Síncrono-em-cron pro volume escolhido (médio, ~1k–50k/dia). Sem Celery/Redis por ora; `serializar()` deixa a porta aberta pra fila.
  - **Handle do nó = identidade.** A chave do nó em `nodes` é o handle visível e o que `{{nodes.<handle>}}` referencia — resolve o requisito "ver a identificação do nó" no contrato, antes mesmo do editor.
  - Esqueleto segue **um caminho por vez** (sem execução paralela de ramos por ora).
- **Output (arquivos):** `apps/automacao/runtime.py`, `apps/automacao/management/commands/testar_fluxo.py`, `tests/test_automacao_runtime.py` (9 testes). README com seção "Runtime".
- **Status:** completed (esqueleto). Demonstrado em terminal (fluxo de 2 nós, dado passando entre eles). Zero impacto em prod (sem models/migrations).

## 2026-06-19 — Editor visual (ilha React Flow, dev-only)

- **Ação:** Editor estilo n8n em `apps/automacao/editor/` (React + @xyflow/react + Vite + TS). Paleta vinda do catálogo, nós custom com **handle visível**, conexões `sucesso`/`erro`, painel de config (JSON) com rename de handle, export JSON e botão **Testar**. Backend: `apps/automacao/views.py` (`nodes_catalogo_api`, `testar_fluxo_api`) + `urls.py` wirado em `/automacao/`. 5 testes de endpoint (sem DB, via RequestFactory).
- **Decisão:**
  - **React Flow** em vez de Drawflow — é a peça mais estratégica e UX é prioridade; resolve identificação de nó + bugs de UX de fábrica. Custo (build JS) fica numa **ilha** isolada; o motor Python e o JSON do grafo não mudam.
  - **Handle do nó = identidade visível** no card (atende o requisito "ver o nó").
  - **Persistência:** export/import JSON por ora (zero DB); models de Fluxo/Nó depois.
  - **CSRF:** endpoint `testar-fluxo` `csrf_exempt` DEV-ONLY — endurecer antes de deploy.
- **Output:** `apps/automacao/editor/*` (Vite project, builda — 196 módulos), `apps/automacao/{views,urls}.py`, `gerenciador_vendas/urls.py` (+ `/automacao/`), `tests/test_automacao_editor_api.py`.
- **Validação:** build do editor OK; views testadas (RequestFactory); URLs resolvem. Round-trip visual no browser = passo manual (runserver + npm run dev + login) documentado em `editor/README.md`.
- **Status:** completed (dev-only). **Nada vai pro deploy** — Vite dev server local, zero impacto em prod (sem migrations). Nota: a suíte com DB não roda local por falta da extensão `vector` (pgvector) no Postgres — por isso os testes da automação são todos DB-free.

## 2026-06-19 — Persistência (model Fluxo) + cache-bust

- **Ação:** Model `Fluxo` (TenantMixin) com `grafo` JSONField (mesmo formato do runtime) — `apps/automacao/models.py` + migration `0001_initial` aplicada **só no dev** (`migrate automacao`, não `migrate` geral — havia 2 migrations não aplicadas, incl. `0007_pgvector_extension` que falha local). CRUD: `fluxos_api` (GET lista / POST cria) + `fluxo_api` (GET/PUT/DELETE), tenant explícito. Editor ganhou **nome + seletor de fluxos + Salvar + ＋novo** (carrega via `deRuntime`, preserva posição/label). Cache-bust do bundle por mtime (`?v=`) — sem mais hard-refresh.
- **Decisão:** grafo como **JSONField** (não models normalizados de Nó/Conexão) — impedância zero com runtime/editor. Posição/label guardados no grafo (runtime ignora).
- **Output:** `apps/automacao/models.py`, `migrations/0001_initial.py`, `views.py` (+CRUD, +cache-bust), `urls.py`, editor `{App,flow,api,styles}`.
- **Validação:** CRUD round-trip contra `aurora_dev` (criar→ler→listar→deletar) OK; check limpo; editor builda. **Testes do CRUD não viram pytest** (pgvector bloqueia criar DB de teste) — verificado via RequestFactory contra dev DB.
- **Status:** completed. Migration **só em dev**; **não há push/deploy**. Em prod a migration sobe via CI/CD com OK do dono.

## 2026-06-19 — Nós if/delay + Triggers (webhook) + execução persistida

- **Ação P2:** nós `if` (saídas true/false, operadores igual/maior/contem/vazio…) e `delay` (pausa → `aguardando`). 9 testes.
- **Ação P3:** **webhook** (`webhook_token` no Fluxo + `POST /automacao/webhook/<token>/`; corpo → `{{var.payload}}`) + **execução persistida** (`ExecucaoFluxo` + `execucao.py`: `executar_e_persistir`/`retomar_pendentes`/`_rehidratar`) + cron `automacao_retomar`. Editor: seção "Gatilho: Webhook" (ativar + URL). Migration `0002` aplicada só no dev.
- **Decisão:** webhook autenticado pelo token secreto na URL; execução guarda `Contexto.serializar()`; `delay` pausa e o cron retoma. Re-hidratação restaura tenant+variaveis+nodes (entidades por id ficam pra fase de evento). `runtime` passou a incluir `aguardar_segundos` no `aguardando`.
- **Output:** `models.py` (+webhook_token, +ExecucaoFluxo, migration 0002), `execucao.py`, `views.py` (+webhook +ativar), `urls.py`, `management/commands/automacao_retomar.py`, nós `if_node.py`/`delay.py`, editor (webhook UI, save/load).
- **Validação:** E2E via shell em `aurora_dev` — webhook dispara → `delay` pausa (`aguardando`, trace [n1,n2]) → `retomar_pendentes` → `completado` (trace [n1,n2,n3]). check limpo; 4 nós no editor; build OK.
- **Status:** completed. Migrations **só dev**; sem push/deploy. Dívida: rate-limit do webhook + CSRF (DEV-ONLY) antes de qualquer deploy.

## 2026-06-19 — Editor de nó estilo n8n (form por schema + ícones)

- **Ação:** cada nó passou a declarar `icone` (bi-*) e `campos_config()` (schema dos campos). Catálogo (`/api/nodes/`) expõe os dois. Editor: **modal de detalhe** (duplo-clique no nó) com INPUT · PARÂMETROS · OUTPUT + "Executar nó" — formulário renderizado a partir do schema (texto/textarea/numero/booleano/select/keyvalue/lista_campos), com escape-hatch "config JSON (avançado)". Ícones no card e na paleta (Bootstrap Icons via CDN). Sidebar virou atalho (handle + "Editar parâmetros").
- **Decisão:** nó declara suas properties (estilo n8n) → editor renderiza form genérico, **zero código de form por nó** (a skill já gera o schema). Bootstrap Icons (mesma lib do DS) no editor via CDN.
- **Output:** `nodes/base.py` (+icone, +campos_config), cada nó (+icone +campos_config), `views.py` (catálogo via REGISTRY), editor `NodeModal.tsx` (novo), `BlocoNode`/`App`/`flow`/`api`/`styles`, `index.html`/`editor.html` (bootstrap-icons).
- **Validação:** catálogo retorna icone+campos OK; 52 testes verdes; check limpo; build OK.
- **Status:** completed (P4a/b/c). Falta P4d (endurecer CSRF + rate-limit webhook antes de deploy). Dev-only, sem deploy.

## 2026-06-19 — Card do nó (limpeza + cor) + fix do webhook no middleware

- **Ação (visual):** card do nó simplificado — **ícone + nome/handle**, removido o label redundante ("Condição (If)") e o tipo. **Cor por categoria** (1ª etapa do formato "híbrido" escolhido): barra lateral + ícone coloridos por grupo (Core azul, Fluxo roxo, Transformação verde-água); paleta idem. Card cresce conforme nº de saídas.
- **Fix (correção real):** webhook público `/automacao/webhook/` era **bloqueado pelo `LoginRequiredMiddleware`** (o teste via shell não pegou, pois chamava a view direto). Adicionado ao `_EXEMPT_PATTERNS` em `apps/sistema/middleware.py` (mesmo padrão dos webhooks inbox/assistente). **Verificado over HTTP real** (sem login): `POST /automacao/webhook/<token>/` → 200, `completado`, payload → `{{var.payload}}`.
- **Pendente do "híbrido":** formato especial pra **Gatilho** e **Finalização** — vem junto com o nó de Trigger/Start explícito (item 4 da fundação).
- **Status:** completed (etapa visual + fix). Build OK; dev-only.

## 2026-06-19 — Fundação do núcleo (contrato + runtime + segurança)

- **F1 — Nó declara as próprias `saidas`:** `BaseNode.saidas` + cada nó (http: sucesso/erro, if: true/false, delay: default). Catálogo expõe; editor lê do catálogo (`SAIDAS` deixou de ser hardcoded no `flow.ts`). Nó novo/da skill já funciona sozinho.
- **F2 — Nome de exibição ≠ handle:** card mostra `nome` (livre, ex: "Enviar Typing"); o `id` é o **handle** (slug seguro, sem espaço/acento) usado em `{{nodes.<handle>}}`. Editor: campo Nome (livre) + campo Handle (slugificado, reescreve arestas). Resolve o bug de referência quebrada por nome com espaço/`?`.
- **F3 — Runtime à prova de exceção:** nó que estoura vira `NodeResult(erro)` controlado (segue aresta `erro` ou encerra com motivo) — não derruba mais o fluxo/endpoint.
- **F4 — Validação de grafo:** `validar_fluxo` rejeita conexão cuja `saida` não é uma saída declarada pelo nó de origem.
- **F5 — Segurança:** removido `csrf_exempt` dos endpoints do editor; `editor_page` com `@ensure_csrf_cookie` + editor manda `X-CSRFToken` (lido do cookie). Webhook público mantém `csrf_exempt` (server-to-server) mas ganhou **rate-limit** (60/min por token, via cache) + **cap de payload** (256 KB). Verificado: webhook 200, `testar-fluxo` sem login → 302.
- **Output:** `nodes/{base,http_request,if_node,delay}.py`, `runtime.py`, `views.py`, editor `{flow,api,App,BlocoNode}`. Testes: +2 (F3/F4). Suíte verde, build OK.
- **Status:** completed. Fundação do núcleo fechada. Dev-only, sem deploy.

## 2026-06-19 — Gatilho vira nó (Webhook trigger node)

- **Ação:** webhook deixou de ser propriedade no sidebar e virou **nó de gatilho** (estilo n8n). `BaseNode.is_trigger` (catálogo expõe). Nó `webhook` (grupo Gatilho, laranja, `saidas=['default']`, `is_trigger`). Editor: trigger **sem porta de entrada** + forma especial (pill arredondada à esquerda, laranja). Token gerado no save quando há nó webhook no grafo (`_ensure_webhook_token`); a URL aparece no painel ao selecionar o nó (seção do sidebar removida). O nó é o **início** do fluxo (resolve o `inicio` inferido).
- **Decisão:** um único índice de token no `Fluxo` (sem migration); o nó é a representação + entrada. Evento/agendamento/manual virão como outros nós de gatilho.
- **Output:** `nodes/base.py` (+is_trigger), `nodes/webhook_trigger.py` (novo), `views.py` (catálogo +is_trigger; auto-token no save), editor `{flow,api,App,BlocoNode,styles}`.
- **Validação:** fluxo com `webhook → set_fields` roda E2E (payload passa); 16 testes verdes; build/check OK.
- **Status:** completed (nó Webhook). Próximo gatilho: **evento do sistema** (convergência).

## 2026-06-19 — Nó Evento do sistema (catálogo de eventos + filtros) — parte 1

- **Ação:** `eventos.py` — catálogo dos eventos reais do sistema (12, mapeados dos signals/cron dos motores atuais: lead_criado, lead_qualificado, oportunidade_movida, mensagem_recebida, conversa_aberta/resolvida, docs_validados, indicacao_convertida, lead_sem_contato, tarefa_vencida, etc.), cada um com **subcampos filtráveis** (`lead.origem`, `var.estagio`, `var.conteudo`…). Nó `evento` (gatilho, `is_trigger`) com config = `select` do evento + **filtros** (campo/operador/valor). Endpoint `/automacao/api/eventos/`. Editor: tipo de campo `filtros` (repeater com campo vindo dos subcampos do evento escolhido).
- **Decisão:** um único nó "Evento do sistema" com select (não um nó por evento). Filtros = gate de condição (reusa operadores do `if`). Subcampos = caminhos resolvíveis (`entidade.campo` / `var.chave`).
- **Output:** `eventos.py`, `nodes/evento_trigger.py`, `views.py` (+eventos_api), `urls.py`, editor `{api,App,NodeModal,styles}`.
- **Validação:** catálogo retorna 12 eventos com subcampos; 16 testes verdes; build/check OK.
- **Status:** completed (parte 1 — catálogo + config + editor). **Parte 2 pendente (wiring):** assinar os signals existentes → achar fluxos com o gatilho do evento + filtros que batem → rodar (filtrado por tenant). É o que encosta nos motores em produção.

## 2026-06-19 — Nós de domínio: WhatsApp (Uazapi)

- **Ação:** 1ºs nós de domínio. `services/whatsapp.py` (`uazapi_do_tenant`) resolve o `UazapiService` do tenant via `IntegracaoAPI` (tipo='uazapi') — **reusa** o serviço existente (`apps.integracoes.services.uazapi`), não reimplementa. Nós: `whatsapp_texto` (enviar_texto), `whatsapp_midia` (enviar_midia: image/doc/audio/video), `whatsapp_presenca` (enviar_presenca: digitando). Grupo "WhatsApp" (verde), categoria `atendimento`, saídas sucesso/erro. Sem Uazapi no tenant → erro controlado.
- **Decisão:** executor de domínio único (camada `services/whatsapp.py` compartilhada). Poucos nós focados (texto/mídia/presença) em vez das 24 operações do UazapiService. Categoria marca o gating por tenant (ainda não enforced).
- **Output:** `services/{__init__,whatsapp}.py`, `nodes/whatsapp.py`, editor `flow.ts` (cor WhatsApp), `tests/test_automacao_whatsapp.py` (mock do service, 6 testes).
- **Validação:** 17 testes verdes; check/build OK. Envio real precisa de `--tenant` com Uazapi (aurora-hq/fatepifaespi).
- **Status:** completed.

## 2026-06-20 — Âncora + retoma por resposta (motor conversacional)

- **Ação:** o motor passou a **conversar**. `NodeResult.espera` ({tipo: timer|resposta, chave, segundos}) descreve a pausa. `ExecucaoFluxo` ganhou âncora: `no_pausado`, `modo_espera`, `chave` (contato), `lead` (FK p/ jornada futura) — migration `0003` (dev). `execucao.py`: `retomar(execucao, branch, dados)` continua do nó pausado seguindo o branch (injeta `{{var.resposta}}`); `retomar_pendentes` (timer → resume; resposta vencida → saída `timeout`); `retomar_por_resposta` (acha a execução pausada pelo contato e segue `resposta`). Nó `whatsapp_pergunta` (envia + pausa; saídas resposta/timeout). Signal blindado `apps/automacao/signals.py` (`inbox.Mensagem` de contato → `retomar_por_resposta`, try/except, não quebra o inbox).
- **Decisão (arquitetura):** **um motor, três comportamentos** pela âncora — timer (automação n8n), resposta (conversa), lead (jornada/enrollment RD/HubSpot, futuro). Não forka o runtime; o `executar_fluxo` é o mesmo. Retoma sai do **nó pausado** + branch (não de um "próximo" fixo), pra suportar resposta/timeout.
- **Output:** `nodes/base.py` (+espera), `runtime.py` (pausa carrega no_pausado/espera), `nodes/delay.py`, `models.py` (+âncora, migration 0003), `execucao.py` (reescrito), `nodes/whatsapp.py` (+pergunta), `services/whatsapp.py` (+chave_telefone), `signals.py` (novo) + `apps.py` ready.
- **Validação:** E2E em `aurora_dev` — fluxo `whatsapp_pergunta → (resposta) set_fields` pausa (modo=resposta, chave=tel) e **retoma na resposta** (status completado, trace [pergunta, guardar]); 17 testes verdes; check/build OK.
- **Status:** completed. Base pronta pro modo **jornada/enrollment** (âncora `lead` já no model). Migration só dev; sem deploy. ⚠️ Signal do inbox roda na msg de contato (blindado) — revisar antes de prod.

## 2026-06-20 — Fechar fundação (skill, editor, testes de banco) + fix do INSTALLED_APPS

- **FF1 — Skill atualizada:** `/criar-no-automacao` reescrita pro contrato completo de hoje (icone, grupo/subgrupo, saidas, campos_config com tipos, is_trigger, espera, nome≠handle, reuso de service pra nós de domínio). A skill voltou a reproduzir a fundação corretamente.
- **FF2 — Editor:** deletar nó/aresta (`deleteKeyCode` + botão "Excluir nó") + feedback de campo obrigatório (`obrigatorio` no schema → `*` + aviso no modal).
- **FF3 — Testes de banco:** command `testar_automacao_db` (não-destrutivo, contra `aurora_dev`, CI-friendly) — 5 checks: fluxo simples, execução persistida, conversa pausa, retoma na resposta, trace. Substitui pytest de DB (bloqueado pelo pgvector do `suporte` + FK `inbox→suporte`).
- **FF4 — Fix crítico:** `apps.automacao` tinha sido **removido do `INSTALLED_APPS`** por uma edição externa do `settings.py` durante a sessão — o que quebrou descoberta de management commands e pytest ("Model class ... isn't in an application in INSTALLED_APPS"). **Re-adicionado.** ⚠️ A engine **depende** dessa linha; não pode ser dropada (ver [[feedback-prod-safe-app-refs]]).
- **Validação:** app registrado; **60 testes verdes**; `testar_automacao_db` 5/5; editor builda; check limpo.
- **Status:** completed. Fundação fechada (1+2+3). Dev-only, sem deploy.

## 2026-06-22 — Picker de nós em 2 níveis (estilo n8n)

- **Ação:** o seletor de nós ("Adicionar nó") virou **2 níveis** como o n8n: abre listando **categorias** (Gatilho, Core, Fluxo, Transformação, WhatsApp) com ícone + descrição + drill-in (`→`); clica numa categoria → vê os nós dela (por subgrupo). A **busca achata** tudo (vai direto no nó). **Gatilho** fica em destaque (laranja) e primeiro (todo fluxo começa por um). `GRUPO_INFO` (ícone/descrição/ordem por grupo) no editor.
- **Decisão:** classificação unificada (categoria) + dispatch unificado, **nós separados** — igual n8n. Triggers são uma categoria de nó (`is_trigger`), não um nó único.
- **Output:** editor `App.tsx` (NodePanel reescrito + GRUPO_INFO), `styles.css` (np-cat/drill-in). Build OK.
- **Status:** completed (UX do picker). Falta ainda: paleta contextual (só gatilhos no fluxo vazio) — opcional.

## 2026-06-22 — Wiring: camada de gatilho unificada (evento → fluxo roda sozinho)

- **Ação:** ligado o gatilho de **evento do sistema** à engine. Agora um evento (ex: `lead_criado`) faz os fluxos que o escutam rodarem **sozinhos**. Peças:
  - `Fluxo.gatilho_evento` (índice denormalizado, populado no `save()` a partir do grafo) — acha rápido "quais fluxos escutam o evento X".
  - `gatilhos.on_evento(evento, contexto, tenant)`: acha fluxos do tenant, monta `Contexto` (entidades + escalares), avalia filtros (reusa `_comparar` do `if`), **enfileira** execução `pendente`.
  - `execucao.rodar_novos()` + `automacao_retomar` (cron): roda as enfileiradas **fora do thread do evento**.
  - **1 linha blindada** (try/except) no `disparar_evento` do marketing (único toque no sistema vivo) → `on_evento`.
  - Migration 0004 (campo + status `pendente`), dev only.
- **Decisão (modelo deferido):** o hook **NÃO roda o fluxo na hora** — só query barata + enfileira; o cron roda depois. Responde direto à preocupação de **sobrecarga**: o evento nunca espera o fluxo (nem se tiver nó lento de HTTP/WhatsApp).
- **Segurança:** kill-switch `AUTOMACAO_WIRING_ATIVO` (prod **off** por padrão = inerte mesmo deployado; dev **on**); guard de re-entrância (anti-cascata); tudo por tenant; hook blindado (erro no motor novo não quebra o antigo).
- **Limitação anotada:** execução deferida re-hidrata só o `lead` (FK); oportunidade/conversa como entidade ficam de follow-up (seus subcampos são `var.*`, que já funcionam).
- **Output:** `gatilhos.py` (novo), `models.py`, `execucao.py`, `automacao_retomar.py`, `settings.py`+`settings_local.py`, `marketing/automacoes/engine.py` (hook), `testar_automacao_db.py` (+6 checks). Commits `2a062b0` (isolado) + `0e5ae80` (sistema vivo), na branch `feat/engine-automacao`.
- **Validação (dev):** `testar_automacao_db` 11/11 PASS (enfileira, cron roda → completa, trace `ev→g`, filtro bloqueia/passa) + 60 testes DB-free + `manage.py check` limpo.
- **Status:** completed. **Não deployado** (kill-switch off em prod). Próximo: mover ações do marketing pra nós (convergência) e/ou modo jornada.

## 2026-06-22 — Convergência (1/N): ação `criar_tarefa` vira nó (service de domínio)

- **Ação:** primeira ação do motor de marketing convergida pra engine nova, no padrão **service único + nó** (via skill `/criar-no-automacao`):
  - `services/acoes.py::criar_tarefa(tenant, *, titulo, tipo, prioridade, lead, oportunidade, responsavel, prazo_dias)` — fonte única da lógica (resolve responsável default: lead.responsavel → staff → superuser). Recebe params **já resolvidos** + tenant explícito.
  - nó `criar_tarefa` (grupo **Comercial › Tarefas**, saídas sucesso/erro) — resolve templates e chama o service. Não toca ORM direto.
  - grupo novo "Comercial" registrado no editor (`GRUPO_INFO` + `CORES_GRUPO`); skill atualizada com esse passo.
- **Decisão (sequência de risco):** **passo 1 = só construir** (service + nó); o `_acao_criar_tarefa` do marketing **fica intacto** por enquanto (zero risco ao motor que roda). Passo 2 (depois) = apontar o marketing pro mesmo service (aposentadoria de fato).
- **Validação (dev):** 5/5 pytest unit (mock do service) + smoke DB 13/13 (cria `TarefaCRM` real via gatilho→nó→service e limpa) + check limpo + build do editor.
- **Status:** completed. Faltam as outras ações (notificacao_sistema, mover_estagio, … → 🔴 enviar_whatsapp/email/hubsoft com cuidado) + o swap do marketing (passo 2).

## 2026-06-22 — Convergência (2/N): ação `notificacao_sistema` vira nó

- **Ação:** nó `notificacao_sistema` ("Notificar equipe", grupo **Notificações › Sistema**, saídas sucesso/erro). Aqui o **service de domínio já existia** (`apps.notificacoes.services.criar_notificacao`), então só adicionei o executor fino `services/acoes.notificar` (broadcast, `codigo_tipo='sistema_geral'`) + o nó que o chama. Grupo "Notificações" registrado no editor.
- **Comportamento:** se o tipo de notificação não estiver cadastrado pro tenant, o nó segue a saída **erro** com mensagem clara (mesma semântica do marketing). Marketing intacto (passo 1).
- **Validação (dev):** 5/5 pytest unit (mock do service) + smoke DB 13/13 + check + build.
- **Status:** completed.

## 2026-06-22 — Convergência (3/N): 5 ações CRM/CS de uma vez

- **Ação:** convergidas as **verdes restantes** (DB-only) no padrão service+nó, via skill:
  - `mover_estagio` (Comercial › Oportunidades) — precisa de oportunidade no contexto.
  - `criar_oportunidade` (Comercial › Oportunidades) — idempotente; pipeline/estágio padrão se vazios.
  - `criar_venda` (Comercial › Vendas) — idempotente; status pendente-ERP.
  - `atribuir_responsavel` (Comercial › Oportunidades) — round-robin (menos carregado) ou fixo (username).
  - `dar_pontos` (CS › Clube) — CPF do config ou do lead; **agora filtra por tenant** (corrige gap multi-tenant do código antigo).
  - Executores em `services/acoes.py` (todos com `all_tenants` + tenant explícito, pois a engine roda fora de request). Grupo novo "CS" no editor.
- **Decisão:** ficaram **de fora** as 🔴 com efeito externo/crítico — `enviar_whatsapp`/`enviar_email` (hoje N8N hardcoded + config string única, precisam de redesenho) e `sincronizar_prospecto_hubsoft` (Nuvyon). `webhook` já está coberta pelo `http_request`. Marketing **intacto** (passo 1).
- **Validação (dev):** 82 pytest unit (22 novos) + smoke dos 5 services reais (imports/queries OK, sem fixtures) + check + build.
- **Status:** completed. **Verdes 100% convergidas (7 ações).** Faltam: as 🔴 (redesenho) + o **swap do marketing** (passo 2: `_acao_*` delega pros services).

## 2026-06-22 — Picker 3 níveis (Integrações) + canal/provedor explícito

- **Decisão de design (discutida):** "WhatsApp" não é uma integração, é **capacidade com canais** (Uazapi, Matrix, Meta Cloud) e cada tenant tem o seu. Os canais **não são intercambiáveis** (Uazapi = texto livre; Meta = exige template fora da janela 24h; Matrix = sai pelo bot dela). Logo, **expor o canal/provedor é mais correto** do que abstrair — quem monta o fluxo precisa saber a infra do tenant. → menu de **3 níveis** nas integrações (a intuição original do usuário).
- **Ação:** picker ganhou 3º nível **só na ramificação "Integrações"** (grupo → provedor → ações); os demais grupos seguem 2 níveis (`TRES_NIVEIS={'Integrações'}` no editor). Os 4 nós Uazapi migraram de grupo "WhatsApp" → **Integrações / "WhatsApp · Uazapi"** (provedor = subgrupo). Grupo "Integrações" no `GRUPO_INFO`/`CORES_GRUPO`.
- **Modelo escolhido:** **ações por provedor** (cada um com suas capacidades reais), não um nó genérico com seletor de canal. Default futuro: canal ativo do tenant.
- **Output:** `nodes/whatsapp.py` (grupo/subgrupo), `editor/src/App.tsx` (TRES_NIVEIS + NodePanel 3 níveis), `flow.ts` (cor). Build OK, whatsapp 6/6, check limpo.
- **Status:** completed (estrutura). Próximos provedores (Matrix, Meta, HubSoft, SGP) entram sob Integrações com suas ações.

## 2026-06-22 — Integrações: Matrix · disparar HSM (1º provedor outbound)

- **Ação:** primeiro nó **outbound de integração** — `matrix_hsm` ("Matrix: disparar HSM (WhatsApp)", **Integrações › Matrix**). Dispara template HSM aprovado via Matrix Brasil.
  - **Service:** implementado `MatrixBrasilService.enviar_hsm(cod_conta, hsm, contato, tipo_envio, variaveis, url_file)` — `POST /rest/v1/sendHsm` (v1, token raw — mesmo auth que o service já usava). Trata `cod_error != 0` como erro.
  - **Wrapper:** `apps/automacao/services/matrix.py::matrix_do_tenant` (resolve `MatrixBrasilService.from_tenant`, None se sem integração) — espelha `uazapi_do_tenant`.
  - **Nó:** campos cod_conta, hsm (template), telefone, nome, variaveis (keyvalue), tipo_envio, url_file. Resolve templates, monta `contato`, chama o service. Saídas sucesso/erro.
- **Por que HSM (e não livre):** fora da janela 24h o WhatsApp exige template aprovado. `dialogoWhatsapp`/`sendSms` são **v2 (JWT)** — ficam de follow-up (precisam do fluxo de auth v2 + cache de token).
- **⚠️ Outbound REAL (não testado de verdade):** manda mensagem pra cliente. Validado só com **unit test mockado (5/5)** + check + build. **NÃO** disparei nada real. Teste real exige: tenant Nuvyon + `cod_conta`/`hsm` de um template de teste + um número seguro + **OK do usuário**.
- **Status:** completed (código). **Pendente:** disparo real de validação (com o usuário) + provedores v2 (dialogoWhatsapp/sendSms) + consultar status (`hsmEnviadas`).

## 2026-06-22 — Convergência passo 2 (piloto): marketing `_acao_criar_tarefa` delega pro service

- **Ação:** o `_acao_criar_tarefa` do motor de marketing virou **adaptador fino** — parseia o formato antigo de config (linhas string) e **chama `apps.automacao.services.acoes.criar_tarefa`** (a mesma fonte que o nó da engine nova usa). A cópia da lógica (criar TarefaCRM + fallback de responsável) **saiu do marketing**.
- **É a aposentadoria começando:** agora há **1 implementação** de "criar tarefa", chamada pelos dois motores. Repetir pras outras ações esvazia o motor antigo.
- **Risco:** toca código de prod do marketing — feito **swap fiel** (mesma config, mesmos params, mesmo retorno). **Dev-only até deploy.**
- **Validação:** 7/7 pytest (2 do adaptador mockado + 5 do nó) + check limpo.
- **Status:** completed (piloto). Faltam os swaps das outras 6 ações (notificacao_sistema, mover_estagio, criar_oportunidade, criar_venda, atribuir_responsavel, dar_pontos) — atenção: `dar_pontos`/`atribuir` no service usam tenant explícito, swap = corrige multi-tenancy em prod (mudança consciente).
- **Atualização (22/06, mesma sessão): os 6 swaps restantes FEITOS.** Todas as 7 ações DB-only do marketing agora delegam pros services de `acoes.py` (1 implementação, 2 motores). Removido o import órfão `User` do `engine.py`. `dar_pontos` agora filtra MembroClube por **tenant** (corrige vazamento) — mudança consciente em prod. Validado: 10/10 pytest dos adaptadores (mock) + check. Falta só o swap das 🔴 (enviar_whatsapp/email/hubsoft) quando elas forem redesenhadas/convergidas. **O motor de marketing já não tem cópia própria da lógica das ações DB-only.**

## 2026-06-22 — Integrações: HubSoft (1º provedor ERP) — sincronizar prospecto + consultar cliente

- **Ação:** HubSoft entra como **3º provedor** sob Integrações (ao lado de Matrix e WhatsApp · Uazapi). Starter set sólido (o service HubSoft tem 30+ operações — o resto entra incremental):
  - 🔴 **`hubsoft_sincronizar_prospecto`** — cria rascunho/atualiza prospecto no ERP (core do pipeline Nuvyon). Reusa `hubsoft_prospecto_rascunho.sincronizar_prospecto_hubsoft(lead)` — **a mesma fonte** que a ação `_acao_sincronizar_prospecto_hubsoft` do marketing → converge a última 🔴. Precisa de lead (com pk) no contexto.
  - 🟢 **`hubsoft_consultar_cliente`** — read por CPF/CNPJ (enriquecimento).
  - Wrapper `apps/automacao/services/hubsoft.py` (`hubsoft_do_tenant` + `sincronizar_prospecto` + `consultar_cliente`).
- **⚠️ Outbound real (sincronizar):** validado só com unit mockado (8/8). NÃO sincronizei nada real — teste real exige Nuvyon + lead de teste + OK.
- **Próximo (e ROI do mecanismo dinâmico):** HubSoft tem APIs de **listagem** (`listar_modelos_contrato`, `listar_servicos`, `listar_planos_por_cep`…) — quando construir o **select_dinamico + preview** (adiado no Matrix), o HubSoft é onde ele se paga.
- **Status:** completed (starter set). Resto da API HubSoft (contrato, faturas, serviços técnicos, viabilidade, OS) entra sob demanda.
- **Atualização (22/06, mesma sessão): +2 nós read HubSoft** — `hubsoft_listar_faturas` (boletos por CPF/CNPJ, só-pendentes opcional) e `hubsoft_planos_cep` (viabilidade por CEP). HubSoft agora com **4 nós** (1 🔴 write + 3 🟢 read). Wrappers `listar_faturas`/`listar_planos_por_cep` em `services/hubsoft.py`. 12/12 pytest.

## 2026-06-22 — Geração em massa: HubSoft completo + engine comercial (44 nós no total)

- **Pedido:** gerar todos os nós da engine comercial + todos os HubSoft possíveis, com **params/filtros customizáveis** (obrigatórios mantidos). Feito em 6 lotes inline, commitados.
- **HubSoft (24 nós, base `HubsoftNode` em `hubsoft_base.py` — resolve service + trata erro):**
  - **Reads (17):** consultar_cliente, listar_faturas, planos_cep, listar_servicos, listar_vencimentos, listar_modelos_contrato, viabilidade (endereço/coords), atendimentos/OS do cliente, extrato_conexão, renegociações (listar + simular), clientes/OS/atendimentos (todos, paginados), horários de agenda.
  - **Writes moderados (7):** sincronizar_prospecto, criar/aceitar contrato, efetivar_renegociacao, abrir_atendimento_os, agendar_os, abrir_os.
  - **🔴🔴 fora (decisão):** suspender/habilitar/ativar serviço, solicitar_desconexao, desbloqueio_confianca, reset_mac/phy (afetam serviço do cliente). `anexar_arquivos_contrato` fora (exige bytes).
  - Cada nó espelha os params do método (obrigatórios → `obrigatorio:True`; filtros → campos opcionais). Reusa os métodos do `HubsoftService` (sem 2ª cópia).
- **Engine comercial (2 nós genéricos, reusam os registries existentes):**
  - `condicao_comercial` (Fluxo › Lógica) — expõe as **12 condições** (`automacao_condicoes`) via select + operador + valor + campo; saídas true/false; avalia sobre a oportunidade.
  - `acao_comercial` (Comercial › Pipeline) — expõe as **7 ações** (`_EXECUTORES_ACAO`) via select + params keyvalue.
- **Validação:** **145 testes** da automação passam + check. **Nenhum outbound real disparado** (writes validados com mock). Branch instável (outra sessão jogando na main) — restaurado várias vezes; trabalho commitado a cada lote.
- **Total: 44 nós** (Integrações 29, Comercial 6, Fluxo 3, Gatilho 2, Core/Transformação/Notificações/CS 1 cada).
- **Status:** completed.

## 2026-06-22 — Engine mesclada na `main` + tela de execuções (observabilidade)

- **Merge na main:** `feat/engine-automacao` → `main` (local, **não pushado/deployado**). Motivo: outra sessão concorrente vivia jogando o working tree na `main`, derrubando o editor (404) toda hora; com a engine na main, parar nela deixa de quebrar. Feito com segurança (merge `main`→branch primeiro, 1 conflito resolvido — `extrair_historico_matrix.py`, peguei a versão da main; auto-merge do `settings.py` manteve `apps.automacao` + apps novos da main; 145 testes + check verdes — só então fast-forward na main). Revert point: main estava em `71f5cd7`. **Antes de deployar:** revisar signal do inbox (roda por mensagem) + mudança do `dar_pontos` (filtro por tenant); migrations 0001-0004 sobem no deploy (tabelas aditivas); Dockerfile não muda (bundle React pré-buildado + collectstatic).
- **Tela de execuções (observabilidade):** duas formas — (a) **aba "Execuções" DENTRO do editor** (estilo n8n: troca Editor↔Execuções sem sair da página, o fluxo continua montado), via `ExecucoesPanel` React + API JSON `/automacao/api/execucoes/` (tenant-scoped, filtro por status, toggle "só deste fluxo"); (b) página standalone `/automacao/execucoes/` (DS: layout_app + stat_card + badge) como visão global. Lista `ExecucaoFluxo`: status, quando, trace expansível por nó, erro. Validado: render real 200 + API 200 + check + build TS.
- **Status:** completed. Próximos da evolução (acordados): **nó de loop/iterar** + **Testar com contexto de exemplo**.

## 2026-06-22 — Opções dinâmicas (dropdowns por tenant) — mecanismo genérico

- **Pedido:** "tudo que dá pra fazer dinâmico dentro do nosso sistema deve ser feito". Gatilho: o filtro de `lead_entrou_segmento` pedia o nome do segmento **digitado** em vez de uma lista.
- **Mecanismo (genérico, reusável):** `apps/automacao/opcoes.py` — registry `FONTES` (`fonte -> (tenant)->[{value,label}]`) + endpoint `/automacao/api/opcoes/<fonte>/` (login + tenant). Um campo declara `'fonte': '<nome>'` no `campos_config` (ou no subcampo do evento) e vira **dropdown carregado da API**. No editor: component `OpcoesSelect` (cache por fonte) usado no `renderCampo` e no valor do `FiltrosCampo` (quando o campo escolhido tem fonte).
- **Fontes locais ligadas (4):** `segmentos` (SegmentoCRM), `pipelines` (Pipeline), `estagios` (PipelineEstagio, label "Pipeline › Estágio"), `responsaveis` (PerfilUsuario staff). Campos ligados: filtro de evento (segmento/estágio/pipeline/responsável), `criar_oportunidade` (pipeline/estágio), `mover_estagio` (estágio), `atribuir_responsavel` (usuário).
- **Validação (dev):** as 4 fontes retornam dados reais (6/3/19/4) + check + build TS.
- **Status:** completed (fontes locais). **HubSoft (externo)** pode entrar como fonte depois (chama a API do tenant — `listar_servicos`/`modelos_contrato`/`planos_cep`), com cache. Bug de layout do bloco Filtros também corrigido (não estoura mais).

## 2026-06-22 — Capacidade de Agente IA — D1: Agentes gerenciados + serviço LLM + playground

- **Por quê:** trazer fluxos conversacionais com IA pra engine (alvo: bot WhatsApp Megalink NPS+upsell). Convergência do Atendimento. Plano completo: `C:\Users\lucas\.claude\plans\a-gente-deve-gerar-expressive-pixel.md`.
- **Decisões (com o usuário):** (1) **Agentes são entidades gerenciadas** (área `/automacao/agentes/`), não config inline no nó — o fluxo referencia por dropdown (reusa o mecanismo de opções dinâmicas). (2) **Tools moram no agente** (loop LLM↔tool interno no nó; não mexe no runtime/editor). (3) **Memória:** janela = execução pausada (já existe); fatos = CRM via tools (já existe); **sem tabela nova** (chat persistente deferido, vira flag no `Agente` se precisar — usuário indeciso, porta aberta).
- **D1 entregue:**
  - `services/ia.py` — `integracao_ia_do_tenant(tenant, integracao_id=None)` + `chamar_llm(integracao, messages, modelo=None, max_tokens=1000)`. **Extraído** de `atendimento/engine.py:1465` (`_chamar_llm_simples`), cópia canônica multi-provider (OpenAI/Groq/Anthropic/Google AI) — executor de domínio único, NÃO importa do motor a aposentar.
  - Model `Agente(TenantMixin)` (`nome`, `integracao_ia` FK, `modelo`, `system_prompt`, `tools` JSON pré-preparado p/ D3, `ativo`) + migration **0005_agente** aplicada em `aurora_dev`.
  - Tela `/automacao/agentes/` (estende `layout_app`): lista (cards) + criar/editar (modal) + **playground** ("testar agente": manda msg → resposta do LLM, sem memória). Nav Editor·Execuções·Agentes.
- **Gate D1 (validado):** `check` limpo; `agentes_page` renderiza (200); playground 404 p/ agente inexistente; **`chamar_llm` real retornou texto** (OpenAI da `fatepifaespi`/`aurora-hq`). Falta o usuário criar um agente na UI e testar no playground.
- **Status:** completed (aguardando validação do usuário antes do D2: nó `ia_agente`).

## 2026-06-23 — Agente IA — D2: nó `ia_agente` (turno conversacional + memória)

- **O que:** nó que referencia um `Agente` gerenciado e roda 1 turno de conversa. `apps/automacao/nodes/ia_agente.py` — config `agente_id` (dropdown `fonte:'agentes'`, nova fonte em `opcoes.py`) + `mensagem` (default `{{var.conteudo}}`; se vazio usa `var.resposta` da retoma ou `var.conteudo`). Monta system prompt do agente + histórico + msg → `services/ia.chamar_llm` → `output.resposta`. Saídas `sucesso/erro`.
- **Memória (janela):** histórico em `var._hist_agente_<id>` acumulado via `promote` (janela 10 turnos). Persiste no `estado` da execução → na retoma volta junto. **Sem tabela nova.** Loop conversacional = topologia do fluxo (ex: `ia_agente` → `whatsapp_pergunta` que pausa → resposta volta pro `ia_agente`); o nó em si **não** pausa (separação: enviar/aguardar é do nó de WhatsApp).
- **Reuso:** `services/ia.chamar_llm` (D1). Não duplica chamada LLM.
- **Gate (validado):** `check` limpo; **7 testes** (`tests/test_automacao_ia_agente.py`, mock de `Agente`+`chamar_llm`) verdes; **E2E real em dev** (agente `Hotspot`/`TESTE D2` no `aurora-hq` + OpenAI real) → `branch=sucesso`, resposta coerente, histórico acumulado. Nó aparece na paleta (IA › Agente) sem rebuild (catálogo em runtime).
- **Não commitado ainda** (risco de push automático pra prod pela sessão concorrente — aguardar OK do usuário pra commitar).
- **Status:** completed. Próximo: **D3** (tools no agente — modelo CTO: descritor curado que delega a nós, com idempotência + teto de output + params pinados).

## 2026-06-23 — Agente IA — D3: tools no agente (loop tool-calling)

- **Modelo (parecer do CTO):** a camada de tool é própria (`services/ia_tools.py`: chave + descrição p/ LLM + schema dos args) e **delega** ao executor de domínio — NÃO é "todo nó vira tool automático". Garantias: **teto de output** (`_cap`, 1200 chars), **tenant-safe** (`contexto.tenant`), **allowlist por agente** (`Agente.tools`), **params pinados** (ex: pipeline não exposto ao LLM), **idempotência** (tools de escrita delegam a nós já idempotentes).
- **`services/ia.py::chamar_llm_com_tools(integracao, messages, tools_schema, despachar_tool, modelo, max_iter=5)`** — loop extraído de `atendimento/engine.py:2338`, com `despachar_tool(nome,args)->str` **injetado** (desacopla de `atendimento`). Só OpenAI/Groq; senão cai em `chamar_llm`.
- **2 tools curadas:** `registrar_feedback(nota, comentario)` — self-contained, grava `LogSistema` no lead (caso NPS); `criar_oportunidade(titulo, valor)` — **delega ao nó** `criar_oportunidade` (pipeline pinado, idempotente).
- **Nó `ia_agente`:** quando o agente tem `tools`, monta o schema e chama `chamar_llm_com_tools`; histórico guarda só user+assistant final (não o trace de tools).
- **UI:** seção **Ferramentas** (checkboxes) no editor do agente (`/automacao/agentes/`); `agente_salvar` lê `tools[]`.
- **Gate (validado):** `check` limpo; **15 testes** (`test_automacao_ia_tools.py` + `_ia_agente.py`) verdes; **E2E real** em dev — agente com `registrar_feedback` + msg "minha nota é 9, adorei" → o LLM **chamou a tool** (extraiu nota=9 + comentário) e gravou `LogSistema` (0→1). Não commitado ainda (risco de push da sessão concorrente).
- **Status:** completed. Próximo: **D4** (RAG — `services/rag.py` + tool `consultar_base_conhecimento` reusando `apps/suporte/services.buscar_artigos`).

## 2026-06-23 — Agente IA — D4: RAG com filtro por categoria (opção B)

- **Decisão (usuário):** opção **B** — o agente enxerga um **subconjunto** da base de conhecimento (por categoria), não a base inteira. Isolamento entre clientes já vem do `buscar_artigos` (filtra `tenant`); B adiciona escopo **dentro** do tenant (ex: agente de Vendas só vê a categoria "Vendas").
- **Estrutura reusada (já existia, madura):** módulo **Suporte › Base de Conhecimento** — `CategoriaConhecimento`/`ArtigoConhecimento` (pgvector 1536, embedding por signal), telas `/suporte/conhecimento/gerenciar/`, busca `buscar_artigos` + `/api/buscar/`, "perguntas sem resposta". Não construímos base nova.
- **Entregue:**
  - `Agente.base_categorias` (JSON, ids de CategoriaConhecimento; vazio = base inteira) + migration **0006**.
  - `buscar_artigos(..., categorias=None)` estendido (backward-compatible; `.filter(categoria_id__in=...)`).
  - `services/rag.py::buscar_conhecimento(tenant, pergunta, categorias, k)` — envolve `buscar_artigos`, formata título+trecho, **degrada gracioso** (sem embedding/pgvector → texto neutro, não levanta).
  - Tool `consultar_base_conhecimento` em `ia_tools.py` (assinatura das tools virou `fn(contexto, args, agente)`; `despachar(..., agente)`; nó passa o agente) — usa `agente.base_categorias`.
  - UI: seção **Base de conhecimento** (checkboxes de categorias) no editor do agente; painel do nó `ia_agente` mostra prompt + tools + categorias.
- **Gate (validado):** `check` limpo; **21 testes** (`test_automacao_rag.py` + tools + agente); tela renderiza; **dev NÃO roda RAG** (aurora_dev sem coluna `embedding`/pgvector). Validação de **dado real em prod (read-only):** `aurora-hq` tem 6 categorias com artigos embeddados (Produto 8, Integrações 5, Vendas 4, Técnico 2, Onboarding 2, FAQ 1) → o filtro por categoria tem dado real. Não commitado (risco de push da sessão concorrente).
- **Pendências do RAG:** **pgvector no `aurora_dev`** (pra testar localmente) e **clientes-alvo popularem a base** (nuvyon/tr_carrion/fatepi/megalink ainda não têm artigos). Hoje só `aurora-hq` e `demo` têm base.
- **Status:** completed. Próximo: **D5** (pausa-por-humano via `if` em `{{var.modo_atendimento}}` + canal Evolution se necessário) e/ou montar o **fluxo de teste** do bot.

## 2026-06-23 — Agente IA — D5: pausa-por-humano (+ Evolution deferido)

- **Decisão:** modelo **declarativo** (não hard-guard). Hard-guard no resume quebraria o loop porque `inbox.Conversa.modo_atendimento` tem **default `'humano'`** (bot/humano/finalizado_bot) — bloquear em 'humano' pararia toda conversa. Então o fluxo **opta** por checar via nó `if`.
- **Entregue (4 edições pequenas):**
  - `inbox/signals.py` (`on_mensagem_recebida`): o contexto do evento `mensagem_recebida` agora carrega `modo_atendimento` (estado da conversa no disparo).
  - `eventos.py`: `mensagem_recebida` expõe o subcampo filtrável `var.modo_atendimento`.
  - `execucao.py`: `retomar(..., extra_vars=None)` + `retomar_por_resposta(..., modo_atendimento=None)` — na retoma, **refresca** `var.modo_atendimento` (o `_rehidratar` não restaura a entidade conversa, então promove o escalar atual).
  - `automacao/signals.py`: o gancho de retoma passa `conversa.modo_atendimento` atual.
- **Como o fluxo usa:** nó `if` no topo do loop — esquerda `{{var.modo_atendimento}}`, operador `igual`, direita `humano` → saída `true` encerra (bot não responde); `false` segue pro Agente IA. Visível e à prova de loop (default não bloqueia salvo se o autor adicionar o check).
- **Premissa:** depende do inbox marcar a conversa como `'humano'` quando um atendente assume (semântica já existente do campo; o motor antigo usa isso).
- **Evolution API:** **deferido** — nosso sistema usa Uazapi/Matrix; o alvo (Megalink) re-plataforma no canal nosso. Só fazer se um cliente exigir Evolution.
- **Gate (validado):** `check` limpo; **24 testes** (`test_automacao_pausa_humano.py` + regressão D2–D4); o `if` ramifica certo por `modo_atendimento`; `retomar_por_resposta` aceita o novo arg (compat). Não commitado (risco de push da sessão concorrente).
- **Status:** completed. **Capacidade de Agente IA completa (D1–D5).** Falta: montar o **fluxo de teste** do bot, **ligar o wiring** em prod (com revisão do signal do inbox + `dar_pontos`), e **commitar**.

## 2026-06-24 — Tools de fato (paridade com o n8n) + fluxo Hotspot

- **Contexto:** o D1–D5 foi commitado (`4a83cfc`). O fluxo n8n Megalink tinha 4 "saves" (nota, é-cliente, intenção, energia); só `registrar_feedback` existia.
- **3 tools novas em `ia_tools.py`** (mesmo padrão curado, self-contained, tenant-safe via `LogSistema`, `fn(contexto,args,agente)`): `marcar_cliente` (é cliente da Megalink?), `marcar_intencao` (intenção de compra), `marcar_intencao_energia` (interesse no Mega Energia). Helper `_marcar_fato`. Aparecem automático na seção Ferramentas do agente.
- **Fluxo "Bot Hotspot (teste)"** (id 36, dev, `ativo=False`) + agente **Hotspot** com o **system prompt real do n8n** (NPS hotspot + upsell Mega Energia) + as 4 tools ligadas.
- **Gate (validado):** `check` + **27 testes** (3 novos parametrizados); **E2E real de 4 turnos** em dev → bot segue o script (NPS → é-cliente → pitch Mega Energia), `registrar_feedback` e `marcar_cliente` dispararam no momento certo e gravaram no CRM.
- **Status:** completed. Bot Megalink remontado nativo. Pendente: go-live (wiring) e clientes-alvo terem base/canal.

## 2026-06-24 — Simulador de conversa (chat) no editor do agente

- **Por quê:** testar o bot interativamente sem WhatsApp (o E2E até aqui era via script). O playground era 1 turno só.
- **O que:** o "Testar" do agente virou um **chat multi-turno**. Endpoint `agente_simular_api` (`POST /automacao/api/agentes/simular/`) roda o agente com o histórico do chat + tools (que **rodam de verdade em dev**) e devolve `{resposta, tools}` (quais dispararam). Front em `agentes.html`: bolhas user/bot + chips 🔧 das tools que rodaram. Reusa `chamar_llm`/`chamar_llm_com_tools` + `despachar`. Tenant-safe.
- **Gate:** `check` ok; página renderiza; 2 turnos reais → memória carrega + `registrar_feedback` dispara e é reportada na UI. Server-side (sem rebuild do editor).
- **Status:** completed.

## 2026-06-24 — Edição de agente vira PÁGINA (não modal) + chat ao lado

- **Pedido do usuário:** editar agente numa página dedicada, não em modal.
- **O que:** `agente_editar_page` (`/automacao/agentes/novo/` e `/<id>/editar/`) — template `agente_editar.html` com **form (esquerda) + chat de teste (direita)** lado a lado. A lista (`agentes.html`) virou só gerência: cards com **Editar/Testar** (link pra página) + **Excluir**; modais de form/chat removidos. O chat (simulador) migrou pra página de edição. `agentes_page` view enxugada (sem agentes_json/tools/categorias). Removido o endpoint morto `agente_playground_api` (substituído por `agente_simular`).
- **Gate:** `check` ok; lista/novo/editar renderizam (200).
- **Status:** completed.

## 2026-06-25 — RAG fecha o ciclo (perguntas sem resposta) + anti-invenção

- **Problema visto pelo usuário:** o Hotspot (sem RAG ligado) **inventou** um prazo de desconto que não estava em lugar nenhum (alucinação).
- **3 ajustes:**
  1. **RAG:** quando `consultar_base_conhecimento`/`rag.buscar_conhecimento` **acha 0**, registra a pergunta em `PerguntaSemResposta` (reusa `suporte.services.registrar_pergunta_sem_resposta`, tenant + pergunta + lead) — fecha o ciclo de melhoria da base (aparece em `/suporte/conhecimento/perguntas/`). **Só registra em "achou 0", não em erro de infra** (pgvector/credencial ausente cai no except e não registra). Blindado (try/except, nunca quebra o agente).
  2. **Hotspot (dev):** ligada a tool `consultar_base_conhecimento` + **regra anti-invenção** no prompt ("só informe prazos/valores/condições se estiver na base; senão diga que confirma com o time; nunca invente").
  3. Tool passa o `lead` do contexto pro registro do gap.
- **Gate:** `check` + **testes** (gap registrado em "achou 0"; NÃO registrado em erro de infra). **E2E:** a pergunta que antes ele inventou ("quanto tempo pro desconto?") → agora o agente **consulta a base, não acha (dev), e responde "vou confirmar com o time"** (não inventa). Gap registrado (`PerguntaSemResposta`).
- **Nota dev:** RAG não busca de verdade no `aurora_dev` — `gerar_embedding` falha (lib `openai` com assinatura diferente, erro `proxies`) → `buscar_artigos` volta vazio. Em prod funciona (22 artigos embeddados). O comportamento anti-invenção + registro de gap está provado mesmo assim.
- **Bug do dedup corrigido (Suporte):** o usuário notou que a pergunta do desconto não aparecia na lista. Causa: `_primeiro_termo_significativo` (suporte/services.py) escolhia a 1ª palavra significativa e `registrar_pergunta_sem_resposta` dedupava por `icontains` dela — mas **"quanto" não estava nas stop-words**, então "quanto tempo…" colava em "Quanto custa o plano…" (incrementava em vez de criar). Fix: adicionadas as palavras-de-pergunta (`quanto/quantos/quanta/quantas/qual/quais/quando/onde/quem/porque/pra/pro`) ao `_STOP_WORDS_PT` em **`suporte/services.py` E `atendimento/engine.py`** (mantidos em sync). Validado: o termo virou "tempo" e a pergunta do desconto criou registro novo (`criada=True`). Afeta os dois motores (melhora ambos).
- **Status:** completed.

## 2026-06-25 — Convergência marketing (finalização): FREIO por lead

- **Contexto:** retomando a convergência do marketing (passo 1+2 já feitos). Mapeei o motor antigo: 8 ações já delegam pro `acoes.py`; faltam (a) `enviar_email` (deferido — email é projeto à parte), (b) controles por lead, (c) tradutor de regras, (d) cutover, (e) wiring on. `enviar_whatsapp`→`whatsapp_texto` (Uazapi); `webhook`→`http_request`.
- **Freio por lead (decisão: versão SIMPLES, só onde precisa):** o motor antigo tem `max_execucoes_por_lead`/`cooldown`/`periodo` + tabela `ControleExecucao`. Em vez de portar tudo, a engine nova ganha um freio leve **configurável no nó-gatilho `evento`**: `max_por_lead` (0=ilimitado) + `cooldown_horas` (0=sem espera). Aplicado em `gatilhos._despachar` (via `_freio_bloqueia`) **antes de enfileirar** — conta `ExecucaoFluxo` por (fluxo, lead). Sem migration (config vive no grafo). Idempotência + âncora de lead continuam por cima.
- **Gate:** `check` + **6 testes** (`test_automacao_freio.py`, mock de ExecucaoFluxo: sem lead/sem config não barra; cooldown barra se recente; max barra ao atingir). Campos aparecem no editor sem rebuild (catálogo runtime).
- **Status:** completed (freio). Próximo: tradutor RegraAutomacao→Fluxo.

## 2026-06-25 — Convergência marketing: TRADUTOR (RegraAutomacao → Fluxo)

- **O que:** `apps/automacao/migracao_marketing.py` (`traduzir_regra(regra) → (grafo, avisos)`) + command `migrar_regras_marketing` (dry-run por padrão; `--tenant/--regra/--salvar`). Converte os 2 formatos legacy: **visual** (`NodoFluxo`+`ConexaoNodo`) e **linear** (`CondicaoRegra`+`AcaoRegra`) → grafo `{inicio,nodes,conexoes}` da engine nova.
- **Mapeamento:** trigger→`evento` (com freio da regra: max/cooldown); condition→`if`; delay→`delay`; action→nó da ação (pelo subtipo). Saída legacy (default/true/false) → saída do nó novo pelo tipo da origem (ação default→`sucesso`). **Template flat→var:** `{{lead_nome}}`→`{{var.lead_nome}}` (dot-notation mantida). Renome de campo por subtipo (ex: `tipo_tarefa`→`tipo`). Ações sem nó (`enviar_email`/`enviar_whatsapp`/`webhook`/`hubsoft`) viram **aviso** (regra segue no motor antigo). `--salvar` cria `Fluxo` **inativo** (cutover liga depois).
- **Bug corrigido na validação:** o campo `NodoFluxo.tipo` tem valores **em PT e EN** nos dados (`acao`/`action`, `condicao`/`condition`) — versões diferentes do editor. Normalizado (`_TIPO_NORM`) antes de mapear; sem isso, ações/condições eram puladas (fluxo só com gatilho).
- **Gate:** **dry-run no dev → 10/10 regras válidas** (8 visual + 2 linear); `enviar_email` corretamente flagado (1 aviso); nós/conexões batem. **12 testes** (`test_automacao_migracao.py` lógica pura + freio).
- **Status:** completed (tradutor). Próximo: cutover (motor antigo pula regra migrada; sem disparo duplo).

## 2026-06-25 — Convergência marketing: CUTOVER (sem disparo duplo)

- **Risco:** o evento dispara nos DOIS motores (o antigo roda a `RegraAutomacao` E o `on_evento` enfileira o `Fluxo`) → ação 2×. Como os dois já filtram por ativo (`RegraAutomacao.ativa` / `Fluxo.ativo`), o cutover é só **flipar o par atomicamente**.
- **Entregue:** campo **`Fluxo.origem_regra`** (int, sem FK — não acopla a marketing) + migration **0007**. O `migrar_regras_marketing --salvar` agora seta `origem_regra` e é **idempotente** (upsert por origem_regra, não duplica). Command **`cutover_marketing`** (dry-run por padrão; `--ativar`/`--reverter`; `--tenant`/`--fluxo`): em transação, liga o Fluxo migrado e desliga a regra de origem (ou o inverso).
- **Gate (provado no dev, tenant demo):** `--salvar` criou Fluxos 38/39 (inativos, com origem_regra); cutover dry-run listou os pares; **`--ativar` no Fluxo 38** → `Fluxo.ativo False→True` + `regra.ativa True→False` (atômico, sem duplo); **`--reverter`** → voltou tudo. Reversível.
- **Status:** completed (cutover). Falta só: **wiring on em prod** + revisão (signal inbox + dar_pontos) — passo gated/deploy.

## 2026-06-25 — Convergência marketing: revisão de go-live + runbook (wiring) [GATED]

- **Revisão de segurança (verde):** `dar_pontos` tenant-safe (`filter(tenant, cpf)`); wiring `on_evento` blindado (try/except + kill-switch `AUTOMACAO_WIRING_ATIVO` + guard de re-entrância + deferido via cron `rodar_novos`); signals do inbox (`on_mensagem_recebida`/`on_mensagem_resposta`) baratos (query indexada).
- **Fato-chave (prod read-only):** **0 Fluxos no total** em prod (0 com gatilho de evento) e **8 RegraAutomacao ativas**. Logo, **ligar o wiring em prod é INERTE** — `on_evento` não acha fluxo, não faz nada — até a migração rodar lá. Risco do go-live é baixo e gradual.
- **Runbook de go-live (prod, GATED — autorização explícita do usuário por passo):**
  1. (Opcional, recomendado) tornar `AUTOMACAO_WIRING_ATIVO` **env-driven** (toggle no EasyPanel sem deploy; rollback instantâneo).
  2. `migrar_regras_marketing --tenant <slug> --salvar` em prod → cria 8 Fluxos **inativos** (`origem_regra` setado). Conferir avisos (ações sem nó: email etc.).
  3. **Ligar o wiring** (`AUTOMACAO_WIRING_ATIVO=True`). Inerte (fluxos ainda inativos).
  4. `cutover_marketing --fluxo <id> --ativar` **regra por regra** (começar por 1 de baixo risco) → liga o Fluxo, desliga a regra antiga (atômico, sem duplo). Monitorar `automacao_execucao`.
  5. Rollback de qualquer passo: `cutover_marketing --fluxo <id> --reverter` (volta pro motor antigo) ou desligar a flag.
- **Status do build:** convergência marketing **construída e testada** (freio + tradutor + cutover, dry-run 10/10). O **go-live em prod** é o passo deploy/gated, aguardando autorização. `enviar_email` fica no motor antigo (deferido).

## 2026-06-27 — Go-live do marketing: preparação (env-driven flag)

- **Decisão (usuário):** fazer o go-live — e é **seguro**: prod tem **0 execuções do motor de marketing nos últimos 30 dias** (57 históricas), 8 regras ativas mas paradas (aurora-hq/demo internos; só fatepifaespi+nuvyon reais, nuvyon mal-configurada). Nada ativo pra atropelar.
- **Estado de prod (read-only):** já está com migrations `0001`–`0007` aplicadas (inclui `0007 origem_regra`) e o código da convergência deployado (dormente). `origin/main` == HEAD local. **Não precisa deploy de código novo** — só ativar.
- **Feito:** `AUTOMACAO_WIRING_ATIVO` virou **env-driven** em `settings.py` (`os.environ.get(...)`, default False) → liga/desliga pelo EasyPanel sem deploy, rollback instantâneo. `settings_local` segue True.
- **Runbook de ativação (EasyPanel console + env):** (1) deploy pra pegar o settings env-driven; (2) `migrar_regras_marketing --salvar` (cria Fluxos inativos); (3) setar env `AUTOMACAO_WIRING_ATIVO=true` (inerte — fluxos inativos); (4) `cutover_marketing --ativar` regra a regra (começar pela real, fatepifaespi); rollback: `--reverter` ou env=false. Monitorar `automacao_execucao`.
- **Status:** flag env-driven pronto. Próximo: deploy + os passos no EasyPanel (mãos do usuário no console/env).

## 2026-06-28 — Pipeline de triagem de suporte (multi-agente) + nó `switch` + saídas dinâmicas

- **Objetivo (Hubtrix/aurora-hq):** primeira automação nativa de verdade — triagem de suporte estilo "Visor": cliente reporta → classifica intenção → roteia → agente especializado **abre ticket**. Norte: o ticket alimenta um agente Claude que corrige o bug (separado).
- **Mecanismo de saídas dinâmicas (genérico, reusável):** `BaseNode.saidas_dinamicas`/`campo_saidas` + `saidas_de(config)`; `validar_fluxo` e o catálogo (`views.py`) passam a usar `saidas_de`. Editor: `flow.ts::saidasDeNo(tipo,config)` + `BlocoNode` com `useUpdateNodeInternals` desenham as portas a partir da config. **Backward-compat:** nó estático devolve `self.saidas`.
- **Nó `switch`** (`nodes/switch.py`): config `valor` (testa, aceita `{{...}}`) + `casos` (textarea, 1/linha → ramos + `default`). Casa **normalizado** (trim+minúsc.) pra aguentar saída de LLM. 9 testes.
- **Service `criar_ticket`** (`services/tickets.py`, executor único): centraliza o `solicitante` (Ticket exige User; resolve staff do tenant) e a categoria por nome (get-or-create tenant-scoped). `numero` via `Ticket.save()`.
- **Tool `abrir_ticket`** (`services/ia_tools.py`): delega ao service; prioridade **derivada de `Ticket.PRIORIDADE_CHOICES`** (nada hardcoded). 3 testes. Habilitável por agente.
- **Decisão de arquitetura:** ação (`abrir_ticket`) virou **tool no agente** (não nó), e a classificação virou **agente + switch** (categoria é arg da tool / valor do switch — não ramo hardcoded). Tudo config-driven (reforço do usuário: "nada hardcoded").
- **Scaffold dev (aurora-hq):** Agente "Classificador de Suporte" (id 3, sem tools) + "Capturador de Bug" (id 4, tool `abrir_ticket`) + Fluxo "Triagem de Suporte" (id 40, **inativo**). Integração OpenAI id 8.
- **Validado ponta a ponta (LLM real):** classificou 4/4 (bug/duvida/financeiro/outro); fluxo `gatilho→classificador→switch(bug)→capturador` → **ticket #5 criado** (cat Bug, prio alta, solicitante resolvido, descrição rica). `check` limpo; testes por-arquivo verdes (a suite inteira erra por infra de DB de teste pré-existente, pgvector).
- **Status:** Fase 1 **completed**. Fase 2 **pending**: ramos `duvida` (Respondedor + RAG), `financeiro`, `default` (triagem humana) com especialistas. Fase 4 (norte) **pending**: agente Claude consumindo tickets de bug.
- **Upgrade do `switch` p/ modelo "Rules" do n8n (mesmo dia):** a pedido do usuário (referência da UI do n8n), o `switch` deixou de casar string-igualdade (`casos`) e passou a **regras completas** `esquerda [operador] direita → saída` (config `regras`, tipo de campo novo `regras`). Reusa `if_node._comparar` (mesmos operadores) — generalização N-via do `if`. Editor: widget `RegrasCampo` (linha por regra) + `saidas_de`/`saidasDeNo` extraem o nome da saída do dict (`saida`). Saídas dinâmicas mantidas. 9 testes reescritos; fluxo de triagem re-scaffoldado (regra `resposta igual bug`) e re-validado ponta a ponta (ticket #6). "Expression mode" do n8n (retornar índice) **deferido**.

### Pendências / próximos passos
- **~~Opções dinâmicas ADIADAS~~ → FEITO (22/06) pras fontes locais** (segmentos/pipelines/estágios/responsáveis). Falta só ligar fontes **externas** (HubSoft: serviços/modelos/planos) como `fonte` que chama a API do tenant + cache. Matrix segue sem API de listar templates (manual).
- **Decisão (22/06): opções dinâmicas + preview ADIADAS.** Quería-se dropdown de contas/templates Matrix + preview do HSM ao selecionar. Mas o **Matrix não expõe API de listar templates** (confirmado), então a única fonte do preview seria um **registro local** (cópia do corpo por tenant) — com manutenção manual e risco de drift vs o template aprovado. Decidido **manter `cod_conta`/`hsm` manuais** por ora. O **mecanismo genérico de opções dinâmicas** (`select_dinamico` carregado de endpoint por-tenant + painel de preview) fica pra quando entrar uma integração com **API de listagem real** (ex: HubSoft, ou "listar pipelines" do CRM) — aí o investimento se paga em vários provedores.
- **Pending:** decidir volume/dia por tenant + latência → runtime síncrono-em-cron (modelo marketing) vs. fila. Bloqueia a fase de runtime.
- **Pending (convergência):** extrair executores de domínio (`criar_oportunidade`, `webhook`...) pra service único tenant-aware; aposentar motores na ordem marketing → atendimento → comercial.
- **Dívida (anotada na doc):** DNS-rebinding (pinning de IP), allowlist de destino por tenant, nó `code` com sandbox (nunca `eval`).

## 2026-07-01 — Migração da automação do funil comercial (Fase 1: node-ificar as ações)

- **Objetivo:** migrar a automação do funil (`RegraPipelineEstagio` + `crm/services/automacao_pipeline.py`, que roda **2 clientes vivos** — Nuvyon 16 regras/1787 disparos, TR Carrion 8/2726) pra engine nova, **sem downtime e sem tocar no motor antigo** até a Fase 4. Plano aprovado (parallel-run + shadow + cutover reversível por tenant).
- **Restrição-chave (usuário):** criar **tudo no motor novo primeiro, autossuficiente** — a lógica de cada `_acao_*` é **portada** pra `apps/automacao/services/acoes.py` (o motor novo **não importa** do antigo). Só depois do shadow provar paridade mexemos no antigo (Fase 3 desativa regra=dado, Fase 4 deleta código).
- **Decisão de design (usuário, 3 lembretes):** (1) todo node **configurável ao abrir** (`campos_config`); (2) nodes de **integração** precisam de **seletor de credencial** (qual `IntegracaoAPI`) — padrão do uazapi: campo `{'fonte': 'integracoes_uazapi'}` + `uazapi_do_tenant(tenant, integ_id)` (vazio = 1ª ativa). Espelhar nos nodes HubSoft/WhatsApp da migração.
- **Feito (2/6 ações):**
  - `mover_para_perdido_sem_viabilidade` (molde): porta `_acao_*` → `acoes.py` (idempotente, motivo template {cep}/{cidade}/{uf}, HistoricoPipelineEstagio); node `Comercial › Oportunidades`; 5 testes.
  - `adicionar_item_oportunidade`: porta `_acao_*` → `acoes.py` (lead.id_plano_rp → ProdutoServico.id_externo → ItemOportunidade; idempotente; devolve `(item, criado, motivo)`); node com `quantidade` configurável; 6 testes.
- **Ação local (ORM), sem credencial** nas 2 primeiras. As de integração precisam do seletor.
- **Descoberta no mapeamento:** `sincronizar_prospecto_hubsoft` **já era node** (`hubsoft_sincronizar_prospecto`/H1, mesmo helper — paridade por construção). Então das "4 restantes" sobram **3 nodes de verdade**: `gerar_contrato_hubsoft`, `assinar_contrato_hubsoft`, `enviar_venda_whatsapp`.
- **Seletor de credencial em TODO node HubSoft (opção B do usuário):** os H1-H9 usavam `hubsoft_do_tenant(tenant)` sem picker. Retrofit: `opcoes.py` ganhou a fonte `integracoes_hubsoft`; `services/hubsoft.py` ganhou `integ_id` opcional em todas as fns (incl. `sincronizar_prospecto`, via `integracao=` que o helper de rascunho **já aceitava** — caminho vivo intocado); `hubsoft_base.HubsoftNode` injeta o campo "Conta (HubSoft)" automático (`campos_config` = `_campos_extra` + conta) e resolve o `integ_id` no `executar`; os 4 nodes de `executar` próprio (consultar/faturas/planos/sincronizar) ganharam o campo + thread. Retrocompatível (integ_id vazio = 1ª ativa). 24 nodes, `check` limpo, **36+4 testes verdes**.
- **3 nodes de integração (feitos):**
  - `enviar_venda_whatsapp` (Comercial › Vendas): porta p/ `services/whatsapp.enviar_venda`; idempotente (flag no lead); **picker uazapi**. O service de domínio `leads.services_whatsapp_venda.enviar_venda_whatsapp` ganhou `integ_id` opcional (retrocompatível — motor antigo chama sem).
  - `gerar_contrato_hubsoft` (Comercial › Contrato): 🔴 outbound real; porta a orquestração criar→anexar→aceitar p/ `services/contrato_hubsoft.gerar_contrato`, reusando `contrato_service`/`contrato_tracking`/`HubsoftService` (helpers de domínio, não o motor antigo). Config id_contrato_modelo/id_empresa (fallback nos extras) + **picker HubSoft**. `origem='automacao_engine'` no tracking.
  - `assinar_contrato_hubsoft` (Comercial › Contrato): 🔴 outbound real; porta consultar→aceitar (+ ativar_servico opcional) p/ `services/contrato_hubsoft.assinar_contrato`. **picker HubSoft**.
- **Output:** `manage.py check` limpo; **45 testes verdes** (11 contrato + 7 venda + 16 hubsoft + 5 mover + 6 item). Catálogo do README atualizado. Motor antigo **intocado**.
- **Status:** Fase 1 **completed**. Todas as ações do funil node-ificadas na engine nova (autossuficiente). Próximo: **Fase 2** — tradutor `RegraPipelineEstagio → Fluxo` + SHADOW (log-only) + comparador de paridade.

## 2026-07-01 — Migração do funil, Fase 2 (mapa de eventos + Passo 1: tradutor)

- **Mapa de eventos (decisão do usuário): Opção A, espelho fiel.** O motor antigo NÃO é event-driven: os 6 signals do CRM são "pulsos de recalcule" — qualquer um chama `processar_oportunidade`, que reavalia TODAS as regras (as condições da regra decidem, não o signal). O catálogo semântico novo só cobria 2 dos 6 momentos → Opção B (semântico) deixaria 4 momentos sem gatilho e furaria a paridade. Escolhido: **1 evento `crm_reavaliar_oportunidade`** disparado dos mesmos 6 pontos; cada regra vira um Fluxo com filtros idênticos. Semântico fica como faxina pós-cutover (Fase 4+).
- **Passo 1 — tradutor (feito):**
  - Evento `crm_reavaliar_oportunidade` no catálogo (`eventos.py`).
  - `tradutor_pipeline.regra_para_grafo(regra)`: `[evento] → [condicao_comercial × N (AND)] → alvo`. Alvo = `mover_estagio` (regra com estágio) OU `acao_comercial × N` (regra de ação, roda todas via sucesso+erro). Puro, sem DB. **Paridade por construção**: `condicao_comercial`/`acao_comercial` reusam os MESMOS registries do motor antigo (`automacao_condicoes`/`_EXECUTORES_ACAO`).
  - `regra_traduzivel`: pula regra sem condição (nunca dispara no antigo) e regra de ação sem ações.
  - Command `migrar_regras_pipeline` (idempotente por `origem_regra`, `--dry-run`, `--tenant`, cria Fluxos **inativos/shadow**; NÃO toca no motor antigo, só lê).
  - 7 testes do tradutor (grafo + `validar_fluxo` == []).
- **Validação com dados reais (prod read-only, sem escrever):** rodei o tradutor sobre as **24 regras ativas reais** (16 Nuvyon + 8 TR Carrion). Resultado: **24/24 traduzidas, 0 puladas, 0 grafos inválidos**. Regras de estágio viram `mover_estagio`; regras de ação viram `acao_comercial` (criar_venda, atribuir_agente, sincronizar_prospecto, gerar/assinar contrato, enviar_venda_whatsapp, criar_tarefa, mover_para_perdido).
- **Semânticas cross-regra NÃO reproduzidas** (cada regra = 1 fluxo independente): "primeiro-match-vence" entre regras de estágio + ordem por prioridade. O comparador do shadow (Passo 3) vai medir essas divergências antes do cutover.
- **Status:** Fase 2 **in progress**. Passo 1 (tradutor) **completed**, validado nas 24 regras reais. Próximo: Passo 2 (shadow log-only — hook via observador do `LogSistema motor_disparado`) + Passo 3 (comparador de paridade).

## 2026-07-01 — Migração do funil, Fase 2, Passo 2 (shadow / espião log-only)

- **Hook (decisão): observador do `LogSistema(acao='motor_disparado')`.** O motor antigo grava esse log no INÍCIO de cada pulso (antes de avaliar as regras). Um `post_save` receiver NOVO em `signals_dominio.py` escuta esse log → carrega a op → roda o shadow. Vantagem: avalia no MESMO instante e estado que o motor antigo, sem tocar em NENHUM código do antigo (nem `signals.py` nem `automacao_pipeline`). Fiel + zero acoplamento.
- **`shadow.py`:** `avaliar_fluxo_shadow(grafo, avaliar_cond)` anda o grafo do Fluxo migrado sem efeito colateral — avalia `condicao_comercial` de verdade (read-only) e REGISTRA nós de ação como "faria" sem executar. `avaliar_pulso_shadow(op)` roda todos os fluxos migrados (com `origem_regra`) do tenant, monta o contexto das condições UMA vez (mesmo registry do antigo, sem importar dele), e grava `LogSistema(acao='shadow_fluxo')` só quando algo dispararia (baixo volume). 100% blindado.
- **Flag `AUTOMACAO_SHADOW_ATIVO`** (env-driven, default False, separado do wiring de produção): liga o espião sem ligar a execução real, rollback instantâneo. `settings_local` = True (dev).
- **Latência:** o shadow roda síncrono no pulso (fiel), mas só pra tenants com fluxos migrados, e o contexto das condições é montado 1x por pulso. Off por padrão; monitorar ao ligar em prod.
- **Testes:** 6 do runner (dispara/não dispara, AND, ações em ordem, grafo vazio, guardas). check limpo.
- **Status:** Passo 2 **completed** (dormente, flag off em prod). Falta Passo 3: comparador de paridade (cruza `shadow_fluxo` vs os fires reais do antigo `mover_regra`/`acoes_regra`).

## 2026-07-01 — Migração do funil, Fase 2, Passo 3 (comparador de paridade)

- **`comparador_pipeline.py`:** núcleo puro `comparar_op(eventos)` — por op, cada `motor_disparado` abre um PULSO; acumula fires reais do antigo (`mover_regra`/`acoes_regra` → `regra_id`) e o que o shadow faria (`shadow_fluxo` → `origem_regra`); compara os conjuntos (`origem_regra` do fluxo == `regra_id` da regra). `resumir()` agrega paridade %, divergentes, regras só-antigo (novo perderia) e só-novo (novo faria a mais).
- **Command `comparar_shadow_pipeline`** (read-only): puxa o LogSistema da janela, agrupa por tenant/op, roda o comparador e imprime o relatório por tenant (`--tenant`, `--dias`, `--exemplos`). Gate do cutover: **0 divergência por N dias com atividade**.
- **6 testes do comparador** (match, novo-a-mais, novo-perderia, eventos órfãos ignorados, 2 pulsos, resumir).
- **Fase 2 build COMPLETA (dormente):** tradutor + shadow + comparador. 19 testes (7+6+6), check limpo. Tudo com flag off em prod.
- **Runbook pra ligar em prod (mãos do usuário, com confirmação):** (1) deploy do código; (2) `migrar_regras_pipeline --tenant <slug>` (cria os Fluxos inativos/shadow); (3) setar env `AUTOMACAO_SHADOW_ATIVO=true` (só o espião, wiring de produção segue off); (4) deixar rodar N dias; (5) `comparar_shadow_pipeline --tenant <slug> --dias N` até 0 divergência; (6) aí sim Fase 3 (cutover). Rollback do shadow: env=false.
- **Status:** Fase 2 **completed** (código). Próximo: ligar o shadow em prod + medir (runbook) → Fase 3 (cutover por tenant).

## 2026-07-02 — Migração do funil: PIVOT pra eventos finos (v2)

- **Decisão do usuário (revisão de rumo):** o espelho fiel (v1, gatilho genérico `crm_reavaliar_oportunidade` em todos) estava **fotocopiando um mecanismo ruim** do motor antigo — 393 pulsos em 6h, a maioria ruído ("gatilhos que não deveriam contar"), e todos os fluxos disparando juntos a cada pulso. A prova read-only confirmou o over-fire (regra 8 dispararia em 39/40 ops, porque condições de estágio são cumulativas). Escolhido: **eventos finos (Opção B)** — cada fluxo dispara no SEU evento de negócio real; os pulsos-lixo somem. Isso também mata o over-fire naturalmente (cada evento acontece uma vez).
- **Reaproveitamento (orientação do usuário "tudo deve ser reaproveitado"):** NÃO reescrever. O tradutor, os nodes, o shadow runner e o comparador são **reusados**; a mudança é mínima.
- **Passo 1 feito (catálogo + inferência):**
  - 9 eventos finos novos no catálogo (`eventos.py`, grupo Funil): `documento_status_mudou`, `tag_adicionada`, `historico_contato`, `lead_campo_mudou`, `lead_status_mudou`, `servico_hubsoft_mudou`, `viabilidade_consultada`, `conversa_modo_mudou`, `conversa_atribuida` + `oportunidade_criada` (já emitido, faltava no catálogo).
  - **Inferência config-driven** no tradutor (`evento_gatilho_da_regra`): o evento-gatilho sai do TIPO da condição primária da regra (`_EVENTO_POR_TIPO` + prioridade), nada hardcoded por regra. Casos especiais: `imagem_status todas_iguais`→`docs_validados`; `lead_campo nao_existe`→`oportunidade_criada`. As condições continuam como GUARDA no fluxo (o evento define o quando, a condição confirma).
  - `regra_para_grafo(regra, evento=None)`: mudança mínima — só o evento do nó-gatilho; resto idêntico (reuso).
- **Validado nas 24 regras reais (read-only):** 24/24 mapeiam pra evento real, **0 caíram no pulso genérico, 0 grafos inválidos**. Distribuição: conversa_modo_mudou 6, lead_campo_mudou 4, tag_adicionada 4, historico_contato 2, documento_status_mudou 2, viabilidade_consultada 2, +1 cada (lead_status/servico/docs_validados/conversa_atribuida/oportunidade_criada).
- **Status:** redesign Passo 1 **completed**.

- **Passo 2 feito (emissões dos eventos finos):** receivers novos em `signals_dominio.py` (aditivo, **não toca motor antigo**), com **detecção de mudança** (pre_save guarda o valor antigo, post_save compara → dispara só na transição, sem ruído):
  - `LeadProspecto` (pre+post): `lead_status_mudou` (status_api), `lead_campo_mudou` (8 campos-chave que ganham valor), `viabilidade_consultada` (`dados_custom['viabilidade']['status']`).
  - `HistoricoContato` (created): `historico_contato` (var.status).
  - `ImagemLeadProspecto` (pre+post): `documento_status_mudou` (status_validacao muda).
  - `OportunidadeVenda.tags` (m2m post_add): `tag_adicionada` (var.tag).
  - `ServicoClienteHubsoft` (pre+post): `servico_hubsoft_mudou` (status muda).
  - `Conversa` (pre+post): `conversa_modo_mudou` (**campo `modo_atendimento`**, não `modo`), `conversa_atribuida` (agente ganha valor).
  - **Contexto resolve a op a partir do lead** (`_op_do_lead`) — os fluxos agem na oportunidade.
  - **Gated por `_emissao_ativa()` (wiring OU shadow)** → zero overhead (nem o pre_save roda) quando ambos off. Emissão → `on_evento` (gated por wiring, off em prod) → **no-op em prod hoje**. Blindado (nunca quebra o save).
  - Campos validados por introspecção (`modo_atendimento`, `agente_id`, `cliente.lead`, `tags`). 10 testes das emissões (lógica via receiver direto + mock). check limpo.
- **Status:** redesign Passo 2 **completed**.

- **Passo 4 feito (shadow + comparador v2, reaproveitando o runner):**
  - `shadow.avaliar_evento_shadow(evento, contexto, tenant)` substitui o `avaliar_pulso_shadow` (v1): avalia SÓ os fluxos migrados cujo `gatilho_evento == evento` (targeted, sem over-fire), reusa `avaliar_fluxo_shadow`/`_dados_condicao`/`_fazer_avaliador`. Resolve a op do contexto (direto ou pela do lead). Loga `shadow_fluxo` com o `evento`.
  - **Hook migrou** do observer do `LogSistema(motor_disparado)` (removido do `signals_dominio`) pro `hub.disparar_evento`, que chama o shadow em paralelo ao caminho de produção (gated por `AUTOMACAO_SHADOW_ATIVO`, independente do wiring).
  - **Comparador v2:** `comparar_op_agregado` — como os eventos finos disparam em momentos diferentes do `motor_disparado`, a comparação vira **por-op agregada** (conjunto de regras que o antigo disparou vs o que o shadow faria, na janela), não mais por-pulso. Command `comparar_shadow_pipeline` usa a agregação.
  - 34 testes da v2 (shadow+comparador+tradutor+eventos_finos) + **266 na regressão de automação, 0 falha** (motor antigo intocado).
- **Status:** redesign **completo (código)**.

- **Deploy + re-migrar (operacional, 02-03/07):** a v2 já foi **deployada por outra sessão** (commit `8d3dacd` inclui os 3 commits v2 — hazard multi-sessão: a HEAD moveu, meus commits foram pushados junto). Verificado read-only: prod tem `avaliar_evento_shadow`, os eventos finos e `evento_gatilho_da_regra`. Re-rodei `migrar_regras_pipeline` (nuvyon+tr-carrion): **24 fluxos ATUALIZADOS** (idempotente, 0 criados) — agora com os **gatilhos finos**. Distribuição confirmada em prod: conversa_modo_mudou 6, tag_adicionada 4, lead_campo_mudou 3, documento_status_mudou 2, historico_contato 2, viabilidade_consultada 2, +1 cada (conversa_atribuida, oportunidade_criada, docs_validados, servico_hubsoft_mudou, lead_status_mudou) = 24.
- **Estado em prod:** `AUTOMACAO_SHADOW_ATIVO=true` (medindo por evento), `AUTOMACAO_WIRING_ATIVO=false` (execução real off), 24 fluxos **inativos**. O shadow v2 acumula `shadow_fluxo` conforme o funil tem tráfego real.
- **Status:** v2 **live e dormente em prod, medindo**. Próximo: rodar `comparar_shadow_pipeline` daqui a alguns dias (0 divergência = pronto pro cutover, Fase 3).

## 2026-07-05 — Hardening, Etapa E5 (orçamento global anti-loop)

- **Risco coberto:** o `_freio_bloqueia` (cooldown/max_por_lead) é opcional por fluxo, e o guard de profundidade em `on_evento` é thread-local (só protege dentro do mesmo request). Nenhum dos dois barra o caso fluxo A dispara ação, gera evento, reenfileira o próprio fluxo A, formando um loop que atravessa ciclos de cron (a execução é deferida via `ExecucaoFluxo(status='pendente')`, rodada depois por `rodar_novos`).
- **Feito:** `gatilhos._orcamento_excedido(fluxo, lead)`, teto GLOBAL default on, chamado em `_despachar` logo depois do `_freio_bloqueia`. Janela de 1 hora sobre `ExecucaoFluxo` (usa o índice `(fluxo, lead, criado_em)` já existente). Dois limites independentes: `AUTOMACAO_ORCAMENTO_LEAD_HORA` (default 20, por lead) e `AUTOMACAO_ORCAMENTO_FLUXO_HORA` (default 500, fluxo inteiro); qualquer um `<= 0` desliga o respectivo limite. Ao barrar, registra `LogSistema(categoria='sistema', acao='automacao_freio_global')` com motivo/contagem/limite/lead_id, blindado em try/except (o guard nunca quebra o dispatch).
- **Testes:** `tests/test_automacao_orcamento.py` (5 casos): barra por lead no teto, libera abaixo do teto, barra por fluxo mesmo sem lead, ignora execuções fora da janela de 1h, e desligado (0/0) libera sempre mesmo com volume alto.
- **Gates:** `manage.py check` limpo (só o warning pré-existente de STATICFILES_DIRS); `pytest tests/test_automacao_orcamento.py` 5 passed; `test_automacao_gatilhos.py` não existe no repo (fallback `-k gatilho` rodou 1 teste não relacionado em `test_automacao_tradutor_pipeline.py`, verde).
- **Status:** Etapa E5 **completed**.

## 2026-07-05 — Graduação da engine: hardening pré-cutover COMPLETO (E0-E6)

- **Origem:** auditoria de 04/07 (Fable) achou 4 bloqueadores de cutover (C1 fila sem executor, C2 dupla execução, C3 loop entre ciclos de cron, C4 editor sem permissão) + A4 (sem retry transitório). Plano aprovado pelo usuário com execução delegada a subagentes (Opus nas peças críticas, Sonnet nas mecânicas, Haiku no trivial), Fable revisando/commitando.
- **E0:** tarefa Workspace **#171** criada (projeto 4, aurora-hq prod).
- **E1 (Sonnet, `1ec9976`):** funcionalidades `automacao.ver`/`automacao.gerenciar` no seed + gates inline (`user_tem_funcionalidade`) em todas as views do editor (gerenciar nas writes incl. `testar_fluxo_api`; ver nas leituras); auditoria `registrar_acao('config')` em criar/editar/excluir fluxo/agente (M7); `webhook_receber` com try/except (FluxoInvalido→400, exceção→500 limpo) (M4). 5 testes.
- **E2 (Fable, `927a3ab`):** migration **0010** aditiva: `ExecucaoFluxo.claimed_em` + `tentativas` + índices `(status, claimed_em)` e `(fluxo, lead, criado_em)`.
- **E3+E4 (Opus, `5f32f12`):** `_claim` (CAS pendente/aguardando→rodando, rowcount==1 vence — rodadas sobrepostas do cron nunca processam a mesma execução) + watchdog `destravar_execucoes_presas` (`AUTOMACAO_WATCHDOG_MINUTOS`=10, env) + **retry transitório**: erro NÃO tratado reenfileira com backoff 5/15min até 2x retomando DO NÓ QUE FALHOU (`no_pausado` reaproveitado; `rodar_novos` usa `no_pausado or estado.inicio`); `retry_seguro=False` nos envios sem dedupe (whatsapp texto/mídia/pergunta, matrix_hsm). 9 testes.
- **E5 (Sonnet, `b91df33`):** orçamento global anti-loop (entrada anterior).
- **E6 (Haiku, `cd0763d`):** data migration `cron/0003` seeda CronJob `automacao_retomar` (1min, timeout 300s < watchdog 600s) **ativo=False** — liga só no cutover.
- **Gates finais:** `check` limpo; **285 testes de automação verdes** (266 no início do dia, +19 do hardening).
- **Runbook do cutover ATUALIZADO — passo 0 agora é:** (0) rodar `seed_funcionalidades` + ativar o CronJob `automacao_retomar`; (1) paridade 0 divergência no `comparar_shadow_pipeline`; (2) ativar fluxos + desativar regras antigas por tenant; (3) `AUTOMACAO_WIRING_ATIVO=true`.
- **Backlog registrado (tarefa #171):** webhook async + cache Redis (A1), cofre de segredos/credencial IntegracaoAPI no http_request (A2), purga/TTL de ExecucaoFluxo LGPD (A3), DNS pinning SSRF (A5), confirmação em tools executáveis (M2), versionamento de fluxo (M3), fila real (M5), claim no `retomar_por_resposta`.
- **Status:** hardening **completed** (local, 6 commits, NÃO deployado — aguarda OK do usuário; sobe tudo dormente).

## 2026-07-10 — Gatilho agendado (varredura): nó `agenda` + registry de varreduras + dispatcher

- **O que é:** segundo tipo de gatilho, ao lado do `evento`. Em vez de reagir a um evento do sistema, o nó `agenda` roda em ciclo (intervalo configurável) e cada rodada executa uma **varredura** (busca no banco/API externa) — cada item encontrado vira UMA `ExecucaoFluxo` enfileirada, com os mesmos freios (`max_por_lead`/`cooldown_horas`) do gatilho por evento.
- **Nó `agenda`** (`apps/automacao/nodes/agenda_trigger.py`): config `intervalo_minutos` + `varredura` (dropdown, fonte `varreduras`) + `varredura_config` (keyvalue livre) + `max_por_rodada` (default 25) + freios. `validar_config` exige varredura conhecida (registry) e intervalo > 0.
- **Registry de varreduras** (`apps/automacao/varreduras.py`): `fn(tenant, config) -> list[dict]`, blindado (nunca levanta). Duas implementadas: `oportunidades_perdidas` (win/loss, filtros `janela_dias_min`/`motivo_categoria`/`motivo_ref_id`/`pipeline`/`sem_marcador`, cap 1000) e `atendimentos_matrix_finalizados` (pagina `listar_atendimentos_analitico`, teto 20 páginas, casa por `dados_custom['id_atendimento_matrix']`, pula quem já tem o `marcador`). **Achado de nomenclatura:** a listagem analítica da Matrix (`/rest/v1/relAtAnalitico`) NÃO tem `id_agente` (isso só existe no detalhe de `consultar_atendimento`) — segui os nomes reais usados por `extrair_historico_matrix`: `status` e `agente`.
- **`opcoes.py`:** fontes novas `varreduras` (delega pro registry) e `motivos_perda` (lista `MotivoPerda` ativos do tenant).
- **`Fluxo` (migration `automacao/0011`):** `agenda_intervalo_minutos` + `agenda_ultima_rodada`, sincronizados do grafo no `save()` (mesmo padrão do `gatilho_evento`, `update_fields` unificado pros dois índices).
- **Dispatcher (`gatilhos.py`):** `despachar_agendas()` (gated por `AUTOMACAO_WIRING_ATIVO`) + `_rodar_agenda_do_fluxo` com **CAS claim-then-work** em `agenda_ultima_rodada` (só quem vence a corrida varre) + guard "sem freio nenhum → pula a rodada com warning" (mesma filosofia do E5: varredura sem freio pode inundar a fila).
- **Cron novo:** command `automacao_despachar_agendas` + seed `cron/0004_seed_automacao_despachar_agendas` (`*/5 * * * *`, **ativo=False** — liga só com fluxo de varredura pronto).
- **Testes:** 17 novos (`test_automacao_agenda_trigger.py`, `test_automacao_varreduras.py`, `test_automacao_despachar_agendas.py`) cobrindo nó/validação, a varredura `oportunidades_perdidas` (janela, filtros, estrutura do retorno) e o dispatcher (wiring off, `max_por_rodada`, corrida CAS, guard sem freio, freio `max_por_lead`, sync do `save()`).
- **Gates:** `makemigrations`/`migrate` limpos (automacao 0011 + cron 0004, dev), `check` limpo (só o warning pré-existente de STATICFILES_DIRS), 17/17 nos testes novos, **302 passed** em `-k automacao` (regressão completa, 0 falha).
- **Status:** **completed (local)**. NÃO commitado, NÃO deployado — dormente (cron nasce `ativo=False`, sem fluxo real usando o nó `agenda` ainda).

## 2026-07-11 — Nó `matrix_atendimento` (transcript) + nó `extrair_json` + tool `listar_motivos_perda`

- **`matrix_atendimento`** (`nodes/matrix_atendimento.py`, grupo Integrações › Matrix): consulta um atendimento Matrix por código (`services/matrix.consultar_atendimento`, novo) e monta um transcript legível (`services/matrix.formatar_transcript`, novo) no formato `[cliente|agente|bot] <hora>: <texto>`. Mesma regra de classificação do command `extrair_historico_matrix` (`boleano_entrante='1'` → cliente; `autor` com 'BOT' → bot; resto → agente). Campos: `codigo` (obrigatório, template), `anonimizar` (booleano, default true via `config.get('anonimizar', True)`), `max_mensagens` (corta pras últimas N). Output: `transcript`, `total_mensagens`, `status`, `agente` — os dois últimos batem com a nomenclatura já usada pela varredura `atendimentos_matrix_finalizados` (entrada 2026-07-10: a listagem analítica não tem `id_agente`, só o detalhe do `consultar_atendimento` tem `status`/`agente`).
- **Refactor pré-requisito:** o anonimizador de PII (nome/CPF/CNPJ/telefone/email) que vivia dentro do command `extrair_historico_matrix.py` (`_build_anonimizador`) foi extraído pra `apps/integracoes/services/anonimizador.py` (`construir_anonimizador(contato)` + atalho `anonimizar_texto(texto, contato=None)`), reusado tanto pelo command quanto por `formatar_transcript` (que usa a variante sem contato — só as regras genéricas de regex, já que o transcript não tem o dict `contato` disponível). Comportamento do command idêntico (import trocado, lógica igual).
- **`extrair_json`** (`nodes/extrair_json.py`, grupo Transformação › JSON, ao lado do `set_fields`): parseia JSON embutido em texto livre (ex: resposta de um agente IA) — tolerante a cerca de código markdown (```json ... ```) e a texto ao redor do objeto (recorta entre a primeira `{` e a última `}`). Se `origem` já resolve pra `dict`/`list` (full-match do template), usa direto sem reparsear. Output = o dict parseado direto (pra `{{nodes.<id>.<campo>}}` funcionar); JSON não-dict (ex: lista) vira `{'valor': [...]}`. `salvar_em` opcional promove pra `var.<nome>`.
- **`listar_motivos_perda`** (tool, `services/ia_tools.py`, tipo conhecimento, categoria crm): lista os nomes dos `MotivoPerda` ativos do tenant (`all_tenants.filter(tenant=..., ativo=True).order_by('ordem', 'nome')`), tenant-safe. Sem motivos cadastrados → mensagem padrão fixa.
- **Testes:** `test_automacao_matrix_atendimento.py` (10 casos: registrado, código vazio, `ValueError` do service, caminho feliz com template resolvido + transcript/total/status/agente, `anonimizar` default true e false explícito, + 3 testes puros de `formatar_transcript` incl. anonimização de telefone e corte por `max_mensagens`), `test_automacao_extrair_json.py` (11 casos), `test_automacao_tool_motivos_perda.py` (4 casos, `@pytest.mark.django_db`, isolamento multi-tenant).
- **Gates:** `manage.py check` limpo (só o warning pré-existente de STATICFILES_DIRS); os 3 arquivos de teste novos 24/24 verdes; `-k automacao` **355 passed**; `-k "matrix or historico"` 27 passed + **1 falha pré-existente e não relacionada** (`test_signals.py::TestVerificarConversaoHistorico::test_conversao_move_oportunidade_para_ganho`, erro de campo `valor_estimado` inexistente no signal de conversão do CRM — não tocado por este trabalho). Catálogo `TOOLS.md` regenerado (24 tools).
- **Status:** **completed (local)**. NÃO commitado, NÃO deployado.

## 2026-07-11 — Seed dos fluxos de recuperação (#180) e análise de atendimentos Matrix (#181)

- **Ação:** novo command `apps/automacao/management/commands/seed_fluxos_recuperacao_analise.py` (`--tenant` obrigatório, idempotente por nome, tudo nasce `ativo=False` e um re-run nunca liga/desliga o que já existe). Cria o `Agente` "Analista de Atendimentos" (`tools=['listar_motivos_perda']`, `integracao_ia=None` → usa a default do tenant) + 4 `Fluxo`: **F1** `[#181] Analise de atendimentos Matrix` (agenda a cada 60min → `matrix_atendimento` → `ia_agente` → `extrair_json` → `criar_nota` → `marcar_dados_custom` → `if` → `definir_motivo_perda`); **F2** `[#180] Recuperacao sem retorno, envio` e **F3** `[#180] Recuperacao inviabilidade, envio` (varredura diária de `oportunidades_perdidas` → HSM via `matrix_hsm`, com conta/template propositalmente vazios até alguém preencher com a Gabi); **F4** `[#180] Recuperacao, lead respondeu, reabrir` (evento `historico_contato` → `condicao_comercial` → `reabrir_oportunidade`).
- **Decisão (operador do `if_node` do F1):** `esquerda='{{nodes.json.perdido}}'`, `operador='igual'`, `direita='True'` (maiúscula). O resolvedor de template (`Contexto._interpolar`) devolve o valor BRUTO quando o texto é um único token full-match, então `perdido` chega como `bool` Python; `_comparar` faz `str(a)`, e `str(True) == 'True'` (não `'true'`). Confirmado nos dois sentidos pelo E2E (`perdido=true` define motivo, `perdido=false` não).
- **Melhoria em `varreduras._oportunidades_perdidas`:** filtro opcional `motivo_ref_nome` (nome do `MotivoPerda`, case insensitive) — o id do motivo varia por tenant/ambiente, o nome é portável entre eles. Usado por F2.
- **Achado importante, fora do escopo deste seed (não mexido):** a fila deferida (`gatilhos._enfileirar` grava só `variaveis` + `lead` FK; `execucao._rehidratar` monta o `Contexto` da retomada sem a entidade `oportunidade`, só `lead`) não restaura `contexto.oportunidade` quando o fluxo roda via `rodar_novos` (cron). Todo nó que exige `contexto.oportunidade` diretamente (`criar_nota`, `marcar_dados_custom`, `definir_motivo_perda`, `reabrir_oportunidade`, `condicao_comercial`, e também `mover_estagio` dos fluxos migrados do funil pelo tradutor) vai falhar em produção quando disparado por agenda/evento reais, não só nestes 4 fluxos novos. Os testes E2E aqui contornam isso chamando `runtime.executar_fluxo` direto com um `Contexto(oportunidade=...)` já hidratado (como pedido), mas a lacuna real na fila fica pendente pra antes de qualquer ativação via `AUTOMACAO_WIRING_ATIVO`/cron de agenda.
- **Testes:** `tests/test_automacao_seed_recuperacao.py` (16 casos: idempotência de 2 rodadas, validade estrutural dos 4 grafos via `runtime.validar_fluxo`, preservação de `ativo=True` num re-run tanto do fluxo quanto do agente, tenant inexistente falha, E2E completo do F1 nos dois ramos do `if` e E2E do F4 com/sem o marcador `recuperacao_enviada`); `tests/test_automacao_varreduras.py` +1 caso (`motivo_ref_nome`).
- **Gates:** `manage.py check` limpo (só o warning pré-existente de STATICFILES_DIRS); suíte nova 16/16; `-k automacao` **365 passed**; seed rodado em dev (`nuvyon`, 2x) confirmando idempotência (1º run cria 1 agente + 4 fluxos, 2º run só atualiza, todos `ativo=False`).
- **Status:** **completed (local)**. NÃO commitado, NÃO deployado, NADA tocado em prod. Pendente antes de ativar: preencher conta/template HSM real do F2/F3 com a Gabi; decidir o que fazer com a lacuna de `contexto.oportunidade` na fila deferida (achado acima).

## 2026-07-11 — Tarefas #180/#181 ENTREGUES em prod (inativas) + fix da rehidratação

- **Fix crítico da fila (o achado acima, RESOLVIDO no mesmo dia, commit `ee52de6`):** `_enfileirar` agora persiste as entidades por id (`estado = Contexto.serializar() + inicio`) e `_rehidratar` restaura `lead` (FK com fallback), `oportunidade` e `conversa` por id, tenant-safe e blindado. Teste do caminho completo: `enfileirar → rodar_novos → criar_nota` funciona. Beneficia TODOS os fluxos (incl. os migrados do funil, que teriam quebrado no cutover).
- **Deploy (11/07):** commits `4d6934f`, `f2e9095`, `ad5a108`, `ee52de6`, `b8ea003` pushados + rebuild. Migrations `automacao/0011` + `cron/0004` aplicadas em prod. `check` limpo, **369 testes** de automação verdes.
- **Seed rodado em PROD (nuvyon):** agente "Analista de Atendimentos" (id 1) + fluxos **25** ([#181] Análise de atendimentos Matrix), **26** ([#180] Recuperação sem retorno, envio), **27** ([#180] Recuperação inviabilidade, envio), **28** ([#180] Recuperação, lead respondeu, reabrir) — **TODOS `ativo=False`**. CronJob `automacao_despachar_agendas` (id 21) **inativo**.
- **Validação com API real (read-only):** analítico do Matrix da Nuvyon confirmou os campos que a varredura usa: `status` ('Finalizado'), `agente`, `id_atendimento` presentes no payload real.
- **Tarefas #180/#181:** atualizadas pra `em_andamento` com checklist de ativação nos critérios (HSM com a Gabi; OpenAI do tenant pro F1; ativar agente+fluxos+crons+wiring; piloto = critério final).
- **Status:** engenharia **completed e deployada, tudo dormente**. Ativação = decisão do usuário com a Gabi (checklist nas tarefas).

## 2026-07-12 — Catálogo de propriedades da oportunidade + fixes do piloto (fluxo 25 em prod)

- **Motivo:** o fluxo 25 ([#181] Análise de atendimentos Matrix) rodou em prod (dormente, mas testado manualmente) e expôs 3 problemas do desenho anterior. (1) O agente IA classificou uma perda com um `motivo_nome` fora do catálogo do tenant e o nó `definir_motivo_perda` levantava `ValueError`, erro **determinístico** que o runtime tratava como falha transitória e reexecutava à toa (retry inútil). (2) O motivo estruturado (`motivo_perda_ref`) era aplicado mesmo em oportunidade que **não** estava em estágio `is_final_perdido` (poluição de dado). (3) A nota gerada imprimia `"Perda sugerida: (confianca )"` com os placeholders vazios quando o atendimento não indicava perda.
- **Princípio novo (documentado no README):** escrever **propriedade** de um recurso (um atributo, um par chave/valor) é sempre UM nó com a propriedade escolhida em dropdown (registry extensível). Nó dedicado fica reservado só pra **comportamento** (mover estágio, reabrir, atribuir responsável, criar nota).
- **Novo:** `apps/automacao/propriedades_oportunidade.py`, registry `PROPRIEDADES` (espelha `varreduras.py`) com 4 handlers: `motivo_perda` (rede de segurança, só aplica com `estagio.is_final_perdido`; motivo fora do catálogo ou já preenchido vira skip, nunca exceção), `detalhe_perda` (texto livre), `marcador` (`dados_custom[chave]`, vazio = timestamp), `valor_estimado` (Decimal, override manual). Contrato: `fn(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True) -> {'aplicado', 'motivo_skip', 'detalhe'}`, nunca levanta pra caso de negócio.
- **Novo nó:** `definir_propriedade_oportunidade` (`nodes/definir_propriedade_oportunidade.py`, Comercial › Oportunidades), campo `propriedade` (select, fonte `propriedades_oportunidade`) + `valor`/`chave`/`somente_se_vazio`. `aplicado=False` no output é branch de **sucesso** (skip não é erro, não aciona retry).
- **Removidos:** `nodes/definir_motivo_perda.py`, `nodes/marcar_dados_custom.py` + os testes deles (`test_automacao_definir_motivo_perda.py`, `test_automacao_marcar_dados_custom.py`). As funções `acoes.definir_motivo_perda`/`acoes.marcar_dados_custom` saíram de `services/acoes.py` (lógica movida pros handlers do registry).
- **`opcoes.py`:** fonte nova `propriedades_oportunidade` (dropdown do nó).
- **Seed atualizado (`seed_fluxos_recuperacao_analise.py`):** F1 troca os nós `motivo`/`marcador` por `definir_propriedade_oportunidade`; F2/F3 trocam `marcador`. Contrato do agente ganha o campo `conclusao` no JSON (uma linha pronta pra nota, montada pelo próprio LLM, mata o placeholder vazio do fix #3); a nota do F1 passa a usar `{{nodes.json.conclusao}}` em vez do template fixo antigo. O `system_prompt` agora é gerado por `_system_prompt_agente(tenant)` (chamado no seed, não mais constante) com o **CATÁLOGO DE MOTIVOS DO TENANT inline** (busca os `MotivoPerda` ativos na hora do seed); a tool `listar_motivos_perda` continua como reforço. `DESCRICAO_AGENTE` documenta: "se o catálogo de motivos mudar, re-rodar o seed pra atualizar o prompt". O `if` `se_perdido` do F1 continua (economiza a chamada), mas a rede de segurança real agora é o handler `motivo_perda`.
- **Testes:** `tests/test_automacao_definir_propriedade.py` (novo, 14 casos: registro, validação, sem oportunidade, propriedade desconhecida, `motivo_perda` aplica/pula por estágio/pula por motivo inexistente/pula ou sobrescreve por `somente_se_vazio`, `marcador` com/sem chave/timestamp default, `valor_estimado` válido/inválido). `test_automacao_acoes_crm.py` perdeu os 5 testes das funções movidas (ficam só `criar_nota`/`reabrir_oportunidade`). `test_automacao_seed_recuperacao.py`: `_setup_f1` ganhou o parâmetro `perdida`; os 2 E2E existentes do F1 passaram a montar a op no estágio certo pro cenário e a mockar `conclusao` na resposta do LLM. **Novo E2E** `test_e2e_f1_perdido_true_mas_op_nao_esta_perdida_nao_ganha_motivo` cobre a rede de segurança (LLM diz perdido com motivo válido, op não está perdida, nota e marcador rodam, motivo fica skip, branch `sucesso`, sem erro).
- **Gates:** `manage.py check` limpo (só o warning pré-existente de STATICFILES_DIRS); os 3 arquivos do gate 30/30 verdes; `-k automacao` **370 passed, 0 failed**; `seed_fluxos_recuperacao_analise --tenant nuvyon` (dev) re-rodado com sucesso: os 4 grafos validam (`validar_fluxo`), agente e fluxos só **atualizados** (idempotência preservada, todos seguem `ativo=False`), `system_prompt` do agente confirmado com o catálogo real do tenant embutido.
- **Status:** **completed (local)**. NÃO commitado, NÃO deployado, NADA tocado em prod.

## 2026-07-15 — Varredura `oportunidades_paradas` (SLA por etapa) + fluxo de follow-up (pedido da Gabi, Nuvyon)

- **Motivo:** a Gabi (Nuvyon) pediu uma tarefa de follow-up pra vendedora quando uma oportunidade fica parada tempo demais numa etapa sem avançar ("lead esquecido na coluna"). O limite é POR ETAPA, via `PipelineEstagio.sla_horas` (campo já existia no model, hoje vazio; a Gabi vai preencher no CRM).
- **Nova varredura `_oportunidades_paradas`** (`varreduras.py`, registry `VARREDURAS['oportunidades_paradas']`): base = `OportunidadeVenda` ativa, excluindo estágios finais (`is_final_perdido`/`is_final_ganho`). Calcula `horas_paradas = now - data_entrada_estagio` em Python (SLA varia por estágio, não dá pra fazer isso no ORM puro), com cap defensivo `[:2000]` ordenado por `data_entrada_estagio` (mais parado primeiro). Config opcional: `apenas_com_sla` (default TRUE, só entra estágio com `sla_horas` preenchido), `sla_horas_padrao` (fallback quando `apenas_com_sla=false`), `exige_responsavel` (default TRUE, tarefa nunca nasce órfã), `estagios` (CSV de slugs), `max_ordem` (só as primeiras N colunas). Item devolvido traz `horas_paradas`/`estagio_nome`/`estagio_atual`/`sla_horas`. `cooldown_horas` NÃO é filtro da varredura — é o freio padrão do gatilho `agenda` (`gatilhos._freio_bloqueia`), a varredura só garante que `lead` vem no item pra ele ancorar.
- **Novo command `seed_fluxo_oportunidades_paradas.py`** (`--tenant`, idempotente por nome, nasce `ativo=False`, nunca liga/desliga num re-run): 1 fluxo **`[Nuvyon] Follow-up de oportunidade parada`** — gatilho `agenda` (intervalo 15min, granularidade fina pro SLA de poucas horas; `max_por_rodada=10` teto baixo pra não despejar o backlog acumulado de uma vez; `cooldown_horas=24`) → `criar_tarefa` (tipo `followup`, prioridade `alta`, prazo 1 dia) → `criar_nota`. **Diferente do fluxo de recuperação de perdidas:** aqui NÃO há marcador em `dados_custom` — o follow-up é RECORRENTE (a op pode parar de novo em outra etapa depois), o freio contra recriar a mesma tarefa é só o `cooldown_horas` do gatilho.
- **Testes:** `tests/test_automacao_varreduras.py` +9 casos (`_oportunidades_paradas`: SLA por etapa entra/exclui, estágio final nunca entra, `apenas_com_sla` liga/desliga com `sla_horas_padrao`, `exige_responsavel`, estrutura do item, filtro `estagios` CSV, `max_ordem`). `tests/test_automacao_seed_paradas.py` (novo, 7 casos: idempotência, nasce inativo, grafo válido, re-run preserva `ativo`, tenant inexistente falha, config do gatilho, sem nó de marcador).
- **Gates:** `manage.py check` limpo (só o warning pré-existente de STATICFILES_DIRS); os 2 arquivos de teste novos/atualizados **33/33** verdes; `-k automacao` **408 passed, 4 failed** — as 4 falhas são **pré-existentes e não relacionadas** (`test_automacao_seed_recuperacao.py`, 4 E2E do F1/F4 do seed de recuperação; passam 16/16 quando o arquivo roda isolado e continuam falhando com os arquivos novos excluídos da rodada — poluição de estado entre arquivos de teste já existente antes deste trabalho, não investigada aqui). `seed_fluxo_oportunidades_paradas --tenant nuvyon` (dev) rodado 2x: 1º cria (id=74, `ativo=False`), 2º só atualiza (mesmo id, `ativo=False` preservado).
- **Status:** **completed (local)**. NÃO commitado, NÃO deployado, NADA tocado em prod, NADA ativado. Pendente antes de ativar: Gabi preencher `sla_horas` nos estágios do pipeline Nuvyon no CRM (hoje vazio — sem isso a varredura não encontra nada com `apenas_com_sla=true` default).

## 2026-07-17 — Fechar o ciclo da viabilidade pendente (tarefa #203)

- **Problema:** a regra de viabilidade (22 fora_cobertura / 26 pendente_revisao,
  motor antigo) cria a tarefa "Validar cobertura" mas concluir a tarefa nao muda
  o status de viabilidade (mora em lead.dados_custom.viabilidade). Como a regra
  dispara a cada movimento de estagio, a op ganha tarefa nova pra sempre. Caso
  real op 2092: 3 tarefas identicas em 2 min. 17 leads pendente_revisao + 17
  fora_cobertura sujeitos.
- **Descoberta (poupou trabalho):** o dedupe JA existe (automacao_pipeline.py:940,
  nao cria se ha tarefa pendente/em_andamento igual). O furo foi a tarefa ser
  concluida quase instantaneamente, entao o dedupe (so olha pendentes) nao pegava
  a proxima. Fechar o ciclo (abaixo) resolve isso sozinho: com o status mudando,
  a condicao da regra para de bater e ela nunca mais recria.
- **Solucao via ENGINE (nao hard-code), duas pecas pequenas:**
  1. Evento `tarefa_concluida` (eventos.py + signals_dominio.py): par pre/post_save
     em crm.TarefaCRM que dispara so na virada pra concluida, em qualquer caminho
     de conclusao (view, fluxo, massa). Molde: tarefa_vencida.
  2. Propriedade `viabilidade_lead` no registry propriedades_oportunidade.py
     (zero no novo, por design): escreve lead.dados_custom.viabilidade.status,
     valida contra os 4 status conhecidos, preserva o motivo do HubSoft, carimba
     origem_status=validacao_humana + validado_em, idempotente (ja_estava).
  Fluxo (montado no editor): [tarefa_concluida, filtro titulo contem "Validar
  cobertura"] -> [definir propriedade viabilidade_lead = cobertura_ok].
- **Decisao (reversivel):** validacao humana grava cobertura_ok PERMANENTE, mas com
  timestamp, deixando a porta pra uma politica de revalidacao (cobertura muda; foi
  o que gerou os 11 leads perdidos que viraram clientes). Decisao de expirar ou
  nao fica pro Lucas.
- **Nota:** o fluxo roda ASYNC (execucao nasce pendente, o cron automacao_retomar
  processa). O cobertura_ok nao e instantaneo ao clicar concluir, leva o intervalo
  do cron.
- **Validacao:** manage.py check ok. E2E em dev: concluir a tarefa dispara o
  evento, rodar_novos processa, viabilidade vira cobertura_ok. Handler testado
  isolado (status invalido nao levanta, idempotente, preserva motivo). 32 testes
  (test_automacao_pipeline + definir_propriedade + rehidratacao) passando.
- **Status:** completed (codigo, dev). Falta: seed do fluxo em prod + deploy. Ambos
  pendentes de confirmacao do Lucas.

---

## 2026-07-18 — Checklist configuravel: Fase 1 (models + service)

- **Contexto:** um bot externo (Matrix) vai perguntar coisas ao cliente no
  WhatsApp seguindo um checklist configuravel (a cliente edita as perguntas
  numa tela, sem codigo). Fase 1 = so a fonte das perguntas (models + motor
  puro). Endpoints que o Matrix consome ficam pra Fase 2.
- **Decisao de arquitetura (do dono):** os models ficam em `apps/automacao/models.py`,
  ao lado do `Agente` (mesma natureza: peca de configuracao que alimenta a IA).
  Nao em `apps/comercial`.
- **3 models novos** (`Checklist`, `ItemChecklist`, `RespostaChecklist`, todos
  `TenantMixin`, migration `0013`):
  - `Checklist`: roteiro (contexto, modo_preenchimento, entidade_alvo,
    `bloqueia_avanco` existe mas v1 so sugere).
  - `ItemChecklist`: uma pergunta (tipo_resposta texto_livre/opcoes, `condicao`
    pra ramificar, validacao, `campo` opcional que espelha em CampoCustomizado).
    `URA_TITULO_CHOICES` fechado nos 3 slugs que o Matrix conhece (cada um
    renderiza uma IMAGEM fixa de menu no WhatsApp — slug novo exige mudanca nos
    DOIS sistemas). `clean()` protege o contrato com o Matrix: multipla escolha
    so aceita 2 a 5 opcoes (o flow dele so tem branch pra esses tamanhos; 6+
    cai no default e quebra em silencio), regex tem que compilar, `ura_titulo`
    so com `tipo_resposta='opcoes'`, `condicao` precisa de chave+valor.
  - `RespostaChecklist`: generico via `entidade_tipo`+`entidade_id` (serve lead,
    oportunidade, o que vier depois, sem FK nova por entidade). 1 resposta
    corrente por item/entidade (`unique_together`).
- **Service puro** `services/checklist.py` (sem HTTP): `itens_elegiveis`
  (respeita ordem + `condicao`, operadores igual/diferente/existe/nao_existe),
  `proximo_item` (primeiro sem resposta elegivel), `respostas_da_entidade`,
  `registrar_resposta` (idempotente via `update_or_create`; espelha em
  `dados_custom[campo.slug]` do lead/oportunidade quando o item tem `campo`,
  blindado em try/except + logger — nunca derruba o registro da resposta),
  `progresso` (conta so obrigatorios elegiveis).
- **Testes:** `tests/test_automacao_checklist.py` (novo, 23 casos: clean() —
  1/6 opcoes rejeita, 2/5 aceita, opcao sem texto, regex invalido/vazio/valido,
  ura_titulo sem opcoes, condicao incompleta; itens_elegiveis por ordem +
  inativo + os 4 operadores; proximo_item; registrar_resposta idempotente +
  espelho em lead e oportunidade + sem campo nao mexe; progresso).
- **Gates:** `makemigrations automacao` (sem orfa previa) + `migrate` aplicados
  em dev (`aurora_dev`) OK. `manage.py check` limpo (so o warning pre-existente
  de STATICFILES_DIRS). `test_automacao_checklist.py` **23/23** verde isolado.
  `-k automacao` **431 passed, 4 failed** — as 4 falhas sao em
  `test_automacao_seed_recuperacao.py` (F1/F4 do seed de recuperacao),
  **pre-existentes e nao relacionadas** (mesma poluicao de ordenacao entre
  arquivos ja registrada na entrada de 16/07; passa **16/16** isolado).
- **Nota:** `apps/automacao/services/ia.py` apareceu modificado no `git status`
  no meio da sessao sem eu ter tocado nele — outra sessao concorrente rodando
  na mesma pasta (regra 1.10 do CLAUDE.md). Nao mexi nele.
- **Status:** completed (Fase 1, local). NAO commitado, NAO deployado, nada
  tocado em prod. Falta Fase 2 (endpoints que o Matrix consome) + confirmar
  tarefa Workspace vinculada (nao criada nesta sessao — checar/criar antes do
  proximo bloco).

---

## 2026-07-19 — Bot de vendas consolidado em UM fluxo so + ramo recontato + gap do lead fechado

- **Decisao do dono:** os 2 fluxos separados do `seed_fluxo_bot_venda.py`
  ("proximo passo" / "validar resposta") viravam UM fluxo so, com switch de
  entrada roteando por `{{var.payload.acao}}` ("abro uma tela e vejo o bot
  inteiro"). Adicionado o ramo "recontato" (3o endpoint do contrato do
  Matrix, nunca tinha sido construido).
- **3 correcoes aplicadas:**
  1. `ura.total_opcoes` int de verdade no JSON (nao string) — ja era garantido
     pelo `responder_webhook._resolver_corpo` (resolve o corpo como OBJETO,
     preserva tipo nas folhas, serializa com `json.dumps`); adicionado teste
     de regressao explicito (`json.loads` + `isinstance(..., int)`).
  2. `status_lead` polimorfico virou decisao do grafo: `checklist_progresso`
     + `if` (`respondidos` maior que `0`) escolhem entre `0` (int, lead nunca
     respondeu) e `"em_andamento"` (string, retomando). `"cliente_ativo"`
     documentado como fora de escopo (dependeria de consulta HubSoft).
  3. Gap do lead fechado: no `carregar_lead` novo (Comercial > Leads),
     logo apos o `webhook`, resolve `LeadProspecto` por `lead_id` ou
     `telefone` (so digitos, tolerante a 55/DDD, sufixos 8-13), cria minimo
     se configurado. Mecanismo NOVO e GENERICO: `NodeResult.entidades` (em
     `nodes/base.py`) + `Contexto.injetar_entidades`/`aplicar_resultado` (em
     `nodes/context.py`) fundem a entidade no `contexto.lead` — reusavel por
     qualquer no futuro, nao exclusivo deste.
- **Achado durante a implementacao:** `Contexto.resolver` distingue "chave
  ausente no payload" (devolve o texto `{{...}}` LITERAL) de "chave presente
  com valor `None`" (devolve `None` de verdade) — um `lead_id` opcional que o
  payload simplesmente nao manda vazava o template cru pro no. Corrigido no
  `carregar_lead` (`_resolvido_ou_vazio`); documentado pra quem for usar esse
  padrao em outro no com campo opcional.
- **Arquivos:** `apps/automacao/nodes/base.py` (campo `NodeResult.entidades`),
  `apps/automacao/nodes/context.py` (`injetar_entidades`), `apps/automacao/runtime.py`
  (comentario), `apps/automacao/nodes/carregar_lead.py` (novo),
  `apps/automacao/nodes/__init__.py` (registro), `apps/automacao/management/commands/seed_fluxo_bot_venda.py`
  (reescrito: 1 fluxo, remove os 2 antigos com guard de seguranca — so se
  inativos e sem `ExecucaoFluxo`), `tests/test_automacao_seed_fluxo_bot.py`
  (reescrito), `tests/test_automacao_carregar_lead.py` (novo).
- **Gates:** `manage.py check` limpo (so o warning pre-existente de
  STATICFILES_DIRS). `pytest tests/test_automacao_seed_fluxo_bot.py
  tests/test_automacao_nodes_checklist.py tests/test_automacao_carregar_lead.py`
  **55/55** verde. Seed rodado 2x em dev (`aurora-hq`): 1a rodada cria o
  fluxo novo (id=80) e remove os 2 antigos (id=78/79, estavam inativos e sem
  execucao); 2a rodada so atualiza (idempotente). `validar_fluxo` do grafo
  final: sem erros (23 nos).
- **Achado de infra (fora de escopo, nao investigado a fundo aqui, so
  diagnosticado):** `-k automacao` (suite inteira) mostra falhas nos meus
  testes novos SO quando rodados junto com o resto da suite (isolados: 100%
  verde). Causa raiz identificada: `TenantManager.get_queryset()` (
  `apps/sistema/managers.py`) filtra por thread-local `get_current_tenant()`;
  testes que batem em views reais (Django test client, ex:
  `test_automacao_permissoes.py`) setam esse thread-local via
  `TenantMiddleware` e ele fica "vazado" pros testes seguintes no MESMO
  processo pytest que usam manager default (nao `all_tenants`) num relation
  reverso (`checklist.itens`, `fluxo.execucoes`) — mesmo mecanismo que ja
  quebrava `test_automacao_seed_recuperacao.py`/`test_automacao_acoes_crm.py`
  antes deste trabalho (ver entradas de 16-17/07). Pre-existente, nao
  introduzido aqui; mesma poluicao ja documentada, agora com causa raiz
  identificada — registrar pra quem for investigar/corrigir depois (candidato:
  reset explicito do thread-local em fixture `autouse` de teste).
- **Status:** completed (local). NAO commitado, NAO deployado, nada tocado em
  prod. Tarefa Workspace vinculada: NAO confirmada nesta sessao (subagente
  sem acesso interativo) — usuario precisa criar/vincular conforme secao 1.7
  do CLAUDE.md antes do proximo bloco.

---
