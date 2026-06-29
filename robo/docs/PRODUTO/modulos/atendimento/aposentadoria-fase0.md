# Aposentadoria do motor de atendimento, Fase 0 (investigação)

> Investigação read-only de 29/06/2026 pra decidir se/como aposentar o motor de
> atendimento nativo (`apps/comercial/atendimento`, máquina de estado conversacional,
> editor Drawflow.js) em favor da engine unificada (`apps/automacao`). **Nada foi
> alterado.** Este doc é o gate de decisão; o plano de execução vem depois.

## Veredito em uma linha

Execução **morta em prod** (nenhum tenant ativo roda), mas **acoplado no boot** (inbox
modo bot importa o engine, + APIs N8N expõem rotas). Por isso **NÃO é um drop como o
marketing**: é uma **migração** (portar o nó de pergunta conversacional + `salvar_em` +
validação pro engine novo, desacoplar inbox/N8N) ou, no mínimo, um desligamento cuidadoso
do acoplamento antes de remover.

## 1. Uso real em prod (read-only, por tenant)

| Tabela | Achado |
|---|---|
| `atendimento_log_fluxo` (cada nó executado) | 973 linhas, **todas do `fatepifaespi`** (tenant **DESATIVADO**). **0 em 30d**, 24 em 60d. Último: 07/05/2026. Nenhum outro tenant tem 1 execução. |
| `atendimentos_fluxo` (sessões) | 100 total: 91 fatepi (inativo), 7 demo, 2 aurora-hq. **0 sessões em 30d** em qualquer tenant. Últimas de tenant ativo: 15/04 (teste). |
| `atendimento_execucao_pendente` (pausadas) | **0.** Nada no meio de uma conversa (nenhuma sessão órfã pra migrar). |
| `fluxos_atendimento` (definições) | 11: tr-carrion(2), aurora-hq(4), fatepi(4 inativo), demo(1). **tr-carrion tem 0 execuções** (roda no Vero N8N; fluxos definidos e nunca usados no nativo). |

**Conclusão de uso:** o único usuário real (FATEPI) está desativado. TR Carrion e Nuvyon
rodam N8N (Vero/Matrix), não o nativo. Risco de cutover **baixo na prática** (nada vivo
executando, 0 pausadas), o problema é o acoplamento de código.

## 2. Anatomia do `apps/comercial/atendimento/`

Módulo grande: ~15.000 a 18.000 linhas de Python (~502 KB), 10 tabelas.

| Arquivo | ~Linhas | Responsabilidade |
|---|---|---|
| `engine.py` | ~2663 | Máquina de estado: traversal do grafo, pausa/retoma, IA, viabilidade, `salvar_em` |
| `models.py` | ~2257 | 10 models (`db_table=atendimento_*` + `fluxos_atendimento`, `questoes_fluxo`, etc.) |
| `views_api.py` | ~2224 | 30+ endpoints (CRUD fluxos/questões/atendimentos) + rotas N8N |
| `views.py` | ~1207 | UI legada do editor Drawflow, sessões, debug |
| `signals.py` | ? | Conecta o inbox ao engine (`iniciar_por_canal`, `processar_resposta_visual`) |
| `engine_contexto.py`, `services/*`, `management/commands/*` | ? | Contexto persistente, serviços, recontato/timeouts |

**Tabelas:** `fluxos_atendimento`, `questoes_fluxo`, `atendimentos_fluxo` (sessão),
`tentativas_resposta`, `respostas_questao`, `atendimento_nodofluxo`,
`atendimento_conexaonodo`, `atendimento_execucao_pendente`, `atendimento_log_fluxo`,
`atendimento_tool_customizada`, `atendimento_motivo_erro_resposta`.

## 3. Capacidades do engine

- **Traversal node-based:** entrada, questão, condição, ação, delay, finalização,
  transferir_humano, ia_classificador, ia_extrator, ia_respondedor.
- **Pausa/retoma:** pausa em questão (`espera_resposta=True`), delay e finalização.
  Delay retomado por cron (`executar_pendentes_atendimento`). Contexto persistido em
  `ExecucaoFluxoAtendimento.contexto_json`.
