# Tarefas — fonte da verdade migrou pro Workspace

**A partir de 04/05/2026**, o backlog de desenvolvimento do Hubtrix vive no módulo **Workspace** do próprio sistema, no tenant interno **Aurora HQ**.

## Onde estão as tarefas agora

- **URL:** `https://app.hubtrix.com.br/workspace/`
- **Tabela:** `workspace_tarefa`
- **Tenant:** Aurora HQ (id 3)
- **Total atual:** 125 tarefas (96 concluídas + 29 em aberto)

## Por que migrou

A pasta `tarefas/backlog/` e `tarefas/finalizadas/` virou um sistema paralelo ao Workspace, com conteúdo duplicado e propenso a desincronizar. O Workspace tem:

- Workflow real (status, data_conclusao, log_execução)
- Multi-usuário (atribuir, comentar)
- UI dedicada (não precisa abrir editor de markdown)
- Multi-tenant (cada cliente vê o próprio)

## Como criar/atualizar tarefas

1. Abrir `https://app.hubtrix.com.br/workspace/projetos/` no browser
2. Selecionar o projeto correspondente (ou criar novo)
3. Adicionar tarefa pela UI

Não criar mais arquivos `.md` em `backlog/` ou `finalizadas/`.

## Status dos arquivos antigos

A pasta `backlog/` e `finalizadas/` ficam **preservadas como histórico** (já estão em git, não vamos deletar). Não editar nem adicionar arquivos novos. Quem precisa atualizar uma tarefa antiga, faz no Workspace.

## Como consultar do CLI (read-only)

Pra Claude Code ou qualquer outro consumidor que precise listar tarefas via SQL:

```sql
SELECT id, titulo, status, prioridade, criado_em::date
FROM workspace_tarefa
WHERE tenant_id = 3 AND status != 'concluida'
ORDER BY
  CASE prioridade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END,
  criado_em DESC;
```

Aplicar via `docker exec` no container do banco em produção (ver `.env.prod_readonly` pra credenciais).

---

## Reuniões e contexto

A pasta `reunioes/` continua viva — é resumos de discussões e decisões, não tarefas. Manter.
