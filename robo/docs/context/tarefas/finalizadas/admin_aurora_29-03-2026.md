---
name: Painel Admin Aurora e sistema de planos
description: Painel de gestão do SaaS com gerenciamento de tenants, planos e features
type: tarefa
status: finalizada
criado_em: 29/03/2026
---

## Objetivo

Criar o painel administrativo da Aurora para gerenciar provedores, planos e features sem depender do Django Admin.

## Atividades

- [x] Criar app admin_aurora separado do app sistema
- [x] Dashboard com stats (tenants, ativos, trial, erros)
- [x] CRUD de tenants (criar, editar módulos/planos, toggle ativo, trial)
- [x] Detalhe do tenant (users, leads, integração HubSoft)
- [x] Logs do sistema com filtros
- [x] Model Plano (modulo, tier, preco_mensal, preco_transacional)
- [x] Model FeaturePlano (slug, nome, categoria, vinculado ao Plano)
- [x] 9 planos criados (3x3) conforme 08-PRECIFICACAO.md
- [x] 115 features distribuídas entre planos
- [x] Tenant vinculado ao Plano via FK (tem_feature, features_ativas)
- [x] Command seed_planos para recriar features
- [x] Command criar_tenant para onboarding
- [x] Gerenciamento visual de planos (/aurora-admin/planos/)
- [x] Edição de features por plano (/aurora-admin/planos/{id}/)
- [x] Topbar com botão Aurora (staff only)
- [x] Context processor multi-tenant (módulos, planos, cores, logo)
- [x] Controle de módulos na topbar e sidebar

## Contexto e referências

- Reunião: docs/context/reunioes/admin_aurora_planos_29-03-2026.md
- Precificação: docs/GTM/08-PRECIFICACAO.md
- URL: /aurora-admin/

## Resultado esperado

Gestão completa do SaaS via painel web. Planos e features editáveis sem deploy.
