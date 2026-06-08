---
name: "Email Builder — Marketing"
description: "Editor visual de e-mails com blocos programados no módulo Marketing"
prioridade: "🔴 Alta"
responsavel: "Claude + Lucas"
---

# Email Builder — 06/04/2026

**Data:** 06/04/2026
**Responsável:** Claude + Lucas
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Construir um editor visual de e-mails dentro do módulo Marketing, semelhante ao HubSpot e RD Station. O usuário monta e-mails arrastando blocos programados (texto, imagem, botão, colunas, etc.) com propriedades editáveis. Os templates são salvos como JSON e renderizados em HTML responsivo.

---

## Tarefas

### Fase 1 — Base
- [ ] Models: CategoriaTemplate, TemplateEmail, EnvioEmail
- [ ] App structure: apps/marketing/emails/
- [ ] Renderer: JSON de blocos → HTML responsivo
- [ ] Views + URLs: CRUD, editor, preview
- [ ] Admin
- [ ] Template: editor visual drag-and-drop com Sortable.js
- [ ] Template: lista de e-mails
- [ ] Registro no settings.py e urls.py

### Fase 2 — Templates prontos
- [ ] 5 a 8 templates base por categoria

### Fase 3 — Integração automações
- [ ] Nova ação "enviar email com template" no engine
- [ ] Seletor de template no editor de fluxos

### Fase 4 — Tracking
- [ ] Pixel de abertura
- [ ] Redirect de cliques
- [ ] Dashboard de métricas

---

## Contexto e referências

- Padrão de apps: TenantMixin, @login_required, JSONField para dados visuais
- Editor de fluxos (automacoes) como referência de UX
- Engine de automações já tem ação enviar_email (texto puro via N8N)

---

## Resultado esperado

Editor funcional onde o usuário cria e-mails visuais com blocos programados, salva como template e visualiza preview desktop/mobile.
