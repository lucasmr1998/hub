# 11. Materiais de Lançamento

**Status:** 🔧 Em construção
**Última atualização:** 26/03/2026

---

## Objetivo

Centralizar todos os materiais necessários para lançar a AuroraISP no mercado. Cada item tem responsável, status e dependências — para que nada seja esquecido antes de ir ao ar.

---

## Brand

| Material | Responsável | Depende de | Status |
|----------|-------------|------------|--------|
| Logo da AuroraISP | CEO | — | ⏳ Pendente |
| Brandbook completo | PMM | Logo | 🟡 Em andamento (aguarda logo) |
| Paleta de cores | PMM | — | ✅ Definida |
| Tipografia (Inter) | PMM | — | ✅ Definida |
| Padrão de interface (light/dark) | PMM | — | ✅ Definido |

---

## Vendas e Enablement

| Material | Responsável | Depende de | Status |
|----------|-------------|------------|--------|
| One-pager | PMM | Logo | ⏳ Aguardando logo |
| Pitch deck | PMM | Logo | ⏳ Aguardando logo |
| Case anônimo em PDF | PMM | — | 🔧 A criar |
| Tabela de preços | PMM | — | ✅ Aprovada |
| Respostas para objeções | PMM | — | 🟡 Rascunho em 06-MENSAGENS_CHAVE.md |
| Script do pitch de 2 minutos | PMM | — | 🟡 Rascunho em 09-ENABLEMENT.md |
| Diagnóstico — Typeform | PMM + Dev | — | 🔧 A criar (ver 13-DIAGNOSTICO.md) |
| Diagnóstico — Script WhatsApp | PMM | — | ✅ Rascunho em exports/drafts/scripts_vendas/ |

---

## Demo

| Material | Responsável | Depende de | Status |
|----------|-------------|------------|--------|
| Ambiente de demo configurado | Dev | Multi-tenancy | ⏳ Aguardando multi-tenancy |
| Roteiro de demo ao vivo | PMM + Parceiro | — | 🔧 A criar |
| Checklist pré-demo | PMM | Roteiro | 🔧 A criar |

---

## Treinamento do Parceiro

| Material | Responsável | Depende de | Status |
|----------|-------------|------------|--------|
| Módulo 1 — Visão geral da AuroraISP | PMM | — | 🔧 A criar |
| Módulo 2 — Comercial a fundo | PMM | — | 🔧 A criar |
| Módulo 3 — Marketing e CS | PMM | — | 🔧 A criar |
| Módulo 4 — Precificação e transacional | PMM | — | 🔧 A criar |
| Módulo 5 — Objeções comuns | PMM | — | 🔧 A criar |
| Módulo 6 — Demo hands-on | PMM + Dev | Ambiente de demo | 🔧 A criar |

---

## Digital

| Material | Responsável | Depende de | Status |
|----------|-------------|------------|--------|
| Landing page | Dev + PMM | Logo, copy | 🔧 A criar |
| Copy da landing page | PMM | — | 🔧 A criar |
| Instagram | PMM | Logo | ⏳ Aguardando logo |
| LinkedIn | PMM | Logo | ⏳ Aguardando logo |
| WhatsApp Business configurado | CEO | — | 🔧 A verificar |

---

## Produto

| Material | Responsável | Depende de | Status |
|----------|-------------|------------|--------|
| Refatoração do projeto | Dev | — | 🔧 Até 27/03 |
| Multi-tenancy | Dev | Refatoração | 🔧 Até 30/03 |
| Onboarding do cliente | Dev + PMM | Multi-tenancy | 🔧 A criar |
| Documentação de uso para o provedor | PMM | — | 🔧 A criar |

---

## Resumo por status

| Status | Qtd |
|--------|-----|
| ✅ Pronto | 4 |
| 🟡 Rascunho/Em andamento | 3 |
| ⏳ Aguardando desbloqueador | 5 |
| 🔧 A criar | 13 |

---

## Principal desbloqueador

A **logo** é o item que mais trava o avanço. One-pager, deck, brandbook, redes sociais e landing page dependem dela diretamente.

---

## Dependências críticas

```
Logo
  └── Brandbook completo
  └── One-pager
  └── Pitch deck
  └── Redes sociais
  └── Landing page

Multi-tenancy (30/03)
  └── Ambiente de demo
  └── Módulo 6 — Demo hands-on
  └── Onboarding do cliente
```
