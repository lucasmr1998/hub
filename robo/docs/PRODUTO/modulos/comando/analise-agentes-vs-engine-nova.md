# Agentes do `comando` (gestão legado) vs engine nova, análise de Fase 0

> Análise read-only de 29/06/2026 pra decidir como "terminar de trazer o workspace pra cá":
> a camada de agentes IA (`apps/comando`, schema dormente herdado do `gestao` do megaroleta)
> deve ser ressuscitada como está, ou expressa em cima da engine nova (`apps/automacao`)?
> Nada foi alterado. Este doc é o gate de decisão.

## Contexto

A migração do workspace foi em fases. **Fase 1 (núcleo: projetos, tarefas, documentos, Drive)
está pronta em `apps/workspace`, em prod.** A **camada de agentes IA** (a "empresa de agentes"
do gestão: Agente, ToolAgente, Automacao, Proposta, Alerta, Reuniao, FAQ) veio só como **schema
dormente em `apps/comando`** (11 models, sem views/lógica). "Terminar de trazer" = dar vida a essa
camada. A questão é COMO.

## 1. O roster de agentes já existe (e melhor)

Os 17 agentes do gestão batem quase 1:1 com os 20 de `robo/docs/AGENTES/`, que é uma versão
**evoluída e adaptada pro contexto SaaS** do mesmo roster (e é o mesmo conjunto de personas que o
CLAUDE.md usa pra classificar respostas).

| Gestão (megaroleta) | Hubtrix hoje |
|---|---|
| CEO, CTO, CPO, CFO, CMO | `AGENTES/executivo/` |
| PMM, PM | `AGENTES/produto/` (+ UX, novo) |
| Growth, Content, Customer Marketing | `AGENTES/marketing/` (Growth, Conteúdo, CRM e Automação; + Copy, Performance) |
| CS Manager, Community, Support | `AGENTES/comercial/cs` + marketing |
| Comercial B2B | `AGENTES/comercial/` (Head de Vendas, Parcerias) |
| Analista de Dados | `AGENTES/tech/data` |
| QA, DevOps | roster do CLAUDE.md (seção 13) |

**Conclusão:** as personas já existem, em versão melhor. Não há ganho em reimportar definições do
gestão.

## 2. Paradigma velho (agente do gestão)

Persona IA gerenciada em banco (`prompt`, `prompt_autonomo`, `modelo`, `time`). Roda em 3 modos:

- **Chat 1:1:** `ai_service.chat_agente()` monta prompt + contexto cacheado (5min) + histórico,
  chama OpenAI/Gemini. A resposta passa por `agent_actions.processar_acoes()`, que faz **regex em
  texto livre** procurando blocos `---CRIAR_TAREFA---..---FIM---` (19 tipos) e executa handlers.
- **Rotina autônoma (cron):** `executar_automacoes` acorda uma `Automacao`. Modo agente = 3 etapas
  (coleta dados via `consulta_dados_service`, agente analisa e age, gera `Proposta` diferida).
- **Proposta:** fica pendente com `dados_execucao` (JSON) até o CEO aprovar, então executa.
- **Reunião multi-agente:** moderador determinístico escolhe N agentes que respondem em sequência.

Tools = blocos de texto regex. Consulta de dados = 16 queries sobre models do **Megalink**
(MembroClube, PremioRoleta, cupons, parceiros, indicações). FAQ por IA e geração de imagem (Gemini).

## 3. Paradigma novo (agente do `apps/automacao`)

Agente é um **nó (`ia_agente`) dentro de um fluxo**. `system_prompt` + memória + **function-calling
real** (schema OpenAI). `chamar_llm_com_tools()` faz o loop de tool-calling de verdade. Tools são
`@_tool` decorators (hoje: registrar_feedback, criar_oportunidade, consultar_base_conhecimento,
marcar_cliente, marcar_intencao, abrir_ticket). Multi-provider (OpenAI/Anthropic/Groq/Google) e
multi-tenant via `IntegracaoAPI`. Memória = registry (`conversa`). Pausa/retoma com estado em
`ExecucaoFluxo`. Sem `prompt_autonomo` (memória + fluxo fazem o papel).

**A engine nova é arquiteturalmente superior** ao motor de IA do gestão: function-calling > regex,
multi-provider > hardcoded, fluxo componível > agente monolítico.

## 4. Mapa de capacidades e gaps

| Capacidade gestão | Equivalente novo | Gap / esforço |
|---|---|---|
| Tool via bloco de texto (regex) | function-calling real | reescrever como `@_tool`. Médio |
| Consulta de dados (16 queries) | tool customizada | **as queries do gestão são de models do Megalink, não servem ao Hubtrix.** Criar tools de dados do Hubtrix (leads/vendas/churn/tickets). Médio |
| Rotina autônoma (cron acorda agente) | gatilho cron + fluxo | a engine já tem cron na fila. Médio |
| Proposta com aprovação humana (execução diferida) | **não existe** | nó "solicitar aprovação" + UI de propostas. **Alto, é o coração** |
| Reunião multi-agente | não existe | nó moderador. Alto, baixo ROI (descartável) |
| FAQ por IA | não existe | agente Operador + storage. Médio, opcional |
| Geração de imagem (Gemini) | não exposto | nó/tool dedicado. Médio, opcional |

## 5. Veredito

**Expressar em cima do `apps/automacao`, reaproveitando o roster do `AGENTES/`. NÃO ressuscitar o
motor de IA do gestão** (regex + ai_service seria andar pra trás). O trabalho real não são os
agentes (já temos), são **3 primitivas faltantes:** tools de consulta de dados do Hubtrix, gatilho
autônomo/cron por agente, e **fluxo de proposta/aprovação** (o maior gap).

## 6. Sobre importar do megaroleta (a pergunta-chave)

Existe o command `importar_megaroleta_gestao` que copia 1:1 as tabelas do gestão pra `comando`.
**Mesmo indo pro escopo completo, NÃO importar "da forma que está lá".** Motivos:

- **Prompts são de contexto Megalink/roleta**, não Hubtrix SaaS. O `AGENTES/` já é a versão certa.
- **As 16 consultas de dados leem models do Megalink** (MembroClube, roleta, cupons) que o Hubtrix
  não tem. Importar essas queries é inútil; as tools de dados do Hubtrix são outras.
- **Os dados** (LogTool, MensagemChat, propostas, alertas) são **histórico operacional do Megalink**,
  irrelevante pro Hubtrix.

O `gestao` é um **blueprint** (prova que o padrão funciona e mostra o desenho), **não uma fonte de
import**. Em qualquer cenário, a gente constrói com o roster do `AGENTES/` + tools nativas do Hubtrix.
O `importar_megaroleta_gestao` e o schema dormente do `comando` viram referência, e provavelmente o
`comando` é redesenhado (inclusive a decisão mono vs multi-tenant).

## 7. Escopo (a decidir)

- **(A) Fatia fina:** roster vira registros `Agente` na engine + tools de consulta de dados do
  Hubtrix, rodando sob demanda. ~1 semana, alto reaproveitamento. Entrega "agentes que executam
  quando chamados".
- **(B) Empresa autônoma completa:** + cron por agente + propostas/aprovação. 4 a 10 semanas. É
  praticamente um produto novo. Mesmo aqui, **não é import 1:1** (ver seção 6).

Decisões abertas pro time: escopo (A vs B), mono vs multi-tenant, e prioridade (é ferramenta interna
da Aurora HQ, com clientes ativos e a aposentadoria do atendimento em aberto).
