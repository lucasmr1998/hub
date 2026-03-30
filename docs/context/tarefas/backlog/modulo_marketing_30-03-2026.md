# Desenvolver Módulo Marketing — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / PM
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O módulo Marketing está listado no hub como "a desenvolver". Atualmente existe apenas o app `apps/marketing/campanhas/` com detecção de tráfego pago. É necessário expandir para cobrir o escopo completo do módulo: réguas de automação, segmentação de base, integrações de e-mail e WhatsApp em massa, e relatórios de performance.

---

## Tarefas

- [ ] Definir escopo do MVP do módulo Marketing (Start vs Pro)
- [ ] Especificar models: Campanha, Segmento, Disparo, Metricas
- [ ] Implementar segmentação de base de leads/clientes
- [ ] Implementar disparo em massa (WhatsApp via N8N, e-mail)
- [ ] Criar dashboard de performance de campanhas
- [ ] Integrar com réguas de automação
- [ ] Definir limites por plano (Start vs Pro)
- [ ] Testar fluxos com tenant de teste

---

## Contexto e referências

- App existente: `apps/marketing/campanhas/`
- Réguas: `docs/PRODUTO/01-REGUAS_PADRAO.md` (M01 a M03)
- Precificação: `docs/GTM/08-PRECIFICACAO.md` (transacional por base de leads)

---

## Resultado esperado

Módulo Marketing funcional no plano Start (réguas básicas, segmentação simples). Base para evolução ao plano Pro (IA, tráfego pago).
