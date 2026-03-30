# Roadmap de Produto — AuroraISP

**Status:** 🔧 Em construção
**Última atualização:** 29/03/2026
**Base:** Análise completa do código fonte (robo/) em 28/03/2026. Atualizado após refatoração de 29/03/2026.

---

## 1. Inventário do sistema atual

### 1.1 Estrutura de código

| Item | Valor |
|------|-------|
| Framework | Django 5.2, Python 3.11 |
| Banco | PostgreSQL 15+ |
| Apps Django | 14+ (10 novos em apps/ + vendas_web legado + integracoes + crm + admin_aurora) |
| Models totais | 67+ (originais + Tenant, PerfilUsuario, Plano, FeaturePlano + 20 CS migrados) |
| Rotas totais | 360+ (288 originais + 76 CS migrados) |
| Templates | 100+ (30 originais + 67 CS migrados) |
| Linhas de código | ~30.000+ |
| Testes | 16 (isolamento de tenant) |
| Multi-tenancy | ✅ Implementado (29/03/2026). Pendente deploy em produção |

### 1.2 Apps existentes

#### `vendas_web` (God App, precisa separar)
27 models em um único `models.py` de 5.349 linhas. 128 funções em `views.py` de 7.464 linhas. Concentra 7 domínios diferentes misturados.

#### `integracoes` (app separado, bem estruturado)
4 models: IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft.
Service dedicado para HubSoft com OAuth, sync de clientes e management commands.

#### `crm` (app separado, bem estruturado)
12 models com pipeline kanban, equipes, metas, segmentos, retenção e configuração.
66 rotas, 10 templates, signals de auto-criação de oportunidade e conversão automática.

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

| Débito | Impacto | Esforço |
|--------|---------|---------|
| **Multi-tenancy inexistente** | Impossível ter mais de 1 provedor no sistema | Alto |
| **Credenciais hardcoded** (DB, SECRET_KEY, token Matrix) | Comprometimento total em repo público | Baixo |
| **APIs sem autenticação** (middleware isenta `^api/`) | Qualquer pessoa manipula dados | Médio |
| **DEBUG=True em produção** | Expõe stack traces com variáveis | Baixo |

### 3.2 Altos (impactam operação)

| Débito | Impacto | Esforço |
|--------|---------|---------|
| **God App (vendas_web)** com 27 models em 1 arquivo | Manutenção cada vez mais difícil, multi-tenancy impossível de aplicar limpo | Alto |
| **Chamadas HTTP síncronas em signals** | Save trava 30s+ se API externa cair | Médio |
| **Zero testes** para 25.000+ linhas | Regressões silenciosas, medo de refatorar | Alto |
| **50+ endpoints com @csrf_exempt** | Vulnerabilidade CSRF em todo o sistema | Médio |
| **Monkey-patch do User** (add_to_class) | Frágil, quebra com updates do Django | Baixo |

### 3.3 Médios (dívida técnica)

| Débito | Impacto | Esforço |
|--------|---------|---------|
| Sem Django REST Framework (serialização manual) | Código repetitivo, sem validação padrão | Médio |
| Sem versionamento de API (/api/v1/) | Mudança breaking afeta todos os consumidores | Baixo |
| Endpoints N8N duplicam lógica dos normais | Manutenção dobrada | Médio |
| Rotas legado sem prazo de remoção | Dívida crescente | Baixo |
| WeasyPrint não está no requirements.txt | Deploy quebra em ambiente limpo | Baixo |

---

## 4. Arquitetura de apps

**Decisão (29/03/2026):** Opção A — sub-apps por pasta. Cada domínio é um app Django completo dentro do seu módulo. Aprovada pelo CEO por permitir migrations isoladas, ativação/desativação por plano (Start/Pro) e refatoração incremental do vendas_web.

### Estado atual

```
gerenciador_vendas/
├── vendas_web/     → 27 models, 128 views, 222 rotas (God App)
├── integracoes/    → 4 models (bem separado)
└── crm/            → 12 models (bem separado, referência de qualidade)
```

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

### Fase 0 — Segurança e Fundação (bloqueadores)
**Prazo alvo:** até 30/03/2026
**Responsável:** Dev (CTO)

