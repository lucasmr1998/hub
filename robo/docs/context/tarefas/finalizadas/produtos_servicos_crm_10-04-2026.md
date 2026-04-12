---
name: "Produtos/Servicos no CRM"
description: "Catalogo generico de produtos e servicos vinculados a oportunidades"
prioridade: "🔴 Alta"
responsavel: "PM + Tech Lead"
---

# Produtos/Servicos no CRM — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** PM + Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ✅ Concluido

---

## Descricao

CRM agora tem catalogo generico de produtos/servicos, desacoplado de PlanoInternet (ISP). Produtos podem ser vinculados a oportunidades com quantidade, valor e desconto. PlanoInternet permanece como mapeamento opcional para integracao HubSoft.

---

## Tarefas

- [x] Criar model ProdutoServico no CRM (nome, descricao, preco, recorrencia, categoria, ativo)
- [x] Criar model ItemOportunidade (oportunidade + produto + qtd + valor + desconto)
- [x] FK opcional para PlanoInternet (mapeamento HubSoft)
- [x] Propriedade valor_total_itens e metodo recalcular_valor na OportunidadeVenda
- [x] Views: CRUD de produtos + APIs de itens da oportunidade
- [x] Template de gestao de produtos (grid com cards)
- [x] Secao de itens no detalhe da oportunidade (adicionar/remover via modal)
- [x] Sidebar: link "Produtos" na secao CRM
- [x] Admin: ProdutoServicoAdmin, ItemOportunidadeAdmin, inline na OportunidadeVenda
- [x] Migration 0005
- [x] Documentacao atualizada (07-MODULO_COMERCIAL.md, STATUS_PRODUTO)

---

## Contexto e referencias

- Models: `apps/comercial/crm/models.py` (ProdutoServico, ItemOportunidade)
- Views: `apps/comercial/crm/views.py` (produtos_lista, api_produto_salvar, api_itens_oportunidade, etc.)
- Templates: `crm/produtos.html`, `crm/oportunidade_detalhe.html`
- URLs: `apps/comercial/crm/urls.py`
- Sessao 12/04/2026

---

## Resultado

CRM tem catalogo de produtos generico. Oportunidades podem ter multiplos produtos vinculados com quantidade, valor e desconto. Valor estimado recalculado automaticamente.
