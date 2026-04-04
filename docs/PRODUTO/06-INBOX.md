# Módulo Inbox (Atendimento/Suporte) — AuroraISP

**Última atualização:** 03/04/2026
**Status:** ✅ Implementado (3 sessões de desenvolvimento)
**Localização:** `apps/inbox/`

---

## Visão Geral

O Inbox é o módulo de conversas em tempo real da AuroraISP, estilo Chatwoot/Intercom. Permite que agentes do provedor conversem com leads e clientes via WhatsApp (webhook) e Chat Widget (embeddable), com interface three-panel unificada, equipes, filas de atendimento, distribuição automática, FAQ, métricas e integração com automações.

**Localização no painel:** Menu `Suporte` → Sidebar `ATENDIMENTO`

**Dois canais:**
- **WhatsApp** — mensagens chegam/saem via webhook (pronto para N8N)
- **Chat Widget** — JS embeddable para sites de provedores, com FAQ e 3 abas

---

## Arquitetura

### Models (17 models)

| Model | Tabela | Descrição |
|-------|--------|-----------|
| **Core** | | |
| `CanalInbox` | `inbox_canais` | Configuração do canal: tipo (whatsapp/widget/email/interno) + webhook URLs |
| `EtiquetaConversa` | `inbox_etiquetas` | Labels/tags com cor para classificar conversas |
| `Conversa` | `inbox_conversas` | Conversa principal: canal, lead, agente, equipe, fila, status, etiquetas |
| `Mensagem` | `inbox_mensagens` | Mensagem individual: remetente, tipo de conteúdo, lida, entrega, erro |
| `RespostaRapida` | `inbox_respostas_rapidas` | Templates de resposta com atalhos (ex: `/ola`) |
| `NotaInternaConversa` | `inbox_notas_internas` | Notas visíveis apenas para agentes |
| **Equipes e Filas** | | |
| `EquipeInbox` | `inbox_equipes` | Equipe de atendimento com líder, cor, membros |
| `MembroEquipeInbox` | `inbox_membros_equipe` | M2M: agente pode estar em múltiplas equipes (agente/supervisor/gerente) |
| `PerfilAgenteInbox` | `inbox_perfis_agente` | Status do agente (online/ausente/offline) + capacidade máxima |
| `FilaInbox` | `inbox_filas` | Fila com modo de distribuição (round-robin/menor carga/manual) |
| `RegraRoteamento` | `inbox_regras_roteamento` | Regra de roteamento: por canal, etiqueta ou horário → direciona para fila |
| `HistoricoTransferencia` | `inbox_historico_transferencia` | Audit trail de transferências entre agentes/equipes/filas |
| **Configuração** | | |
| `HorarioAtendimento` | `inbox_horario_atendimento` | Dias/horas de funcionamento por tenant |
| `ConfiguracaoInbox` | `inbox_configuracao` | Singleton: mensagem fora do horário, distribuição padrão |
| **FAQ** | | |
| `CategoriaFAQ` | `inbox_faq_categorias` | Categoria de artigos: nome, slug, ícone, cor |
| `ArtigoFAQ` | `inbox_faq_artigos` | Artigo: título, conteúdo HTML, visualizações |
| **Widget** | | |
| `WidgetConfig` | `inbox_widget_config` | Singleton: token público UUID, cores, posição, FAQ, campos obrigatórios, domínios |

Todos os models herdam de `TenantMixin` (multi-tenancy automático).

