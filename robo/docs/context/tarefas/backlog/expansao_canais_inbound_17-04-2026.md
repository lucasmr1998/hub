---
name: "Expansão de canais de captura inbound (Instagram, Messenger, Telegram, telefonia)"
description: "Hoje o Hubtrix so capta nativamente WhatsApp e widget; outros canais comuns (Instagram DM, FB Messenger, Telegram, telefonia) exigem N8N ou nao funcionam"
prioridade: "🟡 Média"
responsavel: "Tech"
---

# Expansão de canais inbound — 17/04/2026

**Data:** 17/04/2026
**Responsável:** Tech
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Descrição

Estágio 2 de A2 (Primeiro contato) revelou gaps importantes em canais de captura. Hoje o Hubtrix recebe nativamente:

- ✅ WhatsApp (via Uazapi / Evolution)
- ✅ Widget no site
- ✅ Formulário de cadastro público

Mas NÃO tem captação direta de:

- ❌ **Instagram DM** — hoje depende de N8N amarrando Meta API
- ❌ **Facebook Messenger** — idem
- ❌ **Telegram** — nada
- ❌ **Telefonia** — vendedor registra lead manualmente, sem integração com PBX

Para muitos ISPs, Instagram é fonte relevante de leads (jovens, regiões urbanas). Não ter nativo significa perder atribuição e forçar cliente a montar esquema no N8N.

Surgiu de A2 estágio 2 em `PRODUTO/VISAO.md`.

---

## Tarefas

### Instagram DM + Facebook Messenger (Meta)
- [ ] Avaliar Meta Graph API (permissões necessárias, custo, onboarding)
- [ ] Criar provider `MetaInbound` em `apps/integracoes/providers/`
- [ ] Webhook inbound normalizando payloads do Meta pra formato interno
- [ ] UI de configuração no `/configuracoes/integracoes/`

### Telegram
- [ ] Criar bot Telegram template (Hubtrix oficial ou por tenant)
- [ ] Provider `TelegramInbound`
- [ ] Webhook + vinculação com Inbox

### Telefonia (longo prazo)
- [ ] Pesquisar integração com PBX virtual (3CX, Twilio Voice, MkVoip)
- [ ] Modelo conceitual: "ligação" como Conversa com campo especial
- [ ] Registro manual enquanto não tem integração automática — melhorar UX do lead por telefone
- [ ] Futuramente: transcrição automática da chamada (IA) como conteúdo da Conversa

---

## Priorização sugerida

1. **Instagram DM** — mais pedido por ISPs (atribuição de campanha)
2. **Telegram** — nicho mas quick win (API simples)
3. **Messenger** — junto com Instagram (mesma Graph API)
4. **Telefonia** — complexo, deixar pra depois

---

## Impacto esperado

- Cobertura completa de canais que ISPs usam
- Atribuição de campanha em canais onde hoje é perdida
- Reduz dependência de N8N do cliente (simplifica onboarding)
