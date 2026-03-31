---
name: "Docker e Containerização"
description: "O projeto não possui Dockerfile nem docker-compose. O deploy é manual via Gunicorn + Nginx no servidor. Para escalar o S"
prioridade: "🔴 Alta"
responsavel: "DevOps"
---

# Docker e Containerização — 30/03/2026

**Data:** 30/03/2026
**Responsável:** DevOps
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

O projeto não possui Dockerfile nem docker-compose. O deploy é manual via Gunicorn + Nginx no servidor. Para escalar o SaaS com multi-tenancy e facilitar onboarding de novos clientes, é necessário containerizar a aplicação.

---

## Tarefas

- [ ] Criar Dockerfile para a aplicação Django
- [ ] Criar docker-compose.yml (Django + PostgreSQL + Nginx + Redis)
- [ ] Configurar volumes para media/static files
- [ ] Criar .dockerignore
- [ ] Configurar variáveis de ambiente via docker-compose
- [ ] Testar build e startup local
- [ ] Documentar processo de deploy com Docker

---

## Contexto e referências

- Gunicorn config atual: `robo/dashboard_comercial/gerenciador_vendas/gunicorn.conf.py`
- Deploy atual: manual, servidor com user `darlan`, porta 8003

---

## Resultado esperado

Aplicação containerizada com docker-compose. Dev local roda com um comando (`docker-compose up`). Base para CI/CD e deploy automatizado.
