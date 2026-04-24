---
name: "CI gate: bloquear PR em engine.py sem novo teste"
description: "Adicionar step no CI que falha quando engine.py de atendimento muda sem mudanca correspondente em test_engine_nodos.py"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# CI gate engine.py — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ✅ Concluída (aplicado em ci.yml, testa no proximo PR)

---

## Descrição

Bug do var.X ficou latente por semanas porque engine.py foi mexido (introduziu ContextoLogado) mas os testes nao foram atualizados pra cobrir o novo caminho. Prevencao: gate no CI que falha quando engine critico muda sem teste novo.

## Proposta

Adicionar step em `.github/workflows/ci.yml`:

```yaml
- name: Gate — mudanca em engine.py exige mudanca em tests
  if: github.event_name == 'pull_request'
  run: |
    CHANGED_ENGINE=$(git diff --name-only origin/main HEAD | grep -E "apps/comercial/atendimento/engine\.py$|apps/marketing/automacoes/engine\.py$" | wc -l)
    CHANGED_TESTS=$(git diff --name-only origin/main HEAD | grep -E "tests/test_engine_nodos\.py$|tests/test_automacoes\.py$|tests/test_automacao_pipeline\.py$" | wc -l)
    if [ "$CHANGED_ENGINE" -gt 0 ] && [ "$CHANGED_TESTS" -eq 0 ]; then
      echo "❌ engine.py mudou sem teste. Adicionar teste em tests/ ou justificar com [no-test-needed] no titulo do PR."
      exit 1
    fi
    echo "✅ Gate ok"
```

Exceção via `[no-test-needed]` no titulo do PR pra correcoes triviais (typo, comentario) — ai o gate nao roda.

## Tarefas

- [ ] Editar `.github/workflows/ci.yml`
- [ ] Abrir PR de teste (com engine.py modificado mas sem teste) → confirmar que falha
- [ ] Abrir PR de teste com `[no-test-needed]` → confirmar que passa
- [ ] Merge em main

## Alternativa menos pesada

Em vez de bloquear, marcar o PR com label `needs-test` automaticamente — permite merge mas fica visivel. Menos atrito, menos seguranca.
