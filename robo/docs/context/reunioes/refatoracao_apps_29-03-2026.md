# Refatoração em Apps por Módulo — 29/03/2026

**Data:** 29/03/2026
**Participantes:** CEO, CTO, PM, Tech Lead
**Duração:** ~2 horas

---

## Contexto

O sistema em produção (`robo/`) concentra 27 models em um único app (`vendas_web`), com 5.349 linhas de models, 7.464 linhas de views e 222 rotas. Isso bloqueia o multi-tenancy e a separação por módulos (Comercial, Marketing, CS) necessária para vender o SaaS.

---

## Principais pontos discutidos

- Análise completa do sistema robo: models, views, urls, análise crítica existente, GTM_PRODUTO.md, GTM_ROADMAP_CRM.md
- App `crm/` já existia separado com 12 models (referência de qualidade)
- Definição da estrutura de CRM do parceiro: 5 estágios, qualificação A/B, campos por etapa, critérios de avanço
- Discussão sobre 3 opções de arquitetura: sub-apps por pasta (A), flat com prefixo (B), módulo como app único (C)
- Comparativo detalhado entre Opção A e Opção C
- Decisão pela Opção A: cada domínio é um app Django completo dentro do módulo

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Opção A (sub-apps por pasta) | Migrations isoladas, ativação/desativação por plano, refatoração incremental, CRM já existe como app separado |
| 10 apps + 3 módulos futuros (CS) | Reflete os módulos do produto: Sistema (base), Comercial, Marketing, CS |
| TenantMixin como base | Todos os models herdam tenant FK via mixin abstrato |
| Migração incremental | Novos apps coexistem com vendas_web durante transição. Sem risco para produção |
| db_table mantido | Nenhuma tabela do banco muda de nome. Migrations usarão SeparateDatabaseAndState |
| Permissão de edição no robo/ | CLAUDE.md atualizado para permitir edição do projeto robo |

---

## O que foi implementado

| Item | Status |
|------|--------|
| Estrutura `apps/` com 10 apps (96 arquivos) | ✅ |
| `apps/sistema/` com 7 models (Tenant, PerfilUsuario, 5 configs) + middleware + mixin | ✅ |
| `apps/integracoes/` copiado do app existente | ✅ |
| `apps/comercial/crm/` copiado do app existente | ✅ |
| Scaffold de leads, atendimento, cadastro, viabilidade, campanhas, notificacoes, dashboard | ✅ |
| Models migrados para todos os novos apps (5.902 linhas total) | ✅ |
| `settings.py` atualizado com INSTALLED_APPS | ✅ |
| `urls.py` atualizado (legadas ativas, novas comentadas) | ✅ |
| Roadmap de produto atualizado com status | ✅ |
| CRM do parceiro: pipeline 5 estágios, qualificação, campos, critérios | ✅ |

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Atualizar vendas_web/models.py para re-exportar dos novos apps | Dev |
| Criar migrations com SeparateDatabaseAndState para cada app | Dev |
| Mover views e urls para cada app | Dev |
| Ativar novas rotas e desativar legadas | Dev |
| Mover templates para dentro de cada app | Dev |
| Atualizar imports em signals, admin, services | Dev |
| Remover vendas_web após migração completa | Dev |
| Atualizar FKs cross-app (de vendas_web.X para app_novo.X) | Dev |
| Segurança: remover credenciais hardcoded | Dev (urgente) |

---

## Próximos passos

- [ ] Atualizar vendas_web/models.py com re-exports dos novos apps
- [ ] Criar migrations SeparateDatabaseAndState
- [ ] Mover views por app (começando por leads)
- [ ] Mover urls por app
- [ ] Testar localmente com SQLite
- [ ] Resolver credenciais hardcoded (bloqueador de segurança)
