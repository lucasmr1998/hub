# Roadmap de Produto — AuroraISP

**Status:** ✅ Atualizado
**Última atualização:** 31/03/2026
**Base:** Análise completa do código fonte (robo/) em 28/03/2026. Refatoração completa finalizada em 31/03/2026. vendas_web removido do INSTALLED_APPS.

---

## 1. Inventário do sistema atual

### 1.1 Estrutura de código

| Item | Valor |
|------|-------|
| Framework | Django 5.2, Python 3.11, DRF |
| Banco | PostgreSQL 15+ |
| Apps Django | 15 modulares em apps/ (vendas_web removido do INSTALLED_APPS) |
| Models totais | 67+ (todos com app_label natural, sem referência a vendas_web) |
| Views migradas | 9.457 linhas migradas para apps modulares |
| Rotas totais | 139 rotas em urls.py de cada app |
| Templates | 24 templates migrados para diretórios de cada app |
| Admin migrado | 3.676 linhas de admin distribuídas em 7 apps |
| Linhas de código | ~30.000+ |
| Testes | 225 (10 arquivos, 28+ factories, CI/CD) |
| Multi-tenancy | ✅ Implementado (29/03/2026). TenantMixin em todos os models incluindo CRM. Pendente deploy |
| Segurança | ✅ 5 críticas + 12 altas/médias corrigidas (30/03/2026) |
| API REST | ✅ DRF com TokenAuth + SessionAuth. Swagger em /api/docs/ |

### 1.2 Apps existentes

#### `vendas_web` — DESATIVADO (31/03/2026)
Removido do INSTALLED_APPS. Todos os 27 models, 128 views, 24 templates, 139 rotas, 3.676 linhas de admin, signals e services foram migrados para os 15 apps em `apps/`. O `urls.py` e `admin.py` estão vazios. Migrations limpas e regeneradas do zero.

#### `apps/` — Estrutura modular (15 apps)
Todos os models têm app_label natural (sem `app_label='vendas_web'`). Cada app possui seus próprios models, views, urls, templates, admin e migrations. Base.html e static files centralizados em `apps/sistema/`.

---

## 2. Mapa completo de funcionalidades

### 2.1 Domínio: Leads (vendas_web)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Captura de leads via WhatsApp/N8N | LeadProspecto | Produção |
| Score de qualificação automático (0-100) | LeadProspecto.score_qualificacao | Produção |
| Upload e validação de documentos | ImagemLeadProspecto | Produção |
| Workflow de processamento | Prospecto | Produção |
| Histórico de interações | HistoricoContato | Produção |
| Listagem com filtros e busca | views.leads_view | Produção |
| Visualização da conversa HTML/PDF | views.visualizar_conversa_lead | Produção |

### 2.2 Domínio: Atendimento/Bot (vendas_web)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Fluxos conversacionais configuráveis | FluxoAtendimento | Produção |
| 20 tipos de questão (texto, CPF, CEP, IA, condicional) | QuestaoFluxo | Produção |
| Sessão de atendimento com estado | AtendimentoFluxo | Produção |
| Respostas e tentativas registradas | RespostaQuestao, TentativaResposta | Produção |
| APIs dedicadas para N8N (15+ endpoints) | views_api_atendimento | Produção |
| Fluxo inteligente com roteamento condicional | QuestaoFluxo.condicoes_avancadas | Produção |

### 2.3 Domínio: Cadastro e Contrato (vendas_web)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Formulário de cadastro de cliente | CadastroCliente | Produção |
| Gestão de documentos por lead | DocumentoLead | Produção |
| Configuração do formulário de cadastro | ConfiguracaoCadastro | Produção |
| Catálogo de planos de internet | PlanoInternet | Produção |
| Opções de vencimento | OpcaoVencimento | Produção |
| Geração de PDF do contrato (WeasyPrint) | Signal automático | Produção |
| Envio de docs e aceite no HubSoft | contrato_service.py | Produção |

