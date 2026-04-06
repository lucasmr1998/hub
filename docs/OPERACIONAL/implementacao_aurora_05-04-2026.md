# Implementação Aurora — Primeiro Cliente

**Data início:** 05/04/2026
**Status:** 🔧 Em andamento
**Cliente:** AuroraISP (nós mesmos)
**WhatsApp:** Uazapi
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
Uazapi (API WhatsApp)
    │
    ├── Webhook → Aurora /inbox/api/n8n/mensagem-recebida/
    │              (ou endpoint dedicado Uazapi)
    │
    └── API ← Aurora envia mensagens
              POST /send/text, /send/image, etc.
```

**Sem ERP:** Leads e oportunidades ficam apenas no Aurora. Sem sync com sistema externo.
**Sem N8N (por enquanto):** Integração direta Aurora ↔ Uazapi via API REST.

---

## Fase 1 — Tenant Aurora

### 1.1 Criar tenant

```bash
python manage.py criar_tenant \
  --nome "AuroraISP" \
  --slug "aurora" \
  --plano full_pro \
  --admin-user lucas \
  --admin-email lucas@auroraísp.com.br \
  --admin-senha XXXXX \
  --settings=gerenciador_vendas.settings_local
```

### 1.2 Seed inicial

```bash
python manage.py seed_planos --settings=gerenciador_vendas.settings_local
python manage.py seed_funcionalidades --settings=gerenciador_vendas.settings_local
python manage.py seed_perfis --tenant aurora --settings=gerenciador_vendas.settings_local
```

### 1.3 Configurações

- [ ] ConfiguracaoEmpresa (logo Aurora, cores da marca)
- [ ] ConfiguracaoCRM (pipeline padrão, estágios)
- [ ] Planos de internet (não se aplica, Aurora vende software)
- [ ] Pipeline personalizado para venda de SaaS

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

## Fase 2 — Integração Uazapi

### 2.1 Sobre o Uazapi

Uazapi é uma API para WhatsApp (não oficial, baseada em Baileys/WPPConnect). Permite enviar e receber mensagens via REST API + Webhooks.

**Docs:** https://docs.uazapi.com/

### 2.2 Dados da instância

| Item | Valor | Status |
|------|-------|--------|
| URL base da API | `https://______.uazapi.com` ou self-hosted | Preencher |
| Token da instância | `XXXXX` | Preencher |
| Número WhatsApp | `55XX9XXXXXXXX` | Preencher |
| Webhook URL configurado | `https://aurora.../inbox/api/uazapi/webhook/` | Configurar |

### 2.3 Endpoints Uazapi que vamos usar

#### Enviar mensagens (Aurora → Uazapi)

| Ação | Método | Endpoint | Body |
|------|--------|----------|------|
| Texto | POST | `/send/text` | `{phone, message}` |
| Imagem | POST | `/send/image` | `{phone, image, caption}` |
| Documento | POST | `/send/document` | `{phone, document, fileName}` |
| Áudio | POST | `/send/audio` | `{phone, audio}` |

**Headers:** `Content-Type: application/json`, `token: TOKEN_INSTANCIA`

#### Receber mensagens (Uazapi → Aurora via Webhook)

O Uazapi envia POST para a URL configurada com payload:

```json
{
  "event": "message",
  "data": {
    "key": {
      "remoteJid": "5589999999999@s.whatsapp.net",
      "fromMe": false,
      "id": "XXXXX"
    },
    "message": {
      "conversation": "Olá, quero saber mais sobre o Aurora"
    },
    "messageTimestamp": 1234567890,
    "pushName": "Nome do Contato"
  }
}
```

#### Outros endpoints úteis

| Ação | Método | Endpoint |
|------|--------|----------|
| Status da instância | GET | `/instance/status` |
| Info do contato | GET | `/contact/info/{phone}` |
| Marcar como lido | POST | `/chat/markAsRead` |
| Verificar número | POST | `/misc/checkNumber` |

