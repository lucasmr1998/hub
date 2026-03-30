---
name: Migração completa do vendas_web para apps modulares
description: Finalizar a migração de models, views, urls e templates do vendas_web para a nova estrutura de apps
type: tarefa
status: em andamento
criado_em: 29/03/2026
---

## Objetivo

Concluir a separação do God App `vendas_web` nos novos apps modulares. A estrutura e os models já foram criados. Falta mover views, urls, templates e criar as migrations de transição.

## Atividades

- [x] Criar estrutura de pastas apps/ com 10 apps
- [x] Criar models em apps/sistema (Tenant, PerfilUsuario, configs)
- [x] Copiar integracoes e crm para apps/
- [x] Migrar models para comercial/leads, comercial/atendimento, comercial/cadastro, comercial/viabilidade
- [x] Migrar models para notificacoes, marketing/campanhas
- [x] Atualizar settings.py e urls.py
- [x] Atualizar vendas_web/models.py com re-exports dos novos apps
- [x] Atualizar FKs cross-app (vendas_web.X → app_novo.X)
- [x] Django check passando sem erros
- [x] Migrations rodando localmente (SQLite)
- [ ] Criar migrations com SeparateDatabaseAndState para produção
- [ ] Mover views de vendas_web/views.py para cada app
- [ ] Mover views de vendas_web/views_api_atendimento.py para comercial/atendimento
- [ ] Mover urls de vendas_web/urls.py para cada app
- [ ] Mover templates para dentro de cada app
- [ ] Mover signals para cada app
- [ ] Mover admin registrations para cada app
- [ ] Mover services (contrato_service, atendimento_service, notification_service)
- [ ] Ativar novas rotas no urls.py principal
- [ ] Testar localmente com SQLite
- [ ] Remover vendas_web

## Contexto e referências

- Reunião: docs/context/reunioes/refatoracao_apps_29-03-2026.md
- Roadmap: docs/PRODUTO/02-ROADMAP_PRODUTO.md (seção 4)
- Decisão: Opção A (sub-apps por pasta), aprovada em 29/03/2026

## Resultado esperado

`vendas_web` removido. Cada módulo do produto (Comercial, Marketing, CS) é um namespace com apps Django independentes. Multi-tenancy pronto para ativar via Tenant + TenantMixin.