### 2.4 Domínio: Notificações (vendas_web)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Tipos de notificação (lead_novo, venda_aprovada...) | TipoNotificacao | Produção |
| Canais (WhatsApp, webhook) | CanalNotificacao | Produção |
| Preferências por usuário | PreferenciaNotificacao | Produção |
| Histórico de envios | Notificacao | Produção |
| Templates de mensagem | TemplateNotificacao | Produção |
| Config de WhatsApp Business | API dedicada | Produção |

### 2.5 Domínio: Campanhas (vendas_web)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Cadastro de campanhas de tráfego pago | CampanhaTrafego | Produção |
| Detecção automática por keyword | DeteccaoCampanha | Produção |
| Atribuição de origem ao lead | Signal automático | Produção |
| Métricas por campanha (leads, conversão) | Dashboard | Produção |

### 2.6 Domínio: Viabilidade (vendas_web)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Cadastro de cidades/bairros com cobertura | CidadeViabilidade | Produção |
| Consulta por CEP com ViaCEP | API pública | Produção |

### 2.7 Domínio: Sistema/Config (vendas_web)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Configuração da empresa (nome, logo, cores) | ConfiguracaoEmpresa | Produção |
| Configurações gerais do sistema | ConfiguracaoSistema | Produção |
| Configuração de recontato | ConfiguracaoRecontato | Produção |
| Status customizáveis | StatusConfiguravel | Produção |
| Log de auditoria | LogSistema | Produção |
| Gestão de usuários | User + monkey-patch telefone | Produção (com débito) |

### 2.8 Domínio: Integrações (app `integracoes`)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Conexão OAuth com HubSoft | IntegracaoAPI | Produção |
| Sincronização de clientes (command + systemd timer) | ClienteHubsoft | Produção |
| Sincronização de serviços/planos | ServicoClienteHubsoft | Produção |
| Log de auditoria de todas as chamadas | LogIntegracao | Produção |

### 2.9 Domínio: CRM (app `crm`)

| Funcionalidade | Model | Status |
|----------------|-------|--------|
| Pipeline kanban com estágios configuráveis | PipelineEstagio | Pronto |
| Oportunidade de venda (card do kanban) | OportunidadeVenda | Pronto |
| Drag and drop entre estágios | api_mover_oportunidade | Pronto |
| Histórico imutável de movimentação | HistoricoPipelineEstagio | Pronto |
| Equipes de vendas com líder | EquipeVendas | Pronto |
| Perfil de vendedor (cargo, ID HubSoft) | PerfilVendedor | Pronto |
| Tags de classificação | TagCRM | Pronto |
| Tarefas com vencimento, lembrete, auto-vence | TarefaCRM | Pronto |
| Notas internas (fixar, menções, tipos) | NotaInterna | Pronto |
| Metas individuais e por equipe | MetaVendas | Pronto |
| Segmentação dinâmica/manual de leads | SegmentoCRM, MembroSegmento | Pronto |
| Alertas de retenção (churn, inadimplência) | AlertaRetencao | Pronto |
| Auto-criação de oportunidade por score | Signal (post_save Lead) | Pronto |
| Conversão automática quando lead fecha | Signal (post_save Historico) | Pronto |
| Webhooks N8N por evento (novo, mudança, tarefa) | ConfiguracaoCRM | Pronto |
| Scanner de retenção | api_scanner_retencao | Pronto |
| Webhook inbound HubSoft contrato | webhook_hubsoft_contrato | Pronto |

### 2.10 Domínio: Dashboard e Relatórios (vendas_web)

| Funcionalidade | Status |
|----------------|--------|
| Dashboard com métricas em tempo real | Produção |
| Gráficos de funil e conversão | Produção |
| Monitoramento de atendimentos em tempo real | Produção |
| Jornada completa do cliente | Produção |
| Relatório de leads por período | Produção |
| Relatório de clientes ativos | Produção |
| Relatório de atendimentos com métricas | Produção |
| Relatório de conversões | Produção |
| Funil insights | Produção |

---

## 3. Débitos técnicos que bloqueiam o SaaS

### 3.1 Críticos (bloqueiam novos clientes)

