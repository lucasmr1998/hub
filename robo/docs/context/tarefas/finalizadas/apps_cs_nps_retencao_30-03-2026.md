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
**Status:** 🔧 Em andamento

---

## Descrição

As pastas `apps/cs/nps/` e `apps/cs/retencao/` existem no projeto mas não estão em `INSTALLED_APPS`. É necessário definir os models, views e URLs desses apps, registrá-los no Django e integrá-los ao módulo CS.

---

## Tarefas

- [x] Definir models do app `nps` (ConfiguracaoNPS, PesquisaNPS com TenantMixin)
- [x] Definir models do app `retencao` (ScoreCliente, AlertaChurn, AcaoRetencao com TenantMixin)
- [x] Criar views e URLs básicos para ambos
- [x] Registrar em `INSTALLED_APPS`
- [ ] Gerar migrations (executar manualmente)
- [ ] Integrar no menu do CS
- [x] Adicionar TenantMixin nos models
- [x] Registrar models no admin

---

## Contexto e referências

- Réguas CS01 a CS07 em `docs/PRODUTO/01-REGUAS_PADRAO.md`
- Apps CS migrados: `finalizadas/migracao_megaroleta_29-03-2026.md`

---

## Resultado esperado

Apps `nps` e `retencao` funcionais, com models, views e URLs integrados ao módulo CS. Prontos para receber as réguas de automação.
