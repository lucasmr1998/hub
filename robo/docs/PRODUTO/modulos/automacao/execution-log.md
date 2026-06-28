# Execution log — Automação (engine unificada)

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

### Pendências / próximos passos
- **~~Opções dinâmicas ADIADAS~~ → FEITO (22/06) pras fontes locais** (segmentos/pipelines/estágios/responsáveis). Falta só ligar fontes **externas** (HubSoft: serviços/modelos/planos) como `fonte` que chama a API do tenant + cache. Matrix segue sem API de listar templates (manual).
- **Decisão (22/06): opções dinâmicas + preview ADIADAS.** Quería-se dropdown de contas/templates Matrix + preview do HSM ao selecionar. Mas o **Matrix não expõe API de listar templates** (confirmado), então a única fonte do preview seria um **registro local** (cópia do corpo por tenant) — com manutenção manual e risco de drift vs o template aprovado. Decidido **manter `cod_conta`/`hsm` manuais** por ora. O **mecanismo genérico de opções dinâmicas** (`select_dinamico` carregado de endpoint por-tenant + painel de preview) fica pra quando entrar uma integração com **API de listagem real** (ex: HubSoft, ou "listar pipelines" do CRM) — aí o investimento se paga em vários provedores.
- **Pending:** decidir volume/dia por tenant + latência → runtime síncrono-em-cron (modelo marketing) vs. fila. Bloqueia a fase de runtime.
- **Pending (convergência):** extrair executores de domínio (`criar_oportunidade`, `webhook`...) pra service único tenant-aware; aposentar motores na ordem marketing → atendimento → comercial.
- **Dívida (anotada na doc):** DNS-rebinding (pinning de IP), allowlist de destino por tenant, nó `code` com sandbox (nunca `eval`).
