# Implementação Aurora — Primeiro Cliente

**Data início:** 05/04/2026
**Última atualização:** 06/04/2026
**Status:** 🔧 Em andamento
**Cliente:** AuroraISP (nós mesmos)
**WhatsApp:** Uazapi (consulteplus.uazapi.com)
**ERP:** Nenhum (por enquanto)

---

## Objetivo

Usar a própria plataforma Aurora para gerenciar leads, atendimento e vendas da AuroraISP. O primeiro cliente do produto é o próprio produto.

---

## Stack de integração

```
Cliente (WhatsApp)
    │
    ▼
Uazapi (consulteplus.uazapi.com)
    │
    ├── Webhook → Aurora /inbox/api/webhook/uazapi/{canal_id}/
    │              (Provider Pattern, escalável)
    │
    └── API ← Aurora envia mensagens
              POST /send/text  {number, text}
              POST /send/media {number, type, file}
              POST /send/menu  {number, type, choices}
```

**Sem ERP:** Leads e oportunidades ficam apenas no Aurora.
**Sem N8N:** Integração direta Aurora ↔ Uazapi via Provider Pattern.

---

## Fase 1 — Tenant Aurora ✅ Concluída

### 1.1 Tenant criado

Tenant "Aurora HQ" (slug: `aurora-hq`, ID: 3) com plano full_pro.

### 1.2 Seeds executados

```bash
python manage.py seed_planos          # 9 planos, 115 features
python manage.py seed_funcionalidades # 35 funcionalidades
python manage.py seed_perfis          # 11 perfis padrão por tenant
```

### 1.3 Configurações ✅

- [x] ConfiguracaoEmpresa (logo Aurora, cores da marca)
- [x] Perfis de permissão (11 perfis padrão criados)
- [ ] Pipeline personalizado para venda de SaaS
- [ ] ConfiguracaoCRM (pipeline padrão, estágios)

### 1.4 Pipeline sugerido para venda SaaS

| Ordem | Nome | Tipo | Probabilidade |
|-------|------|------|---------------|
| 1 | Lead Inbound | novo | 10% |
| 2 | Primeiro Contato | qualificacao | 20% |
| 3 | Demo Agendada | qualificacao | 40% |
| 4 | Demo Realizada | negociacao | 60% |
| 5 | Proposta Enviada | negociacao | 75% |
| 6 | Negociação | fechamento | 85% |
| 7 | Fechado Ganho | cliente | 100% |
| 8 | Perdido | perdido | 0% |

---

## Fase 2 — Integração Uazapi ✅ Concluída

### 2.1 Dados da instância

| Item | Valor | Status |
|------|-------|--------|
| URL base da API | `https://consulteplus.uazapi.com` | ✅ Configurado |
| Token da instância | `9ef0cf61-87b3-444a-8769-07b0b74563e5` | ✅ Em configuracoes_extras |
| Número WhatsApp | `553181167572` | ✅ Conectado |
| Nome da instância | `AuroraISP` | ✅ |
| IntegracaoAPI ID | `1` (tipo=uazapi, tenant=Aurora HQ) | ✅ |
| CanalInbox ID | `6` (tipo=whatsapp, provedor=uazapi) | ✅ |
| Webhook URL | `/inbox/api/webhook/uazapi/6/` | ✅ Configurado no Uazapi |

### 2.2 Arquitetura implementada (Provider Pattern)

```
apps/inbox/providers/
    __init__.py          # Registry + get_provider(canal) factory
    base.py              # BaseProvider ABC
    uazapi.py            # UazapiProvider (wraps UazapiService)
    webhook.py           # GenericWebhookProvider (fallback N8N)
```

Para adicionar novo provider (ex: Evolution API): criar `evolution.py` com `@register_provider`. Zero mudanças em services.py ou views.py.

### 2.3 Endpoints implementados no UazapiService

**Headers:** `Content-Type: application/json`, `Accept: application/json`, `token: TOKEN`

#### Enviar mensagens (Aurora → Uazapi)

