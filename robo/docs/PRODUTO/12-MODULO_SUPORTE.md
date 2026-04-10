# Módulo Suporte & Inbox — AuroraISP

**Ultima atualizacao:** 10/04/2026
**Status:** ✅ Em produção
**Localização:** `apps/inbox/` + `apps/suporte/`

---

## Visão Geral

O módulo de Suporte & Inbox é o sistema de atendimento omnichannel da Aurora. Composto por dois sub-apps que trabalham juntos: o **Inbox** (chat em tempo real, WhatsApp, widget) e o **Suporte** (tickets formais com SLA). O Inbox é o app principal, com 20 models, 20+ views, provider pattern para multi-provedor, distribuição automática, WebSocket e widget embeddable.

```
Cliente (WhatsApp / Widget / E-mail)
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                    PROVIDERS                          │
│  Uazapi │ Evolution │ Meta Cloud │ Twilio │ Webhook  │
└────────────────────┬─────────────────────────────────┘
                     │ parse_webhook()
                     ▼
┌──────────────────────────────────────────────────────┐
│                     INBOX                             │
│  Receber mensagem → Distribuir → Conversa → Agente   │
│  Enviar mensagem ← Provider ← Agente                 │
│  Notas internas, etiquetas, transferências            │
└────────────────────┬─────────────────────────────────┘
                     │ Criar ticket
                     ▼
┌──────────────────────────────────────────────────────┐
│                    SUPORTE                            │
│  Ticket → Comentários → SLA → Resolução → Fechamento │
└──────────────────────────────────────────────────────┘
```

---

## 1. Inbox (`apps/inbox/`)

### Models (20)

#### Conversa (central)
Tabela: `inbox_conversas` | Unique: (tenant, numero)

| Grupo | Campos |
|-------|--------|
| **Identificação** | numero (auto, sequencial por tenant), identificador_externo (thread ID WhatsApp) |
| **Contato** | contato_nome, contato_telefone (indexado), contato_email |
| **Canal** | canal FK CanalInbox |
| **Status** | status (aberta/pendente/resolvida/arquivada), prioridade (baixa/normal/alta/urgente) |
| **Atribuição** | agente FK User, equipe FK EquipeInbox, fila FK FilaInbox |
| **Vinculações** | lead FK LeadProspecto, ticket FK Ticket, oportunidade FK OportunidadeVenda |
| **Etiquetas** | etiquetas M2M EtiquetaConversa |
| **Métricas** | ultima_mensagem_em, ultima_mensagem_preview, mensagens_nao_lidas, tempo_primeira_resposta_seg |
| **Timestamps** | data_abertura (auto), data_resolucao, data_arquivamento |
| **Extra** | metadata (JSON) |

**6 índices:** status+agente, canal+status, ultima_mensagem_em, contato_telefone, equipe+status, fila+status

#### Mensagem
Tabela: `inbox_mensagens`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `conversa` | FK Conversa | Conversa pai |
| `remetente_tipo` | CharField | contato, agente, sistema, bot |
| `remetente_user` | FK User | Se agente |
| `remetente_nome` | CharField | Nome exibido |
| `tipo_conteudo` | CharField | texto, imagem, arquivo, audio, video, localizacao, sistema |
| `conteudo` | TextField | Conteúdo da mensagem |
| `arquivo_url` | URLField | URL do arquivo (se mídia) |
| `arquivo_nome` | CharField | Nome do arquivo |
| `lida` | Boolean | Se foi lida |
| `data_envio` | DateTime | Timestamp de envio |
| `data_entrega` / `data_leitura` | DateTime | Timestamps de entrega/leitura |
| `identificador_externo` | CharField | Message ID do provider |
| `erro_envio` | TextField | Erro ao enviar (se houver) |

