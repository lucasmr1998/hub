---
name: "Monitorar 48h fluxo v3 FATEPI pos-fix"
description: "Verificar em 24h e 48h se a distribuicao de nodos confirma que o fix destravou matriculas"
prioridade: "🟡 Média"
responsavel: "Lucas"
---

# Monitor FATEPI v3 48h — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Lucas
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando deploy

---

## Tarefas

Rodar a query abaixo em **24h** e **48h** apos o deploy do fix var.X:

```sql
SELECT nodo_atual_id, status, COUNT(*) as n
FROM atendimentos_fluxo
WHERE tenant_id=7 AND fluxo_id=6
  AND data_inicio > NOW() - INTERVAL '24 hours'
GROUP BY nodo_atual_id, status
ORDER BY n DESC;
```

## Criterios de aceite

**Ruim (precisa investigar):**
- Todos atendimentos novos parados em 521 (nome) ou 523 (curso) → fluxo nao ta chegando em IA
- Atendimentos parados em 529 com `validacao_curso=curso_valido` → fix nao pegou
- Cron nao processando delays → ExecucaoPendente acumulando

**Bom:**
- Pelo menos 1-2 atendimentos em 539 (PIX) ou 541 (sucesso)
- Distribuicao espalhada (candidatos em varias fases)
- Nenhum parado em 529 com curso valido

## Proxima acao se ruim

Rodar `scripts/teste_e2e_fatepi_v3.py` em prod → comparar output com o que a query mostra → abrir tarefa de bug.

## Relacionados

- Tarefa irma: `e2e_fatepi_pos_deploy_23-04-2026.md`
