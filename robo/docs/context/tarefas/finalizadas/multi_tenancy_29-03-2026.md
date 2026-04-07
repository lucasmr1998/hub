---
name: Implementar multi-tenancy no sistema
description: Tenant, PerfilUsuario, TenantMixin, TenantManager, middleware com auto-filtro e auto-save
type: tarefa
status: finalizada
criado_em: 29/03/2026
---

## Objetivo

Permitir que múltiplos provedores usem o mesmo sistema com dados isolados.

## Atividades

- [x] Criar model Tenant (provedor, módulos, planos, trial, HubSoft)
- [x] Criar model PerfilUsuario (substitui monkey-patch User.add_to_class)
- [x] Criar TenantMixin (FK tenant + managers automáticos)
- [x] Criar TenantManager (auto-filtra objects.all() por tenant do request)
- [x] Criar TenantMiddleware (resolve tenant via thread-local)
- [x] Todos os 27+ models herdam TenantMixin
- [x] Auto-save: TenantMixin.save() preenche tenant automaticamente
- [x] Escape hatch: all_tenants manager para admin/commands
- [x] Seed do tenant Megalink + associação de users
- [x] Isolamento testado com 3 tenants
- [x] 16 testes automatizados passando

## Contexto e referências

- Reunião: docs/context/reunioes/multi_tenancy_29-03-2026.md
- Settings local: gerenciador_vendas/settings_local.py (SQLite)

## Resultado esperado

Multi-tenancy funcionando localmente. Cada provedor só vê seus próprios dados.