| Débito | Impacto | Esforço | Status |
|--------|---------|---------|--------|
| **Multi-tenancy inexistente** | Impossível ter mais de 1 provedor no sistema | Alto | ✅ Concluído (29/03). TenantMixin em todos os models |
| **Credenciais hardcoded** (DB, SECRET_KEY, token Matrix) | Comprometimento total em repo público | Baixo | ✅ Concluído (29/03). Todas em variáveis de ambiente |
| **APIs sem autenticação** (middleware isenta `^api/`) | Qualquer pessoa manipula dados | Médio | ✅ Concluído (30/03). 27 endpoints com @api_token_required, 21 com @login_required |
| **DEBUG=True em produção** | Expõe stack traces com variáveis | Baixo | ✅ Concluído (29/03) |

### 3.2 Altos (impactam operação)

| Débito | Impacto | Esforço | Status |
|--------|---------|---------|--------|
| **God App (vendas_web)** com 27 models em 1 arquivo | Manutenção cada vez mais difícil | Alto | ✅ Concluído (31/03). vendas_web removido do INSTALLED_APPS. 15 apps modulares |
| **Chamadas HTTP síncronas em signals** | Save trava 30s+ se API externa cair | Médio | ⏳ Pendente (migrar para Celery ou Django-Q) |
| **Zero testes** para 25.000+ linhas | Regressões silenciosas | Alto | ✅ Concluído (30/03). 225 testes passando, CI/CD configurado |
| **50+ endpoints com @csrf_exempt** | Vulnerabilidade CSRF | Médio | ✅ Concluído (30/03). CSRF corrigido nos endpoints do frontend |
| **Monkey-patch do User** (add_to_class) | Frágil, quebra com updates do Django | Baixo | ⏳ Pendente (substituir por PerfilUsuario) |

### 3.3 Médios (dívida técnica)

| Débito | Impacto | Esforço | Status |
|--------|---------|---------|--------|
| Sem Django REST Framework (serialização manual) | Código repetitivo, sem validação padrão | Médio | ✅ Concluído (30/03). DRF implementado com TokenAuth + SessionAuth |
| Sem versionamento de API (/api/v1/) | Mudança breaking afeta todos os consumidores | Baixo | ✅ Concluído (30/03). API em /api/v1/, Swagger em /api/docs/ |
| Endpoints N8N duplicam lógica dos normais | Manutenção dobrada | Médio | ⏳ Pendente |
| Rotas legado sem prazo de remoção | Dívida crescente | Baixo | ✅ Concluído (31/03). vendas_web/urls.py vazio |
| WeasyPrint não está no requirements.txt | Deploy quebra em ambiente limpo | Baixo | ⏳ Pendente |

---

## 4. Arquitetura de apps

**Decisão (29/03/2026):** Opção A — sub-apps por pasta. Cada domínio é um app Django completo dentro do seu módulo. Aprovada pelo CEO por permitir migrations isoladas, ativação/desativação por plano (Start/Pro) e refatoração incremental do vendas_web.

### Estado atual (31/03/2026)

```
gerenciador_vendas/
├── apps/           → 15 apps modulares. FONTE DA VERDADE. Todos os models, views, templates, URLs, admin
├── vendas_web/     → MORTO. Removido do INSTALLED_APPS. urls.py e admin.py vazios
├── integracoes/    → Legacy. Código copiado para apps/integracoes/
└── crm/            → Legacy. Código copiado para apps/comercial/crm/
```

> **Migração concluída:** 9.457 linhas de views, 24 templates, 139 rotas, 3.676 linhas de admin migrados. Migrations limpas e regeneradas do zero. Todos os models com app_label natural.

### Estado alvo

