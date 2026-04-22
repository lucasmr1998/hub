# Sistema de Permissões — Hubtrix

**Última atualização:** 19/04/2026
**Status:** ✅ Implementado (42 funcionalidades, 11 perfis padrão)
**Localização:** `apps/sistema/`

---

## Visão Geral

O sistema de permissões controla o acesso de cada usuário a funcionalidades específicas do sistema. Funciona em 3 camadas:

```
Camada 1: PERFIL DE PERMISSÃO (role reutilizável)
    Admin cria perfis como "Vendedor", "Supervisor", "Gerente"
    Cada perfil tem uma lista de funcionalidades habilitadas

Camada 2: FUNCIONALIDADE (granular)
    42 funcionalidades fixas agrupadas por módulo
    Cada funcionalidade = 1 checkbox no perfil

Camada 3: ATRIBUIÇÃO (usuário → perfil)
    Cada usuário recebe 1 perfil
    Muda o perfil = muda para todos os usuários com aquele perfil
```

**Retrocompatível:** superusers passam tudo. Usuários sem perfil atribuído também (legado).

**Importante:** todas as views usam `user_tem_funcionalidade()` para verificar permissões. O campo `is_superuser` do Django é reservado apenas para o painel Aurora Admin (`/aurora-admin/`) e proteções internas (ex: impedir exclusao de superusers). Nunca usar `is_superuser` para controle de acesso em views do sistema.

---

## Arquitetura

### Models

```
Funcionalidade (42 registros fixos, seed)
    ├── modulo: comercial | marketing | cs | inbox | configuracoes
    ├── codigo: "comercial.ver_pipeline" (unique)
    ├── nome: "Ver Pipeline"
    └── descricao: "Visualizar pipeline Kanban e oportunidades"

PerfilPermissao (criado pelo admin, por tenant)
    ├── nome: "Vendedor" (unique por tenant)
    ├── descricao: "Acesso básico ao comercial"
    └── funcionalidades: M2M → Funcionalidade

PermissaoUsuario (1:1 com User)
    ├── user: OneToOne User
    ├── tenant: FK Tenant
    └── perfil: FK PerfilPermissao (nullable)
```

### Como a verificação funciona

```
Request chega
    │
    ▼
PermissaoMiddleware (apps/sistema/middleware.py)
    │
    ├── Superuser? → passa
    ├── Sem PermissaoUsuario? → passa (retrocompatível)
    ├── URL contém /crm/ ? → verifica perm.acesso_comercial
    ├── URL contém /marketing/ ? → verifica perm.acesso_marketing
    ├── URL contém /cs/ ou /roleta/ ? → verifica perm.acesso_cs
    ├── URL contém /inbox/ ou /suporte/ ? → verifica perm.acesso_inbox
    └── URL contém /configuracoes ? → verifica perm.acesso_configuracoes
         │
         └── Se não tem acesso → HTTP 403 "Acesso negado"
```

A sidebar e topbar filtram os menus via context processor (`perm` e `is_superuser` disponíveis em todos os templates).

---

## 42 Funcionalidades

### Comercial (12)

| Código | Nome | Escopo |
|--------|------|--------|
| `comercial.ver_dashboard` | Ver Dashboard | Acesso ao dashboard comercial |
| `comercial.ver_pipeline` | Ver Pipeline | Visualizar pipeline Kanban |
| `comercial.mover_oportunidade` | Mover Oportunidades | Arrastar entre estágios |
| `comercial.ver_todas_oportunidades` | Ver Todas as Oportunidades | Escopo supervisor/gerente (não só as suas) |
| `comercial.criar_tarefa` | Criar e Editar Tarefas | CRUD de tarefas no CRM |
| `comercial.ver_desempenho` | Ver Relatórios de Desempenho | Dashboard de performance |
| `comercial.gerenciar_metas` | Gerenciar Metas | CRUD de metas de vendas |
| `comercial.gerenciar_equipes` | Gerenciar Equipes | Criar equipes e atribuir membros |
| `comercial.configurar_pipeline` | Configurar Pipelines | Pipelines, estágios, webhooks, config CRM |
| `comercial.ver_relatorios` | Ver Relatórios Gerais | Acessar dashboard principal e relatórios |
| `comercial.excluir_lead` | Excluir Leads | Exclusão permanente (leads, oportunidades, tarefas, notas, conversas vinculadas) |
| `comercial.excluir_oportunidade` | Excluir Oportunidades | Exclusão permanente (oportunidades, tarefas, notas, itens vinculados) |

