---
name: "Testes automatizados de isolamento de tenant"
description: "Escrever testes automatizados que garantam o isolamento correto de dados entre tenants. Cada tenant deve enxergar apenas"
prioridade: "🔴 Alta"
responsavel: "QA / Tech Lead"
---

# Testes automatizados de isolamento de tenant — 29/03/2026

**Data:** 29/03/2026
**Responsável:** QA / Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Escrever testes automatizados que garantam o isolamento correto de dados entre tenants. Cada tenant deve enxergar apenas seus próprios registros, e nenhuma operação deve vazar dados entre tenants.

---

## Tarefas

- [ ] Criar fixtures de teste com múltiplos tenants
- [ ] Testar que queries via TenantManager filtram corretamente por tenant
- [ ] Testar que o TenantMiddleware atribui o tenant correto ao request
- [ ] Testar que criação de registros atribui automaticamente o tenant do usuário
- [ ] Testar que um usuário de um tenant não consegue acessar dados de outro tenant
- [ ] Testar que o Painel Admin Aurora lista apenas dados do tenant correto
- [ ] Testar cenários de erro: usuário sem tenant, tenant inativo, tenant inexistente
- [ ] Integrar testes ao pipeline de CI

---

## Contexto e referências

- Reunião: `docs/context/reunioes/tech_refatoracao_29-03-2026.md`
- Tarefa concluída: `docs/context/tarefas/finalizadas/refatoracao_apps_29-03-2026.md`
- Depende de: deploy do multi-tenancy (pode rodar em ambiente local antes do deploy)

---

## Resultado esperado

Suite de testes automatizados cobrindo todos os cenários de isolamento de tenant, executável localmente e no CI. Qualquer vazamento de dados entre tenants deve ser detectado automaticamente.