### Campos importantes de `Conversa`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `numero` | PositiveIntegerField | Auto-increment por tenant |
| `canal` | FK → CanalInbox | Canal de origem |
| `lead` | FK → LeadProspecto | Vinculado automaticamente por telefone/email |
| `contato_nome` / `contato_telefone` / `contato_email` | CharField | Denormalizados para exibição |
| `status` | CharField | `aberta`, `pendente`, `resolvida`, `arquivada` |
| `prioridade` | CharField | `baixa`, `normal`, `alta`, `urgente` |
| `agente` | FK → User | Atendente atribuído |
| `equipe` | FK → EquipeInbox | Equipe atribuída |
| `fila` | FK → FilaInbox | Fila de atendimento |
| `etiquetas` | M2M → EtiquetaConversa | Labels visuais |
| `ticket` | FK → Ticket | Link com suporte |
| `oportunidade` | FK → OportunidadeVenda | Link com CRM |
| `identificador_externo` | CharField | WhatsApp thread ID ou visitor_id do widget |
| `ultima_mensagem_em` / `ultima_mensagem_preview` | DateTime/Char | Para lista sem join |
| `mensagens_nao_lidas` | PositiveIntegerField | Badge |
| `tempo_primeira_resposta_seg` | PositiveIntegerField | SLA |

### Índices

**Conversa:** `(status, agente)`, `(canal, status)`, `(ultima_mensagem_em)`, `(contato_telefone)`, `(equipe, status)`, `(fila, status)`
**Mensagem:** `(conversa, data_envio)`, `(identificador_externo)`

---

## Relações com Módulos Existentes

```
                    ┌─────────────┐
                    │ LeadProspecto│
                    │  (leads)    │
                    └──────┬──────┘
                           │ FK lead
┌──────────┐        ┌──────▼──────┐        ┌──────────────┐
│EquipeInbox│───FK──▶│  Conversa   │────FK──▶│    Ticket     │
│FilaInbox  │       │  (inbox)    │        │  (suporte)   │
└──────────┘        └──────┬──────┘        └──────────────┘
                           │ FK oportunidade
                    ┌──────▼──────┐
                    │Oportunidade │
                    │  Venda (crm)│
                    └─────────────┘
```

---

## Services (Lógica de Negócio)

### Arquivo: `apps/inbox/services.py`

### Funções principais

| Função | O que faz |
|--------|-----------|
| `receber_mensagem(telefone, nome, conteudo, tenant, ...)` | Processa mensagem WhatsApp: normaliza telefone, busca/cria conversa, vincula lead, distribui, notifica WS |
| `receber_mensagem_widget(visitor_id, nome, conteudo, tenant, ...)` | Processa mensagem do widget: usa visitor_id em vez de telefone, vincula lead por email/telefone |
| `enviar_mensagem(conversa, conteudo, user, ...)` | Agente envia: cria mensagem, calcula SLA, webhook async, WS notify |
| `atribuir_conversa(conversa, agente, atribuido_por)` | Atribui agente + mensagem de sistema |
| `resolver_conversa(conversa, user)` | Status → resolvida |
| `reabrir_conversa(conversa, user)` | Status → aberta |
| `transferir_conversa(conversa, transferido_por, para_agente/equipe/fila, motivo)` | Transfere + HistoricoTransferencia + redistribui se para equipe/fila |
| `criar_ticket_de_conversa(conversa, titulo, user, categoria)` | Cria Ticket com histórico das últimas 10 mensagens |
| `marcar_mensagens_lidas(conversa)` | Marca todas contato como lidas + zera badge |
| `atualizar_status_entrega(identificador_externo, status, tenant)` | Atualiza delivery/read de mensagem externa |

---

## Engine de Distribuição

### Arquivo: `apps/inbox/distribution.py`

| Função | O que faz |
|--------|-----------|
| `verificar_horario_atendimento(tenant)` | Checa HorarioAtendimento para dia/hora atual. Sem registros = sempre aberto |
| `determinar_fila(conversa, tenant)` | Itera RegraRoteamento por prioridade. Match por canal, etiqueta ou horário |
| `selecionar_agente(fila, tenant)` | Round-robin (circular via ultimo_agente_id) ou menor carga (menos conversas abertas). Verifica status=online e capacidade |
| `distribuir_conversa(conversa, tenant)` | Orquestrador: fila → agente → atribui → mensagem de sistema |

### Integração

Chamado automaticamente em `receber_mensagem()` e `receber_mensagem_widget()` quando nova conversa é criada. Também chamado em `transferir_conversa()` quando destino é equipe/fila.

---

## APIs

### API Webhook (N8N / Externos)