| Ação | Prioridade | Esforço |
|------|-----------|---------|
| Remover credenciais hardcoded do código | Urgente | 1 dia | ✅ Concluído (29/03) |
| Rotacionar senha do banco, token Matrix, SECRET_KEY | Urgente | 1 dia | ⏳ Pendente (deploy) |
| DEBUG=False em produção | Urgente | 1 hora | ✅ Concluído (29/03) |
| Restringir APIs (remover isenção geral `^api/`) | Urgente | 2 dias | ⏳ Pendente |
| Implementar token auth para N8N | Urgente | 1 dia | ⏳ Pendente |
| Multi-tenancy (model Tenant + middleware + FK em todos os models) | Crítico | 1-2 semanas | ✅ Concluído (29/03) |
| Remover @csrf_exempt dos endpoints do frontend | Alto | 2 dias | ⏳ Pendente |

### Fase 1 — Validação comercial (produto mínimo para vender)
**Prazo alvo:** abril/2026
**Meta:** 15 clientes pagantes até junho/2026

| Ação | Prioridade | Esforço | Status |
|------|-----------|---------|--------|
| Criar app `apps.sistema` com Tenant, PerfilUsuario, configs | Alto | 1 semana | ✅ Scaffold + models prontos (29/03) |
| Extrair `apps.comercial.leads` de vendas_web | Alto | 3 dias | 🔧 Scaffold criado, falta mover models |
| Extrair `apps.comercial.atendimento` de vendas_web | Alto | 3 dias | 🔧 Scaffold criado, falta mover models |
| Extrair `apps.comercial.cadastro` de vendas_web | Alto | 3 dias | 🔧 Scaffold criado, falta mover models |
| Extrair `apps.comercial.viabilidade` de vendas_web | Alto | 1 dia | 🔧 Scaffold criado, falta mover models |
| Mover `crm/` para `apps.comercial.crm` | Alto | 1 dia | ✅ Copiado, apps.py atualizado (29/03) |
| Mover `integracoes/` para `apps.integracoes` | Alto | 1 dia | ✅ Copiado, apps.py atualizado (29/03) |
| Extrair `apps.notificacoes` de vendas_web | Alto | 2 dias | 🔧 Scaffold criado, falta mover models |
| Extrair `apps.marketing.campanhas` de vendas_web | Alto | 1 dia | 🔧 Scaffold criado, falta mover models |
| Criar `apps.dashboard` (views de relatório) | Alto | 2 dias | 🔧 Scaffold criado, falta mover views |
| Renomear `gerenciador_vendas/` para `config/` | Alto | 1 dia | ⏳ Aguardando |
| Substituir monkey-patch do User por PerfilUsuario | Alto | 2 dias |
| Mover chamadas HTTP de signals para tasks assíncronas (Celery ou Django-Q) | Alto | 1 semana |
| Testes unitários para services e signals | Alto | 1 semana |
| Ambiente de demo multi-tenant | Alto | 3 dias |
| Onboarding automatizado (criar tenant + config inicial) | Alto | 3 dias |

### Fase 2 — Produto completo Comercial
**Prazo alvo:** maio/2026

| Ação | Prioridade | Esforço |
|------|-----------|---------|
| CRM integrado ao fluxo de vendas (já pronto, validar com clientes) | Alto | Validação |
| Validação automática de documentos por IA | Médio | 2 semanas |
| Relatórios de conversão por etapa do pipeline | Médio | 1 semana |
| Adotar Django REST Framework | Médio | 2 semanas |
| Versionamento de API (/api/v1/) | Médio | 1 semana |
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
| TipoNotificacao, CanalNotificacao, TemplateNotificacao, Notificacao | vendas_web (mover para notificacoes/) | Marketing (réguas, e-mail, WhatsApp) |
| PreferenciaNotificacao | vendas_web (mover para notificacoes/) | Marketing e CS |
| CampanhaTrafego, DeteccaoCampanha | vendas_web (mover para campanhas/) | Marketing (performance, atribuição) |
| SegmentoCRM, MembroSegmento | crm/ | Marketing (segmentação de base) |
| ClienteHubsoft, ServicoClienteHubsoft | integracoes/ | CS (base ativa, churn, NPS) |
| AlertaRetencao | crm/ | CS (churn prevention) |
| N8N integrado com APIs dedicadas | vendas_web/ | Marketing e CS (automações) |
| OportunidadeVenda.churn_risk_score | crm/ | CS (health score) |
| ConfiguracaoCRM.webhook_n8n_* | crm/ | Marketing e CS (event-driven) |

---

## 7. Critérios de transição entre fases

| De | Para | Critério |
|----|------|---------|
| Fase 0 | Fase 1 | Multi-tenancy funcionando. Zero credenciais expostas. APIs autenticadas |
| Fase 1 | Fase 2 | 5 clientes ativos e pagantes. Separação em apps concluída |
| Fase 2 | Fase 3 | 15 clientes. CRM validado com feedback. DRF adotado |
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
