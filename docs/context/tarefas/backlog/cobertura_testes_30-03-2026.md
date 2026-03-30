---
name: "Cobertura de Testes"
description: "A cobertura de testes é ~1%. Existe apenas 1 arquivo de teste real (`test_tenant_isolation.py` com 16 testes). Para um S"
prioridade: "🔴 Alta"
responsavel: "QA / Dev"
---

# Cobertura de Testes — 30/03/2026

**Data:** 30/03/2026
**Responsável:** QA / Dev
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

A cobertura de testes é ~1%. Existe apenas 1 arquivo de teste real (`test_tenant_isolation.py` com 16 testes). Para um SaaS multi-tenant em produção, é crítico ter testes automatizados cobrindo os fluxos principais. Meta: 80% de cobertura nos models e views críticos.

---

## Tarefas

- [ ] Instalar pytest-cov e configurar .coveragerc
- [ ] Atualizar requirements.txt com dependências de teste (pytest, pytest-django, pytest-cov, factory-boy)
- [ ] Criar testes para models do módulo comercial (Lead, Atendimento, Cadastro)
- [ ] Criar testes para fluxo de integração HubSoft
- [ ] Criar testes para models do módulo CS (Clube, Parceiros, Indicações)
- [ ] Criar testes para o sistema de planos e features (Admin Aurora)
- [ ] Criar testes para middleware de tenant (cenários de edge case)
- [ ] Criar testes para views críticas (login, dashboard, cadastro de lead)
- [ ] Gerar relatório de cobertura e identificar gaps
- [ ] Definir meta mínima de cobertura no CI (ex: 60% para começar)

---

## Contexto e referências

- Testes existentes: `robo/dashboard_comercial/gerenciador_vendas/tests/`
- Fixtures: `conftest.py` com tenant_a, tenant_b, user_a, user_b
- Factories: `factories.py` com TenantFactory, UserFactory, PerfilFactory
- pytest.ini configurado com `settings_local`

---

## Resultado esperado

Cobertura de testes >60% nos módulos críticos. Relatório de coverage integrado ao CI. Factories e fixtures reutilizáveis para todos os apps.
