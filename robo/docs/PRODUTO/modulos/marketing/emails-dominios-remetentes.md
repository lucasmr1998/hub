---
modulo: Marketing — Emails (Domínios e Remetentes)
status: 🟢 Implementado (em modo stub até configurar RESEND_API_KEY)
data: 29/04/2026
---

# Marketing — Domínios e Remetentes de email (envio personalizado)

Permite que cada tenant envie emails do **próprio domínio** (ex: `atendimento@meuprovedor.com.br`) em vez de saírem do domínio Hubtrix. Estratégia: **Domain authentication via Resend** (provedor master), **sem SMTP fallback**.

## Arquitetura

```
[Tenant configura DNS]                    [Hubtrix master no Resend]
        ↓                                          ↓
  meuprovedor.com.br ──────[SPF/DKIM/DMARC]──── api.resend.com
        ↑                                          ↓
  [emails saem como atendimento@meuprovedor.com.br]
        ↓
  [destinatario]
        ↓
  [eventos de webhook] ──→ /api/public/resend/webhook/ ──→ EnvioEmail.status
```

## Models novos

### `DominioRemetente`
Cada tenant pode ter **múltiplos domínios**.
- `dominio` — `meuprovedor.com.br` (unique por tenant)
- `nome_amigavel` — pra organizar quando tem várias marcas
- `resend_domain_id` — ID do dominio no Resend
- `status` — pendente_dns / validando / verificado / falhou / desabilitado
- `registros_dns` (JSON) — 3 registros que tenant precisa colocar no DNS dele
- `validado_em`, `ultima_verificacao`, `falha_motivo`
- **Flags de captura:**
  - `capturar_bounces` (default True)
  - `capturar_complaints` (default True)
  - `auto_remover_lista` (default **False** — desligado por padrão; cliente decide)

### `RemetenteEmail`
Endereços específicos dentro de um domínio verificado.
- `dominio` FK — pertence a um DominioRemetente
- `local_part` — parte antes do @ (ex: `atendimento`, `noreply`)
- `nome_exibicao` — "Atendimento Hubtrix"
- `reply_to` (opcional, ignorado por enquanto se vazio)
- `padrao` (apenas 1 ativo por tenant)
- `ativo`

### Acréscimos em `EnvioEmail` existente
- `remetente` FK → `RemetenteEmail`
- `resend_message_id` — pra correlacionar webhooks
- `entregue_em`, `bounce_type`, `complaint_type`
- Status novos: `pendente`, `entregue`, `complained`

## URLs novas

| URL | Descrição |
|-----|-----------|
| `/marketing/emails/dominios/` | Lista de domínios |
| `/marketing/emails/dominios/criar/` | Adicionar domínio |
| `/marketing/emails/dominios/<pk>/` | Detalhe — DNS records, remetentes, configurações |
| `/marketing/emails/dominios/<pk>/verificar/` | POST — checa status no Resend |
| `/marketing/emails/dominios/<pk>/excluir/` | POST — apaga (também no Resend) |
| `/marketing/emails/dominios/<pk>/flags/` | POST — atualiza flags |
| `/marketing/emails/dominios/<dominio_pk>/remetentes/criar/` | Adicionar remetente |
| `/marketing/emails/remetentes/<pk>/excluir/` | POST |
| `/marketing/emails/remetentes/<pk>/padrao/` | POST — marca como padrão |
| **Público:** `/api/public/resend/webhook/` | POST — recebe eventos do Resend |

## Service

`apps/marketing/emails/services/resend_service.py`:
- `create_domain(dominio)` — chama API Resend, recebe DNS records
- `get_domain(resend_id)` / `verify_domain(resend_id)` / `delete_domain(resend_id)`
- `send_email(...)` — wrapper de envio
- `disparar_para_lead(template, lead, remetente=None, ...)` — orquestrador completo (renderiza, cria EnvioEmail, dispara, atualiza)
- `verify_webhook_signature(payload_bytes, signature)` — valida HMAC

## Modo stub (sem chave Resend)

Se `RESEND_API_KEY` vazio (default em dev):
- `create_domain` retorna DNS records fake
- `verify_domain` sempre retorna `verified`
- `send_email` retorna message_id fake (loga, não envia)

Permite testar UI/fluxo sem custo.

## Fluxo de configuração (UX)

1. Tenant abre `/marketing/emails/dominios/`, clica **Adicionar domínio**
2. Digita `meuprovedor.com.br` → sistema chama `Resend.create_domain` → recebe 3 DNS records
3. Tela de detalhe mostra os 3 registros (SPF / DKIM / DMARC) com botão **Copiar** em cada
4. Tenant adiciona no DNS dele (Cloudflare / Registro.br / GoDaddy / etc.)
5. Volta no Hubtrix, clica **Verificar agora** → sistema chama `Resend.verify_domain`
6. Status vira `verificado` ou `validando` (DNS ainda propagando — tentar de novo em 5min)
7. Com domínio verificado, adiciona remetentes: `atendimento@`, `marketing@`, `noreply@` etc.
8. Marca um como padrão (apenas 1 ativo por tenant)

## Webhook (eventos do provedor)

Endpoint público em `/api/public/resend/webhook/`. Eventos suportados:
- `email.sent`, `email.delivered`, `email.opened`, `email.clicked`
- `email.bounced`, `email.complained`
- `email.delivery_delayed` (ignorado, só log)

Comportamento:
- Atualiza `EnvioEmail.status` baseado no evento
- Salva `bounce_type` ou `complaint_type` quando aplicável
- Se `DominioRemetente.auto_remover_lista=True` AND evento bounce/complaint → marca `LeadProspecto.aceita_emails = False`
- Validação HMAC via header `svix-signature` (Svix é o provedor que Resend usa pra webhooks)

## Configuração em produção

1. Criar conta no Resend → pegar API key
2. Variáveis de ambiente:
   ```
   RESEND_API_KEY=re_xxx...
   RESEND_WEBHOOK_SECRET=whsec_xxx...
   ```
3. Configurar webhook no painel Resend apontando pra `https://seudominio.com.br/api/public/resend/webhook/`
4. Selecionar eventos: `email.sent`, `email.delivered`, `email.opened`, `email.clicked`, `email.bounced`, `email.complained`

## Próximas evoluções (fora do escopo desta entrega)

- Reply-to ativo (criar conversa no Inbox quando responder) — pergunta 5 deixada de fora
- Aquecimento automático de domínio novo (cliente gerencia hoje — pergunta 6)
- UI de stats agregadas por domínio (taxa de entrega, abertura, bounce)
- Multi-template: cada template vincula a um remetente específico (hoje usa o padrão)
- Renderer Django Template completo (hoje usa um regex simples `{{lead.X}}`)

## Migration

`apps/marketing/emails/migrations/0002_envioemail_bounce_type_envioemail_complaint_type_and_more.py`

## Decisões fechadas com user (sessão 29/04/2026)

| # | Decisão |
|---|---------|
| 1 | Provedor: **Resend** |
| 2 | Estratégia: **só B** (DNS auth, sem SMTP fallback) |
| 3 | **Múltiplos domínios** por tenant: SIM |
| 4 | Editor de template: já existe (visual de blocos) |
| 5 | Reply-to: ignora por enquanto (capturar campo mas não rotear) |
| 6 | Aquecimento: cliente gerencia |
| 7 | Bounce/complaint: capturar sempre; flag de auto-remover (off por default) |
