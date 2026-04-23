---
name: "Exemplo comentado de automacao (C02 Follow-up) + debug playbook"
description: "Documentar a regua C02 como caso ilustrativo (trigger + delay + condicao + 4 acoes), com estado nas tabelas de execucao e secao de debug"
prioridade: "🟡 Média"
responsavel: "PM"
---

# Exemplo automacao C02 + debug playbook — 23/04/2026

**Data:** 23/04/2026
**Responsável:** PM
**Prioridade:** 🟡 Média
**Status:** ✅ Concluída

## Descrição

Fecha itens 1 e 2 do plano de doc de marketing:
- Item 1: exemplo comentado ponta a ponta (faltava)
- Item 2: debug playbook (faltava)

Usa regua **C02 Follow-up de Lead Sem Resposta** (ja especificada em `reguas-padrao.md`, status: spec) como caso ilustrativo.

## Tarefas

- [x] `docs/PRODUTO/modulos/marketing/automacoes/exemplo-automacao.md`
- [x] Panorama da C02 no editor visual (grafo ASCII com 6 nodos e 3 saidas limpas)
- [x] 2 jornadas: Maria (reengajou em 24h) e Pedro (cascata completa 72h)
- [x] Tabelas: estado em `ExecucaoPendente`, `LogExecucao`, `ControleExecucao`
- [x] Secao debug: 6 queries (regra ativa, signal, pendente travada, rate limit, branch, ação executada mas msg nao chegou)
- [x] Tabela de 7 armadilhas conhecidas
- [x] Aviso no topo: regua em spec, nao implementada
- [x] Linkar no README de automacoes
