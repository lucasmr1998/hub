# Testes — AuroraISP

**Última atualização:** 01/04/2026
**Total de testes:** 291 (287 passando, 4 skipped)
**Cobertura global:** 40%
**Framework:** pytest + pytest-django + pytest-cov + factory_boy

---

## Como rodar

```bash
cd robo/dashboard_comercial/gerenciador_vendas

# Rodar todos os testes
python -m pytest tests/

# Com cobertura
python -m pytest tests/ --cov=apps --cov-report=term

# Arquivo específico
python -m pytest tests/test_automacoes.py -v

# Teste específico
python -m pytest tests/test_automacoes.py::EngineDispararEventoTest::test_condicao_verdadeira_executa -v
```

O `pytest.ini` já configura `DJANGO_SETTINGS_MODULE = gerenciador_vendas.settings_local` (SQLite in-memory).

---

## Estrutura dos testes

| Arquivo | Testes | O que cobre |
|---------|--------|-------------|
| `test_tenant_isolation.py` | 62 | Isolamento multi-tenant: auto-filtro, cross-tenant, middleware, set/get tenant |
| `test_endpoint_auth.py` | 48 | Autenticação de endpoints: @login_required, @api_token_required, acesso negado |
| `test_models_comercial.py` | 35 | Models de leads, atendimento, cadastro, CRM: criação, validações, str |
| `test_models_cs.py` | 28 | Models CS: MembroClube, NivelClube, Parceiro, Cupom, Indicação, Carteirinha |
| `test_models_integracoes.py` | 15 | Models IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft |
| `test_models_marketing.py` | 8 | Models CampanhaTrafego, DeteccaoCampanha |
| `test_models_notificacoes.py` | 12 | Models TipoNotificacao, CanalNotificacao, Notificacao, Template |
| `test_api_drf.py` | 17 | API DRF: CRUD leads N8N, panel ViewSets, autenticação Token/Session |
| `test_signals.py` | 15 | Signals: auto-criação CRM, envio HubSoft, conversão lead |
| `test_module_access.py` | 6 | Acesso a módulos por plano (Start vs Pro) |
| `test_admin_aurora.py` | 2 | Admin Aurora: dashboard, criar tenant |
| **test_automacoes.py** | **43** | **Automações: models, engine, condições, ações, views, tenant isolation** |

**Factories:** 30+ classes em `tests/factories.py` cobrindo todos os apps.

---

## Cobertura por módulo

### Bem cobertos (>70%)

| Arquivo | Cobertura | Obs |
|---------|-----------|-----|
| `sistema/middleware.py` | 98% | Core do multi-tenant |
| `sistema/mixins.py` | 100% | TenantMixin |
| `sistema/models.py` | 86% | Tenant, PerfilUsuario, configs |
| `sistema/authentication.py` | 93% | APITokenAuthentication |
| `sistema/context_processors.py` | 100% | |
| `sistema/logging_filters.py` | 100% | PIIFilter |
| `crm/models.py` | 90% | Pipeline, Oportunidade, Tarefa |
| `crm/signals.py` | 85% | Auto-criação CRM |
| `clube/models.py` | 93% | MembroClube, NivelClube, Regras |
| `parceiros/models.py` | 96% | Parceiro, Cupom, Resgate |
| `indicacoes/models.py` | 98% | Indicação |
| `notificacoes/models.py` | 98% | Todos os models |
| `integracoes/models.py` | 100% | IntegracaoAPI, ClienteHubsoft |
| `campanhas/models.py` | 93% | CampanhaTrafego |
| `automacoes/models.py` | 93% | RegraAutomacao, Condição, Ação |
| `automacoes/views.py` | 97% | CRUD completo |
| `automacoes/engine.py` | 71% | Dispatcher + executores |
| `api/serializers_panel.py` | 100% | ViewSets DRF |
| `api/serializers_n8n.py` | 93% | Serializers N8N |

### Parcialmente cobertos (30-70%)

