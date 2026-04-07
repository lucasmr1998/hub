---
name: "Migração do módulo CS (megaroleta) para o hub"
description: "Migrar o módulo CS (Clube de Benefícios) do projeto megaroleta para dentro do hub, integrando os apps, models, URLs e te"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Migração do módulo CS (megaroleta) para o hub — 29/03/2026

**Data:** 29/03/2026
**Responsável:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ✅ Concluída

---

## Descrição

Migrar o módulo CS (Clube de Benefícios) do projeto megaroleta para dentro do hub, integrando os apps, models, URLs e templates ao layout unificado do vendas_web.

---

## Tarefas

- [x] Migrar 4 apps do megaroleta: clube, parceiros, indicacoes, carteirinha
- [x] Migrar 20 models para o hub
- [x] Migrar 76 URLs
- [x] Migrar 67+ templates
- [x] Integrar templates CS ao layout do hub (estendem vendas_web/base.html)
- [x] Criar sidebar CS com sub-seções: Clube, Parceiros, Carteirinhas, Indicações
- [x] Resolver conflitos CSS com modais (display:none inline)
- [x] Definir CRM do parceiro com 5 estágios (Lead identificado, Em contato, Em negociação, Trial ativo, Finalizada)

---

## Contexto e referências

- Reunião: `docs/context/reunioes/tech_refatoracao_29-03-2026.md`
- Projeto origem: `megaroleta/` (somente leitura)
- Decisão: app Gestão (17 models, agentes IA) NÃO migra para o hub

---

## Resultado esperado

Módulo CS completamente integrado ao hub com 4 apps funcionais, templates unificados e sidebar de navegação. Pendente refinamento visual e substituição de URLs hardcoded.