| Método | Endpoint | Body | Status |
|--------|----------|------|--------|
| `enviar_texto` | POST `/send/text` | `{number, text}` | ✅ Testado |
| `enviar_midia` | POST `/send/media` | `{number, type, file, caption?, docName?}` | ✅ Implementado |
| `enviar_imagem` | via `/send/media` type=image | | ✅ |
| `enviar_documento` | via `/send/media` type=document | | ✅ |
| `enviar_audio` | via `/send/media` type=audio | | ✅ |
| `enviar_video` | via `/send/media` type=video | | ✅ |
| `enviar_sticker` | via `/send/media` type=sticker | | ✅ |
| `enviar_voz` | via `/send/media` type=ptt | | ✅ |
| `enviar_menu` | POST `/send/menu` | `{number, type, text, choices, ...}` | ✅ Implementado |
| `enviar_botoes` | via `/send/menu` type=button | | ✅ |
| `enviar_lista` | via `/send/menu` type=list | | ✅ |
| `enviar_enquete` | via `/send/menu` type=poll | | ✅ |
| `enviar_carrossel` | via `/send/menu` type=carousel | | ✅ |
| `enviar_vcard` | POST `/send/contact` | `{number, contactName, contactPhone}` | ✅ |
| `enviar_localizacao` | POST `/send/location` | `{number, lat, lng, name, address}` | ✅ |
| `enviar_presenca` | POST `/send/presence` | `{number, type}` | ✅ |
| `enviar_botao_pix` | POST `/send/pix` | `{number, key, amount, description}` | ✅ |
| `solicitar_localizacao` | POST `/send/requestLocation` | `{number, text}` | ✅ |
| `solicitar_pagamento` | POST `/send/requestPayment` | `{number, amount, description}` | ✅ |
| `enviar_story_texto` | POST `/send/stories` | `{type:text, text, backgroundColor}` | ✅ |
| `enviar_story_midia` | POST `/send/stories` | `{type, file, caption}` | ✅ |

#### Consultas

| Método | Endpoint | Status |
|--------|----------|--------|
| `status_instancia` | GET `/instance/status` | ✅ Testado |
| `verificar_numero` | POST `/misc/checkNumber` | ✅ |
| `marcar_como_lido` | POST `/chat/markAsRead` | ✅ |

#### Receber mensagens (Uazapi → Aurora via Webhook)

Formato real do payload Uazapi:

```json
{
    "BaseUrl": "https://consulteplus.uazapi.com",
    "EventType": "messages",
    "chat": {
        "phone": "+55 53 8152-1653",
        "wa_chatid": "555381521653@s.whatsapp.net",
        "wa_contactName": "Nome do Contato",
        "name": "Nome"
    },
    "message": {
        "text": "oi",
        "messageType": "Conversation",
        "fromMe": false,
        "messageid": "3EB016C93EBA029158EF14",
        "senderName": "Nome do Contato",
        "chatid": "555381521653@s.whatsapp.net"
    },
    "token": "9ef0cf61-87b3-444a-8769-07b0b74563e5"
}
```

**UazapiProvider.parse_webhook** suporta dois formatos:
1. Formato Uazapi real (`EventType`, `message.text`, `chat.phone`)
2. Formato Baileys/legacy (`event`, `data.key.remoteJid`, `data.message.conversation`)

### 2.4 Testes realizados

| Teste | Resultado |
|-------|-----------|
| Testar conexão (botão na página de integrações) | ✅ Uazapi conectado |
| Receber mensagem via webhook (WhatsApp → Inbox) | ✅ Mensagem aparece no Inbox |
| Enviar mensagem texto (Inbox → WhatsApp) | ✅ Mensagem chega no WhatsApp |
| Resolver conversa (não aparece mais no inbox) | ✅ |

### 2.5 Problemas encontrados e resolvidos

| Problema | Causa | Solução |
|----------|-------|---------|
| 404 no webhook | Uazapi envia sem barra final, APPEND_SLASH=False | Adicionada rota sem barra |
| 400 Bad Request | Payload Uazapi diferente do esperado (não é Baileys) | Implementado `_parse_uazapi_format` |
| 401 Invalid token no envio | Campo `access_token` criptografado com chave diferente | Token salvo em `configuracoes_extras` |
| 400 Missing required fields | Uazapi usa `number`/`text` em vez de `phone`/`message` | Corrigido no UazapiService |
| DisallowedHost | Domínio ngrok não no ALLOWED_HOSTS | `ALLOWED_HOSTS = ['*']` no settings_local |