```
gerenciador_vendas/
│
├── manage.py
├── requirements.txt
│
├── config/                              # Projeto Django (renomear gerenciador_vendas/)
│   ├── settings/
│   │   ├── base.py                      # Settings compartilhado
│   │   ├── local.py                     # SQLite, DEBUG=True
│   │   └── production.py                # PostgreSQL, DEBUG=False
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   │
│   │ ══════════════════════════════════
│   │  BASE (sempre ativo, todo tenant)
│   │ ══════════════════════════════════
│   │
│   ├── sistema/                         # Infraestrutura do SaaS
│   │   ├── models.py
│   │   │   ├── Tenant                   # NOVO: empresa cliente (provedor)
│   │   │   ├── PerfilUsuario            # NOVO: OneToOne(User) + FK(Tenant)
│   │   │   ├── ConfiguracaoEmpresa
│   │   │   ├── ConfiguracaoSistema
│   │   │   ├── ConfiguracaoRecontato
│   │   │   ├── StatusConfiguravel
│   │   │   └── LogSistema
│   │   ├── middleware.py                # TenantMiddleware + Auth
│   │   ├── mixins.py                   # TenantMixin (FK Tenant para herdar)
│   │   ├── context_processors.py
│   │   ├── admin.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── migrations/
│   │   └── templates/sistema/
│   │
│   ├── notificacoes/                    # Motor de comunicação (cross-module)
│   │   ├── models.py
│   │   │   ├── TipoNotificacao
│   │   │   ├── CanalNotificacao
│   │   │   ├── PreferenciaNotificacao
│   │   │   ├── Notificacao
│   │   │   └── TemplateNotificacao
│   │   ├── services/notification_service.py
│   │   ├── signals.py
│   │   ├── admin.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── migrations/
│   │   └── templates/notificacoes/
│   │
│   ├── integracoes/                     # Já existe, mover para apps/
│   │   ├── models.py
│   │   │   ├── IntegracaoAPI
│   │   │   ├── LogIntegracao
│   │   │   ├── ClienteHubsoft
│   │   │   └── ServicoClienteHubsoft
│   │   ├── services/hubsoft.py
│   │   ├── management/commands/
│   │   │   ├── processar_pendentes.py
│   │   │   ├── setup_hubsoft.py
│   │   │   └── sincronizar_clientes.py
│   │   ├── admin.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── migrations/
│   │
│   ├── dashboard/                       # Dashboard e relatórios (cross-module)
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── templates/dashboard/
│   │       ├── base.html                # Layout master (topbar + sidebar)
│   │       ├── dashboard.html
│   │       ├── relatorios.html
│   │       └── ajuda.html
│   │
│   │ ══════════════════════════════════
│   │  MÓDULO COMERCIAL (Start / Pro)
│   │ ══════════════════════════════════
│   │
│   ├── comercial/
│   │   ├── __init__.py                  # Package (não é app Django)
│   │   │
│   │   ├── leads/                       # App: captura e qualificação
│   │   │   ├── models.py               # LeadProspecto, ImagemLeadProspecto, Prospecto, HistoricoContato
│   │   │   ├── signals.py
│   │   │   ├── admin.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   ├── migrations/
│   │   │   └── templates/comercial/leads/
│   │   │
│   │   ├── atendimento/                 # App: bot conversacional (N8N)
│   │   │   ├── models.py               # FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, RespostaQuestao, TentativaResposta
│   │   │   ├── services/atendimento_service.py
│   │   │   ├── admin.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   ├── migrations/
│   │   │   └── templates/comercial/atendimento/
│   │   │
│   │   ├── cadastro/                    # App: registro e ativação
│   │   │   ├── models.py               # CadastroCliente, DocumentoLead, ConfiguracaoCadastro, PlanoInternet, OpcaoVencimento
│   │   │   ├── services/contrato_service.py
│   │   │   ├── signals.py
│   │   │   ├── admin.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   ├── migrations/
│   │   │   └── templates/comercial/cadastro/
│   │   │
│   │   ├── viabilidade/                 # App: cobertura técnica
│   │   │   ├── models.py               # CidadeViabilidade
│   │   │   ├── admin.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   └── migrations/
│   │   │
│   │   └── crm/                         # App: CRM Kanban (Plano Pro)
│   │       ├── models.py               # PipelineEstagio, EquipeVendas, PerfilVendedor, TagCRM, OportunidadeVenda, HistoricoPipelineEstagio, TarefaCRM, NotaInterna, MetaVendas, SegmentoCRM, MembroSegmento, AlertaRetencao, ConfiguracaoCRM
│   │       ├── management/commands/
│   │       ├── signals.py
│   │       ├── admin.py
│   │       ├── views.py
│   │       ├── urls.py
│   │       ├── migrations/
│   │       └── templates/comercial/crm/
│   │
│   │ ══════════════════════════════════
│   │  MÓDULO MARKETING (Start / Pro)
│   │ ══════════════════════════════════
│   │
│   ├── marketing/
│   │   ├── __init__.py                  # Package (não é app Django)
│   │   │
│   │   ├── campanhas/                   # App: tráfego pago e atribuição
│   │   │   ├── models.py               # CampanhaTrafego, DeteccaoCampanha
│   │   │   ├── admin.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   ├── migrations/
│   │   │   └── templates/marketing/campanhas/
│   │   │
│   │   ├── automacoes/                  # App: motor de réguas (a construir)
│   │   │   ├── models.py               # Regua, EtapaRegua, ExecucaoRegua, LogExecucao
│   │   │   ├── services/regua_engine.py
│   │   │   ├── admin.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   ├── migrations/
│   │   │   └── templates/marketing/automacoes/
│   │   │
│   │   └── email/                       # App: e-mail marketing (a construir)
│   │       ├── models.py               # ProvedorEmail, CampanhaEmail, EnvioEmail
│   │       ├── services/
│   │       ├── admin.py
│   │       ├── views.py
│   │       ├── urls.py
│   │       ├── migrations/
│   │       └── templates/marketing/email/
│   │
│   │ ══════════════════════════════════
│   │  MÓDULO CS (Start / Pro)
│   │ ══════════════════════════════════
│   │
│   └── cs/
│       ├── __init__.py                  # Package (não é app Django)
│       │
│       ├── retencao/                    # App: churn prevention (a construir)
│       │   ├── models.py               # HealthScore, AcaoRetencao
│       │   ├── services/
│       │   ├── admin.py
│       │   ├── views.py
│       │   ├── urls.py
│       │   ├── migrations/
│       │   └── templates/cs/retencao/
│       │
│       ├── nps/                         # App: NPS automatizado (a construir)
│       │   ├── models.py               # PesquisaNPS, RespostaNPS, ConfiguracaoNPS
│       │   ├── admin.py
│       │   ├── views.py
│       │   ├── urls.py
│       │   ├── migrations/
│       │   └── templates/cs/nps/
│       │
│       └── clube/                       # App: clube de benefícios (megaroleta)
│           ├── models.py               # A definir
│           ├── admin.py
│           ├── views.py
│           ├── urls.py
│           ├── migrations/
│           └── templates/cs/clube/
│
├── static/css/dashboard.css             # Design system global
└── templates/admin/                     # Admin customizado
```

