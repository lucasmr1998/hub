---
name: "Migrar App Gestão do Megaroleta (FUTURO — sem ETA)"
description: "App gestao do megaroleta (projetos, kanban, automações, sala de agentes, alertas, FAQ) ficou intencionalmente fora da migração inicial. Reavaliar quando houver demanda."
prioridade: "🟢 Baixa"
responsavel: "Dev"
status: "🔮 Futuro — sem ETA"
---

# Migrar App Gestão do Megaroleta — 30/03/2026

**Data criação:** 30/03/2026
**Última atualização:** 26/04/2026
**Responsável:** Dev
**Prioridade:** 🟢 Baixa
**Status:** 🔮 **Futuro — sem ETA**

---

## ⚠ Decisão atual: NÃO migrar agora

Em 26/04/2026 foi confirmado que o módulo `megaroleta/gestao/` **não vai ser migrado nesse ciclo**. Não é gap nem esquecimento — é decisão consciente de escopo da equipe.

Conteúdo do `gestao/` (segundo auditoria de 26/04):
- Projetos
- Kanban
- Automações
- Sala de agentes IA
- Alertas
- 17 models, vários templates

**Quando reavaliar:** se um cliente pedir explicitamente alguma funcionalidade do gestão, ou se o time decidir trazer agentes IA / kanban interno pro Hubtrix.

**Não tratar como gap em auditorias futuras.**

---

## Tarefas (preservadas pra quando o tema voltar)

- [ ] Auditar os 17 models do `gestao` no megaroleta
- [ ] Definir quais models são relevantes e pra qual app destino vão
- [ ] Migrar models selecionados (provavelmente FAQ + configurações de agentes IA)
- [ ] Atualizar referências no app `clube` (resolver TODO em [apps/cs/clube/views/membro_views.py:193](robo/dashboard_comercial/gerenciador_vendas/apps/cs/clube/views/membro_views.py#L193))
- [ ] Gerar migrations
- [ ] Testar localmente

---

## Contexto e referências

- TODO em `apps/cs/clube/views/membro_views.py:193` — pode ser refatorado pra remover dependência ou adiado
- App original: `megaroleta/gestao/` (read-only)
- Tarefa relacionada: `finalizadas/migracao_megaroleta_29-03-2026.md`
- Memória do projeto: `project_modulo_gestao_nao_migrado.md` (registra a decisão)

---

## Histórico

- **30/03/2026:** tarefa criada como prioridade média, status "Aguardando"
- **26/04/2026:** auditoria de paridade CS megaroleta vs robo confirmou que gestão **não foi migrado intencionalmente**. Status alterado pra "Futuro — sem ETA", prioridade rebaixada pra 🟢 Baixa.
