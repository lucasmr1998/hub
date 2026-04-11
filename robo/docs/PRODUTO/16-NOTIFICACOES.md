# Modulo de Notificacoes — AuroraISP

**Ultima atualizacao:** 11/04/2026
**Status:** ✅ Implementado
**Localizacao:** `apps/notificacoes/`

---

## Visao Geral

O sistema de notificacoes permite alertar usuarios sobre eventos do sistema em tempo real. Funciona com notificacoes in-app (sino no topbar), com suporte a canais externos (WhatsApp, Email, Webhook).

```
Evento acontece (lead novo, conversa, ticket)
  → Signal dispara
    → Service cria Notificacao no banco
      → Frontend faz polling a cada 15s
        → Badge atualiza + toast aparece + som toca
```

---

## Arquitetura

### Camadas

| Camada | Arquivo | Responsabilidade |
|--------|---------|------------------|
| **Models** | `models.py` | 5 models (tipo, canal, notificacao, template, preferencia) |
| **Services** | `services/notificacao_service.py` | Logica centralizada: criar, marcar lida, contar |
| **Signals** | `signals.py` | Disparo automatico por eventos Django |
| **Views/APIs** | `views.py` | 30+ endpoints REST |
| **Admin** | `admin.py` | Interface Django admin completa |
| **Frontend** | `sistema/base.html` | Sino, badge, sidebar, toasts, som |

### Fluxo de dados

```
[Signal] �� services.criar_notificacao() → Notificacao (banco)
                                              ↓
[Frontend] ← /api/notificacoes/nao-lidas/ ← polling 15s
                                              ↓
                                    badge + toast + som
```

---

## Banco de Dados (5 Models)

### TipoNotificacao

Define os tipos de evento que geram notificacao.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| codigo | CharField(50) | Identificador unico por tenant |
| nome | CharField(100) | Nome legivel |
| descricao | TextField | Descricao do tipo |
| ativo | BooleanField | Se esta ativo |
| template_padrao | TextField | Template de mensagem padrao |
| prioridade_padrao | CharField | baixa, normal, alta, urgente |
| icone | CharField(50) | Classe FontAwesome (ex: fas fa-bell) |
| whatsapp_config | JSONField | Config WhatsApp especifica |
| tenant | FK Tenant | Multi-tenancy |

**unique_together:** (tenant, codigo)

**Tipos disponiveis:**

| Codigo | Categoria |
|--------|-----------|
| lead_novo, lead_convertido, venda_aprovada, venda_rejeitada, prospecto_aguardando | Comercial |
| conversa_recebida, conversa_transferida, mensagem_recebida | Inbox |
| tarefa_vencendo, tarefa_atribuida, oportunidade_movida | CRM |
| ticket_criado, ticket_respondido, sla_estourando | Suporte |
| mencao_nota, sistema_geral | Sistema |

### CanalNotificacao

Define os canais de entrega.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| codigo | CharField(20) | sistema, email, whatsapp, webhook |
| nome | CharField(50) | Nome legivel |
| ativo | BooleanField | Se esta ativo |
| configuracao | JSONField | Config especifica do canal |
| icone | CharField(50) | Icone FontAwesome |
| tenant | FK Tenant | Multi-tenancy |

**unique_together:** (tenant, codigo)

### Notificacao

Registro de cada notificacao enviada.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| tipo | FK TipoNotificacao | Tipo do evento |
| canal | FK CanalNotificacao | Canal de entrega |
| destinatario | FK User | Usuario destinatario |
| destinatario_email | EmailField | Email (canais externos) |
| destinatario_telefone | CharField(20) | Telefone (WhatsApp) |
| titulo | CharField(200) | Titulo |
| mensagem | TextField | Corpo da mensagem |
| dados_contexto | JSONField | Dados extras para personalizacao |
| url_acao | CharField(500) | Link ao clicar na notificacao |
| status | CharField(20) | pendente, enviando, enviada, falhou, cancelada |
| prioridade | CharField(20) | baixa, normal, alta, urgente |
| lida | BooleanField | Se foi lida pelo usuario |
| data_lida | DateTimeField | Quando foi lida |
| tentativas | PositiveIntegerField | Tentativas de envio |
| max_tentativas | PositiveIntegerField | Maximo de tentativas |
| data_criacao | DateTimeField | Criacao |
| data_envio | DateTimeField | Envio efetivo |
| data_agendamento | DateTimeField | Agendamento futuro |
| resposta_externa | JSONField | Resposta da integracao (N8N, webhook) |
| erro_detalhes | TextField | Detalhes de erro |
| tenant | FK Tenant | Multi-tenancy |

**Indices:** status, data_criacao, tipo, canal, (destinatario + lida)

### TemplateNotificacao

Templates de mensagem por tipo+canal.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| tipo_notificacao | FK TipoNotificacao | Tipo |
| canal | FK CanalNotificacao | Canal |
| nome | CharField(100) | Nome do template |
| assunto | CharField(200) | Assunto (email) |
| corpo_html | TextField | HTML |
| corpo_texto | TextField | Texto simples |
| variaveis | JSONField | Lista de variaveis disponiveis |
| ativo | BooleanField | Se esta ativo |
| tenant | FK Tenant | Multi-tenancy |

