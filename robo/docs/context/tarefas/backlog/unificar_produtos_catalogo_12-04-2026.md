---
name: "Unificar catalogo de produtos (PlanoInternet → ProdutoServico)"
description: "Tornar ProdutoServico a fonte unica de verdade, absorvendo PlanoInternet e OpcaoVencimento como dados do ERP"
prioridade: "🟡 Media"
responsavel: "Tech Lead + PM"
---

# Unificar Catalogo de Produtos — 12/04/2026

**Data:** 12/04/2026
**Responsavel:** Tech Lead + PM
**Prioridade:** 🟡 Media
**Status:** ⏳ Aguardando

---

## Descricao

Hoje existem dois conceitos de "produto" no sistema:

1. `PlanoInternet` (cadastro) — ISP-specific, campos de velocidade, wifi6, etc.
2. `ProdutoServico` (CRM) — generico, nome/preco/categoria

O Hubtrix precisa ser agnostico de nicho. `ProdutoServico` deve ser a fonte unica de verdade. Dados especificos do ERP (velocidade, vencimento, etc.) ficam em `dados_extras` (JSONField) ou em fields opcionais.

---

## Visao de Arquitetura

### Antes (hoje)
```
PlanoInternet (cadastro)         ProdutoServico (CRM)
  velocidade_download              nome
  velocidade_upload                preco
  wifi_6                           categoria
  valor_mensal                     recorrencia
  id_sistema_externo               id_externo
       |                                |
  CadastroCliente               ItemOportunidade
  (2 fontes de verdade, dados duplicados)
```

### Depois
```
ProdutoServico (CRM) ← fonte unica
  nome, preco, categoria, recorrencia
  id_externo (ID no ERP)
  dados_erp: JSONField {
    velocidade_download: 100,
    velocidade_upload: 50,
    wifi_6: true,
    dia_vencimento: 10,
    ... qualquer campo do ERP
  }
       |
       +── ItemOportunidade (CRM)
       +── CadastroCliente (substitui FK PlanoInternet)
       +── Integracao ERP (sync bidirecional)
```

### Principio
- **Hubtrix nao sabe o que e um plano de internet.** Ele sabe o que e um produto.
- Dados especificos do ERP (velocidade, tecnologia, etc.) ficam em `dados_erp` (JSONField).
- A UI de configuracao de produtos mostra os campos extras de forma dinamica.
- Ao integrar com HubSoft, o sync popula `dados_erp` com os campos do plano.
- Ao integrar com outro ERP, o sync popula `dados_erp` com os campos desse ERP.

---

## Tarefas

### Fase 1: Evolucao do ProdutoServico
- [ ] Adicionar `dados_erp` (JSONField) ao ProdutoServico
- [ ] Adicionar campo `dia_vencimento` (IntegerField, opcional) ao ProdutoServico
- [ ] Migration para popular ProdutoServico a partir de PlanoInternet existentes
- [ ] Migrar dados de OpcaoVencimento para campo no ProdutoServico ou config do tenant

### Fase 2: Atualizar referencias
- [ ] CadastroCliente: FK `plano_selecionado` aponta para ProdutoServico em vez de PlanoInternet
- [ ] CadastroCliente: FK `vencimento_selecionado` usa campo do ProdutoServico ou config
- [ ] Fluxo de cadastro: views e templates usam ProdutoServico
- [ ] OportunidadeVenda: remover `plano_interesse` (legado), usar ItemOportunidade
- [ ] Atualizar tela de configuracoes de cadastro

### Fase 3: Sync com ERP
- [ ] HubSoft sync: ao sincronizar planos, cria/atualiza ProdutoServico com `dados_erp`
- [ ] HubSoft sync: mapeia `id_sistema_externo` → `id_externo`
- [ ] Tela de configuracao: mostrar campos de `dados_erp` de forma dinamica

### Fase 4: Limpeza
- [ ] Deprecar PlanoInternet (manter model por retrocompatibilidade de migrations)
- [ ] Deprecar OpcaoVencimento
- [ ] Remover tela "Planos de Internet" e "Opcoes de Vencimento" das configuracoes
- [ ] Atualizar documentacao

---

## Contexto e referencias

- PlanoInternet: `apps/comercial/cadastro/models.py`
- OpcaoVencimento: `apps/comercial/cadastro/models.py`
- ProdutoServico: `apps/comercial/crm/models.py`
- CadastroCliente: `apps/comercial/cadastro/models.py` (FKs plano_selecionado, vencimento_selecionado)
- HubSoft sync: `apps/integracoes/services/hubsoft.py`
- Tela config cadastro: `apps/comercial/cadastro/views.py` (configuracoes_cadastro_view)
- Sessao 12/04/2026

---

## Resultado esperado

Um unico catalogo de produtos generico que funciona para ISPs, faculdades, consultorias ou qualquer nicho. Dados do ERP sincronizados como metadados (JSONField), sem poluir o model com campos ISP-specific.
