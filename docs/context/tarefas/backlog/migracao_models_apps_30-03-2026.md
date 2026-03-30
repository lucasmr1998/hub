---
name: "Limpeza de Apps Legados e Imports"
description: "Os models já foram migrados para os apps modulares (29/03). Restavam apps legados duplicados e imports antigos. A limpez"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# Limpeza de Apps Legados e Imports — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Os models já foram migrados para os apps modulares (29/03). Restavam apps legados duplicados e imports antigos. A limpeza principal foi concluída em 30/03.

---

## Tarefas

- [x] Remover `crm/` (raiz) do `INSTALLED_APPS` — substituído por `apps.comercial.crm`
- [x] Remover `integracoes/` (raiz) do `INSTALLED_APPS` — substituído por `apps.integracoes`
- [x] Registrar `apps.comercial.crm` e `apps.integracoes` no `INSTALLED_APPS`
- [x] Migrar imports de `from vendas_web.models import X` para `from apps.X.models import X` (~40 arquivos)
- [x] Migrar imports de `from crm.models import X` para `from apps.comercial.crm.models import X`
- [x] Migrar imports de `from integracoes.*` para `from apps.integracoes.*`
- [x] Mover middleware (LoginRequiredMiddleware) para `apps.sistema.middleware`
- [x] Mover context_processors para `apps.sistema.context_processors`
- [x] Atualizar URLs para usar `apps.integracoes.urls` em vez de `integracoes.urls`
- [x] Registrar apps CS e admin_aurora no settings.py principal
- [x] Corrigir settings_local.py para herdar INSTALLED_APPS do settings.py
- [x] `manage.py check` passando (0 erros)
- [x] 16 testes de isolamento passando
- [ ] Remover monkey-patch de User em `vendas_web/models.py`
- [ ] Migrar views/URLs do `vendas_web` para apps modulares (escopo grande, tarefa separada)
- [ ] Remover pastas `crm/` e `integracoes/` legadas da raiz (após validação em produção)

---

## Contexto e referências

- Refatoração concluída: `finalizadas/refatoracao_apps_29-03-2026.md`
- `vendas_web/models.py` é re-export (zero models próprios), mantido por compatibilidade de views
- `crm/` e `integracoes/` na raiz removidos do INSTALLED_APPS, imports atualizados

---

## Resultado esperado

Todos os imports apontam para `apps/`. Apps modulares registrados corretamente. Próximo passo: migrar views/URLs do vendas_web para os apps (tarefa separada).