| Arquivo | Cobertura | O que falta |
|---------|-----------|-------------|
| `sistema/decorators.py` | 58% | Testar @webhook_token_required |
| `sistema/encrypted_fields.py` | 59% | Testar encrypt/decrypt |
| `sistema/validators.py` | 40% | Testar validate_image_upload |
| `leads/models.py` | 49% | Properties e methods complexos |
| `leads/admin.py` | 56% | Actions admin |
| `atendimento/admin.py` | 45% | Admin customizado |
| `cadastro/models.py` | 74% | Geração de PDF, signals |
| `integracoes/signals.py` | 36% | Envio para HubSoft (mock) |
| `automacoes/signals.py` | 67% | Mais cenários de evento |

### Sem cobertura significativa (<30%)

| Arquivo | Cobertura | Motivo |
|---------|-----------|--------|
| `dashboard/views.py` | 8% | 736 linhas, muitas queries complexas |
| `clube/views/api_views.py` | 7% | 393 linhas, integração HubSoft |
| `clube/views/dashboard_views.py` | 18% | Dashboards com Chart.js |
| `crm/views.py` | 16% | 784 linhas, CRM pipeline |
| `leads/views.py` | 22% | 679 linhas, listagem, filtros |
| `sistema/views.py` | 23% | Autenticação, configurações |
| `notificacoes/views.py` | 16% | 508 linhas, maioria desativada |
| `integracoes/services/hubsoft.py` | 12% | Chamadas HTTP externas |
| `suporte/views.py` | 15% | Dashboard, tickets |
| `cadastro/services/contrato_service.py` | 0% | Integração HubSoft/Matrix |
| `atendimento/services/atendimento_service.py` | 0% | Lógica do bot |
| Management commands | 0% | seed_planos, criar_tenant, etc |

---

## O que é testado hoje

### Multi-tenancy (prioridade máxima)
- TenantManager filtra automaticamente por tenant ativo
- Dados de tenant A não vazam para tenant B
- Middleware resolve tenant corretamente
- Cross-tenant access retorna vazio
- Models com TenantMixin isolam dados

### Autenticação e segurança
- Endpoints protegidos retornam 401/403 sem auth
- @api_token_required valida token
- @login_required redireciona para login
- API DRF com TokenAuth e SessionAuth

### Models
- Criação, validações, str de todos os models principais
- Relacionamentos (ForeignKey, ManyToMany)
- Properties calculadas (taxa_sucesso, nivel_atual, etc)

### Automações (novo)
- Engine: disparo de evento, avaliação de condições (7 operadores), execução de ações
- Ações: notificação, WhatsApp (mock), webhook (mock), criar tarefa, dar pontos
- Delay/agendamento
- Tenant isolation
- Views: CRUD completo, toggle, histórico

### Signals
- Auto-criação de oportunidade CRM quando lead qualificado
- Envio para HubSoft (parcial)
- Conversão de lead

---

## O que precisa melhorar

### Prioridade 1: Views de página
As views representam 60%+ do código mas têm <25% de cobertura. Motivo: testam lógica de negócio + renderização + queries complexas. Abordagem recomendada: testes de integração com `client.get()` verificando status_code, context e conteúdo.

**Arquivos prioritários:**
- `crm/views.py` (784 linhas, 16%) — Pipeline, configurações, equipes
- `leads/views.py` (679 linhas, 22%) — Listagem, filtros, APIs internas
- `dashboard/views.py` (736 linhas, 8%) — Dashboards e relatórios

### Prioridade 2: Services com integração externa
Services que chamam APIs externas (HubSoft, N8N, Matrix) têm 0-12% de cobertura. Precisam de mocks.

**Arquivos:**
- `integracoes/services/hubsoft.py` (12%) — Mock de requests
- `cadastro/services/contrato_service.py` (0%) — Mock de upload de docs
- `clube/services/hubsoft_service.py` (16%) — Mock de conexão PostgreSQL

### Prioridade 3: Management commands
Nenhum command tem testes. São executados manualmente mas podem quebrar silenciosamente.

---

## Configuração

### pytest.ini
```ini
[pytest]
DJANGO_SETTINGS_MODULE = gerenciador_vendas.settings_local
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

### CI/CD
GitHub Actions roda os testes automaticamente em cada push via `.github/workflows/ci.yml`.

### Banco de testes
SQLite in-memory (`:memory:`) via `settings_local.py`. Cada test case cria e destrói o banco automaticamente.