### Marketing (7)

| Código | Nome | Escopo |
|--------|------|--------|
| `marketing.ver_leads` | Ver Leads | Lista de leads e detalhes |
| `marketing.gerenciar_campanhas` | Gerenciar Campanhas | CRUD campanhas de tráfego |
| `marketing.ver_segmentos` | Ver Segmentos | Visualizar segmentos e membros |
| `marketing.gerenciar_segmentos` | Gerenciar Segmentos | Criar/editar regras de filtro |
| `marketing.ver_automacoes` | Ver Automações | Lista e histórico |
| `marketing.gerenciar_automacoes` | Gerenciar Automações | Editor visual, criar/editar |
| `marketing.configurar` | Configurar Marketing | Landing page, ativar/desativar automações |

### Customer Success (6)

| Código | Nome | Escopo |
|--------|------|--------|
| `cs.ver_dashboard` | Ver Dashboard CS | Dashboard do Clube |
| `cs.gerenciar_membros` | Gerenciar Membros | Editar saldo e extrato |
| `cs.gerenciar_cupons` | Gerenciar Cupons e Parceiros | CRUD parceiros, cupons, resgates |
| `cs.aprovar_cupons` | Aprovar/Rejeitar Cupons | Aprovação de cupons de parceiros |
| `cs.gerenciar_indicacoes` | Gerenciar Indicações | Status e conversão de indicações |
| `cs.configurar` | Configurar CS | Regras, níveis, banners, carteirinhas |

### Inbox (8)

| Código | Nome | Escopo |
|--------|------|--------|
| `inbox.ver_minhas` | Ver Minhas Conversas | Apenas atribuídas a mim |
| `inbox.ver_equipe` | Ver Conversas da Equipe | Escopo supervisor |
| `inbox.ver_todas` | Ver Todas as Conversas | Todas do tenant |
| `inbox.responder` | Responder Conversas | Enviar mensagens e notas |
| `inbox.transferir_agente` | Transferir para Agente | Entre agentes da mesma equipe |
| `inbox.transferir_equipe` | Transferir entre Equipes | Entre equipes/filas |
| `inbox.resolver` | Resolver e Reabrir | Mudar status da conversa |
| `inbox.configurar` | Configurar Inbox | Equipes, filas, horários, canais, widget |

### Suporte (4, módulo `inbox`)

| Código | Nome | Escopo |
|--------|------|--------|
| `suporte.ver_tickets` | Ver Tickets de Suporte | Lista de tickets |
| `suporte.gerenciar_tickets` | Gerenciar Tickets | Criar, editar, atribuir, fechar |
| `suporte.ver_conhecimento` | Ver Base de Conhecimento | Acessar artigos |
| `suporte.gerenciar_conhecimento` | Gerenciar Base de Conhecimento | Criar/editar artigos |

### Configurações (5)

| Código | Nome | Escopo |
|--------|------|--------|
| `config.gerenciar_usuarios` | Gerenciar Usuários | CRUD de usuários |
| `config.gerenciar_perfis` | Gerenciar Perfis | Criar/editar perfis de permissão |
| `config.gerenciar_planos` | Gerenciar Planos e Vencimentos | CRUD planos de internet |
| `config.gerenciar_fluxos` | Gerenciar Fluxos de Atendimento | Configurar bot |
| `config.gerenciar_notificacoes` | Gerenciar Notificações | Tipos e canais |

