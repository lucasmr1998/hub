---
name: "Implementar Django REST Framework"
description: "O projeto possui APIs (HubSoft, N8N, webhooks) mas sem Django REST Framework. Não há serializers, versionamento de API, "
prioridade: "🟡 Média"
responsavel: "Dev"
---

# Implementar Django REST Framework — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O projeto possui APIs (HubSoft, N8N, webhooks) mas sem Django REST Framework. Não há serializers, versionamento de API, autenticação por token nem documentação automática. À medida que o SaaS escala com multi-tenancy, uma camada de API padronizada é essencial.

---

## Tarefas

- [ ] Instalar djangorestframework e adicionar ao requirements.txt
- [ ] Configurar DRF no settings (autenticação, permissões, paginação)
- [ ] Criar serializers para os models principais (Lead, Cliente, Tenant)
- [ ] Migrar endpoints existentes para ViewSets/APIViews
- [ ] Implementar autenticação por token (TokenAuth ou JWT)
- [ ] Adicionar versionamento de API (v1/)
- [ ] Configurar drf-spectacular ou similar para documentação OpenAPI
- [ ] Testar endpoints migrados

---

## Contexto e referências

- Dívida técnica documentada em `docs/PRODUTO/02-ROADMAP_PRODUTO.md`
- Endpoints N8N duplicados mencionados no roadmap

---

## Resultado esperado

API padronizada com DRF, autenticação por token, versionamento e documentação Swagger/OpenAPI acessível.