### Registro no Django

```python
# config/settings/base.py

INSTALLED_APPS = [
    # Base (sempre ativo)
    'apps.sistema',
    'apps.notificacoes',
    'apps.integracoes',
    'apps.dashboard',

    # Módulo Comercial
    'apps.comercial.leads',
    'apps.comercial.atendimento',
    'apps.comercial.cadastro',
    'apps.comercial.viabilidade',
    'apps.comercial.crm',           # Apenas Plano Pro

    # Módulo Marketing (quando contratado)
    'apps.marketing.campanhas',
    'apps.marketing.automacoes',
    'apps.marketing.email',

    # Módulo CS (quando contratado)
    'apps.cs.retencao',
    'apps.cs.nps',
    'apps.cs.clube',
]
```

```python
# config/urls.py

urlpatterns = [
    path('admin/', admin.site.urls),

    # Base
    path('',              include('apps.sistema.urls')),
    path('dashboard/',    include('apps.dashboard.urls')),
    path('notificacoes/', include('apps.notificacoes.urls')),
    path('integracoes/',  include('apps.integracoes.urls')),

    # Módulo Comercial
    path('comercial/leads/',        include('apps.comercial.leads.urls')),
    path('comercial/atendimento/',  include('apps.comercial.atendimento.urls')),
    path('comercial/cadastro/',     include('apps.comercial.cadastro.urls')),
    path('comercial/viabilidade/',  include('apps.comercial.viabilidade.urls')),
    path('comercial/crm/',          include('apps.comercial.crm.urls')),

    # Módulo Marketing
    path('marketing/campanhas/',    include('apps.marketing.campanhas.urls')),
    path('marketing/automacoes/',   include('apps.marketing.automacoes.urls')),
    path('marketing/email/',        include('apps.marketing.email.urls')),

    # Módulo CS
    path('cs/retencao/',  include('apps.cs.retencao.urls')),
    path('cs/nps/',       include('apps.cs.nps.urls')),
    path('cs/clube/',     include('apps.cs.clube.urls')),
]
```