---

## Matriz de permissões (perfis padrão × funcionalidades)

Fonte da verdade: `apps/sistema/management/commands/seed_perfis_padrao.py`. Rodar `python manage.py seed_perfis_padrao` (idempotente) pra criar/atualizar os perfis em cada tenant.

### Comercial

| Funcionalidade | Vendedor | Supervisor Com. | Gerente Com. | Admin |
|---|:-:|:-:|:-:|:-:|
| ver_dashboard | ✅ | ✅ | ✅ | ✅ |
| ver_pipeline | ✅ | ✅ | ✅ | ✅ |
| mover_oportunidade | ✅ | ✅ | ✅ | ✅ |
| ver_todas_oportunidades | ❌ | ✅ | ✅ | ✅ |
| criar_tarefa | ✅ | ✅ | ✅ | ✅ |
| ver_desempenho | ✅ | ✅ | ✅ | ✅ |
| gerenciar_metas | ❌ | ✅ | ✅ | ✅ |
| gerenciar_equipes | ❌ | ❌ | ✅ | ✅ |
| configurar_pipeline | ❌ | ❌ | ✅ | ✅ |
| ver_relatorios | ❌ | ❌ | ❌ | ✅ |
| excluir_lead | ❌ | ❌ | ❌ | ✅ |
| excluir_oportunidade | ❌ | ❌ | ❌ | ✅ |

### Marketing

| Funcionalidade | Analista Mkt | Gerente Mkt | Admin |
|---|:-:|:-:|:-:|
| ver_leads | ✅ | ✅ | ✅ |
| gerenciar_campanhas | ✅ | ✅ | ✅ |
| ver_segmentos | ✅ | ✅ | ✅ |
| gerenciar_segmentos | ✅ | ✅ | ✅ |
| ver_automacoes | ✅ | ✅ | ✅ |
| gerenciar_automacoes | ❌ | ✅ | ✅ |
| configurar | ❌ | ✅ | ✅ |

### Customer Success

| Funcionalidade | Operador CS | Gerente CS | Admin |
|---|:-:|:-:|:-:|
| ver_dashboard | ✅ | ✅ | ✅ |
| gerenciar_membros | ✅ | ✅ | ✅ |
| gerenciar_cupons | ✅ | ✅ | ✅ |
| aprovar_cupons | ❌ | ✅ | ✅ |
| gerenciar_indicacoes | ✅ | ✅ | ✅ |
| configurar | ❌ | ✅ | ✅ |

### Inbox (Atendimento)

| Funcionalidade | Agente Sup. | Supervisor Sup. | Gerente Sup. | Admin |
|---|:-:|:-:|:-:|:-:|
| ver_minhas | ✅ | ✅ | ✅ | ✅ |
| ver_equipe | ❌ | ✅ | ✅ | ✅ |
| ver_todas | ❌ | ❌ | ✅ | ✅ |
| responder | ✅ | ✅ | ✅ | ✅ |
| transferir_agente | ✅ | ✅ | ✅ | ✅ |
| transferir_equipe | ❌ | ✅ | ✅ | ✅ |
| resolver | ✅ | ✅ | ✅ | ✅ |
| configurar | ❌ | ❌ | ✅ | ✅ |

### Suporte (tickets + conhecimento)

Não estão nos perfis padrão atuais. Só **Admin** tem por padrão (via `__all__`). Adicionar a outros perfis via UI de "Gerenciar perfis" conforme a operação do tenant.

### Configurações

Só **Admin** tem por padrão (via `__all__`). Outros perfis não gerenciam usuários/perfis/planos/fluxos/notificações — típico de SaaS multi-tenant onde só o operador do tenant faz isso.

### Resumo por perfil (contagem)

