# Deploy do multi-tenancy em produção — 29/03/2026

**Data:** 29/03/2026
**Responsável:** DevOps / Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Realizar o deploy do sistema de multi-tenancy em produção. Isso envolve rodar as migrations no banco de produção, criar o tenant seed da Megalink, preencher o campo tenant_id nos registros existentes e rotacionar todas as credenciais expostas anteriormente no código.

---

## Tarefas

- [ ] Rodar migrations de multi-tenancy no banco de produção (com backup prévio)
- [ ] Criar tenant seed da Megalink Telecom
- [ ] Preencher tenant_id em todos os registros existentes (atribuir ao tenant Megalink)
- [ ] Rotacionar todas as credenciais no servidor (HubSoft API, N8N, Matrix, etc.)
- [ ] Atualizar variáveis de ambiente no servidor de produção
- [ ] Validar que o sistema funciona corretamente com o tenant Megalink
- [ ] Testar acesso ao Painel Admin Aurora (/aurora-admin/) em produção

---

## Contexto e referências

- Reunião: `docs/context/reunioes/tech_refatoracao_29-03-2026.md`
- Tarefa concluída: `docs/context/tarefas/finalizadas/refatoracao_apps_29-03-2026.md`
- Tarefa relacionada: `docs/context/tarefas/backlog/seguranca_credenciais_29-03-2026.md`

---

## Resultado esperado

Multi-tenancy ativo em produção com o tenant Megalink operacional, credenciais rotacionadas e seguras, painel admin acessível. Sistema pronto para onboarding de novos tenants.