### Resumo por camada

| Camada | Apps | Models | Sempre ativo? |
|--------|------|--------|---------------|
| **Base** | sistema, notificacoes, integracoes, dashboard | 16 | Sim |
| **Comercial Start** | comercial/leads, comercial/atendimento, comercial/cadastro, comercial/viabilidade | 15 | Por contratação |
| **Comercial Pro** | Start + comercial/crm | +13 | Por contratação |
| **Marketing Start** | marketing/campanhas | 2 | Por contratação |
| **Marketing Pro** | Start + marketing/automacoes + marketing/email | +7 (novos) | Por contratação |
| **CS Start** | cs/retencao + cs/nps | Novos | Por contratação |
| **CS Pro** | Start + cs/clube | Novos | Por contratação |

### Mapeamento: módulos AuroraISP vs apps

| Módulo AuroraISP | Apps Django |
|------------------|------------|
| **Sistema (base)** | apps.sistema, apps.notificacoes, apps.integracoes, apps.dashboard |
| **Comercial Start** | apps.comercial.leads, apps.comercial.atendimento, apps.comercial.cadastro, apps.comercial.viabilidade |
| **Comercial Pro** | Comercial Start + apps.comercial.crm |
| **Marketing Start** | apps.marketing.campanhas |
| **Marketing Pro** | Marketing Start + apps.marketing.automacoes, apps.marketing.email |
| **CS Start** | apps.cs.retencao, apps.cs.nps |
| **CS Pro** | CS Start + apps.cs.clube |

---

## 5. Roadmap de produto por fases

### Fase 0 — Segurança e Fundação (bloqueadores) ✅ CONCLUÍDA
**Prazo alvo:** até 30/03/2026
**Responsável:** Dev (CTO)
**Status:** Todos os itens críticos concluídos entre 29/03 e 31/03/2026.

| Ação | Prioridade | Status |
|------|-----------|--------|
| Remover credenciais hardcoded do código | Urgente | ✅ Concluído (29/03) |
| Rotacionar senha do banco, token Matrix, SECRET_KEY | Urgente | ⏳ Pendente (requer deploy) |
| DEBUG=False em produção | Urgente | ✅ Concluído (29/03) |
| Restringir APIs (remover isenção geral `^api/`) | Urgente | ✅ Concluído (30/03). 48+ endpoints autenticados |
| Implementar token auth para N8N | Urgente | ✅ Concluído (30/03). @api_token_required |
| Multi-tenancy (Tenant + middleware + FK em todos os models) | Crítico | ✅ Concluído (29/03). TenantMixin em todos os models |
| Remover @csrf_exempt dos endpoints do frontend | Alto | ✅ Concluído (30/03) |
| Scan de segurança completo | Alto | ✅ Concluído (30/03). 5 críticas + 12 altas/médias corrigidas |

### Fase 1 — Validação comercial (produto mínimo para vender) 🔧 EM ANDAMENTO
**Prazo alvo:** abril/2026
**Meta:** 15 clientes pagantes até junho/2026
**Status:** Migração completa. vendas_web removido. Foco agora em deploy e ambiente de demo.

