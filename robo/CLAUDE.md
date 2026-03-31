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

O projeto foi refatorado de um monolito (vendas_web) para apps modulares:

```
gerenciador_vendas/
├── manage.py
├── gerenciador_vendas/          # Projeto Django (settings, urls, wsgi)
│   ├── settings.py              # Produção (PostgreSQL)
│   ├── settings_local.py        # Desenvolvimento (SQLite)
│   └── urls.py
│
├── apps/
│   ├── sistema/                 # Tenant, PerfilUsuario, configs do SaaS
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
│   │   └── crm/                 # CRM Kanban (Plano Pro)
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
├── vendas_web/                  # God App legado (em processo de migração)
├── integracoes/                 # App original (copiado para apps/integracoes)
└── crm/                         # App original (copiado para apps/comercial/crm)
```

### Multi-tenancy

Implementado localmente, pendente deploy em produção.
- **Tenant:** model central que representa cada provedor
- **TenantMixin:** mixin com FK tenant + auto-save + auto-filtro
- **TenantManager:** filtra automaticamente por tenant do request
- **TenantMiddleware:** resolve o tenant via thread-local
- **Admin Aurora:** painel /aurora-admin/ para gerenciar tenants e planos

### Padrão de Frontend

O projeto segue o design system documentado em `FRONTEND_BLUEPRINT.md`:
- Topbar (52px) + Sidebar (220px) + Main Content
- CSS em `vendas_web/static/vendas_web/css/dashboard.css`
- Variáveis CSS com prefixo `--` (ex: `--primary`, `--border`)
- Font: Inter (Google Fonts)
- Icons: FontAwesome 6

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
```