- **`salvar_em`** (engine.py:180-182): grava a resposta direto em campo do LeadProspecto
  (whitelist: nome, email, telefone, cpf_cnpj, cidade, cep, etc.). `pular_se_preenchido`.
- **check_viabilidade** (engine.py:847-905): consulta `viabilidade.consultar_viabilidade(cep)`,
  salva `cobertura_status`/`cidade_detectada`/`uf_detectada`. Determinístico.
- **Base de conhecimento** no fallback de resposta inválida.
- **Validação de resposta** complexa (regex, intervalo, opções, webhook N8N, IA).

## 4. Quem depende (acoplamento)

- **Inbox (crítico):** `apps/inbox/signals.py:345,364-384` importa
  `from apps.comercial.atendimento.engine import iniciar_por_canal, processar_resposta_visual`.
  No `post_save` de Mensagem, se `modo_atendimento=='bot'`, chama o engine. **Import no boot.**
- **APIs N8N:** `/api/n8n/atendimento/iniciar|consultar|responder|avancar`, `/api/n8n/fluxos/`
  (`views_api.py` + `apps/api/serializers_n8n.py`). N8N usa REST, não importa classes, mas
  as rotas existem e somem se o app sair.
- **Viabilidade:** engine chama `consultar_viabilidade` (unidirecional, sem dep reversa).
- **Leads:** `salvar_em` escreve em `LeadProspecto`.

## 5. Cobertura do engine novo (`apps/automacao`) e gaps

**Já tem:** agente IA + memória de conversa, switch/if, delay, viabilidade (via
`hubsoft_viabilidade`), `promote` (variáveis no contexto), webhook/http, criar oportunidade/tarefa,
mover estágio.

**Faltam pra substituir (portar):**

| Feature | Status no novo | Esforço |
|---|---|---|
| **Nó de pergunta com aguardar resposta** (pausa + retoma) | ❌ não existe (chat.py é só gatilho de teste) | Alto (~500-800 linhas) |
| **`salvar_em` gravando em campo do LeadProspecto** | ⚠️ `promote` só mexe em variáveis de contexto | Médio (~200) |
| **Validação de resposta** (regex/intervalo/webhook/IA) | ❌ sem equivalente | Médio (~400) |
| **Cascata de viabilidade** (CEP→cobertura em variáveis) | ✅ quase (lógica pronta, adaptar nó) | Baixo (~150) |
| **Sessão persistente** (mapear `AtendimentoFluxo`→`ExecucaoFluxo`) | ⚠️ formato diferente | Médio |
| **Roteamento inbox→engine novo** (signals) | precisa decidir por `fluxo.tipo` | Médio (~200) |
| **Migração de dados** (fluxos visuais → grafo novo) | ❌ | Alto (~1000+) |

**Escopo estimado:** ~2.500 a 3.500 linhas de código novo + testes pra paridade.

## 6. Riscos de sumir sem migrar

- **Inbox modo bot** importa o engine no boot: remover o app quebra o import do `signals.py`
  (decouple obrigatório antes).
- **APIs N8N** `/api/n8n/atendimento/*` somem (se algum workflow externo chamar, quebra).
- **Sessões em andamento** ficariam órfãs, mas hoje há **0 pendentes** em prod (risco real baixo).
- Editor visual Drawflow, `salvar_em`, recontato automático, validação customizada deixam de existir.

## 7. Caminhos possíveis (pra decidir na Fase 1)

- **A. Migração completa:** portar o nó de pergunta + `salvar_em` + validação, migrar os
  poucos fluxos vivos (na prática quase nada ativo), desacoplar inbox/N8N, depois dropar.
  Mais trabalho, fecha a unificação de verdade.
- **B. Decouple e congelar:** como ninguém ativo usa, remover o acoplamento (inbox para de
  importar; rotas N8N viram 410/aviso), parar de evoluir, e dropar tabelas/código depois de
  uma janela de quarentena. Mais barato; não entrega paridade conversacional no novo.
- **C. Não mexer agora:** está morto em execução mas inerte; priorizar outra frente.

Recomendação preliminar: como o uso é zero, o ganho está em **matar o acoplamento e o código
morto** (B) sem o custo de portar paridade que ninguém usa, a menos que exista plano de usar o
nó conversacional do engine novo pra um cliente. Confirmar com o time antes da Fase 1.
