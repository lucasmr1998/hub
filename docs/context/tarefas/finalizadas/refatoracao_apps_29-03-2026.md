# Refatoração em apps + Multi-tenancy + Segurança — 29/03/2026

**Data:** 29/03/2026
**Responsável:** Tech Lead / DevOps / Segurança (AppSec)
**Prioridade:** 🔴 Alta
**Status:** ✅ Concluída

---

## Descrição

Refatorar o monolito vendas_web em apps Django separados por módulo, implementar multi-tenancy para viabilizar o modelo SaaS e remover secrets hardcoded do código fonte.

---

## Tarefas

- [x] Definir estrutura de apps (Opção A: sub-apps por pasta, aprovada pelo CEO)
- [x] Separar vendas_web em 10 apps: sistema, notificacoes, integracoes, dashboard, leads, atendimento, cadastro, viabilidade, crm, campanhas
- [x] Implementar multi-tenancy: Tenant, PerfilUsuario, TenantMixin, TenantManager, TenantMiddleware
- [x] Criar Painel Admin Aurora (/aurora-admin/) com dashboard de tenants, planos e features
- [x] Remover secrets do código fonte e migrar para variáveis de ambiente
- [x] Criar agentes Segurança (AppSec), DevOps e QA

---

## Contexto e referências

- Reunião: `docs/context/reunioes/tech_refatoracao_29-03-2026.md`
- Decisão de estrutura aprovada pelo CEO (Opção A)
- Projeto: `robo/` (módulo Comercial da AuroraISP)

---

## Resultado esperado

Código refatorado em apps modulares, multi-tenancy funcional em desenvolvimento, credenciais seguras via variáveis de ambiente, painel admin Aurora operacional. Pronto para deploy em produção como próximo passo.
