---
name: "Deploy do fix _resolver_campo_contexto em producao"
description: "Subir commit 5eb2e35 (fix var.X) pro EasyPanel/VPS pra que fluxos de atendimento passem a rotear corretamente"
prioridade: "🔴 Alta"
responsavel: "Lucas"
---

# Deploy fix var.X em producao — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Lucas (EasyPanel/SSH)
**Prioridade:** 🔴 Alta (bloqueador do fluxo v3 FATEPI)
**Status:** ⏳ Aguardando deploy

---

## Descrição

Fix aplicado em `engine.py` + 10 novos testes (commit `5eb2e35` em origin/main). Suite local passou com 901 testes. Sem o deploy, toda condicao `var.X == valor` nos fluxos de atendimento continua retornando false silenciosamente — incluindo o fluxo v3 FATEPI que nao esta entregando matriculas.

## Tarefas

- [ ] Entrar no EasyPanel (painel web ou SSH VPS 103.199.187.4)
- [ ] Deploy do servico `projetos_hub` (pull do `origin/main` → rebuild → restart)
- [ ] Verificar container novo subiu: `docker ps --filter name=projetos_hub`
- [ ] Confirmar fix no container: `docker exec <container> grep "hasattr(obj, 'get')" /app/apps/comercial/atendimento/engine.py`
- [ ] Rodar teste e2e (ver tarefa irma `e2e_fatepi_pos_deploy`)

## Referencias

- Commit: `5eb2e35` (Fix: _resolver_campo_contexto aceita MutableMapping (ContextoLogado))
- Tarefa irma: `e2e_fatepi_pos_deploy_23-04-2026.md`
- Bug: [fix_resolver_campo_contextologado_23-04-2026.md](../finalizadas/fix_resolver_campo_contextologado_23-04-2026.md)
