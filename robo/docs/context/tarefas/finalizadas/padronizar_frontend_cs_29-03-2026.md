---
name: "Padronizar frontend do módulo CS"
description: "Os templates do módulo CS (clube, parceiros, indicacoes, carteirinha) foram migrados do megaroleta e ainda usam o layout"
prioridade: "🟡 Média"
responsavel: "CTO"
---

# Padronizar frontend do módulo CS — 29/03/2026

**Data:** 29/03/2026
**Responsável:** CTO
**Prioridade:** 🟡 Média
**Status:** 🔧 Em andamento

---

## Descrição

Os templates do módulo CS (clube, parceiros, indicacoes, carteirinha) foram migrados do megaroleta e ainda usam o layout antigo (base.html próprio com topbar/sidebar do megaroleta). O `extends` já foi trocado para `vendas_web/base.html`, mas os estilos internos (CSS inline, classes, cores) ainda não seguem o design system do hub.

Padronizar para usar as classes e variáveis CSS do hub (mesma abordagem aplicada no CRM).

---

## Tarefas

- [ ] Padronizar templates do clube/dashboard (home, premios, participantes, gamificacao, banners, config, etc.)
- [ ] Padronizar templates do parceiros/dashboard (home, parceiros, cupons, cupom_detalhe)
- [ ] Padronizar templates do indicacoes/dashboard (home, indicacoes, visual)
- [ ] Padronizar templates do carteirinha/dashboard (home, modelos, regras, preview)
- [ ] Garantir que modais usem .modal-overlay com display:none
- [ ] Remover referências a cores hardcoded, usar CSS variables

---

## Contexto e referências

- Design system: `vendas_web/static/vendas_web/css/dashboard.css`
- Variáveis: --primary (#3b82f6), --bg-page (#f8fafc), --border (#e5e7eb), etc.
- Classes: .page-header, .page-title, .stats-grid, .stat-card, .admin-table, .btn-primary, .btn-secondary, .card, .modal-overlay
- CRM já padronizado como referência

---

## Resultado esperado

Todas as páginas do módulo CS com visual consistente com o restante do hub (Comercial, CRM, Dashboard). Sem gradientes roxos, sem CSS inline extenso, usando variáveis e classes do design system.