Autenticação: `APITokenAuthentication` (Bearer token). Arquivo: `apps/inbox/views_n8n.py`

| URL | Método | Descrição |
|-----|--------|-----------|
| `/api/v1/n8n/inbox/mensagem-recebida/` | POST | Recebe mensagem de contato (WhatsApp) |
| `/api/v1/n8n/inbox/status-mensagem/` | POST | Callback de delivery/leitura |

### APIs Internas (Painel)

Protegidas por `@login_required`. Arquivo: `apps/inbox/views.py`

| URL | Método | Descrição |
|-----|--------|-----------|
| `/inbox/` | GET | Inbox three-panel |
| `/inbox/dashboard/` | GET | Dashboard de métricas |
| `/inbox/configuracoes/` | GET/POST | Configurações (equipes, filas, FAQ, widget, etc.) |
| `/inbox/api/conversas/` | GET | Lista com filtros (status, agente, canal, busca) |
| `/inbox/api/conversas/<pk>/` | GET | Detalhe com contexto (lead, CRM, notas) |
| `/inbox/api/conversas/<pk>/mensagens/` | GET | Mensagens paginadas |
| `/inbox/api/conversas/<pk>/enviar/` | POST | Agente envia mensagem |
| `/inbox/api/conversas/<pk>/atribuir/` | POST | Atribuir agente |
| `/inbox/api/conversas/<pk>/resolver/` | POST | Resolver conversa |
| `/inbox/api/conversas/<pk>/reabrir/` | POST | Reabrir conversa |
| `/inbox/api/conversas/<pk>/transferir/` | POST | Transferir para agente/equipe/fila |
| `/inbox/api/conversas/<pk>/ticket/` | POST | Criar ticket de suporte |
| `/inbox/api/conversas/<pk>/etiquetas/` | POST | Atualizar etiquetas |
| `/inbox/api/conversas/<pk>/notas/` | POST | Adicionar nota interna |
| `/inbox/api/agente/status/` | POST | Atualizar status do agente (online/ausente/offline) |
| `/inbox/api/respostas-rapidas/` | GET | Listar respostas rápidas |
| `/inbox/api/etiquetas/` | GET | Listar etiquetas |

### API Pública (Widget — sem login)

Autenticação: `token` público UUID no query param. CORS manual. Arquivo: `apps/inbox/views_public.py`

| URL | Método | Descrição |
|-----|--------|-----------|
| `/api/public/widget/config/?token=X` | GET | Config do widget + categorias FAQ |
| `/api/public/widget/faq/?token=X&categoria=slug` | GET | Artigos de uma categoria |
| `/api/public/widget/faq/buscar/?token=X&q=texto` | GET | Busca artigos por título/conteúdo |
| `/api/public/widget/conversa/iniciar/` | POST | Inicia conversa (visitor_id, nome, email, mensagem) |
| `/api/public/widget/conversa/<id>/mensagens/?token=X&visitor_id=Y` | GET | Mensagens da conversa |
| `/api/public/widget/conversa/<id>/enviar/` | POST | Visitante envia mensagem |
| `/api/public/widget/conversas/?token=X&visitor_id=Y` | GET | Lista conversas do visitante |

**Segurança:** `@csrf_exempt`, validação de Origin contra `dominios_permitidos`, não expõe notas internas, sobrenome do agente, dados do lead ou mensagens de sistema de atribuição.

---

## WebSocket (Tempo Real)

### Consumer: `InboxConsumer` em `apps/inbox/consumers.py`

| Group | Formato | Quem entra |
|-------|---------|------------|
| Tenant | `inbox_tenant_{tenant_id}` | Todos os agentes do tenant |
| Usuário | `inbox_user_{user_id}` | Agente específico |
| Conversa | `inbox_conversa_{conversa_id}` | Agentes com chat aberto |

| Action (cliente → servidor) | O que faz |
|------------------------------|-----------|
| `join_conversa` | Entra no group da conversa |
| `leave_conversa` | Sai do group |
| `typing` | Broadcast typing indicator |
| `set_status` | Atualiza status (online/ausente/offline) |
| `mark_read` | Marca mensagens como lidas |

