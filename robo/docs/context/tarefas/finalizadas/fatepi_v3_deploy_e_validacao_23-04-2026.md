---
name: "FATEPI v3 — deploy do fix var.X + E2E + monitoramento (CONCLUÍDA)"
description: "Workstream sequenciado: deploy do fix var.X em prod, E2E e monitor de distribuição. Concluída em 27/04/2026."
prioridade: "🔴 Alta"
responsavel: "Lucas + Tech Lead"
status: "✅ Concluída"
---

# FATEPI v3 — Deploy + Validação + Monitor

**Início:** 23/04/2026
**Conclusão:** 27/04/2026
**Status:** ✅ **Concluída — fix validado em prod**

---

## Resultado das 3 fases

### ✅ Fase 1 — Deploy
- Commit `5eb2e35` (fix var.X + 10 testes) deployado em prod via EasyPanel.
- Container `projetos_hub` reinicializado com sucesso.

### ✅ Fase 2 — E2E em prod (27/04/2026)
Script `teste_e2e_fatepi_v3.py` rodado dentro do container `projetos_hub` via console EasyPanel. Criou 1 lead temp + atendimento, simulou 3 mensagens, deletou tudo no fim.

**Trajetória do fluxo:**
| Passo | Resposta | Nodo (antes → depois) | Tipo |
|-------|----------|-----------------------|------|
| 1 (nome) | "Lucas Teste QA" | start → 521 → 523 | questao/texto |
| 2 (curso) | **"Psicologia"** | 523 → 532 | questao/texto |
| 3 (ingresso) | **"ENEM"** | 532 → 535 | ia_respondedor |

**Evidências do fix funcionando:**
- ✅ `variaveis.validacao_curso=curso_valido` — comparação `var.X == valor` retornou TRUE (era o que falhava antes)
- ✅ `oport_dados_custom_curso_interesse=Psicologia`, `forma_ingresso=ENEM` gravados
- ✅ Log do engine: `"Oportunidade ja existe para lead 255, dados_custom atualizados"` — alcançou a ação `criar_oportunidade`, não travou no nodo 529 ("curso inválido")
- ✅ Cleanup limpo: 1 atendimento + 21 logs + 1 lead removidos

**IDs diferentes da spec original (530 → 532)** porque o fluxo foi reeditado entre 23/04 e 27/04. Lógica de roteamento condicional confirmada.

### ✅ Fase 3 — Monitor (27/04/2026)
Query rodada via psycopg2 contra DB prod read-only.

**Achado relevante: fluxo v3 não está mais em uso operacional.**
- Fluxo 6 (FATEPI v3): zero atendimentos nas últimas 48h. Último em **21/04 às 15:01**.
- Fluxo 15 ("Inicial"): 8 atendimentos nas últimas 48h, todos com `status=transferido` e `nodo_atual=None` — transfere direto pro humano sem processar nodos.
- 5 atendimentos zumbis em fluxo 6 (ids 164–168, status=iniciado desde 20-21/04, presos sem progredir — bug pré-fix, agora histórico).

**Conclusão:** o fix técnico funciona, mas o fluxo v3 foi desativado em prod entre 21/04 e 27/04. Time decidiu rodar com o fluxo Inicial (handoff humano) em vez do v3. **Não é bloqueador de receita atualmente.**

---

## Pendências derivadas (entram em outras tarefas/decisões)

- [ ] **Decidir o destino do v3:** vale reativar agora que o fix está validado? Ou abandonar definitivamente?
- [ ] **Limpar zumbis:** os 5 atendimentos travados (ids 164–168, fluxo 6) podem ser fechados com `status=cancelado` e motivo "bug var.X (pré-fix), órfão"
- [ ] **Investigar transição v3 → Inicial:** entender por que houve o switchover (decisão consciente ou rollback emergencial?)

Vale criar uma tarefa nova `fatepi_decisao_v3_27-04-2026.md` no backlog se quiser tratar essas pendências.

---

## Histórico

- **23/04:** 3 tarefas separadas criadas (deploy, E2E, monitor)
- **26/04:** consolidadas em workstream único
- **~24/04 a 26/04:** deploy do fix em prod
- **21/04 → 27/04:** decisão de produto/operação levou ao switch de v3 → Inicial (não relacionado ao fix)
- **27/04:** Fase 2 + Fase 3 executadas com sucesso. Tarefa fechada.
