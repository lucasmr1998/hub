# Plano — Venda automática multi-empresa no Hubtrix: contrato do Matrix por cima do motor nativo

## Context

O `techub/robo_v2` faz venda automática por WhatsApp: a plataforma de bot "Matrix" conduz o flow e, a
cada mensagem, chama uma **API** (FastAPI `ia_validacao`) que valida a resposta e decide o próximo
passo. Está em produção na Megalink, mas é **single-tenant e cheio de hardcodes** (persona "Aurora",
planos, IDs HubSoft, FAQ). Levar para outra empresa exige fork.

O `hub` (Hubtrix) é um SaaS Django **multi-tenant em produção** que — descoberto nesta análise — **já
tem quase tudo pronto e configurável por empresa**:
- **Motor de atendimento visual** (`apps/comercial/atendimento`, editor Drawflow) que já cobre ~90% do
  robo_v2: perguntas, validação (CPF/CEP/email/opções/IA multi-provider/webhook), roteamento por grafo,
  estado por telefone (`AtendimentoFluxo`), salvar no lead, telemetria de erro — **tudo tenant-aware e
  editável por UI**.
- **Config por empresa com UI pronta**: planos/vencimentos/IDs vêm do catálogo HubSoft sincronizado
  (`crm.ProdutoServico`/`OpcaoVencimentoCRM`); defaults (vendedor, origem, plano-padrão, modelo de
  contrato) em `IntegracaoAPI.configuracoes_extras`, editáveis em `/configuracoes/integracoes/`.
- **Camada de IA por empresa**: model `Agente` (persona/prompt/modelo/tools) + base de conhecimento RAG
  (`apps/suporte`, pgvector), editáveis em `/workspace/agentes/` e `/suporte/conhecimento/`.
- **Simulador de chat + trace por turno** já existentes (reaproveitáveis para o console).

**Objetivo:** expor **o contrato exato da API do robo_v2 por cima do motor nativo do Hubtrix** — o mesmo
flow do Matrix da Megalink roda em qualquer empresa só trocando a URL. A lógica (perguntas, validação,
persona, planos, IDs) vira **dado editável por empresa**, não código. E trazer o **console de chat**.

**Decisões tomadas:**
1. **Cérebro do fluxo:** reusar o **motor de atendimento visual** (`apps/comercial/atendimento`, Drawflow).
   A API do Matrix vira um **adaptador fino** que traduz contrato ↔ motor. (Não portar máquina de estados
   como código; não criar models de regra/mensagem.)
2. **Quem edita os fluxos:** equipe Hubtrix, por empresa (no editor visual existente).
3. **Camada de IA:** usar `Agente` + RAG do hub (aposenta a persona "Aurora" e o `FAQ_BASE` hardcoded).
4. **Hospedagem:** endpoints Django no próprio hub (não FastAPI separada).
5. **Identidade da empresa:** por **token/slug na URL** (`/robo/<token>/ia/...`) — payload inalterado.
6. **Console de chat:** reescrever no hub (o chatsim original não está no repositório).
7. **Ordem:** determinístico (`/proximo-passo`+`/validar`+`/recontato`) primeiro; conversacional depois.
8. **Contrato preservado** byte a byte (mesmo flow do Matrix serve todas as empresas).

Raiz Django do hub: `hub/robo/dashboard_comercial/gerenciador_vendas/` (`GV/`).
Origem/contrato (leitura): `techub/apps/comercial/robo_v2/` — contrato em `docs/API_IA_VALIDACAO.md`.

---

## Arquitetura

**Peça central nova = adaptador de contrato Matrix ↔ motor de atendimento.** Tudo o mais é reuso.

```
Matrix (flow genérico da empresa)
   │  POST /robo/<token>/ia/proximo-passo | validar | recontato | validar-imagem
   ▼
ADAPTADOR (app fino novo)  ── resolve tenant pelo <token> na URL (padrão do hub)
   │   traduz contrato robo_v2  ⇄  motor de atendimento
   ▼
apps/comercial/atendimento (REUSO)
   iniciar_por_canal / processar_resposta_visual (GV/apps/comercial/atendimento/engine.py:70,125)
   estado: AtendimentoFluxo (nodo_atual + dados_respostas)  ·  lookup telefone→lead (views_api.py:1743)
   validação por nó (engine.py:927) · fallback IA (Agente + RAG) · salvar_em no lead
   config por empresa: FluxoAtendimento (Drawflow, editor /configuracoes/fluxos/<id>/editor/)
   │
   ├── planos/IDs/vencimentos: crm.ProdutoServico / OpcaoVencimentoCRM + configuracoes_extras (REUSO)
   ├── persona/FAQ: Agente + RAG (REUSO)
   └── HubSoft (prospecto/contrato/OS): apps/integracoes services + nós (REUSO)
```