Auto-offline no `disconnect()`. Fallback para polling 5s quando WS não disponível.

---

## Integração com Automações

### Arquivo: `apps/inbox/signals.py`

| Signal | Evento disparado |
|--------|------------------|
| `on_conversa_criada` (Conversa created) | `conversa_aberta` |
| `on_mensagem_recebida` (Mensagem created, remetente=contato) | `mensagem_recebida` |
| `on_conversa_resolvida` (Conversa status=resolvida) | `conversa_resolvida` |

---

## Chat Widget (Embeddable)

### Arquivo: `apps/inbox/static/inbox/widget/aurora-chat.js`

JS vanilla, self-contained (~15KB), zero dependências. Embed:

```html
<script src="https://app.auroraisp.com/static/inbox/widget/aurora-chat.js"
        data-token="<token-do-tenant>"></script>
```

### Interface (3 abas)

```
┌─────────────────────────────────┐
│ ✕                               │
│                                 │
│  Olá 👋                        │  ← Header com gradiente (cor_header)
│  Como podemos ajudar?           │
│                                 │
├─────────────────────────────────┤
│                                 │
│  [Envie uma mensagem      →]   │  ← CTA para abrir chat
│                                 │
│  Qual é a sua dúvida?    🔍    │  ← Busca FAQ
│                                 │
│  Planos e Preços           →   │  ← Categorias FAQ
│  Suporte Técnico           →   │
│  Financeiro                →   │
│                                 │
├─────────────────────────────────┤
│  🏠 Início  💬 Mensagens  ❓ Ajuda │  ← 3 abas
└─────────────────────────────────┘
```

### Funcionalidades

- **Botão flutuante** (bottom-right/left, cor configurável)
- **Aba Início:** saudação + CTA + busca FAQ + categorias com artigos
- **Aba Mensagens:** lista de conversas do visitante, chat com bolhas, formulário de dados (nome/email/telefone) antes do primeiro contato (configurável)
- **Aba Ajuda:** browser de FAQ por categoria + busca
- **Visitor ID:** UUID em localStorage para continuidade entre sessões
- **Polling 5s** para novas mensagens
- **Responsivo:** full-screen em telas < 480px
- **Isolamento CSS:** classes prefixadas `.aw-*`

### Configuração via painel

Em `/inbox/configuracoes/` aba "Widget":
- Título, mensagem de boas vindas
- Cores (primária + header)
- Posição (inferior direito/esquerdo)
- Mostrar FAQ, pedir dados antes do chat
- Campos obrigatórios (nome, email, telefone)
- Domínios permitidos (CORS)
- Código embed para copiar

---

## Dashboard de Métricas

### URL: `/inbox/dashboard/`

| Seção | Dados |
|-------|-------|
| **KPIs** (5 cards) | Abertas, Pendentes, Resolvidas hoje, Tempo médio 1ª resposta, Total conversas |
| **Gráfico** | Linha: volume nos últimos 30 dias (Chart.js) |
| **Por Canal** | Tabela com volume por canal |
| **Por Equipe** | Volume por equipe com badges coloridos |
| **Ranking Agentes** | Top 15 agentes: resolvidas (30d) + tempo médio |

---

## Página de Configurações

### URL: `/inbox/configuracoes/`

9 abas:

| Aba | O que configura |
|-----|-----------------|
| **Equipes** | CRUD equipes + adicionar/remover membros (cargo: agente/supervisor/gerente) |
| **Filas** | CRUD filas (round-robin/menor carga/manual) + regras de roteamento (por canal/etiqueta/horário) |
| **Respostas Rápidas** | CRUD templates com atalhos (ex: `/ola`) |
| **Etiquetas** | CRUD labels com cores |
| **Canais** | Configurar webhook de envio por canal |
| **Horário** | Dias/horas de atendimento (segunda a domingo) |
| **FAQ** | CRUD categorias + artigos (título + conteúdo) |
| **Widget** | Config visual + campos + domínios + código embed |
| **Geral** | Distribuição padrão, auto-atribuir ao responder, mensagem fora do horário |

