---
name: "Painel de Monitoramento no Admin Aurora"
description: "Criar página de monitoramento do sistema no painel /aurora-admin/"
prioridade: "🟡 Média"
responsavel: "DevOps"
---

# Painel de Monitoramento no Admin Aurora — 31/03/2026

**Data:** 31/03/2026
**Responsável:** DevOps
**Prioridade:** 🟡 Média
**Status:** ✅ Concluída

---

## Descrição

Criar uma página de monitoramento completa no Admin Aurora (/aurora-admin/monitoramento/) que exiba o status do sistema, métricas operacionais, logs de integração e erros recentes. Também melhorar a página de logs existente com filtros avançados e auto-refresh.

---

## Tarefas

- [x] Criar view monitoramento_view com health check, métricas e logs
- [x] Adicionar URL /aurora-admin/monitoramento/
- [x] Adicionar link "Monitoramento" na navbar do Admin Aurora
- [x] Criar template monitoramento.html com cards de status, métricas e tabelas
- [x] Melhorar logs_view com filtro por módulo, busca por texto e contagem por nível
- [x] Melhorar logs.html com badges de contagem, auto-refresh e filtros avançados

---

## Contexto e referências

- Admin Aurora: apps/admin_aurora/
- Health check existente: /health/ (apps/sistema/views.py)
- Models: LogSistema, LogIntegracao, Tenant, LeadProspecto, AtendimentoFluxo

---

## Resultado esperado

Painel de monitoramento funcional com visão consolidada do sistema: status do banco, contagem de erros/warnings, métricas de leads e atendimentos, logs de integração HubSoft e últimos erros. Página de logs melhorada com busca, filtro por módulo e auto-refresh.