| Ação | Prioridade | Status |
|------|-----------|--------|
| Criar app `apps.sistema` com Tenant, PerfilUsuario, configs | Alto | ✅ Concluído (29/03) |
| Extrair `apps.comercial.leads` de vendas_web | Alto | ✅ Concluído (31/03). Models, views, URLs, templates, admin migrados |
| Extrair `apps.comercial.atendimento` de vendas_web | Alto | ✅ Concluído (31/03). Models, views, URLs, templates, admin migrados |
| Extrair `apps.comercial.cadastro` de vendas_web | Alto | ✅ Concluído (31/03). Models, views, URLs, templates, admin migrados |
| Extrair `apps.comercial.viabilidade` de vendas_web | Alto | ✅ Concluído (31/03). Models, views, URLs, templates, admin migrados |
| Mover `crm/` para `apps.comercial.crm` | Alto | ✅ Concluído (29/03) |
| Mover `integracoes/` para `apps.integracoes` | Alto | ✅ Concluído (29/03) |
| Extrair `apps.notificacoes` de vendas_web | Alto | ✅ Concluído (31/03). Models, views, URLs, templates, admin migrados |
| Extrair `apps.marketing.campanhas` de vendas_web | Alto | ✅ Concluído (31/03). Models, views, URLs, templates, admin migrados |
| Criar `apps.dashboard` (views de relatório) | Alto | ✅ Concluído (31/03). Views migradas |
| vendas_web removido do INSTALLED_APPS | Alto | ✅ Concluído (31/03). urls.py e admin.py vazios |
| Migrations limpas e regeneradas | Alto | ✅ Concluído (31/03) |
| Django REST Framework implementado | Alto | ✅ Concluído (30/03). TokenAuth + SessionAuth, Swagger |
| Testes unitários (225 testes) | Alto | ✅ Concluído (30/03). 10 arquivos, 28+ factories, CI/CD |
| Renomear `gerenciador_vendas/` para `config/` | Médio | ⏳ Aguardando (baixo impacto) |
| Substituir monkey-patch do User por PerfilUsuario | Alto | ⏳ Pendente |
| Mover chamadas HTTP de signals para tasks assíncronas | Alto | ⏳ Pendente |
| Ambiente de demo multi-tenant | Alto | ⏳ Pendente (requer deploy) |
| Onboarding automatizado (criar tenant + config inicial) | Alto | ⏳ Pendente |

### Fase 2 — Produto completo Comercial
**Prazo alvo:** maio/2026

| Ação | Prioridade | Esforço |
|------|-----------|---------|
| CRM integrado ao fluxo de vendas (já pronto, validar com clientes) | Alto | Validação |
| Validação automática de documentos por IA | Médio | 2 semanas |
| Relatórios de conversão por etapa do pipeline | Médio | 1 semana |
| Adotar Django REST Framework | Médio | ✅ Concluído (30/03) |
| Versionamento de API (/api/v1/) | Médio | ✅ Concluído (30/03) |
| Case público com autorização de cliente | Médio | Comercial |

### Fase 3 — Módulo Marketing
**Prazo alvo:** julho/2026
**Base existente:** notificacoes (5 models), campanhas (2 models), crm.SegmentoCRM

| Ação | O que existe | O que falta |
|------|-------------|-------------|
| Motor de réguas de automação | N8N já roda. Templates de notificação existem | Engine interna com gatilhos por evento, tempo e comportamento |
| E-mail marketing | Templates de notificação existem | Integração com provedor de e-mail (SendGrid, SES) |
| WhatsApp automatizado | Canal WhatsApp já configurado | Réguas completas (trial, pós-ativação, retenção) |
| Segmentação avançada | SegmentoCRM com filtros JSON existe | UI para criar segmentos por comportamento |
| Relatórios de campanha | Métricas básicas por campanha existem | Dashboard dedicado com CAC, ROAS, LTV |
| Tráfego pago com IA | Rastreamento de campanhas existe | Otimização automática de criativos |

### Fase 4 — Módulo CS
**Prazo alvo:** setembro/2026
**Base existente:** integracoes.ClienteHubsoft, crm.AlertaRetencao, notificacoes