| Perfil | Funcionalidades | Escopo principal |
|---|---|---|
| Vendedor | 9 | CRM básico + Inbox próprio |
| Supervisor Comercial | 13 | CRM time + Inbox equipe |
| Gerente Comercial | 16 | CRM completo + Inbox total |
| Analista Marketing | 5 | Marketing leitura/criação |
| Gerente Marketing | 7 | Marketing completo |
| Operador CS | 4 | CS membros + cupons + indicações |
| Gerente CS | 6 | CS completo |
| Agente Suporte | 4 | Inbox próprio básico |
| Supervisor Suporte | 6 | Inbox equipe + transferência |
| Gerente Suporte | 8 | Inbox total + configuração |
| **Admin** | **42 (todas)** | Tudo — seed via `__all__` |

---

## Onde gerenciar

| O que | Onde | Quem acessa |
|-------|------|-------------|
| Criar/editar perfis | Configurações > Usuários > botão "Perfis" (`/configuracoes/perfis/`) | Admin |
| Atribuir perfil a usuário | Configurações > Usuários > Editar > select "Perfil de Permissão" | Admin |
| Seed de funcionalidades | `python manage.py seed_funcionalidades` | DevOps |
| Django Admin | `/admin/sistema/funcionalidade/` e `/admin/sistema/perfilpermissao/` | Superuser |

---

## Exemplos de perfis sugeridos

### Vendedor
Comercial: ver_dashboard, ver_pipeline, mover_oportunidade, criar_tarefa
Inbox: ver_minhas, responder

### Supervisor Comercial
Tudo do Vendedor +
Comercial: ver_todas_oportunidades, ver_desempenho
Inbox: ver_equipe, transferir_agente

### Gerente Comercial
Tudo do Supervisor +
Comercial: gerenciar_metas, gerenciar_equipes, configurar_pipeline
Inbox: ver_todas, transferir_equipe, resolver

### Analista Marketing
Marketing: ver_leads, gerenciar_campanhas, ver_segmentos, gerenciar_segmentos, ver_automacoes

### Gerente Marketing
Tudo do Analista +
Marketing: gerenciar_automacoes, configurar

### Operador CS
CS: ver_dashboard, gerenciar_membros, gerenciar_cupons, gerenciar_indicacoes

### Agente Suporte
Inbox: ver_minhas, responder, transferir_agente, resolver

### Admin
Todas as 35 funcionalidades

---

## Arquivos do sistema

| Arquivo | O que contém |
|---------|-------------|
| `apps/sistema/models.py` | Funcionalidade, PerfilPermissao, PermissaoUsuario |
| `apps/sistema/middleware.py` | PermissaoMiddleware (verifica por URL) |
| `apps/sistema/decorators.py` | `@permissao_required`, `user_tem_funcionalidade()` |
| `apps/sistema/context_processors.py` | `perm` e `user_funcs` em templates |
| `apps/sistema/admin.py` | Admin para Funcionalidade, PerfilPermissao, PermissaoUsuario |
| `apps/sistema/management/commands/seed_funcionalidades.py` | Seed das 35 funcionalidades |
| `apps/sistema/templates/sistema/configuracoes/perfis_permissao.html` | Página de gestão de perfis |
| `apps/sistema/templates/sistema/configuracoes/usuarios.html` | Atribuição de perfil por usuário |
| `apps/sistema/templates/sistema/base.html` | Sidebar/topbar filtrados por permissões |

---

## O que funciona hoje

1. **Middleware bloqueia acesso por módulo** (URL-based, HTTP 403)
2. **Verificacao granular nas views** via `user_tem_funcionalidade()` em CRM, Sistema e Notificacoes
3. **Filtro de escopo no CRM** baseado em `comercial.ver_todas_oportunidades` (vendedor ve so suas, supervisor/gerente ve todas)
4. **Topbar esconde módulos** sem acesso
5. **Sidebar esconde menus de configuração** para não-gerentes
6. **Perfis reutilizáveis** com checkboxes de funcionalidades por módulo
7. **Atribuição** via select na edição de usuário
8. **Retrocompatível** (superuser e sem perfil = acesso total)
9. **35 funcionalidades seedadas** via management command
10. **Tela de usuarios filtrada por tenant** (cada tenant ve apenas seus usuarios)
11. **Campo Staff removido** da interface (apenas Ativo/Inativo visivel)

