# Migrar App Gestão do Megaroleta — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O app `gestao` do megaroleta (17 models, agentes IA) não foi migrado para o hub. Existe um TODO no código (`apps/cs/clube/views/membro_views.py:193`) referenciando essa pendência. É necessário avaliar quais models são relevantes e migrá-los.

---

## Tarefas

- [ ] Auditar os 17 models do `gestao` no megaroleta
- [ ] Definir quais models serão migrados e para qual app destino
- [ ] Migrar models relevantes (FAQ, configurações de agentes IA)
- [ ] Atualizar referências no app `clube` (resolver TODO)
- [ ] Gerar migrations
- [ ] Testar localmente

---

## Contexto e referências

- TODO em `apps/cs/clube/views/membro_views.py:193`
- App original: `megaroleta/gestao/` (somente leitura)
- Tarefa relacionada: `finalizadas/migracao_megaroleta_29-03-2026.md`

---

## Resultado esperado

Models relevantes do `gestao` integrados ao hub. TODO resolvido. Funcionalidades de FAQ e agentes IA disponíveis no módulo CS.
