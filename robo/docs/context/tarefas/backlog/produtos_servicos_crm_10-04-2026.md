---
name: "Produtos/Servicos no CRM"
description: "Planos de internet e datas de vencimento como funcionalidades do CRM"
prioridade: "🟡 Media"
responsavel: "PM + Tech Lead"
---

# Produtos/Servicos no CRM — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** PM + Tech Lead
**Prioridade:** 🟡 Media
**Status:** ⏳ Aguardando

---

## Descricao

Hoje "Planos de Internet" e "Datas de Vencimento" sao funcionalidades isoladas do modulo de cadastro (legado HubSoft). Devem migrar para o CRM como "Produtos/Servicos", permitindo que qualquer tipo de empresa (nao so ISPs) configure seus produtos, precos e condicoes.

---

## Tarefas

- [ ] Criar model `ProdutoServico` no CRM (nome, descricao, preco, recorrencia, ativo)
- [ ] Vincular produtos a oportunidades (muitos-para-muitos)
- [ ] Migrar dados de PlanoInternet para ProdutoServico
- [ ] Datas de vencimento como campo do produto ou da oportunidade
- [ ] UI de gestao de produtos (CRUD)
- [ ] Selector de produto na criacao de oportunidade
- [ ] Atualizar relatorios para usar produtos

---

## Contexto e referencias

- Model atual: `apps/comercial/cadastro/models.py` → `PlanoInternet`
- Oportunidade: `apps/comercial/crm/models.py` → `OportunidadeVenda.plano_interesse`
- Sessao 10/04/2026

---

## Resultado esperado

CRM tem catalogo de produtos/servicos generico. Oportunidades vinculadas a produtos com preco e condicoes.
