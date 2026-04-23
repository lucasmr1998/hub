# Sessao — documentacao de atendimento/marketing + estrategia de testes — 23/04/2026

**Data:** 23/04/2026
**Participantes:** Lucas + PM/Tech Lead (Claude)
**Duração:** ~2h (continuacao da [sessao FATEPI v3](sessao_fatepi_v3_fixes_23-04-2026.md))

---

## Contexto

Apos resolver os fixes da FATEPI v3, a preocupacao do usuario foi estrategica: **atendimento e automacoes de marketing sao as duas partes mais complexas do sistema**, e um bug (var.X) ficou latente semanas sem ninguem notar. Pergunta orientadora: **como garantir que isso nao se repita?**

Duas frentes foram levantadas: **doc** (qual eh o estado hoje?) e **testes** (onde tem buraco estrutural?).

---

## Principais pontos discutidos

### 1. Estado da documentacao antes da sessao

**Atendimento:** 8 arquivos, 528 linhas. Cobre bem engine, integracao inbox, sessoes, recontato. Faltava: catalogo de tipos de nodo, exemplo comentado ponta a ponta, debug playbook. Consequencia pratica: pra entender o bug do `var.X` tive que ler 2500 linhas de `engine.py`.

**Marketing/Automacoes:** 7 arquivos, 918 linhas. Bem melhor coberto (engine, signals, editor, endpoints, reguas padrao como spec). Faltava: exemplo comentado, debug playbook, separacao do que esta implementado vs spec em `reguas-padrao.md`.

### 2. Estado dos testes antes da sessao

- **Atendimento:** 20+ testes unit de nodos, mas nenhum percorria ContextoLogado com dot notation (`var.X`). Por isso o bug passou. Zero teste percorrendo fluxo real de 20+ nodos.
- **Marketing:** 18 testes E2E no command `testar_automacoes`. Razoavel. Mas 2 eventos marcados "pendente implementacao" (venda_aprovada, cliente_aniversario).
- **Cron de producao:** zero teste direto. So validado em prod.

### 3. Plano de doc (acordado)

4 itens, em ordem de valor:
1. **Catalogo de tipos de nodo** (atendimento) — alto valor pro consultor/dev montando fluxo
2. **Fluxo de exemplo comentado** (FATEPI v3 como caso real)
3. **Emails (marketing)** — subpasta zero
4. **Glossario**

Fizemos **1, 2 e um combinado marketing (exemplo C02 + debug playbook)** na sessao. Emails e glossario ficaram em aberto.

### 4. Estrategia de testes (3 opcoes discutidas)

1. **Fixture de fluxo real + e2e percorrimento** (~1 dia) — exportar fluxo v3 FATEPI, teste percorre com LLM mockado
2. **Cobrir matriz variaveis IA × condicao** (~2 dias) — parametrizado, cobre mais combos
3. **Smoke "regras certas por tenant"** (~3 dias) — CI executa fluxos de cada tenant como gate

Decisao: **opcao 1** primeiro (cobre caso concreto que bugou, 20% do esforco pra 80% do risco). Opcao 3 fica pra depois.

---

## Decisoes tomadas

| Decisao | Motivo |
|---|---|
| Criar `tipos-de-nodo.md` no atendimento como catalogo-contrato | Fonte unica de "o que cada nodo aceita e devolve". Antes vivia so no codigo |
| Usar FATEPI v3 como exemplo real para atendimento | Bateu com bug que acabara de acontecer; caso concreto ensina mais que caso hipotetico |
| Usar regua C02 (spec) como exemplo para automacoes, com aviso explicito no topo | Spec ja existia em `reguas-padrao.md`; nao vale criar regua nova so pra doc; aviso impede confusao com o caso FATEPI que e producao |
| Gate de CI para engine.py entra como **tarefa separada**, nao decisao imediata | Afeta todos os PRs futuros, melhor o Lucas aprovar o YAML exato antes |
| Nao fazer deploy automatico — abrir tarefa manual | Deploy em prod continua manual (EasyPanel), fora do escopo do CI atual |

---

## Entregas

### Documentacao criada

