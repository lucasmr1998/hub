# Planejamento migração DS — CRM — 20/04/2026

**Data:** 20/04/2026
**Participantes:** Lucas Rocha, PM
**Duração:** curta (alinhamento de escopo)

---

## Contexto

Com Marketing fechado (escopo revisado — sem Automações), o próximo módulo na fila de migração DS é o **CRM** (Fase 2B do plano macro). Antes de atacar, fizemos o inventário e definimos ordem.

---

## Principais pontos discutidos

### Inventário do CRM (15 templates)

| Template | Status |
|----------|--------|
| `segmentos_lista.html` | ✅ Migrado (veio na onda de Marketing) |
| `segmento_criar.html` | ✅ Migrado |
| `segmento_detalhe.html` | ✅ Migrado |
| `_tarefa_card.html` | Partial — não conta como página |
| `pipeline.html` | ⏳ Pendente |
| `oportunidades_lista.html` | ⏳ Pendente |
| `oportunidade_detalhe.html` | ⏳ Pendente |
| `tarefas_lista.html` | ⏳ Pendente |
| `metas.html` | ⏳ Pendente |
| `desempenho.html` | ⏳ Pendente |
| `equipes.html` | ⏳ Pendente |
| `produtos.html` | ⏳ Pendente |
| `configuracoes_crm.html` | ⏳ Pendente |
| `retencao.html` | ⏳ Pendente — possivelmente migra para CS |

**Sobram 11 páginas pra migrar (10 se `retencao` for pra CS).**

### Ordem proposta
1. **pipeline.html** (kanban) — tela de entrada, define padrão visual, pode revelar componentes faltantes (kanban column, opportunity card)
2. **oportunidade_detalhe.html** — kanban clica e leva pra detalhe
3. **oportunidades_lista.html** — reuso do entity_card já pronto
4. **tarefas_lista.html**, **metas.html**, **desempenho.html** (bloco gestão)
5. **equipes.html**, **produtos.html**, **configuracoes_crm.html** (bloco admin)
6. **retencao.html** — última, ou migra com CS

### Ritmo confirmado
**1-a-1 com checkpoint do usuário** — mesma cadência que valeu pra Leads e Marketing. Sem lote.

### Pergunta em aberto
`retencao.html` está hoje em `apps/comercial/crm/` mas o nome sugere função CS (retenção/churn). A decidir: migrar junto com CRM ou deixar pra fase de CS.

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Próximo módulo = CRM | Core do comercial, alta visibilidade, 80% das telas que vendedor vê diariamente |
| Começar pela pipeline | Tela mais visualizada, define padrão visual do módulo |
| Manter ritmo 1-a-1 com checkpoint | Valeu para Leads e Marketing — evita retrabalho em lote |

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Decidir destino de `retencao.html` (CRM ou CS) | Lucas — responde quando chegar a vez |
| Migrar 10–11 páginas do CRM (pipeline primeiro) | Tech Lead |

---

## Próximos passos

- [ ] Arrancar pela **pipeline.html**
- [ ] Após cada página, aguardar checkpoint do usuário antes da próxima
- [ ] Identificar componentes novos do DS necessários (candidatos iniciais: `kanban_column`, `opportunity_card`) e extrair antes de usar 2x
- [ ] Após CRM: Dashboard (12 templates), depois Inbox (Fase 2C)