**O adaptador faz a tradução de shape** (o trabalho fino e crítico):
- `/proximo-passo` → resolve telefone→`AtendimentoFluxo` (ou `iniciar_por_canal`) → lê o nó atual →
  monta `{proxima_pergunta_id, mensagem_inicial, mensagem_inicial_safe, ura, proximo_passo, status_lead,
  deve_perguntar, deve_transbordar, ...}`.
- `/validar` → recebe `answer`+`question_id` → `processar_resposta_visual` → monta os campos legados
  **string** `"true"/"false"` (`resposta_correta`, `needsReception`, `isAClient`, `retorno_erro_api`,
  `mensagem_resposta`, `viabilidade_cep`, `ret_*`) + bloco V2 (`valido`, `extracted_data`, ...).
- `ura` (menu de opções do robo_v2) montado a partir das opções do nó `select`/`opcoes_dinamicas`.

**Config por empresa — mapa (praticamente zero model novo):**
| Parâmetro robo_v2 (era hardcode) | Onde vive no Hubtrix | Editável em |
|---|---|---|
| IDs de plano / plano padrão / planos ofertáveis | `crm.ProdutoServico` (sync HubSoft) + `configuracoes_extras['planos_permitidos_hubsoft'/'plano_id_padrao']` | `/configuracoes/integracoes/<pk>/`, `/comercial/crm/produtos/` |
| Dias de vencimento + IDs | `crm.OpcaoVencimentoCRM` + `configuracoes_extras` | idem |
| id_vendedor / id_origem / id_origem_servico | `configuracoes_extras` (defaults) + `PerfilUsuario.id_vendedor_hubsoft` | `/configuracoes/integracoes/<pk>/` |
| Viabilidade por cidade | `viabilidade.CidadeViabilidade` + HubSoft | `/comercial/viabilidade/cidades/` |
| id_contrato_modelo / id_empresa | `configuracoes_extras['hubsoft']` | UI de defaults (expor campo — gap fino) |
| Credenciais HubSoft/Matrix/IA/Uazapi | `IntegracaoAPI` (Fernet) | `/configuracoes/integracoes/` |
| Persona / FAQ | `Agente.system_prompt` + base RAG | `/workspace/agentes/`, `/suporte/conhecimento/` |
| Perguntas/validações/mensagens/sequência | `FluxoAtendimento` (grafo Drawflow) | editor de fluxo |
| Campos de lead extras (tipo_imovel, turno/data instalação) | `LeadProspecto.dados_custom` + `CampoCustomizado` | UI de campos customizados |
| Token de identidade da empresa na URL | `IntegracaoAPI.api_token` (ou campo no FluxoAtendimento) | config da integração |

---

## Fases

### Fase 0 — Fundação do adaptador (tenant por token + fluxo piloto)
- App fino novo (ex.: `GV/apps/comercial/robo_matrix/`) só com urls/views do contrato; **sem models de
  regra** (reusa `atendimento`). Resolver `request.tenant` pelo `<token>` na URL reusando o padrão do
  hub (`apps/sistema/authentication.py` / `decorators.api_token_required`; token = `IntegracaoAPI.api_token`).
- Tenant piloto: montar um `FluxoAtendimento` mínimo no editor (2-3 perguntas: CPF, nome, plano) +
  `Agente` + 1 artigo de base RAG. Prova de que config por empresa funciona sem código.
- **Teste:** `manage.py check`; iniciar sessão via adaptador e assertar isolamento entre 2 tenants.

### Fase 1 — Adaptador de contrato determinístico (núcleo do pedido)
- Views `/robo/<token>/ia/proximo-passo | validar | recontato` traduzindo contrato ↔
  `iniciar_por_canal`/`processar_resposta_visual`. Montar `ura`, campos legados string, `mensagem_resposta`.
- Estender, se preciso, o único ponto de validação (`engine.py:_validar_resposta_questao:927`) com tipos
  que faltem para paridade.
- **Teste:** **golden tests** — capturar respostas reais do robo_v2 (rodando local com o banco já baixado)
  e comparar campo a campo com o adaptador, para o mesmo request. `manage.py test`.

### Fase 2 — Shims dos endpoints Django auxiliares do flow do Matrix
- O flow do Matrix também chama endpoints Django diretos (`/api/leads/registrar`, `/api/historicos/registrar`,
  `/api/consultar/leads`, `/integracoes/api/verificar-cliente-cpf`, `/integracoes/api/agendar-instalacao-ia`,
  `/ia_validador/api/regras-validacao`, `/ia_validador/api/ia/log-interacao`). Recriar com contrato idêntico
  (tenant-por-token) sobre os models do hub (`LeadProspecto` etc.), traduzindo os IDs pelo config do tenant.
- **Teste:** replay dos bodies literais do `flow_v5_patched.json` contra um tenant de teste.

### Fase 3 — Console de chat de teste (reescrito no hub)
- Página logada (estende `templates/layouts/layout_app.html`, padrão do `workspace/agente_editar.html`):
  chat WhatsApp-like + inspetor request/response por turno + export PDF. Seletor de tenant (interno →
  depois produto). Consome os endpoints da Fase 1 (decorator que aceita sessão OU token). Reaproveitar o
  simulador do agente e o trace de sessão da monitoria de `atendimento`.
