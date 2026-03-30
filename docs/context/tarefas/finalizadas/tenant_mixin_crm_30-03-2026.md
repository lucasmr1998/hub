# Adicionar TenantMixin nos Models do CRM — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

9 models do CRM não herdam de TenantMixin e não possuem FK tenant. Com multi-tenancy ativo, um tenant consegue ver e manipular dados de outro tenant via CRM (oportunidades, tarefas, metas, alertas). Isso é um risco crítico de vazamento de dados.

---

## Tarefas

- [ ] Adicionar TenantMixin em `OportunidadeVenda`
- [ ] Adicionar TenantMixin em `EquipeVendas`
- [ ] Adicionar TenantMixin em `PipelineEstagio`
- [ ] Adicionar TenantMixin em `PerfilVendedor`
- [ ] Adicionar TenantMixin em `TagCRM`
- [ ] Adicionar TenantMixin em `TarefaCRM`
- [ ] Adicionar TenantMixin em `NotaInterna`
- [ ] Adicionar TenantMixin em `MetaVendas`
- [ ] Adicionar TenantMixin em `AlertaRetencao`
- [ ] Adicionar TenantMixin em `ConfiguracaoCRM`
- [ ] Gerar migrations (campo tenant com null=True para dados existentes)
- [ ] Criar data migration para popular tenant nos registros existentes (via lead.tenant)
- [ ] Atualizar views do CRM para usar o TenantManager
- [ ] Criar testes de isolamento para o CRM (similar a `test_tenant_isolation.py`)
- [ ] Testar localmente com SQLite

---

## Contexto e referências

- Models: `apps/comercial/crm/models.py`
- TenantMixin: `apps/sistema/mixins.py`
- Testes de referência: `tests/test_tenant_isolation.py`
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Todos os models do CRM isolados por tenant. Testes de isolamento passando. Nenhum dado de tenant A visível para tenant B.
