# Componentes novos do DS — 20/04/2026

**Data:** 20/04/2026
**Participantes:** Lucas Rocha, Tech Lead, PM
**Duração:** sessão longa (múltiplas trocas)

---

## Contexto

Durante a migração do módulo Marketing, o usuário percebeu que os cards de entidade (segmentos, campanhas, templates de email) estavam sendo construídos **inline** em cada template, duplicando HTML + CSS e gerando inconsistências visuais. O CLAUDE.md já tinha a regra "criar componente primeiro", mas na prática não foi seguida. A sessão virou a oportunidade de corrigir o curso e criar os componentes faltantes que serão reaproveitados em Leads, CRM, Dashboard, Inbox, CS etc.

---

## Principais pontos discutidos

### Reconhecimento da falha de processo
Eu (assistente) montei o mesmo padrão de card inline em 3 templates (campanhas, segmentos, email lista) sem parar pra extrair. O usuário pediu explicação se havia regra no CLAUDE.md — sim, havia, mas precisava de gatilho operacional pra pegar na hora.

**Regra de reforço salva em memória:** "Ao ver o 2º uso de um bloco visual inline, parar e extrair pra components/ antes de continuar. Vale pra card, header, grid, empty state, etc."

### Componentes criados (5)

| Componente | O que faz | Params principais |
|------------|-----------|-------------------|
| `entity_card.html` | Card clean estilo HubSpot pra listagens de entidade | icon, title, title_url, subtitle, metric_value/label, tag_variant/label, footer_meta, primary_action_*, secondary_action_* |
| `entity_table.html` | Versão linha do entity_card (mesmos params) — usada em modo lista | idem entity_card |
| `list_filters.html` | Barra de filtros com 2 modos: compact (tabs+search) ou grid (múltiplos campos) | `tabs` (lista) OU `fields` (lista), search_*, clear_url |
| `view_toggle.html` | Toggle cards ↔ lista com persistência em localStorage | storage_key, default_mode |
| `pagination.html` | Navegação a partir do `page_obj` do Django Paginator | page_obj, query (preserva filtros) |

Todos ganharam CSS em `templates/partials/_components_styles.html` e exemplos em `/design-system/componentes/`.

### Convenção de uso de filtros (decidido com o usuário)

| Modo | Quando usar | Telas candidatas |
|------|-------------|------------------|
| **A (compact)** | 1 dimensão de filtro + busca livre. "Escaneável". | Emails, Segmentos, Campanhas, Notificações, Templates de fluxo |
| **B (grid)** | 3+ critérios combináveis. "Investigativa". | Leads, Oportunidades (CRM), Tickets (Suporte), Inbox, Auditoria |

**Regra de bolso:** se você abre a tela pra "olhar o todo" → A. Se abre pra "filtrar até achar subconjunto específico" → B.

### Decisão sobre toggle cards ↔ lista
Usuário optou por investir agora em vez de adiar (evitar retrabalho quando volume crescer). Implicou criar view_toggle + entity_table + pagination juntos — ciclo fechado pra qualquer listagem futura.

### Bugs de CSS corrigidos no caminho
- `.field-icon` ficava invisível em inputs com lupa (sem `top`/`transform` pra centralizar; sem padding-left no input). Refatorado: ícone centralizado por default + padding no input via combinador `~`.
- `.block-action-btn` sem contraste sobre fundo escuro — fundo branco sólido + sombra forte + hover preenchido.
- `.block-type-badge` igualmente sem contraste — fundo slate-900 sólido.
- Cards do grid com alturas desalinhadas — wrapper `flex` + `.entity-card { flex:1; height:100% }` + `.entity-card-head { flex:1 }`.

### Aplicação prática
Os componentes foram aplicados em 3 telas completas:
- **Emails** — paginação server-side (`?status=&page=`), toggle, list_filters Modo A
- **Segmentos** — filtro client-side (cards + lista filtram juntos), toggle, pagination
- **Campanhas** — idem segmentos

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Criar os 5 componentes antes de continuar | Reforçar regra "2º uso → extrair". Pagamento imediato em 3 telas; mais 10+ telas futuras se beneficiam |
| Toggle cards ↔ lista agora em vez de depois | Evita retrabalho quando volume crescer; investimento único no DS |
| Paginação server-side (12 por página) | Simples via Django Paginator; preserva filtros na querystring |
| list_filters ter 2 modos em 1 componente | Params exclusivos (`tabs` vs `fields`) decidem o render — 1 lugar só pra manter |
| entity_card suportar `url` OU `onclick` nas ações | Permite usar em listagens com link (segmentos) e com JS callback (campanhas) sem duplicar componente |

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Aplicar entity_card + list_filters + view_toggle em Leads (quando migrar CRM/dashboard) | Tech Lead |
| Aplicar em Inbox / Suporte / CS quando chegar a vez | Tech Lead |

---

## Próximos passos

- [ ] Usar os novos componentes no CRM (próximo módulo a migrar)
- [ ] Se surgir padrão repetido no CRM (ex: kanban column, opportunity card), extrair antes de usar 2x
- [ ] Atualizar `templates/components/README.md` com os 5 componentes novos (hoje só lista candidatos iniciais)

---

## Artefatos gerados

- [components/entity_card.html](robo/dashboard_comercial/gerenciador_vendas/templates/components/entity_card.html)
- [components/entity_table.html](robo/dashboard_comercial/gerenciador_vendas/templates/components/entity_table.html)
- [components/list_filters.html](robo/dashboard_comercial/gerenciador_vendas/templates/components/list_filters.html)
- [components/view_toggle.html](robo/dashboard_comercial/gerenciador_vendas/templates/components/view_toggle.html)
- [components/pagination.html](robo/dashboard_comercial/gerenciador_vendas/templates/components/pagination.html)
- [design_system_components.html](robo/dashboard_comercial/gerenciador_vendas/templates/design_system_components.html) — 2 seções novas
- Memória de feedback: `feedback_extrair_componente_antes.md`