### 2.4 Implementação no Aurora

#### Model de integração

Usar o `IntegracaoAPI` existente com `tipo='uazapi'`:

```python
IntegracaoAPI(
    tenant=tenant,
    nome='Uazapi Aurora',
    tipo='uazapi',
    base_url='https://xxxxx.uazapi.com',
    access_token='TOKEN_INSTANCIA',
    ativa=True,
    configuracoes_extras={
        'numero_whatsapp': '55XX9XXXXXXXX',
        'webhook_secret': 'XXXXX',  # validação do webhook
    }
)
```

#### Service de integração

Criar `apps/integracoes/services/uazapi.py`:

```python
class UazapiService:
    def enviar_texto(self, telefone, mensagem) → dict
    def enviar_imagem(self, telefone, url_imagem, legenda) → dict
    def enviar_documento(self, telefone, url_doc, nome_arquivo) → dict
    def verificar_numero(self, telefone) → bool
    def status_instancia(self) → dict
```

#### Webhook receiver

Criar endpoint `POST /inbox/api/uazapi/webhook/` que:
1. Valida token do webhook
2. Parseia payload do Uazapi
3. Cria/atualiza Conversa no Inbox
4. Cria Mensagem
5. Dispara signal `mensagem_recebida` (para automações)

#### Canal no Inbox

Criar CanalInbox `tipo='whatsapp_uazapi'` com webhook de envio apontando para o UazapiService.

---

## Fase 3 — Configuração do Inbox

- [ ] Criar equipe "Vendas Aurora"
- [ ] Criar fila "WhatsApp" vinculada à equipe
- [ ] Criar canal "WhatsApp Aurora" tipo whatsapp com webhook de envio
- [ ] Configurar horário de atendimento
- [ ] Criar respostas rápidas (saudação, preço, agendar demo)
- [ ] Configurar mensagem fora do horário

---

## Fase 4 — CRM e Pipeline

- [ ] Pipeline "Vendas SaaS" com 8 estágios
- [ ] Tags: Provedor Pequeno, Provedor Médio, Provedor Grande, HubSoft, MK, IXC
- [ ] Criar equipe de vendas
- [ ] Configurar auto-criação de oportunidade (score >= 7)

---

## Fase 5 — Automações básicas

- [ ] Lead criado → Notificação no sistema
- [ ] Lead sem contato 2 dias → Alerta
- [ ] Oportunidade movida para "Demo Agendada" → Notificação
- [ ] Oportunidade em "Proposta Enviada" há 5 dias → Follow-up

---

## Fase 6 — Marketing

- [ ] Campanha "Orgânico LinkedIn"
- [ ] Campanha "Orgânico WhatsApp"
- [ ] Campanha "Indicação"
- [ ] Segmento "Leads com HubSoft" (para direcionar pitch)

---

## Checklist de implementação

```
INFRA
  [ ] Tenant Aurora criado
  [ ] Seeds rodados (planos, funcionalidades, perfis)
  [ ] Usuários criados com perfis de permissão

UAZAPI
  [ ] UazapiService criado em apps/integracoes/services/uazapi.py
  [ ] IntegracaoAPI criada com tipo='uazapi'
  [ ] Webhook receiver criado
  [ ] Canal WhatsApp criado no Inbox
  [ ] Testar envio de mensagem
  [ ] Testar recebimento de mensagem via webhook

INBOX
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

## Decisões pendentes

| Decisão | Opções | Status |
|---------|--------|--------|
| Usar N8N como middleware? | Direto Aurora↔Uazapi vs Aurora→N8N→Uazapi | Decidir |
| Bot de atendimento automático? | Sim (fluxo de qualificação) vs Não (só inbox manual) | Decidir |
| Domínio do painel | app.auroraisp.com.br ou outro | Decidir |
| Deploy | VPS, Docker, ou cloud | Decidir |