| Arquivo | Linhas | Conteudo |
|---|---|---|
| [atendimento/tipos-de-nodo.md](../../PRODUTO/modulos/atendimento/tipos-de-nodo.md) | ~230 | Catalogo dos 11 tipos de nodo — campos aceitos, saidas, exemplo JSON |
| [atendimento/exemplo-fluxo-ia.md](../../PRODUTO/modulos/atendimento/exemplo-fluxo-ia.md) | ~160 | FATEPI v3 ponta a ponta — 3 jornadas (Lucas/Fernanda/Joao) + como debugar + armadilhas |
| [marketing/automacoes/exemplo-automacao.md](../../PRODUTO/modulos/marketing/automacoes/exemplo-automacao.md) | ~220 | C02 comentada — grafo + 2 jornadas + 6 queries de debug + 7 armadilhas conhecidas |
| [atendimento/engine.md](../../PRODUTO/modulos/atendimento/engine.md) | +30 | Secao nova "Contexto e resolucao de campos" com duck typing + regressao do bug |

### Testes criados

- `tests/test_engine_nodos.py`: +10 testes (`TestResolverCampoContexto` + `TestCondicaoComVarContextoLogado`)
- Suite completa pos-fix: **901 passed, 4 skipped, 61 xfailed, 16 xpassed**

### Commits em origin/main

| Commit | Conteudo |
|---|---|
| `5eb2e35` | Fix `_resolver_campo_contexto` + 10 testes |
| `d945611` | Docs novas (tipos-de-nodo + exemplo-fluxo-ia + exemplo-automacao) |
| `826b333` | Scripts FATEPI + finalizadas + `.gitignore` blindado `.backup_*` |
| `f8c3645` | 5 tarefas manuais de backlog |

---

## Pendências (tarefas manuais criadas)

| Tarefa | Responsavel | Link |
|---|---|---|
| Deploy do fix var.X (EasyPanel) | Lucas | [deploy_fix_var_x_23-04-2026.md](../tarefas/backlog/deploy_fix_var_x_23-04-2026.md) |
| Re-rodar e2e pos-deploy | Lucas/Tech Lead | [e2e_fatepi_pos_deploy_23-04-2026.md](../tarefas/backlog/e2e_fatepi_pos_deploy_23-04-2026.md) |
| Gate CI pra engine.py | Tech Lead | [ci_gate_engine_py_23-04-2026.md](../tarefas/backlog/ci_gate_engine_py_23-04-2026.md) |
| Fixture fluxo real + e2e no CI | Tech Lead | [fixture_fluxo_real_e2e_23-04-2026.md](../tarefas/backlog/fixture_fluxo_real_e2e_23-04-2026.md) |
| Monitor 48h FATEPI | Lucas | [monitor_fatepi_48h_23-04-2026.md](../tarefas/backlog/monitor_fatepi_48h_23-04-2026.md) |

---

## Proximos passos (doc que ficou em aberto)

- [ ] Item 3 do plano: criar subpasta `marketing/emails/` (hoje zero docs)
- [ ] Item 4: glossario unificado dos termos de fluxo/automacao
- [ ] Separar em `reguas-padrao.md` o que esta implementado do que e spec

---

## Avaliacao final da sessao (pergunta do usuario "estamos seguros?")

Resposta direta: **ainda nao totalmente**. Doc melhorou; testes ganharam rede nas areas criticas; mas:

1. Fix `var.X` esta em main, **nao em prod** — nao vai ter efeito ate o deploy
2. Sem gate de CI, o proximo var.X pode voltar
3. Fixture de fluxo real ainda nao foi feita

**Pra chegar no "seguro" de verdade:** deploy → validar e2e → gate de CI → fixture e2e. Com essas 4 etapas concluidas, proxima regressao desse tipo eh pega automaticamente.

---

## Observacoes de processo

- **Auto mode + hook de agente funcionou bem** — hook classificador obrigatorio + auto-mode fluido mantiveram ritmo sem default em Tech Lead.
- **Separacao de commits ajudou a auditoria** (fix critico / docs / scripts / tarefas) — um revisor consegue isolar risco em `5eb2e35` sem sair pra ler tudo.
- **CLAUDE.md foi atualizado durante a sessao** (secao Banco de Dados liberando SELECT com salvaguardas). Referencia de credenciais prod agora em arquivo gitignored.