---

## Navegação (Sidebar)

```
ATENDIMENTO
  💬 Inbox              ← /inbox/ (three-panel, full-bleed)
  📊 Dashboard Inbox    ← /inbox/dashboard/

SUPORTE
  📊 Dashboard          ← /suporte/
  📋 Tickets            ← /suporte/tickets/
  ➕ Novo Ticket        ← /suporte/tickets/criar/

CONFIGURAÇÕES
  ⚙️ Configurações      ← /inbox/configuracoes/
```

---

## Management Command

```bash
# Seed dados de teste (qualquer tenant)
python manage.py seed_inbox --tenant=aurora-hq --settings=gerenciador_vendas.settings_local
```

Cria: 2 canais, 5 etiquetas, 5 respostas rápidas, 7 conversas com 29 mensagens.

---

## Estrutura de Arquivos

```
apps/inbox/
├── __init__.py
├── apps.py                          # AppConfig com ready() → importa signals
├── models.py                        # 17 models
├── services.py                      # Lógica de negócio (receber, enviar, transferir, etc.)
├── distribution.py                  # Engine de distribuição (fila, round-robin, menor carga)
├── serializers.py                   # DRF serializers (input/output)
├── widget_auth.py                   # Decorator @widget_token_required + CORS
├── views.py                         # View principal + APIs internas + config + dashboard
├── views_n8n.py                     # 2 endpoints webhook (mensagem recebida, status)
├── views_public.py                  # 7 endpoints públicos do widget (sem login)
├── urls.py                          # Rotas internas (app_name = 'inbox')
├── urls_public.py                   # Rotas públicas do widget
├── signals.py                       # 3 signals → engine de automações
├── consumers.py                     # WebSocket consumer (InboxConsumer)
├── routing.py                       # WebSocket URL routing
├── admin.py                         # Admin para todos os 17 models
├── migrations/
│   ├── 0001_initial.py              # Core: 6 models
│   ├── 0002_*.py                    # Equipes, filas, distribuição: 8 models + 2 FKs
│   └── 0003_*.py                    # FAQ + WidgetConfig: 3 models
├── management/commands/
│   └── seed_inbox.py                # Seed de dados de teste
├── templates/inbox/
│   ├── inbox.html                   # Three-panel chat
│   ├── configuracoes_inbox.html     # 9 abas de configuração
│   └── dashboard_inbox.html         # Dashboard com Chart.js
└── static/inbox/
    ├── css/inbox.css                # Estilos do painel
    ├── js/inbox.js                  # JS do painel (fetch, polling, WebSocket)
    └── widget/aurora-chat.js        # Widget embeddable (vanilla JS, ~15KB)
```

---

## Limitações Conhecidas

1. **Sem Celery:** envio de webhook é síncrono (background thread)
2. **N8N não configurado:** API webhook funciona, mas nenhum workflow WhatsApp conectado
3. **InMemoryChannelLayer em dev:** WebSocket funciona só em processo único. Produção precisa Redis
4. **Sem upload de arquivos:** campo `arquivo_url` espera URL externa
5. **Widget sem WebSocket:** usa polling 5s. WebSocket para visitantes é enhancement futuro
6. **Sem CSAT:** pesquisa de satisfação pós-conversa não implementada

---

## Deploy em Produção (checklist)

1. **Redis:** configurar `CHANNEL_LAYERS` com `RedisChannelLayer`
2. **Daphne:** adicionar `'daphne'` ao INSTALLED_APPS
3. **Nginx:** proxy `/ws/` → Daphne, resto → Gunicorn
4. **N8N:** workflow WhatsApp → POST `/api/v1/n8n/inbox/mensagem-recebida/`
5. **CanalInbox:** criar canal WhatsApp no admin com `webhook_envio_url`
6. **Token:** `N8N_API_TOKEN` no `.env`
7. **Widget:** configurar domínios permitidos em `/inbox/configuracoes/` aba Widget
8. **Migrate:** `python manage.py migrate inbox`
