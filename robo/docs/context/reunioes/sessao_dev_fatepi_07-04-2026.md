# Sessao Dev: Implementacao FATEPI + Seguranca Multi-Tenant — 07/04/2026

**Data:** 07/04/2026
**Participantes:** Lucas (CEO), Claude (Tech Lead / CTO)
**Duracao:** Sessao longa

---

## Principais entregas

### APIs DRF para Agentes/N8N
- GET /api/v1/n8n/crm/pipelines/ (listar pipelines com estagios)
- GET /api/v1/n8n/crm/estagios/ (listar, filtro por pipeline)
- POST /api/v1/n8n/crm/oportunidades/ (criar, nao duplica)
- PUT /api/v1/n8n/crm/oportunidades/<pk>/ (mover estagio, atribuir)
- GET /api/v1/n8n/crm/oportunidades/buscar/ (por lead_id ou telefone)
- POST /api/v1/n8n/crm/tarefas/ (criar)
- PUT /api/v1/n8n/crm/tarefas/<pk>/ (atualizar/concluir)
- POST /api/v1/n8n/inbox/enviar/ (enviar mensagem como bot)
- Serializers DRF completos, audit logging, testado 7/7 OK

### Seguranca Multi-Tenant (CRITICO)
- Auditoria encontrou 40+ queries sem filtro de tenant
- TenantMixin adicionado a IntegracaoAPI, ClienteHubsoft, ServicoClienteHubsoft, LogIntegracao
- 30+ queries no dashboard corrigidas automaticamente via TenantManager
- Admin Aurora corrigido para usar all_tenants.filter(tenant=tenant)
- Signal inbox usa all_tenants com filtro manual (sem middleware)
- CLAUDE.md atualizado com regra CRITICA de multi-tenancy
- Tela de integracoes filtrada por tenant (FATEPI nao ve mais dados da Aurora)

### Token API por Tenant
- Campo api_token adicionado ao IntegracaoAPI
- APITokenAuthentication busca token no banco, identifica tenant automaticamente
- Decorator api_token_required tambem busca por tenant
- Fallback para token global (env var) mantido
- Tokens gerados para FATEPI e Aurora
- Fix: _thread_local -> _thread_locals (causava falha no token por tenant)
- Fix: APIServiceUser agora tem atributo username

### Login por Email
- EmailBackend criado (busca por email, fallback username)
- View e template de login atualizados (campo email)
- Criacao de usuario sem campo username (gerado automaticamente do email)
- Template de usuarios mostra email em vez de @username
- Dois tenants podem ter usuarios "admin" sem conflito

### Webhook Uazapi por Tenant
- Nova rota: /inbox/api/webhook/<api_token>/
- Cada tenant configura webhook proprio no Uazapi
- Parser adaptado para formato real do Uazapi (EventType, chat, message)
- Token Uazapi via configuracoes_extras (EncryptedCharField nao desencripta)
- Payload original do Uazapi repassado completo ao N8N

### Configuracao de Canais no Painel
- Select de integracao por canal (vincular Uazapi ao canal WhatsApp)
- Criar novo canal com tipo e integracao
- Badge mostrando provedor vinculado

### Inbox Visual
- Mensagens bot renderizam no lado direito (como agente)
- Fundo verde claro diferencia bot de agente humano (azul)

### FATEPI — Implementacao
- Tenant criado (ID=7)
- Pipeline "Matriculas FATEPI" com 6 estagios
- Integracao N8N configurada com webhook
- Integracao Uazapi configurada
- Canal WhatsApp vinculado ao provider Uazapi
- Fluxo E2E funcionando: WhatsApp -> Inbox -> N8N -> Inbox -> WhatsApp
- Agente IA "Pedro" respondendo via N8N
- Mensagens registradas no Inbox com historico completo
- Usuario admin@fatepi.com.br criado

---

## Fluxo E2E da FATEPI (funcionando)

```
WhatsApp (lead manda mensagem)
    |
Uazapi webhook -> /inbox/api/webhook/<token_fatepi>/
    |
Nosso sistema: registra no Inbox + cria lead + cria conversa
    |
Signal: encaminha payload completo para N8N
    |
N8N: agente IA "Pedro" processa com OpenAI
    |
N8N: POST /api/v1/n8n/inbox/enviar/ (com delay entre mensagens)
    |
Nosso sistema: registra resposta no Inbox
    |
Provider Uazapi: envia resposta no WhatsApp
```

---

## Decisoes tomadas

1. Token API por tenant (nao global) para isolamento
2. Webhook Uazapi por tenant (token na URL)
3. Login por email (nao username) para multi-tenant
4. Payload original do Uazapi repassado ao N8N (nao reformatado)
5. Mensagens bot no lado direito com cor verde (diferente do agente azul)
6. Delay entre mensagens picadas no N8N para manter ordem
7. Token Uazapi salvo em configuracoes_extras (nao access_token encriptado)

---

## Proximos passos

- [ ] Resolver problema do EncryptedCharField (access_token nao desencripta)
- [ ] Configurar tools no N8N (atualizar lead, criar oportunidade via nossas APIs)
- [ ] Testar fluxo completo com lead real
- [ ] Documentar APIs na tela do painel
- [ ] Deploy em producao