- **Teste:** conversa E2E manual contra o tenant piloto; loop proximo-passo → validar → recontato.

### Fase 4 — Validação de imagem / documentos
- `/robo/<token>/ia/validar-imagem` (IA Vision, credencial do tenant via `IntegracaoAPI`), gravando em
  `DocumentoLead`/`ImagemLeadProspecto` (já existem). Upload no console.

### Fase 5 — Migração do fluxo real da Megalink + homologação
- Converter as ~33 `RegraValidacao` + a sequência do robo_v2 (do banco já baixado) num `FluxoAtendimento`
  do tenant Megalink: um command de seed gera os nós/validações/mensagens; o roteamento (que no robo_v2
  era código `onboarding.py`) é desenhado no editor pela equipe. Homologar pelo console e com número de teste.

### Fase 6 — Conversacional (`/conv/turno`)
- Expor o contrato `/conv/turno` sobre os nós de IA do atendimento (`ia_respondedor`/`ia_agente` + RAG).
  No motor de atendimento a distinção determinístico/conversacional some (validação + fallback IA já
  convivem); o adaptador só mapeia o shape do `TurnoResponse`.

### Fase 7 — Execução no HubSoft (novo serviço / upgrade / conversão)
- Conforme decisão anterior: reintroduzir a automação de painel do robo_v2 como service + guards
  dry-run/allowlist **por tenant**, acionada como ação do fluxo. Fase isolada, maior risco. Aquisição E2E
  (prospecto → contrato → agendamento) já é coberta por nós/serviços HubSoft existentes.

**Transversal:** tarefa no Workspace por unidade; doc em `robo/docs/PRODUTO/modulos/` + `execution-log.md`;
`manage.py check`/`test` (Postgres pgvector :5433, settings_local); todo model novo `TenantMixin`.

---

## Arquivos-chave
- **Criar (fino):** `GV/apps/comercial/robo_matrix/` (urls, views do contrato, tradutores de shape, console).
- **Reuso (motor):** `GV/apps/comercial/atendimento/{engine.py, models.py (AtendimentoFluxo, NodoFluxoAtendimento), views_api.py}` — `iniciar_por_canal`, `processar_resposta_visual`, `_validar_resposta_questao`, `buscar_lead_por_telefone_n8n`.
- **Reuso (config):** `GV/apps/integracoes/` (IntegracaoAPI, sync catálogo), `GV/apps/comercial/crm/models.py` (ProdutoServico, OpcaoVencimentoCRM), `GV/apps/comercial/viabilidade/`.
- **Reuso (IA):** `GV/apps/automacao/models.py` (Agente), `GV/apps/automacao/services/{ia,rag,ia_tools}.py`, `GV/apps/suporte/` (base RAG).
- **Reuso (UI):** `templates/layouts/layout_app.html`, `templates/components/`, `apps/workspace/templates/workspace/agente_editar.html` (padrão do console).
- **Ler (contrato):** `techub/.../robo_v2/docs/API_IA_VALIDACAO.md`, `ia_validacao/src/{app.py, onboarding.py, regras/engine.py}`, `fluxos/flow_v5_patched.json`.

## Verificação
- Golden tests: response do adaptador == response do robo_v2 real para os mesmos requests (robo_v2 local
  como oráculo, usando o banco já baixado).
- `manage.py check` + `manage.py test` (Postgres pgvector :5433, settings_local).
- E2E pelo console contra tenant piloto; replay dos bodies do `flow_v5_patched.json`.
- Isolamento: 2 tenants com fluxos/planos diferentes respondem diferente ao mesmo telefone/pergunta.

## Riscos / decisões abertas
1. **Fidelidade byte a byte do contrato** (campos legados string, `mensagem_resposta`, `ura`): mitigado
   por golden tests. Confirmar `mensagem_resposta` no `/validar` em runtime.
2. **`atendimento` é "legado"** (CLAUDE.md: migração gradual para `automacao`). Decisão consciente:
   usá-lo agora (roda em prod, runtime conversacional pronto); o adaptador é fino, então se a `automacao`
   ganhar runtime conversacional o contrato pode ser reapontado sem mexer no Matrix. Contrato fica estável.
3. **Conversão do fluxo da Megalink** (Fase 5): o roteamento era código (`onboarding.py`); precisa ser
   desenhado no editor. Estimar esforço; começar por um subconjunto (aquisição feliz) e expandir.
4. **Token de identidade da empresa**: reusar `IntegracaoAPI.api_token` vs campo dedicado no FluxoAtendimento.
5. **Campos de instalação** (tipo_imovel/turno/data): `dados_custom`/`CampoCustomizado` vs campo 1ª classe.
6. **HubSoft execução (Fase 7)**: mesmo risco (API oficial não cobre conversão/novo serviço/upgrade →
   automação de painel frágil).
