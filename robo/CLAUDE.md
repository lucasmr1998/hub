# CLAUDE.md — robo/

## Regras do Projeto

### Segurança — Banco de dados

- **NUNCA rodar comandos que afetem o banco de produção.** Sempre usar `--settings=gerenciador_vendas.settings_local` (SQLite local). Isso inclui: `migrate`, `makemigrations`, `createsuperuser`, `flush`, `loaddata`, `dumpdata`, `dbshell`, ou qualquer script que conecte ao PostgreSQL de produção.
- **NAO alterar settings de producao** — O settings.py e settings_production.py só podem ser alterados para correções de segurança ou configuração de variáveis de ambiente.
- **Secrets em variáveis de ambiente.** Nenhuma credencial deve existir hardcoded no código.

### Escopo de edição

1. **Backend permitido:**
   - Criar e editar views, URLs, templates e models dentro de `apps/`
   - Criar migrations locais (SQLite via settings_local)
   - Editar services, signals e admin registrations
   - NAO alterar o banco PostgreSQL de produção

2. **Foco principal:** estrutura modular em `apps/`, templates HTML, CSS, JS, arquivos estáticos

### Estrutura de apps

O projeto foi completamente migrado de um monolito (vendas_web) para apps modulares. A migração foi finalizada em 31/03/2026. O `vendas_web` foi removido do INSTALLED_APPS e seu código é morto (urls.py e admin.py vazios).

```
gerenciador_vendas/
├── manage.py
├── gerenciador_vendas/          # Projeto Django (settings, urls, wsgi)
│   ├── settings.py              # Produção (PostgreSQL)
│   ├── settings_local.py        # Desenvolvimento (SQLite)
│   └── urls.py
│
├── apps/                        # FONTE DA VERDADE — todos os models, views, templates, URLs
│   ├── sistema/                 # Tenant, PerfilUsuario, configs, base.html, static files
│   │   ├── decorators.py        # @api_token_required, @webhook_token_required
│   │   ├── validators.py        # validate_image_upload, tenant_upload_path
│   │   ├── logging_filters.py   # PIIFilter
│   │   ├── context_processors.py
│   │   ├── templates/sistema/base.html  # Template base do projeto
│   │   └── static/sistema/      # CSS e JS globais
│   ├── notificacoes/            # Motor de comunicação (cross-module)
│   ├── integracoes/             # HubSoft API, sync de clientes
│   ├── dashboard/               # Dashboard e relatórios
│   ├── admin_aurora/            # Painel de gestão SaaS (/aurora-admin/)
│   │
│   ├── comercial/
│   │   ├── leads/               # Captura e qualificação
│   │   ├── atendimento/         # Bot conversacional (N8N)
│   │   ├── cadastro/            # Registro, contrato, ativação
│   │   ├── viabilidade/         # Cobertura técnica
│   │   └── crm/                 # CRM Kanban (Plano Pro) — TenantMixin em 13 models
│   │
│   ├── marketing/
│   │   └── campanhas/           # Tráfego pago e atribuição
│   │
│   └── cs/
│       ├── clube/               # Clube de Benefícios (migrado do megaroleta)
│       ├── parceiros/           # Parceiros do clube
│       ├── indicacoes/          # Programa de indicações
│       └── carteirinha/         # Carteirinha digital
│
├── vendas_web/                  # MORTO — removido do INSTALLED_APPS, urls.py e admin.py vazios
├── tests/                       # 225 testes, 10 arquivos, 28+ factories
└── .github/workflows/           # CI/CD com GitHub Actions
```

### Multi-tenancy

Implementado e validado localmente, pendente deploy em produção.
- **Tenant:** model central que representa cada provedor
- **TenantMixin:** mixin com FK tenant + auto-save + auto-filtro. Aplicado em TODOS os models, incluindo 13 models do CRM
- **TenantManager:** filtra automaticamente por tenant do request
- **TenantMiddleware:** resolve o tenant via thread-local
- **Admin Aurora:** painel /aurora-admin/ para gerenciar tenants e planos. Protegido com `superuser_required` + verificação de acesso ao tenant

### API REST (DRF)

- **Django REST Framework** implementado com TokenAuth + SessionAuth
- Endpoints em `/api/v1/`
- Documentação Swagger em `/api/docs/`
- Serializers e ViewSets para os principais models

### Segurança

- **Decorators de autenticação:** `@api_token_required` (27 endpoints N8N), `@login_required` (21 endpoints painel), `@permissao_required('modulo', 'papel_minimo')` para controle granular, 3 endpoints públicos
- **Permissões granulares:** `Funcionalidade` (35 registros fixos), `PerfilPermissao` (M2M funcionalidades, por tenant), `PermissaoUsuario` (user → perfil). `PermissaoMiddleware` bloqueia por URL/módulo. Sidebar/topbar filtrados. Seed: `seed_funcionalidades`. Docs: `docs/PRODUTO/11-PERMISSOES.md`.
- **Webhook:** `@webhook_token_required` para webhooks HubSoft
- **IDOR:** helper `get_tenant_object_or_404` para isolamento de tenant nas APIs
- **PII:** PIIFilter no logging (CPF, email, telefone). 35+ prints removidos
- **Uploads:** `validate_image_upload` (tipo + 5MB) e `tenant_upload_path` para isolamento
- **XSS:** `format_html` corrigido em 9 funções, escape de HTML em JSON
- **Credenciais:** todas em variáveis de ambiente (`.env`)
- **HTTPS:** SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE via env var

### Testes

- **225 testes passando** (tenant isolation, endpoint auth, factories, module access)
- 10 arquivos de teste em `tests/`
- 28+ factories
- CI/CD com GitHub Actions (`.github/workflows/`)

### Padrão de Frontend

O projeto segue o design system documentado em `FRONTEND_BLUEPRINT.md`:
- Topbar (52px) + Sidebar (220px) + Main Content
- CSS em `apps/sistema/static/sistema/css/dashboard.css`
- Variáveis CSS com prefixo `--` (ex: `--primary`, `--border`)
- Font: Inter (Google Fonts)
- Icons: FontAwesome 6
- Navegação por page reload (SPA desativado)

### Módulos da Topbar

Dashboard | Comercial | Marketing | CS | Relatórios
- Configurações acessível pelo menu do perfil do usuário
- Botão Aurora (staff only) leva ao painel /aurora-admin/

### Como Rodar

```
cd dashboard_comercial/gerenciador_vendas
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
```

Acesso: http://127.0.0.1:8001/

### Commands úteis

```bash
# Seed de planos e features
python manage.py seed_planos --settings=gerenciador_vendas.settings_local

# Criar tenant
python manage.py criar_tenant --settings=gerenciador_vendas.settings_local

# Migrations locais
python manage.py makemigrations --settings=gerenciador_vendas.settings_local
python manage.py migrate --settings=gerenciador_vendas.settings_local

# Rodar testes (225 testes)
python manage.py test tests/ --settings=gerenciador_vendas.settings_local

# Check do projeto
python manage.py check --settings=gerenciador_vendas.settings_local
```