**unique_together:** (tenant, tipo_notificacao, canal)

### PreferenciaNotificacao

Preferencias do usuario por tipo+canal.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| usuario | FK User | Usuario |
| tipo_notificacao | FK TipoNotificacao | Tipo |
| canal_preferido | FK CanalNotificacao | Canal preferido |
| ativo | BooleanField | Se quer receber |
| horario_inicio | TimeField | Inicio do horario permitido |
| horario_fim | TimeField | Fim do horario permitido |
| dias_semana | JSONField | Dias [0=seg, 6=dom] |
| tenant | FK Tenant | Multi-tenancy |

**unique_together:** (tenant, usuario, tipo_notificacao, canal_preferido)

---

## Services (API interna)

Arquivo: `services/notificacao_service.py`

| Funcao | Descricao |
|--------|-----------|
| `criar_notificacao(tenant, codigo_tipo, titulo, mensagem, ...)` | Cria notificacao in-app |
| `notificar_usuarios(tenant, codigo_tipo, titulo, mensagem, usuarios, ...)` | Cria para multiplos usuarios |
| `marcar_lida(notificacao_id, user)` | Marca uma como lida |
| `marcar_todas_lidas(tenant, user)` | Marca todas como lidas |
| `contar_nao_lidas(tenant, user)` | Contagem de nao lidas |

**Uso em qualquer parte do sistema:**

```python
from apps.notificacoes.services import criar_notificacao

criar_notificacao(
    tenant=request.tenant,
    codigo_tipo='lead_novo',
    titulo='Novo lead: João',
    mensagem='Lead João (11999999999) foi capturado.',
    destinatario=user,
    url_acao='/comercial/leads/123/',
)
```

---

## Signals (disparo automatico)

Arquivo: `signals.py` — registrados via `apps.py` (ready)

| Signal | Evento | Tipo |
|--------|--------|------|
| `notificar_lead_novo` | LeadProspecto criado | lead_novo |
| `notificar_conversa_recebida` | Conversa criada (com agente) | conversa_recebida |
| `notificar_conversa_transferida` | Conversa muda de agente | conversa_transferida |
| `notificar_ticket_criado` | Ticket criado (com atribuido) | ticket_criado |

Para pular notificacao em operacoes em massa: `instance._skip_notificacao = True`

---

## APIs REST

### Leitura

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/notificacoes/listar/` | Lista paginada do usuario |
| GET | `/api/notificacoes/<id>/` | Detalhes de uma notificacao |
| GET | `/api/notificacoes/nao-lidas/` | Contagem de nao lidas |
| GET | `/api/notificacoes/estatisticas/` | Stats do sistema |

### Acoes

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/notificacoes/enviar/` | Criar notificacao via API |
| POST | `/api/notificacoes/teste/` | Notificacao de teste |
| POST | `/api/notificacoes/<id>/lida/` | Marcar como lida |
| POST | `/api/notificacoes/marcar-todas-lidas/` | Marcar todas como lidas |

### CRUD (admin)

| Recurso | Endpoints |
|---------|-----------|
| Tipos | `/api/tipos-notificacao/` (GET, POST, PUT, DELETE) |
| Canais | `/api/canais-notificacao/` (GET, POST, PUT, DELETE) |
| Templates | `/api/templates-notificacoes/` (GET, POST, PUT, PATCH, DELETE) |
| Preferencias | `/api/notificacoes/preferencias/` + criar/editar/pausar/ativar/remover |
| WhatsApp | `/api/notificacoes/whatsapp/config/`, `/salvar/`, `/test/` |
| Toggle canal | `/api/notificacoes/canais/<id>/toggle/` |

---

## Frontend

### Sino (topbar)

- Botao com icone `fa-bell` + badge contador
- Badge mostra quantidade de nao lidas (dados do backend)
- Clique abre sidebar com lista de notificacoes

### Sidebar

- Lista de notificacoes com icone, titulo, mensagem, tempo relativo
- Indicador visual (bolinha azul) para nao lidas
- Clique na notificacao: marca como lida e navega para `url_acao`
- Botao "marcar todas como lidas" no header

### Polling

- A cada 15 segundos consulta `/api/notificacoes/nao-lidas/`
- Se contagem aumentou: toca som + mostra toasts das novas

### Som

- Beep curto gerado via Web Audio API (sem arquivo externo)
- Toca quando novas notificacoes nao lidas aparecem

### Toasts

- NotificationSystem: toasts no canto da tela
- Tipos: success, warning, error, info
- Auto-dismiss apos 8 segundos
- Maximo 5 na tela simultaneamente

---

## Testes

Arquivo: `tests/test_models_notificacoes.py` �� 9 testes

| Classe | Testes |
|--------|--------|
| TestTipoNotificacao | criar, prioridade padrao |
| TestCanalNotificacao | criar, icone default |
| TestNotificacao | criar, status default, prioridade default, tentativas |
| TestTemplateNotificacao | criar |

---

## Migrations

| # | Descricao |
|---|-----------|
| 0001 | Criacao inicial (5 models) |
| 0002 | unique_together com tenant (tipo, canal) |
| 0003 | Adiciona lida, data_lida, url_acao, icone, resposta_externa. Remove campos n8n. Fix unique_together preferencia e template. Index destinatario+lida |
