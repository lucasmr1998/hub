# Sessao Dev: FATEPI parte 2 — APIs, Tenant, Login, Webhook, CRM — 07-08/04/2026

**Data:** 07-08/04/2026
**Participantes:** Lucas (CEO), Claude (Tech Lead / CTO / PM)

---

## Entregas

### APIs DRF para N8N
- 8 endpoints criados em /api/v1/n8n/crm/ e /inbox/
- Pipelines, estagios, oportunidades (CRUD), tarefas (CRUD), inbox enviar
- Serializers com dados_custom para lead e oportunidade
- Testados 7/7 OK via curl

### Seguranca Multi-Tenant (correcao critica)
- Auditoria encontrou 40+ queries sem filtro de tenant
- TenantMixin adicionado a IntegracaoAPI, ClienteHubsoft, ServicoClienteHubsoft, LogIntegracao
- CLAUDE.md com regra CRITICA de multi-tenancy
- Tela de integracoes filtrada por tenant

### Token API por Tenant
- Campo api_token no IntegracaoAPI
- APITokenAuthentication busca token no banco, identifica tenant
- Fix _thread_local -> _thread_locals
- Fix APIServiceUser sem username

### Login por Email
- EmailBackend (busca por email, fallback username)
- Template e view atualizados
- Username gerado automaticamente do email

### Webhook Uazapi por Tenant
- Rota /inbox/api/webhook/<api_token>/
- Parser adaptado para formato real Uazapi
- Token via configuracoes_extras (fix EncryptedCharField)

### Configuracao de Canais no Painel
- Select de integracao por canal
- Criar/editar canal com provider vinculado

### Campos Custom em Lead e Oportunidade
- Campo entidade (lead/oportunidade) no CampoCustomizado
- dados_custom JSONField na OportunidadeVenda
- APIs aceitam dados_custom nos dois

### Acao Criar Oportunidade nas Automacoes
- Engine + executor + editor visual
- Config: titulo, pipeline (select), estagio (select)
- Fix: salvar_fluxo extrai evento do trigger automaticamente

### Historico de Conversas no CRM
- Tab "Conversas" no detalhe da oportunidade
- Chat com mensagens do Inbox (contato, bot, agente)

### Prompt Agente Pedro
- Prompt completo atualizado para nossas APIs
- 2 tools documentadas (Atualizar Lead, Atualizar Oportunidade)
- Mapeamento de campos e estagios

### FATEPI Funcionando E2E
- Tenant + pipeline + estagios + integracoes + canal
- Automacao: lead_criado -> criar_oportunidade
- Fluxo: WhatsApp -> Uazapi -> Inbox -> N8N -> API enviar -> Inbox -> Uazapi -> WhatsApp
- Lead + oportunidade criados automaticamente

---

## Bugs encontrados e corrigidos
- IntegracaoAPI sem TenantMixin (dados vazavam entre tenants)
- _thread_local vs _thread_locals (token por tenant falhava)
- APIServiceUser sem username (registrar_acao falhava)
- EncryptedCharField nao desencripta (token Uazapi)
- Conversa sem lead apos deletar lead (nao recriava)
- salvar_fluxo nao preenchia campo evento da regra
- Webhook Uazapi formato diferente do esperado
- ALLOWED_HOSTS faltando no settings_local_pg
- Mensagens bot no lado errado do chat (CSS)

---

## Pendente
- [ ] Bug visual: menu tres pontinhos do card CRM expandindo demais
- [ ] Configurar tools no N8N com prompt atualizado
- [ ] Testar tools (Atualizar Lead, Atualizar Oportunidade) via N8N
- [ ] Deploy em producao
