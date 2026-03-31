---
name: "Corrigir erros JS no sistema de navegação SPA"
description: "navigateTo() injeta scripts duplicados causando NotificationSystem/API_URLS already declared e null references"
prioridade: "🔴 Alta"
responsavel: "Dev / Tech Lead"
---

# Corrigir Erros JS no Sistema de Navegação SPA — 31/03/2026

**Data:** 31/03/2026
**Responsável:** Dev / Tech Lead
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

O `base.html` tem um sistema de navegação SPA que usa `navigateTo()` para carregar páginas via fetch e injetar o HTML no DOM. Ao navegar entre páginas, scripts inline são re-executados causando erros de variáveis duplicadas (`NotificationSystem`, `API_URLS` already declared) e referências nulas (elementos DOM que não existem na página atual).

---

## Tarefas

- [ ] Investigar o sistema navigateTo() no base.html
- [ ] Identificar todos os scripts inline que declaram variáveis globais
- [ ] Corrigir injeção duplicada de scripts
- [ ] Corrigir referências a elementos DOM null
- [ ] Testar navegação entre Dashboard, Comercial, Marketing, CS, Relatórios

---

## Contexto e referências

- Erros no console: NotificationSystem already declared, API_URLS already declared, Cannot read properties of null
- Arquivo: apps/sistema/templates/sistema/base.html (função navigateTo)
- Afeta: navegação SPA entre módulos

---

## Resultado esperado

Navegação SPA sem erros no console. Todos os módulos acessíveis sem reload de página.