| Ação | O que existe | O que falta |
|------|-------------|-------------|
| Prevenção de churn | AlertaRetencao com score e scanner existe | Detecção automática por comportamento no ERP |
| NPS automatizado | Sistema de notificações existe | Pesquisa de NPS com régua automática |
| Clube de Benefícios | Projeto megaroleta/ em desenvolvimento | Integrar com o hub e multi-tenancy |
| Upsell automatizado | Segmentos + alertas existem | Régua de oferta por perfil do cliente |
| Health score do cliente | churn_risk_score existe na OportunidadeVenda | Cálculo automático por múltiplas variáveis |

### Fase 5 — Escala
**Prazo alvo:** Q4 2026

| Ação | Responsável |
|------|------------|
| Expansão para outros ERPs (Voalle, SGP) | Dev |
| Inbound (blog, YouTube, LinkedIn) | Marketing |
| Eventos do setor (ISP Summit, ABRINT) | CEO + Parceiro |
| Contato formal com HubSoft para parceria | CEO |
| Segundo parceiro comercial | Head de Vendas |

---

## 6. O que já serve de base para cada módulo futuro

| Base existente no código | Onde está | Módulo que aproveita |
|-------------------------|-----------|---------------------|
| TipoNotificacao, CanalNotificacao, TemplateNotificacao, Notificacao | apps/notificacoes/ | Marketing (réguas, e-mail, WhatsApp) |
| PreferenciaNotificacao | apps/notificacoes/ | Marketing e CS |
| CampanhaTrafego, DeteccaoCampanha | apps/marketing/campanhas/ | Marketing (performance, atribuição) |
| SegmentoCRM, MembroSegmento | apps/comercial/crm/ | Marketing (segmentação de base) |
| ClienteHubsoft, ServicoClienteHubsoft | apps/integracoes/ | CS (base ativa, churn, NPS) |
| AlertaRetencao | apps/comercial/crm/ | CS (churn prevention) |
| N8N integrado com APIs dedicadas | apps/comercial/atendimento/ | Marketing e CS (automações) |
| OportunidadeVenda.churn_risk_score | apps/comercial/crm/ | CS (health score) |
| ConfiguracaoCRM.webhook_n8n_* | apps/comercial/crm/ | Marketing e CS (event-driven) |

---

## 7. Critérios de transição entre fases

| De | Para | Critério |
|----|------|---------|
| Fase 0 | Fase 1 | ✅ Multi-tenancy funcionando. Zero credenciais expostas. APIs autenticadas |
| Fase 1 | Fase 2 | 🔧 Separação em apps concluída. Falta: 5 clientes ativos e pagantes + deploy em produção |
| Fase 2 | Fase 3 | 15 clientes. CRM validado com feedback. DRF adotado (✅ já concluído) |
| Fase 3 | Fase 4 | Motor de réguas rodando. Ao menos 1 régua em produção por cliente |
| Fase 4 | Fase 5 | NPS implementado. Clube de benefícios integrado. 50+ clientes |

---

## 8. Dependências entre fases

```
Fase 0 (Segurança + Multi-tenancy)
  │
  ▼
Fase 1 (Separação em apps + Tenant)
  │
  ├──► Fase 2 (Comercial completo)
  │       │
  │       ├──► Fase 3 (Marketing)
  │       │       │
  │       │       └──► Fase 4 (CS)
  │       │               │
  │       │               └──► Fase 5 (Escala)
  │       │
  │       └──► Feedback de clientes alimenta Fases 3 e 4
  │
  └──► Logo criada (desbloqueador de materiais visuais)
```

---

## Pendências

- [x] CEO: definir prazo real para Fase 0 (segurança) — Resolvido em 29/03/2026. Credenciais removidas do código.
- [x] CTO: estimar esforço real de multi-tenancy — Implementado em 29/03/2026. TenantMixin em todos os models.
- [x] CTO: decidir estratégia de multi-tenancy — FK tenant_id via TenantMixin. Aprovado e implementado.
- [ ] PM: validar com primeiro cliente se CRM kanban atende ou precisa de ajustes
- [x] CEO: definir se megaroleta será integrado ao hub ou mantido separado — Resolvido em 29/03/2026. Apps CS migrados para robo/apps/cs/. App gestão permanece no megaroleta.
