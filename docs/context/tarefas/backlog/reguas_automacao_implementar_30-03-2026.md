# Implementar Réguas de Automação — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / CRM e Automação
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

As 16 réguas de automação estão especificadas (`docs/PRODUTO/01-REGUAS_PADRAO.md`) mas nenhuma foi implementada no código. São o motor de automação do hub, cobrindo os módulos Comercial (C01 a C06), CS (CS01 a CS07) e Marketing (M01 a M03).

---

## Tarefas

- [ ] Definir arquitetura do motor de réguas (models: Regua, EtapaRegua, ExecucaoRegua)
- [ ] Criar app `apps/marketing/automacao/` ou integrar ao `apps/marketing/campanhas/`
- [ ] Implementar réguas do Comercial (C01 a C06) — prioridade: C01 (boas-vindas), C02 (follow-up)
- [ ] Implementar réguas do CS (CS01 a CS07) — prioridade: CS01 (onboarding), CS02 (NPS)
- [ ] Implementar réguas do Marketing (M01 a M03)
- [ ] Integrar com N8N para disparo de WhatsApp/e-mail
- [ ] Criar painel de configuração por tenant (ativar/desativar réguas)
- [ ] Criar logs de execução por régua
- [ ] Testar fluxos end-to-end

---

## Contexto e referências

- Especificação: `docs/PRODUTO/01-REGUAS_PADRAO.md` (16 fluxos detalhados)
- Integração N8N existente: `apps/integracoes/`
- Depende de: Apps NPS e Retenção (`apps_cs_nps_retencao_30-03-2026.md`)

---

## Resultado esperado

Motor de réguas funcional com pelo menos as réguas C01, C02, CS01 e CS02 em produção. Configurável por tenant. Logs de execução visíveis no painel.
