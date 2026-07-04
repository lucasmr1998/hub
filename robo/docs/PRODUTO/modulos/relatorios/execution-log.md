# Execution Log — Relatórios

> Trilha cronológica do que foi implementado/decidido no módulo de relatórios e dashboards self-service. Append no fim, entrada mais nova embaixo. Formato: `## YYYY-MM-DD — título`.

---

## 2026-07-04 — Campos motivo_perda_ref + flags final + operador ultimos_dias

- Ação: DataSource `oportunidade` expõe `motivo_perda_ref__nome` (choice, choices_from crm.MotivoPerda), `estagio__is_final_perdido` e `estagio__is_final_ganho` (bool). Novo operador `ultimos_dias` no query_builder (valor N → campo >= hoje-N dias) pra filtros de data relativa que não ficam obsoletos.
- Why: widgets de "Motivos de perda" agrupavam por `motivo_perda_categoria` (NULL em 96% das perdidas) — o dado real está na FK `motivo_perda_ref`. E não havia como criar widget "últimos 30 dias" sem hardcode de data.
- Output: commit `c8f6424`. Nuvyon: 14 dashboards seed deletados, painel único #15 com 3 widgets validados.
- Status: completed
