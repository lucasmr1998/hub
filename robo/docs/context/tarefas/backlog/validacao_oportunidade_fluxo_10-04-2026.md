---
name: "Validacao de oportunidade no fluxo"
description: "Verificar se lead ja tem oportunidade antes de criar uma nova no fluxo de automacao"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Validacao de Oportunidade no Fluxo — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

No fluxo de atendimento, o nodo "Criar Oportunidade" nao verifica se o lead ja possui uma oportunidade. Como o model usa OneToOneField, causa erro se tentar criar duplicado. Precisa validar antes de criar e, se ja existir, atualizar os dados.

---

## Tarefas

- [ ] No engine `_acao_criar_oportunidade`, verificar se lead ja tem oportunidade
- [ ] Se ja tem: atualizar dados_custom em vez de criar nova
- [ ] Registrar log adequado em ambos os casos
- [ ] Testar com lead que ja tem oportunidade

---

## Contexto e referencias

- Engine: `apps/comercial/atendimento/engine.py` funcao `_acao_criar_oportunidade`
- Model: `OportunidadeVenda` com `OneToOneField` para lead
- Sessao 10/04/2026

---

## Resultado esperado

Fluxo nao quebra quando lead ja tem oportunidade. Atualiza dados existentes.