#### CanalInbox
Tabela: `inbox_canais` | Unique: (tenant, tipo, identificador_canal)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tipo` | CharField | whatsapp, widget, email, interno |
| `nome` | CharField | Nome do canal |
| `integracao` | FK IntegracaoAPI | Integração vinculada |
| `provedor` | CharField | Slug do provider (uazapi, evolution, etc) |
| `identificador_canal` | CharField | Número de telefone, ID da instância |
| `configuracao` | JSONField | webhook_envio_url, tokens, etc |

#### EquipeInbox + MembroEquipeInbox
Equipes de atendimento com membros (agente/supervisor/gerente).

#### PerfilAgenteInbox
Status do agente (online/ausente/offline), capacidade máxima de conversas, check de disponibilidade.

#### FilaInbox + RegraRoteamento
Filas de distribuição com regras por canal, etiqueta ou horário. Modos: round_robin, menor_carga, manual.

#### HorarioAtendimento
Horário por dia da semana (hora_inicio, hora_fim, ativo).

#### ConfiguracaoInbox
Singleton: mensagem_fora_horario, distribuicao_padrao, atribuir_ao_responder.

#### RespostaRapida
Templates de resposta com atalho (ex: `/ola`). Unique: (tenant, atalho).

#### EtiquetaConversa
Tags com cor hex. Unique: (tenant, nome).

#### NotaInternaConversa
Notas privadas do agente na conversa.

#### HistoricoTransferencia
Log de transferências entre agentes/equipes/filas.

#### CategoriaFAQ + ArtigoFAQ
FAQ para o widget de chat. Categorias com ícone e artigos com contagem de visualizações.

#### WidgetConfig
Configuração do widget embeddable: token_publico (UUID), cores, posição, FAQ, campos obrigatórios, domínios permitidos.

---

### Services (`services.py`)

| Função | O que faz |
|--------|-----------|
| `receber_mensagem(telefone, nome, conteudo, tenant, ...)` | Processa mensagem recebida. Normaliza telefone, busca/cria conversa, busca/cria lead, verifica horário, distribui, cria mensagem, notifica via WebSocket |
| `enviar_mensagem(conversa, conteudo, user, ...)` | Agente envia mensagem. Cria Mensagem, calcula tempo de resposta, auto-atribui agente, envia via provider em background thread |
| `atribuir_conversa(conversa, agente, atribuido_por)` | Atribui conversa a agente, cria mensagem de sistema |
| `resolver_conversa(conversa, user)` | Marca como resolvida, seta data_resolucao |
| `reabrir_conversa(conversa, user)` | Reabre conversa resolvida/arquivada |
| `transferir_conversa(conversa, transferido_por, ...)` | Transfere para agente/equipe/fila, cria histórico |
| `criar_ticket_de_conversa(conversa, titulo, user)` | Cria Ticket de suporte a partir da conversa com histórico de mensagens |
| `marcar_mensagens_lidas(conversa)` | Marca mensagens do contato como lidas |
| `atualizar_status_entrega(identificador_externo, status)` | Atualiza status de entrega/leitura da mensagem |
| `receber_mensagem_widget(visitor_id, nome, conteudo, ...)` | Versão widget: usa visitor_id em vez de telefone |
| `buscar_lead_por_telefone(telefone, tenant)` | Busca lead por match exato ou parcial (últimos 11/10 dígitos) |

### Distribuição automática (`distribution.py`)

| Função | O que faz |
|--------|-----------|
| `verificar_horario_atendimento(tenant)` | Verifica se está dentro do horário de atendimento |
| `determinar_fila(conversa, tenant)` | Encontra fila pela regra de roteamento (canal, etiqueta, horário) |
| `selecionar_agente(fila, tenant)` | Seleciona agente disponível (round_robin, menor_carga, manual) |
| `distribuir_conversa(conversa, tenant)` | Orquestra: fila → agente → atribuição |

---

### Provider Pattern (`providers/`)

Abstração para múltiplos provedores de mensageria.

```
providers/
    __init__.py     # Registry + get_provider(canal) factory
    base.py         # BaseProvider ABC
    uazapi.py       # UazapiProvider (WhatsApp via Uazapi)
    webhook.py      # GenericWebhookProvider (N8N fallback)
