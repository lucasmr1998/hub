---
name: "Unificar retencao em apps/cs/retencao/"
description: "Consolidar os dois apps duplicados de retencao (comercial/crm vs cs/retencao) num unico lugar coerente com o dominio (CS)"
prioridade: "🟢 Baixa"
responsavel: "Tech Lead"
---

# Unificar retencao em apps/cs/retencao/ — 20/04/2026

**Data:** 20/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟢 Baixa
**Status:** ⏳ Aguardando

---

## Descrição

Existem **dois apps de retencao** no projeto hoje:

1. **`apps/comercial/crm/`** — implementacao em uso:
   - Model `AlertaRetencao` em `crm/models.py`
   - View `retencao_view` em `crm/views.py:1177`
   - Template `crm/templates/crm/retencao.html` (migrado pro DS em 2026-04-20)
   - URL `/crm/retencao/`

2. **`apps/cs/retencao/`** — app embrionario criado mas nao implementado:
   - Models novos: `ScoreCliente` (health score 0-100), `AlertaChurn` (alerta de cancelamento)
   - `views.py` com 2 linhas, `urls.py` com 5 linhas — sem view funcional
   - Foi criado como "proxima versao" mas nao conectou

**Problema:** retencao e função CS (pos-venda, manter clientes), nao CRM (pre-venda, oportunidades). O codigo esta no app errado e tem duplicacao de intencao. O link do sidebar ja esta no submenu CS, apontando pra URL do CRM.

---

## Tarefas

- [ ] **Decidir produto:** `AlertaRetencao` (CRM atual) e `AlertaChurn` (CS embrionario) sao a mesma entidade com nomes diferentes, ou dois conceitos coexistentes? Decidir antes de mexer no codigo.
- [ ] **Mover model:** `AlertaRetencao` sai de `crm/models.py` e vai pra `cs/retencao/models.py`. Requer migration com `db_table` override pra manter mesma tabela no PostgreSQL (senao precisa renomear em prod — risco).
- [ ] **Mover view + URL:** `retencao_view` sai de `crm/views.py` e vai pra `cs/retencao/views.py`. URL passa de `/crm/retencao/` pra `/cs/retencao/`. Adicionar redirect `/crm/retencao/ → /cs/retencao/` pra nao quebrar bookmarks.
- [ ] **Mover template:** `crm/templates/crm/retencao.html` + `_retencao_row.html` → `cs/retencao/templates/retencao/`.
- [ ] **Atualizar imports:** 13 arquivos referenciam `AlertaRetencao` ou rota retencao (grep mostrou):
  - `apps/comercial/crm/admin.py`
  - `apps/integracoes/management/commands/seed_demo_vendas.py`
  - `apps/sistema/management/commands/seed_planos.py`
  - Qualquer signal, management command ou cron que use o model.
- [ ] **Atualizar sidebar:** `partials/sidebar_subnav.html` linha 124 — trocar `/crm/retencao/` por `/cs/retencao/`.
- [ ] **Migrations de banco:** testar em SQLite (`settings_local`), depois em PostgreSQL (`settings_local_pg`), antes de rodar em prod.
- [ ] **Tests:** garantir que tests existentes de retencao passam apos o move; adicionar smoke test da nova URL.
- [ ] **Doc:** atualizar `robo/docs/PRODUTO/modulos/cs/` com o modulo de retencao agora oficializado em CS.

---

## Contexto e referências

- Template migrado (versao CRM atual): [apps/comercial/crm/templates/crm/retencao.html](robo/dashboard_comercial/gerenciador_vendas/apps/comercial/crm/templates/crm/retencao.html)
- App embrionario: [apps/cs/retencao/](robo/dashboard_comercial/gerenciador_vendas/apps/cs/retencao/)
- Model atual: `apps/comercial/crm/models.py` (classe `AlertaRetencao`)
- Reunião que levantou o problema: [planejamento_migracao_crm_20-04-2026.md](robo/docs/context/reunioes/planejamento_migracao_crm_20-04-2026.md)

---

## Resultado esperado

- Retencao vive em `apps/cs/retencao/` (codigo coerente com dominio).
- URL `/cs/retencao/` e a canonica; `/crm/retencao/` redireciona pra ela.
- Sidebar aponta pra URL nova.
- Zero break em producao (migration testada + redirect pra URLs antigas).
- `AlertaChurn` (embrionario) tem decisao tomada: ou vira o model principal (substitui `AlertaRetencao`), ou e removido, ou coexiste documentado.