---

## Fase 3 — Configuração do Inbox 🔧 Em andamento

- [x] Canal WhatsApp Aurora criado (ID 6, provedor=uazapi)
- [x] Accordion colapsável no painel de contexto
- [x] Conversas anteriores do contato
- [x] Emoji picker inline
- [x] Botão anexar arquivo
- [x] Equipe, prioridade e etiquetas funcionando
- [x] Conversas resolvidas não aparecem por padrão
- [x] Menu sidebar reorganizado (Suporte unificado)
- [ ] Criar equipe "Vendas Aurora"
- [ ] Criar fila "WhatsApp" vinculada à equipe
- [ ] Configurar horário de atendimento
- [ ] Criar respostas rápidas (saudação, preço, agendar demo)
- [ ] Configurar mensagem fora do horário

---

## Fase 4 — CRM e Pipeline (pendente)

- [ ] Pipeline "Vendas SaaS" com 8 estágios
- [ ] Tags: Provedor Pequeno, Provedor Médio, Provedor Grande, HubSoft, MK, IXC
- [ ] Criar equipe de vendas
- [ ] Configurar auto-criação de oportunidade (score >= 7)

---

## Fase 5 — Automações básicas (pendente)

- [ ] Lead criado → Notificação no sistema
- [ ] Lead sem contato 2 dias → Alerta
- [ ] Oportunidade movida para "Demo Agendada" → Notificação
- [ ] Oportunidade em "Proposta Enviada" há 5 dias → Follow-up

---

## Fase 6 — Marketing (pendente)

- [ ] Campanha "Orgânico LinkedIn"
- [ ] Campanha "Orgânico WhatsApp"
- [ ] Campanha "Indicação"
- [ ] Segmento "Leads com HubSoft" (para direcionar pitch)

---

## Checklist de implementação

```
INFRA
  [x] Tenant Aurora criado (Aurora HQ, ID 3)
  [x] Seeds rodados (planos, funcionalidades, perfis)
  [ ] Usuários criados com perfis de permissão
  [ ] Deploy em servidor

UAZAPI
  [x] UazapiService criado (20+ endpoints)
  [x] IntegracaoAPI criada (ID 1, tipo=uazapi)
  [x] Provider Pattern implementado (escalável multi-provider)
  [x] Webhook receiver criado e testado
  [x] Canal WhatsApp criado (ID 6, provedor=uazapi)
  [x] Testar envio de mensagem ✅
  [x] Testar recebimento de mensagem via webhook ✅

INBOX
  [x] Mensagens chegam e são respondidas via WhatsApp
  [x] Accordion, emoji, anexos, conversas anteriores
  [x] Equipe/prioridade/etiquetas salvam
  [ ] Equipe e fila configuradas
  [ ] Respostas rápidas criadas
  [ ] Horário de atendimento configurado

CRM
  [ ] Pipeline SaaS criado
  [ ] Tags criadas
  [ ] Equipe de vendas configurada

AUTOMAÇÕES
  [ ] Regras básicas criadas no editor visual

MARKETING
  [ ] Campanhas cadastradas
  [ ] Segmentos configurados
```

---

## Decisões tomadas

| Decisão | Resultado |
|---------|-----------|
| Usar N8N como middleware? | **Não.** Integração direta via Provider Pattern. |
| Formato de autenticação Uazapi | Header `token: TOKEN` |
| Formato de payload envio | `{number, text}` para texto, `{number, type, file}` para mídia |
| Escalabilidade multi-provider | Provider Pattern implementado. Novo provider = 1 arquivo. |

## Decisões pendentes

| Decisão | Opções | Status |
|---------|--------|--------|
| Bot de atendimento automático? | Sim (fluxo de qualificação) vs Não (só inbox manual) | Decidir |
| Domínio do painel | app.auroraisp.com.br ou outro | Decidir |
| Deploy | VPS, Docker, ou cloud | Decidir |