```

**BaseProvider (ABC):**
- `enviar_texto(telefone, mensagem)` — obrigatório
- `enviar_imagem(telefone, url, legenda)` — obrigatório
- `enviar_documento(telefone, url, nome)` — obrigatório
- `enviar_audio(telefone, url)` — obrigatório
- `enviar_mensagem(conversa, mensagem)` — router por tipo_conteudo
- `parse_webhook(body)` — normaliza payload do provider
- `extrair_msg_id(result)` — extrai message ID da resposta

**UazapiProvider:** wraps UazapiService com 20+ métodos de envio (texto, mídia, menu, carrossel, vCard, localização, PIX). Parse de webhook nos formatos Uazapi real e Baileys/legacy.

**Para adicionar novo provider:** criar 1 arquivo com `@register_provider`, implementar os métodos abstract. Zero mudanças em services/views.

---

### Views (20+)

#### Interface principal

| View | Rota | Descrição |
|------|------|-----------|
| `inbox_view` | `/inbox/` | Interface 3 painéis (conversas, chat, contexto) |
| `dashboard_inbox` | `/inbox/dashboard/` | KPIs, gráficos 30 dias, ranking agentes |
| `configuracoes_inbox` | `/inbox/configuracoes/` | 9 tabs (equipes, filas, respostas, etiquetas, canais, horário, FAQ, widget, geral) |

#### APIs internas (AJAX)

| View | Rota | Método | Descrição |
|------|------|--------|-----------|
| `api_conversas` | `/inbox/api/conversas/` | GET | Lista com filtros (status, agente, busca, escopo) |
| `api_conversa_detalhe` | `/inbox/api/conversas/<pk>/` | GET | Detalhe + lead + oportunidade + conversas anteriores + notas |
| `api_mensagens` | `/inbox/api/conversas/<pk>/mensagens/` | GET | Mensagens paginadas |
| `api_enviar_mensagem` | `/inbox/api/conversas/<pk>/enviar/` | POST | Agente envia mensagem |
| `api_atribuir` | `/inbox/api/conversas/<pk>/atribuir/` | POST | Atribuir agente |
| `api_resolver` | `/inbox/api/conversas/<pk>/resolver/` | POST | Resolver conversa |
| `api_reabrir` | `/inbox/api/conversas/<pk>/reabrir/` | POST | Reabrir conversa |
| `api_transferir` | `/inbox/api/conversas/<pk>/transferir/` | POST | Transferir para agente/equipe/fila |
| `api_criar_ticket` | `/inbox/api/conversas/<pk>/ticket/` | POST | Criar ticket de suporte |
| `api_atualizar_conversa` | `/inbox/api/conversas/<pk>/atualizar/` | POST | Atualizar prioridade, equipe, etiquetas |
| `api_notas` | `/inbox/api/conversas/<pk>/notas/` | POST | Adicionar nota interna |
| `api_respostas_rapidas` | `/inbox/api/respostas-rapidas/` | GET | Listar templates de resposta |
| `api_atualizar_status_agente` | `/inbox/api/agente/status/` | POST | Online/ausente/offline |

#### Webhooks (recebimento de mensagens)

| View | Rota | Descrição |
|------|------|-----------|
| `provider_webhook` | `/inbox/api/webhook/<provedor>/<canal_id>/` | Webhook genérico (escalável, qualquer provider) |
| `uazapi_webhook` | `/inbox/api/uazapi/webhook/` | Webhook legacy Uazapi (backward compat) |

#### APIs N8N (DRF)

| View | Rota | Descrição |
|------|------|-----------|
| `InboxMensagemRecebidaAPIView` | `/api/v1/inbox/mensagem-recebida/` | Receber mensagem via N8N |
| `InboxStatusMensagemAPIView` | `/api/v1/inbox/status-mensagem/` | Status de entrega/leitura |

#### APIs públicas (Widget)

| View | Rota | Descrição |
|------|------|-----------|
| `widget_config` | `/api/public/widget/config/` | Config do widget (cores, FAQ, campos) |
| `widget_faq` | `/api/public/widget/faq/` | Artigos FAQ por categoria |
| `widget_faq_buscar` | `/api/public/widget/faq/buscar/` | Busca FAQ |
| `widget_conversa_iniciar` | `/api/public/widget/conversa/iniciar/` | Iniciar conversa via widget |
| `widget_mensagens` | `/api/public/widget/conversa/<id>/mensagens/` | Mensagens da conversa |
| `widget_enviar` | `/api/public/widget/conversa/<id>/enviar/` | Enviar mensagem via widget |
| `widget_conversas` | `/api/public/widget/conversas/` | Conversas do visitante |

---

### WebSocket (`consumers.py`)

**InboxConsumer** (AsyncJsonWebsocketConsumer):
- Grupos: `inbox_tenant_{id}`, `inbox_user_{id}`, `inbox_conversa_{id}`
- Ações: join/leave conversa, typing indicator, set status, mark read
- Eventos: nova_mensagem, conversa_atualizada, indicador_digitando
- Auto-online ao conectar, auto-offline ao desconectar
- Requer ASGI server (Daphne/Uvicorn). Em dev com runserver, fallback para polling (5s).

### Signals

| Signal | Modelo | Evento disparado |
|--------|--------|-----------------|
| `on_conversa_criada` | Conversa (post_save, created) | `conversa_aberta` |
| `on_mensagem_recebida` | Mensagem (post_save, remetente=contato) | `mensagem_recebida` |
| `on_conversa_resolvida` | Conversa (post_save, status=resolvida) | `conversa_resolvida` |

---

### Widget (`static/inbox/widget/aurora-chat.js`)

Widget de chat embeddable para sites de provedores. Auto-contido (zero dependências, CSS inline).

**Instalação:**
```html
<script src="https://app.aurora.com/static/inbox/widget/aurora-chat.js" data-token="UUID"></script>
```

**Features:**
- 3 tabs: Início (boas-vindas + FAQ), Mensagens (chat), Ajuda (busca FAQ)
- Visitor tracking via UUID no localStorage
- Personalização: cores, posição (bottom-right/left), campos obrigatórios
- CORS: valida domínios permitidos
- Polling a cada 5 segundos para novas mensagens

---

### Templates (3)

| Template | Descrição |
|----------|-----------|
| `inbox.html` | Interface 3 painéis: lista de conversas (esquerda), chat com mensagens (centro), painel de contexto com accordions (direita) |
| `configuracoes_inbox.html` | 9 tabs de configuração: Equipes, Filas, Respostas Rápidas, Etiquetas, Canais, Horário, FAQ, Widget, Geral |
| `dashboard_inbox.html` | Dashboard com KPIs (abertas, pendentes, resolvidas, tempo médio), gráfico 30 dias, ranking agentes |

### Frontend (`static/inbox/`)

**inbox.js** (~700 linhas): App principal do Inbox. Estado, polling, AJAX, WebSocket, filtros, emoji picker, anexos, respostas rápidas, accordions, conversas anteriores.

**inbox.css** (~600 linhas): Three-panel layout, message bubbles, accordions, emoji picker, status badges, responsive.

---

## 2. Suporte / Tickets (`apps/suporte/`)

### Models (4)

#### CategoriaTicket
Tabela: `suporte_categorias` | Unique: (tenant, slug)

Categorias de tickets com nome, slug, ícone FontAwesome, ordem.

#### SLAConfig
Tabela: `suporte_sla_config` | Unique: (tenant, plano_tier)

SLA por plano (starter/start/pro): tempo de primeira resposta e resolução em horas.

#### Ticket
Tabela: `suporte_tickets` | Unique: (tenant, numero)

| Grupo | Campos |
|-------|--------|
| **Identificação** | numero (auto), titulo, descricao |
| **Classificação** | categoria FK, prioridade, status (aberto/em_andamento/aguardando_cliente/resolvido/fechado) |
| **Pessoas** | solicitante FK User, atendente FK User |
| **SLA** | sla_horas (auto do SLAConfig), sla_cumprido (property) |
| **Timestamps** | data_abertura, data_primeira_resposta, data_resolucao, data_fechamento |
| **Provedor** | tenant_cliente FK Tenant |

#### ComentarioTicket
Timeline do ticket: autor, mensagem, interno (flag para visibilidade staff-only).

### Views (4)

| View | Rota | Descrição |
|------|------|-----------|
| `dashboard_suporte` | `/suporte/` | Dashboard KPIs (abertos, em andamento, aguardando, resolvidos, SLA breach) |
| `ticket_lista` | `/suporte/tickets/` | Lista com filtros (status, prioridade, categoria, busca) |
| `ticket_criar` | `/suporte/tickets/criar/` | Formulário de criação |
| `ticket_detalhe` | `/suporte/tickets/<pk>/` | Detalhe com timeline, comentários, ações (alterar status, atribuir, comentar interno/público) |

### Fluxo de vida do ticket

```
ABERTO ──atribuir──▶ EM ANDAMENTO ──resolver──▶ RESOLVIDO ──fechar──▶ FECHADO
   │                      │
   └──aguardar──▶ AGUARDANDO CLIENTE ──responder──┘