---

## O que falta implementar (futuro)

### Prioridade alta

1. **Aplicar permissões no Inbox**
   O Inbox não filtra conversas por agente/equipe baseado nas permissões. Todos veem tudo.
   **Solução:** na view `api_conversas`, verificar `inbox.ver_minhas` / `inbox.ver_equipe` / `inbox.ver_todas` e filtrar o queryset.

### Prioridade média

4. **Cache de permissões**
   Hoje cada request faz query no banco (user → permissao → perfil → funcionalidades M2M). Em alto tráfego pode impactar.
   **Solução:** cachear `perm.funcionalidades` em memória por sessão ou usar `select_related`/`prefetch_related` no middleware.

5. **Audit log de mudanças de perfil**
   Registrar quando um perfil é criado/editado/excluído e quando um usuário muda de perfil.
   **Solução:** signal `post_save` em PerfilPermissao e PermissaoUsuario, salvar em LogSistema.

6. **Herança de perfis**
   Permitir que um perfil herde de outro (ex: "Supervisor" herda tudo de "Vendedor" e adiciona funcionalidades).
   **Solução:** campo `pai` FK em PerfilPermissao. Na verificação, unir funcionalidades do perfil + pai.

### Prioridade baixa

7. **Permissões por objeto**
   Controlar acesso a registros específicos (ex: vendedor X só pode ver leads da cidade Y).
   **Solução:** model `RestricaoObjeto` com filtros dinâmicos. Complexidade alta, avaliar necessidade real.

8. **Funcionalidades customizáveis por tenant**
   Hoje as 35 funcionalidades são fixas (seed). Um tenant pode querer criar funcionalidades próprias.
   **Solução:** campo `tenant` nullable em Funcionalidade. Se null = global, se preenchido = custom do tenant.

---

## Preocupações

### Segurança
- **Verificacao granular aplicada em CRM, Sistema e Notificacoes.** Todas as views sensíveis (configuracoes, criar/editar/excluir) usam `user_tem_funcionalidade()`. O middleware continua como primeira barreira por módulo (URL).
- **APIs N8N não verificam funcionalidades.** As APIs REST (`/api/v1/n8n/...`) só verificam token, não perfil de permissão. Para N8N isso é ok (acesso de serviço), mas se expor APIs para o frontend SPA no futuro, precisa verificar.
- **Inbox ainda não filtra por escopo.** Todos os agentes veem todas as conversas. Pendente aplicar `inbox.ver_minhas` / `inbox.ver_equipe` / `inbox.ver_todas`.

### Performance
- **M2M query a cada request.** A verificação `perm.acesso_comercial` faz `perfil.funcionalidades.filter(modulo='comercial').exists()` que é uma query. Com `prefetch_related` no middleware resolve.
- **35 funcionalidades é gerenciável.** Se crescer para 100+, a página de perfis precisa de busca/filtro.

### Senha Temporaria (Primeiro Acesso)
- **PerfilUsuario.senha_temporaria** (BooleanField, default=False)
- Ao criar usuario ou resetar senha: `senha_temporaria=True`
- Middleware `LoginRequiredMiddleware` redireciona para `/trocar-senha/` enquanto flag for True
- Apos trocar: flag vira False, sessao mantida via `update_session_auth_hash`
- Template: `sistema/trocar_senha_obrigatoria.html` (visual alinhado ao login)

### Operacional
- **Seed obrigatório.** Em cada deploy, rodar `python manage.py seed_funcionalidades`. Se esquecer, a página de perfis fica sem funcionalidades para marcar.
- **Migration de perfis existentes.** Se já existem perfis criados com o modelo antigo (campos booleanos), eles perdem as permissões ao migrar. Precisa reconfigurar manualmente.
