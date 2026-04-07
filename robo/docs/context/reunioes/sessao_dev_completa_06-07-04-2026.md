# Sessao Dev: Leads, Fluxos Visuais, Automacoes, Logging, APIs — 06-07/04/2026

**Data:** 06-07/04/2026
**Participantes:** Lucas (CEO), Claude (Tech Lead / CTO / PM / CMO)
**Duracao:** Sessao longa (~8h)

---

## Principais entregas (11 commits)

### Leads
- Pagina de detalhe do lead (/leads/<id>/) substituindo modal
- Pagina de detalhe do historico com mensagens do Inbox
- Campos customizaveis por tenant (CampoCustomizado + JSONField)
- Tela de configuracao de campos custom (/configuracoes/campos-leads/)

### Fluxos Visuais (Node-Based) para Atendimento
- 3 novos models: NodoFluxoAtendimento, ConexaoNodoAtendimento, ExecucaoFluxoAtendimento
- Model LogFluxoAtendimento para auditoria
- Engine conversacional assincrono (pausa em questoes/delays)
- Editor visual Drawflow com 25+ tipos de nos
- Canal de ativacao por fluxo (whatsapp, site, facebook, etc.)
- Signal no Inbox para iniciar fluxo automaticamente por canal
- Processamento de respostas do lead via signal
- Envio de perguntas do bot de volta no Inbox
- Dual-mode nas APIs N8N (legado + visual)
- CRUD completo na tela de fluxos
- Tela de sessoes ativas com filtros
- Detalhe da sessao com logs de execucao
- Visualizacao do fluxo ao vivo (nodo atual pulsando)
- Modelos prontos de perguntas (nome, email, CPF, cidade...)
- Salvar resposta em campo do lead
- Validacao: tipo, regex, integracao IA (4 providers), webhook
- Acao "Criar Oportunidade" no CRM

### Automacoes Marketing
- Trigger agora gera log de execucao
- Tela de historico melhorada (nodo, lead, status)
- Editor visual reconstroi do banco quando nao tem fluxo_json
- Config especifica por tipo de no (gatilhos, condicoes, acoes)
- Selects dinamicos (pipelines, estagios, usuarios, segmentos, origens, UFs)
- Campo valor da condicao muda conforme campo selecionado
- Testes E2E: 18/18 OK via management command testar_automacoes

### Integracoes IA
- Tipos OpenAI, Anthropic, Groq, Google AI adicionados em IntegracaoAPI
- Validacao por IA nos fluxos de atendimento (4 providers)
- Select de integracao IA no editor de questoes

### Logging Centralizado
- LogSistema evoluido: campos categoria, acao, entidade, entidade_id
- Helper registrar_acao() com auto-deteccao de tenant/usuario/IP
- Decorator @auditar() para views POST/PUT/DELETE automatico
- 49 pontos de auditoria: auth, CRM, leads, inbox, suporte, marketing, config, admin
- Tela centralizada em /configuracoes/logs/ com filtros

### APIs para Agentes/N8N
- GET  /api/v1/n8n/crm/pipelines/
- GET  /api/v1/n8n/crm/estagios/
- POST /api/v1/n8n/crm/oportunidades/
- PUT  /api/v1/n8n/crm/oportunidades/<pk>/
- GET  /api/v1/n8n/crm/oportunidades/buscar/
- POST /api/v1/n8n/crm/tarefas/
- PUT  /api/v1/n8n/crm/tarefas/<pk>/
- POST /api/v1/n8n/inbox/enviar/
- Todas com APITokenAuthentication e audit logging

### Reorganizacao
- docs/ movido para robo/docs/
- exports/ movido para robo/exports/
- robo/CLAUDE.md removido (mesclado na raiz)
- 7 arquivos legados removidos do robo/
- CLAUDE.md reescrito (focado em regras, enxuto)
- README.md reescrito (SaaS multi-tenant)

### Documentacao
- 12-MODULO_SUPORTE.md
- 13-MODULO_FLUXOS.md (configuracao de fluxos e questoes)
- 14-MODULO_ATENDIMENTO.md (execucao, sessoes, N8N, Matrix)
- 15-SERVICOS_CRON.md (todos os crons e servicos periodicos)
- 05-AUTOMACOES.md atualizado
- 08-MODULO_MARKETING.md atualizado
- Analise do fluxo N8N Consultoria (referencia)
- Tarefa APIs Agentes IA no backlog

### Infraestrutura
- PostgreSQL local (aurora_dev) verificado e sincronizado
- 3 ambientes documentados: SQLite, PG local, producao
- Servidor rodando com settings_local_pg

---

## Decisoes tomadas

1. Fluxos de atendimento com sistema node-based paralelo ao legado (QuestaoFluxo)
2. Canal de ativacao por fluxo (cada fluxo tem um canal que o dispara)
3. Validacao por IA via integracoes configuradas (nao hardcoded)
4. Logging centralizado reutilizando LogSistema (nao models separados)
5. APIs primeiro, depois no Agente IA (abordagem em fases)
6. Memoria do agente IA via Redis (ja tem em producao)
7. Tools CRM completo durante conversa do agente
8. Saida do loop do agente por maximo de turnos
9. Chat de teste no painel (futuro)

---

## Proximos passos

- [ ] Implementacao do fluxo da faculdade (FATEPI/FAESPI)
- [ ] No Agente IA no editor visual (Fase 2 do plano)
- [ ] Chat de teste no painel (Fase 3)
- [ ] Config especifica por tipo de no no editor de atendimento (mesma melhoria feita nas automacoes)
- [ ] Definir novo nome do produto (sugestoes: Nexo, Hubly, etc.)
