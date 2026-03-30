---
name: "Ativar Apps CS: NPS e Retenção"
description: "As pastas `apps/cs/nps/` e `apps/cs/retencao/` existem no projeto mas não estão em `INSTALLED_APPS`. É necessário defini"
prioridade: "🟡 Média"
responsavel: "Dev"
---

# Ativar Apps CS: NPS e Retenção — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

As pastas `apps/cs/nps/` e `apps/cs/retencao/` existem no projeto mas não estão em `INSTALLED_APPS`. É necessário definir os models, views e URLs desses apps, registrá-los no Django e integrá-los ao módulo CS.

---

## Tarefas

- [ ] Definir models do app `nps` (PesquisaNPS, RespostaNPS, configurações)
- [ ] Definir models do app `retencao` (AlertaChurn, AcaoRetencao, ScoreCliente)
- [ ] Criar views e templates básicos para ambos
- [ ] Registrar em `INSTALLED_APPS`
- [ ] Gerar migrations
- [ ] Criar URLs e integrar no menu do CS
- [ ] Adicionar TenantMixin nos models

---

## Contexto e referências

- Réguas CS01 a CS07 em `docs/PRODUTO/01-REGUAS_PADRAO.md`
- Apps CS migrados: `finalizadas/migracao_megaroleta_29-03-2026.md`

---

## Resultado esperado

Apps `nps` e `retencao` funcionais, com models, views e URLs integrados ao módulo CS. Prontos para receber as réguas de automação.
