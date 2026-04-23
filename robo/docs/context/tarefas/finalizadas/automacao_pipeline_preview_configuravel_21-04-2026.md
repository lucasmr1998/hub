---
name: "Automações do Pipeline — limite do preview configurável por tenant"
description: "O endpoint de preview de regra avalia até 500 oportunidades hardcoded. Tornar configurável em ConfiguracaoCRM pra que tenants com base grande tenham amostra maior sem travar os pequenos."
prioridade: "🟢 Baixa"
responsavel: "Tech"
---

# Automações do Pipeline — preview configurável — 21/04/2026

**Data:** 21/04/2026
**Responsável:** Tech
**Prioridade:** 🟢 Baixa
**Status:** ⏳ Aguardando priorização

---

## Contexto

No endpoint `POST /crm/automacoes-pipeline/<id>/preview/` (implementado nas Fases 2+3 em `apps/comercial/crm/views.py`), a avaliação é limitada a 500 oportunidades hardcoded:

```python
for opp in oportunidades[:500]:
```

Problema: tenants com base grande (digamos, Megalink com dezenas de milhares de oportunidades) veem uma amostra de 500 que pode não representar o universo. Já tenants pequenos não precisam de 500 — 50 bastaria.

---

## Proposta

Adicionar campo `preview_regras_max` em `ConfiguracaoCRM`:
- Default: 500 (comportamento atual)
- Tenant edita em `/crm/configuracoes/`
- Engine de preview lê o valor do tenant

## Tarefas

- [ ] Adicionar campo `preview_regras_max` (PositiveIntegerField, default=500) em `ConfiguracaoCRM`
- [ ] Migration
- [ ] Atualizar `views.py::regra_pipeline_preview` pra ler do `ConfiguracaoCRM.get_config().preview_regras_max`
- [ ] Expor campo na tela de Configurações CRM (input numérico + help text sobre trade-off de performance)
- [ ] Teste: preview respeita o limite configurado

## Critério de aceite

- Tenant novo tem `preview_regras_max=500` automático
- Alterar o valor em `/crm/configuracoes/` muda o tamanho da amostra no preview
- Valor mínimo 10, máximo sugerido 5000 (validação de form)

## Dependências / bloqueia

- Depende: feature Automações do Pipeline (Fases 1-3) — ✅ concluídas
- Não bloqueia nada crítico (baixa prioridade)

---

## Referências

- Código atual: `apps/comercial/crm/views.py::regra_pipeline_preview` linha que tem `oportunidades[:500]`
- Doc de produto: `robo/docs/PRODUTO/modulos/comercial/crm/automacoes-pipeline.md`
- Tarefa origem: `automacao_pipeline_crm_21-04-2026.md` (Fase 3 incompleta)