```

---

## Integrações entre Inbox e Suporte

```
Conversa (Inbox) ──FK──▶ Ticket (Suporte)
    │
    └── api_criar_ticket: cria ticket com últimas 10 mensagens como descrição
        herda prioridade da conversa
        cria mensagem de sistema "Ticket #N criado"
```

---

## Fluxos completos

### Mensagem WhatsApp → Inbox

```
1. Cliente envia WhatsApp
2. Uazapi recebe → POST webhook Aurora
3. views_webhook.provider_webhook()
4. UazapiProvider.parse_webhook() → normaliza payload
5. services.receber_mensagem()
   a. Normaliza telefone
   b. Busca/cria lead (auto-cria se novo)
   c. Busca conversa aberta ou cria nova
   d. Verifica horário → envia mensagem fora do horário se necessário
   e. Distribui (fila → agente round-robin/menor_carga)
   f. Cria Mensagem
   g. Notifica via WebSocket
6. Agente vê no Inbox em tempo real
```

### Agente responde → WhatsApp

```
1. Agente digita e clica Enviar
2. POST /inbox/api/conversas/<id>/enviar/
3. services.enviar_mensagem()
   a. Cria Mensagem (remetente_tipo=agente)
   b. Calcula tempo_primeira_resposta
   c. Auto-atribui agente se não tinha
   d. Background thread: get_provider(canal).enviar_mensagem()
   e. UazapiService.enviar_texto() → POST Uazapi /send/text
   f. Salva identificador_externo (message ID)
4. Mensagem chega no WhatsApp do cliente
```

### Widget → Inbox

```
1. Visitante abre widget no site do provedor
2. aurora-chat.js gera visitor_id (UUID localStorage)
3. POST /api/public/widget/conversa/iniciar/
4. services.receber_mensagem_widget()
5. Conversa aparece no Inbox do agente
6. Agente responde → mensagem volta ao widget via polling
```

---

## Estatísticas do módulo

| Métrica | Inbox | Suporte | Total |
|---------|-------|---------|-------|
| **Models** | 20 | 4 | 24 |
| **Views** | 25+ | 4 | 29+ |
| **APIs** | 20+ | — | 20+ |
| **Templates** | 3 | 4 | 7 |
| **Services** | 12 funções | — | 12 |
| **Providers** | 2 (uazapi, webhook) | — | 2 |
| **Signals** | 3 | — | 3 |
| **WebSocket** | 1 consumer | — | 1 |
| **Widget** | 1 (JS auto-contido) | — | 1 |
| **Linhas de código** | ~3.500 | ~500 | ~4.000 |
