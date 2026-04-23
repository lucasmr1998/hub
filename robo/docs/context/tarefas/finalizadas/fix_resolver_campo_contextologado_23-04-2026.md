---
name: "Fix _resolver_campo_contexto nao resolve var.X quando contexto eh ContextoLogado"
description: "Engine de atendimento: toda condicao 'var.X == valor' retorna false silenciosamente porque _resolver_campo_contexto usa isinstance(obj, dict) e ContextoLogado nao eh dict"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Fix condicao var.X com ContextoLogado — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🔴 Alta (bug em producao afeta todos os tenants)
**Status:** ✅ Concluída (codigo + testes; pendente deploy)

---

## Descrição

Descoberto via teste end-to-end do fluxo v3 FATEPI: candidato responde "Psicologia", classificador IA diz `validacao_curso=curso_valido`, mas o nodo de condicao `var.validacao_curso == curso_valido` retorna **false** e manda o candidato pra "curso invalido". Log mostra:

```
[sucesso] nodo=528 Condicao: var.validacao_curso igual curso_valido -> false
```

mesmo com `dados_respostas.variaveis.validacao_curso = 'curso_valido'`.

## Causa raiz

`_resolver_campo_contexto` em [engine.py:565-577](../../../../dashboard_comercial/gerenciador_vendas/apps/comercial/atendimento/engine.py#L565-L577) testa `isinstance(obj, dict)` pra navegar em dot notation. `ContextoLogado` (introduzido no `engine_contexto.py`) eh `MutableMapping`, nao `dict`. `isinstance(ContextoLogado(), dict)` retorna False, loop cai no else com `flat_key = 'var_validacao_curso'`, `contexto.get(flat_key)` retorna None, comparacao retorna False, condicao vira branch 'false'.

## Impacto

**Qualquer fluxo** com condicao `campo_check` avaliando variavel IA (`var.X`) esta quebrado. Afeta:
- FATEPI fluxo v3: nenhum candidato chega em "criar oportunidade" nem em "PIX" — 0 matriculas em 34 atendimentos
- Potencialmente outros tenants que usem fluxo visual + ia_classificador/ia_extrator seguido de condicao

## Tarefas

- [x] Abrir tarefa no backlog
- [x] Escrever teste unitario em `tests/test_engine_nodos.py` que reproduz o bug (classes `TestResolverCampoContexto` + `TestCondicaoComVarContextoLogado`, 10 testes)
- [x] Aplicar fix: trocar `isinstance(obj, dict)` por duck typing (`hasattr(obj, 'get') and callable(obj.get)`) em `_resolver_campo_contexto`
- [x] Rodar `pytest tests/` completo: **901 passed, 4 skipped, 61 xfailed, 16 xpassed** — zero regressao
- [x] Teste de nivel fluxo (roteamento e2e micro): `test_roteamento_branch_true_com_var_valida` e `test_roteamento_branch_false_com_var_invalida`
- [x] Atualizar `docs/PRODUTO/modulos/atendimento/engine.md` com secao "Contexto e resolucao de campos"
- [ ] Commit + push (aguardando usuario autorizar)
- [ ] Re-rodar teste e2e FATEPI pos-deploy pra confirmar Psicologia -> nodo 530 (criar oportunidade)

## Contexto e referencias

- Sessao de diagnostico: conversa do dia 23/04/2026
- ContextoLogado: [engine_contexto.py](../../../../dashboard_comercial/gerenciador_vendas/apps/comercial/atendimento/engine_contexto.py)
- Teste e2e que pegou: `scripts/teste_e2e_fatepi_v3.py`
- Tarefa irma (prompts corrigidos): [fix_prompts_fatepi_v3_23-04-2026.md](../finalizadas/fix_prompts_fatepi_v3_23-04-2026.md)

## Resultado esperado

- Condicao `var.validacao_curso == curso_valido` com validacao_curso salvo retorna True
- Condicao `var.tipo_fallback == duvida_valores` funciona
- Fluxo v3 FATEPI: candidato com curso valido avanca ate nodo 530 (criar oportunidade)
- Suite pytest verde (com novo teste cobrindo ContextoLogado)
- Nenhuma regressao em outros fluxos
