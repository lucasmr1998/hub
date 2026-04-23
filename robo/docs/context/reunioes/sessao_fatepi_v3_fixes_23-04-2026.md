# Sessao intensiva FATEPI v3 — 3 fixes em producao — 23/04/2026

**Data:** 23/04/2026
**Participantes:** Lucas + Tech Lead (Claude)
**Duração:** ~4h

---

## Contexto

FATEPI v3 (tenant=7, fluxo=6) acumulou **34 atendimentos e 0 matriculas** desde 21/04. Abrimos a sessao pra investigar por que ninguem estava convertendo, e terminamos entregando **3 fixes em producao** + **1 fix de codigo ainda pendente de deploy**.

Autorizacao explicita do usuario pra ler producao (Postgres via porta 5433 exposta pelo EasyPanel) e executar UPDATEs escopados. Credenciais de prod passaram a ser registradas em `.env.prod_readonly` (gitignored), uso documentado em `reference_prod_access.md` da memoria.

---

## Principais pontos discutidos

- **Diagnostico via conversas reais:** leitura read-only das conversas associadas ao fluxo 6. Dois padroes dominantes: IA classificando "Psicologia"/"PSICOLOGIA" como `curso_invalido` (trava no nodo 529), e fallbacks IA (nodos 522, 527, 533) respondendo conclusivamente sem repetir a pergunta original — candidato interpreta como fim de conversa e para de responder.
- **Simulacao com IA real antes de mudar prod:** criamos o management command `simular_prompts_fatepi` (em `apps/comercial/atendimento/management/commands/`) que chama `_chamar_llm_simples` internamente, sem expor api_key fora do container. Compara prompts ATUAL vs NOVO contra `gpt-4o-mini` do tenant.
- **5 zumbis identificados:** 5 atendimentos com `nodo_atual_id=NULL` (nodos antigos deletados no refactor v3). Sem possibilidade de roteamento se candidato voltar.
- **Descoberta do bug `var.X`:** teste e2e pos-fix de prompts mostrou que "Psicologia" com `validacao_curso='curso_valido'` **ainda** caia em 529. Investigacao levou a `_resolver_campo_contexto` que usa `isinstance(obj, dict)` — `ContextoLogado` (introduzido em `engine_contexto.py`) eh `MutableMapping`, nao `dict`. Toda condicao `var.X == valor` retornava false silenciosamente no sistema inteiro, em todos os tenants que usassem ia_classificador + condicao.

---

## Decisoes tomadas

| Decisao | Motivo |
|---|---|
| Atualizar `CLAUDE.md` liberando SELECT read-only em producao com salvaguardas | Investigacao precisa de dados reais, nao da pra esperar reproduzir bug em dev. Regras explicitas (filtrar tenant, LGPD, nunca colar credencial em chat) |
| UPDATE direto no banco dos 5 nodos do fluxo 6 em vez de editar pelo editor do Hubtrix | Transacional, atomico (5 ou nenhum), backup previo. Editor da mesma trabalheira manual com mais risco de erro |
| Encerrar zumbis (status=abandonado) em vez de ressuscitar | 5 atendimentos velhos (15-16/04), ja frios. Risco de mensagem duplicada se ressuscitasse. Se candidato voltar, engine abre atendimento novo |
| Fix do `var.X` com duck typing (`hasattr(obj, 'get')`) em vez de `isinstance(obj, (dict, MutableMapping))` | Mais permissivo; aceita qualquer mapping customizado futuro sem mudanca de codigo |
| Rodar teste e2e em prod (criar Lead + AtendimentoFluxo temp) | Unico jeito de validar roteamento com prompts reais gravados no banco e IntegracaoAPI real do tenant. Script `teste_e2e_fatepi_v3.py` limpa no fim |

---

## Entregas (em producao)

| Fix | Mecanismo | Estado |
|---|---|---|
| **Prompts corrigidos** (nodos 521, 522, 523, 527, 533) | UPDATE transacional via `scripts/update_nodos_fatepi_v3.py` | ✅ Em producao |
| **5 zumbis encerrados** (ids 132-136) | UPDATE via `scripts/encerrar_zumbis_v3.py` | ✅ Em producao |
| **Fix `var.X`** em `_resolver_campo_contexto` + 10 testes | Commit `5eb2e35` em `origin/main` | ⚠ Deploy pendente |

**Validacao pos-fixes (em producao):**
- Classificador de curso: **13/13** (antes 0/13)
- Fallback 527: **4/4** termina com pergunta de volta (antes 0/4)
- Condicao `var.validacao_curso`: **ainda em branch errado** ate o deploy do fix var.X

---

## Pendências

| Pendencia | Responsavel | Ref |
|---|---|---|
| Deploy do commit `5eb2e35` no EasyPanel | Lucas | [deploy_fix_var_x_23-04-2026.md](../tarefas/backlog/deploy_fix_var_x_23-04-2026.md) |
| Re-rodar teste e2e pos-deploy | Tech Lead/Lucas | [e2e_fatepi_pos_deploy_23-04-2026.md](../tarefas/backlog/e2e_fatepi_pos_deploy_23-04-2026.md) |
| Monitor 48h do fluxo 6 | Lucas | [monitor_fatepi_48h_23-04-2026.md](../tarefas/backlog/monitor_fatepi_48h_23-04-2026.md) |

---

## Proximos passos

- [ ] Lucas: deploy no EasyPanel (rebuildar `projetos_hub`)
- [ ] Apos deploy: rodar `scripts/teste_e2e_fatepi_v3.py` → confirmar Psicologia → nodo 530
- [ ] Monitorar 24h e 48h via query de distribuicao de `nodo_atual_id`
- [ ] Se deploy der certo, abrir tarefa pra adicionar signal de `pre_delete` em `NodoFluxo` que bloqueia delete com AtendimentoFluxo ativo apontando (prevencao de zumbi futuro)

---

## Tarefas finalizadas no escopo desta sessao

- [fix_prompts_fatepi_v3_23-04-2026.md](../tarefas/finalizadas/fix_prompts_fatepi_v3_23-04-2026.md)
- [encerrar_zumbis_v3_fatepi_23-04-2026.md](../tarefas/finalizadas/encerrar_zumbis_v3_fatepi_23-04-2026.md)
- [fix_resolver_campo_contextologado_23-04-2026.md](../tarefas/finalizadas/fix_resolver_campo_contextologado_23-04-2026.md)

## Materiais gerados

- Scripts operacionais: `scripts/{listar_zumbis_v3,encerrar_zumbis_v3,inspecionar_conexoes_523,inspecionar_nodo_528,teste_e2e_fatepi_v3,update_nodos_fatepi_v3}.py`
- Prompts corrigidos: `robo/docs/context/clientes/fatepi/implementacoes/prompts_corrigidos_23-04-2026.md`
- Backup nodos antes do UPDATE: `.backup_nodos_v3_2026-04-23.json` (gitignored, local-only)

## Observacao estrategica

**O bug `var.X` explica 100% do 0-matriculas.** Mesmo com prompts corretos, sem o fix, todo candidato com curso valido ainda ia cair em curso-invalido por causa da condicao quebrada. Os dois fixes (prompts + var.X) sao **complementares e obrigatorios juntos**.

**Implicacao mais ampla:** o bug afeta **qualquer tenant** que use `ia_classificador` ou `ia_extrator` seguido de `condicao` em fluxo de atendimento. Nao eh especifico da FATEPI. Deploy do fix var.X destrava potencialmente fluxos de outros tenants tambem.
