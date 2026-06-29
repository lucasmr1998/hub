# Empresa de agentes: Peca 1 + Peca 2 (organizacao + tools) — 29/06/2026

**Data:** 29/06/2026
**Participantes:** Lucas + Tech Lead/PM (Claude)
**Duracao:** sessao longa (continuacao da camada de agentes)

---

## Contexto

Continuacao de "trazer o gestao pra ca". A Fase 1/2a/3 (chat + propostas + fonte unica do
agente) ja estava feita. Esta sessao trouxe o que faltava do gestao em 4 pecas: **1) organizacao
por time + editor, 2) tools (sistema + acoes), 3) Dashboard CEO, 4) rotinas autonomas + alertas.**
Fizemos a Peca 1 e a Peca 2. No meio, resolvemos uma crise de ambiente (branch).

---

## Principais pontos discutidos

- **Crise de ambiente:** uma sessao concorrente trocava a branch do working tree pra `main` e dava
  push sozinha. Decidimos **parar o processo concorrente** e **consolidar tudo na `main`** (merge da
  `feat/agentes-workspace`, 3 conflitos de CRM/sidebar resolvidos). Trabalhar na main e seguro **so
  porque o concorrente esta parado** e **nada e pushado** ate revisao.
- **Sistema de tools (decisao de arquitetura):** discutimos banco vs codigo. Concluido: **tool =
  registry em codigo** (igual os nos), **sem banco** (drift + o motivo do gestao, prompt no banco,
  nao existe mais com function-calling). O que o usuario queria (descoberta + anti-duplicacao) =
  **catalogo `TOOLS.md` GERADO do registry** + skill que consulta antes de criar.
- **Nao misturar Workspace e CRM:** `criar_tarefa` (tool, workspace) colidia com o NO `criar_tarefa`
  (CRM). Renomeado pra `criar_tarefa_workspace`; regra no skill.

---

## Decisoes tomadas

| Decisao | Motivo |
|---|---|
| Consolidar na `main` (merge da feat) | Acabar a briga de branch com o processo concorrente (parado) |
| Tool = registry em codigo, sem banco | Consistente com os nos; sem drift; function-calling nao precisa de prompt-no-banco |
| Catalogo `TOOLS.md` gerado por comando | Descoberta + anti-duplicacao sem manutencao manual nem drift |
| `tipo` (conhecimento/executavel) + `categoria` co-localizados no `@_tool` | Espelha o `ToolAgente` do gestao; tool se autodescreve |
| `criar_tarefa_workspace` (renomeado) | Nao confundir com tarefa do CRM |
| `explorar_codigo` so pro time tech, com travas | Seguranca (LLM nao le credencial); ruido pros executivos |
| `gerar_imagem` so pro time marketing | Criadores naturais; controla chamada externa (Gemini) |
| `faq_ia` descartada | Redundante (agente ja faz com consultar_base + salvar_documento) |
| Tools per-time via `TOOLS_EXTRA_POR_EQUIPE` no seed | Dar capacidade certa ao time certo |

---

## Pendencias

| Pendencia | Responsavel |
|---|---|
| **PUSH** (nada foi pushado; revisar commits juntos antes do deploy) | Lucas decide quando |
| Peca 3: Dashboard CEO (visao executiva cruzando os dados) | proxima |
| Peca 4: rotinas autonomas na engine + secao 4 (execucao diferida, briefing, travas, processo/SOP) + alertas | depois |
| Drift pre-existente em `notificacoes` (modelo vs migration) — nao meu, nao mexido | a revisar separado |
| Orfaos do automacao: `agente_salvar/excluir/simular/resumo` + templates antigos (UI redirecionada) | cleanup futuro |

---

## Estado do codigo (pra retomar)

- **Tudo na `main`, sem push.** Commits desta sessao: `428fd4c` (merge) → Peca 1 (`6c0b3c8`,
  `24d371a`, `cffa5e9`, `6b69558`, `90ebe43`, `46f567b`) → Peca 2 (`930ce7d`, `9fbf051`, `4e9b6e1`,
  `d132fac`, `264545f`, `62e13a6`) → Peca 3 (`cb51618`, `15e5b33`).
- **Peca 3:** Dashboard CEO em `/workspace/ceo/` — cockpit cruzando workspace+negocio+agentes +
  **briefing IA** (agente CEO le os dados pelas tools e da a leitura executiva) + follow-up. Tarefa #146.
- **Peca 1:** 6 campos no `automacao.Agente` (`equipe/cor/icone/prompt_autonomo/descricao/ordem`,
  migration `0009`); seed preenche time por subpasta do `AGENTES/`; roster `/workspace/agentes/`
  agrupado por time; editor CRUD completo no workspace; `/automacao/agentes/` redireciona.
- **Peca 2:** 23 tools no catalogo. CRUD de workspace (projeto/tarefa/etapa/documento),
  `explorar_codigo`, `gerar_imagem`. Sistema: `gerar_catalogo_tools` -> `docs/PRODUTO/modulos/
  automacao/TOOLS.md`; skill `.claude/skills/criar-tool/`; editor agrupado por categoria.
- **Ambiente:** banco dev = Docker `pgvector/pg17` na 5433 (settings_local default). Server dev na
  **8001** (`runserver 8001 --settings=gerenciador_vendas.settings_local`, exige `docker start
  hubtrix-pg17`). Tarefa Workspace #142 ("Hubtrix Desenvolvimento").
- Validado no browser (Playwright) + testes diretos das tools. `manage.py check` limpo.

---

## Peca 4 — rotinas autonomas NA ENGINE NOVA (design preliminar, pra retomar)

Decisao do Lucas: as rotinas rodam **sobre `apps/automacao`** (a engine ja tem infra de cron:
`execucao.py` rodar_novos/retomar_pendentes + `ExecucaoFluxo.agendado_para`). Rotina = um fluxo com
um no `ia_agente`, disparado periodicamente.

**O que falta construir:**
1. **Gatilho de agendamento/cron** — a engine tem trigger de evento/webhook, mas nao um TIME-based
   que INICIA um fluxo num intervalo. Criar um no `agendamento` (com `intervalo_horas`, como o
   `Automacao` do gestao) via skill `criar-no-automacao`.
2. **Atribuicao tarefa->agente** — a `Tarefa` precisa de um "agente responsavel" (FK pro Agente).
   `nivel_delegacao` JA existe na Tarefa (0=humano, 1-2=agente).
3. **Loop autonomo** — agente acorda -> le o backlog (tarefas dele com nivel_delegacao>=1) -> monta o
   briefing (campos `objetivo/contexto/passos/entregavel/criterios_aceite` JA existem na Tarefa,
   dormentes) -> executa/propoe (tools, incl. `solicitar_aprovacao`) -> registra em `log_execucao`.
4. **Travas anti-loop (CRITICO)** — limite de ciclos por execucao, limite de tools por ciclo, guard de
   custo (max chamadas LLM), `nivel_delegacao` como teto. Sem isso, agente roda em circulo / queima API.
5. **Alertas** — rotina detecta algo (churn alto, meta abaixo) -> cria um `Alerta` (model novo simples:
   tipo/severidade/lido/resolvido, ver gestao; tipos health/churn/metrica/erro) -> aparece no cockpit
   + pode virar Proposta.

**Secao 4 (a cola):** execucao diferida da Proposta (aprovar -> executa `dados_execucao`); briefing
executivo da Tarefa (campos dormentes usados no loop); processo/SOP (`Tarefa.documento_processo`
injetado no agente).

---

## Proximos passos

- [x] Peca 1, 2, 3 — feitas e validadas (na main, sem push).
- [ ] Peca 4: alinhar o design acima, depois construir (gatilho cron + atribuicao + loop + travas + alertas).
- [ ] Quando o Lucas decidir: revisar os commits e **pushar** (deploy).
