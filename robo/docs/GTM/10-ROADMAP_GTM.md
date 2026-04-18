# 10. Roadmap GTM

**Status:** 🔧 Em construção contínua
**Última atualização:** 18/04/2026

---

## Objetivo

Definir as fases de entrada no mercado, com ações concretas, responsáveis e métricas de sucesso. Revisado mensalmente conforme o progresso real.

---

## Onde estamos hoje (18/04/2026)

**Em resumo:**

- Produto está **rodando em produção** com 2 clientes reais:
  - **Megalink** (30k assinantes) — case âncora, validado
  - **Nuvyon** (28k assinantes) — recém-fechada, em setup de onboarding
  - **Fatepi** — faculdade (não é ISP típico, mas usa a plataforma)
- **Fase 1 parcialmente cumprida:** meta era 15 clientes até jun/26; estamos em 2 reais + 1 outlier
- Stack de produto maduro: Comercial, Marketing, CS, Inbox, Atendimento, Fluxos visuais, Assistente CRM WhatsApp
- Material GTM completo: ICP por porte, precificação, 3 JTBDs, case, 5 módulos de treinamento

**Gargalos principais:**

- Sem site comercial público (ainda na reserva do domínio hubtrix.com.br)
- Sem logo finalizado — bloqueia one-pager/deck/brandbook em PDF
- Sem outbound estruturado em operação
- Só 1 case público (Megalink)

---

## Fases

### Fase 0 — Fundação ✅ CONCLUÍDA (mar–abr/2026)

**Principais entregas:**

- Refatoração completa do código (15 apps modulares)
- Multi-tenancy + isolamento
- Segurança (PII filter, CSRF, LGPD)
- Painel Admin Aurora (rota técnica interna)
- Sistema de planos + features
- Precificação definida (Starter/Pro/Advanced)
- GTM estruturado (ICP, concorrentes, posicionamento, mensagens, canais)
- Documentação por JTBD pronta
- Case Megalink documentado anonimamente

### Fase 1 — Validação Comercial 🔧 EM ANDAMENTO (abr/2026 →)

**Meta original:** 15 clientes pagantes até jun/2026
**Meta revisada:** 5–10 clientes pagantes até jul/2026 (mais realista com o tempo de ciclo observado)

| Ação | Responsável | Status |
|------|-------------|--------|
| Fechamento Megalink como referência | CEO | ✅ Feito (operando em produção) |
| Fechamento Nuvyon | Comercial | 🔧 Contrato em ajuste (cláusulas Pro/Advanced invertidas) |
| Onboarding da Nuvyon | CS + Tech | ⏳ Aguarda contrato assinado |
| Abordar comunidades de provedores | Parceiro comercial | 🔧 Pendente de execução estruturada |
| Ajustar pitch com base em objeções reais | PMM | ✅ JTBDs com 20 objeções documentadas |
| Treinar parceiro no produto | CEO + PMM | ✅ 5 módulos de treinamento prontos |
| Coletar feedback pós-ativação da Nuvyon | CS | ⏳ Depois do go-live |

### Fase 2 — Escala Inicial ⏳ PLANEJADA (jul/2026 →)

**Foco:** repetir o processo que funcionou, estruturar geração de demanda

| Ação | Responsável | Dependência |
|------|-------------|-------------|
| Lançar site público hubtrix.com.br | Tech + PMM | Logo finalizado + copy |
| Lançar case Megalink público (com autorização) | PMM + CEO | Negociar com Megalink |
| Nuvyon vira case público (quando resultados maturarem) | PMM + CS | ~6 meses após go-live |
| Ativar outbound estruturado via WhatsApp | Parceiro | Roteiro + CRM configurado |
| Iniciar contato com HubSoft (parceria) | CEO | Momento estratégico |
| Battle card detalhado vs ISPRO AI | PMM | Pesquisa competitiva |
| Dogfooding do funil comercial interno | Tech + CEO | Ver backlog |

### Fase 3 — Crescimento ⏳ PLANEJADA (Q4/2026 →)

**Foco:** novos canais, novos mercados, novas integrações

| Ação | Responsável | Meta |
|------|-------------|------|
| Expansão para outros ERPs (SGP primeiro, IXC e MK depois) | Tech | Destrava ISPs não-HubSoft |
| Inbound estruturado (blog, YouTube, LinkedIn) | PMM + Copywriter | Geração de demanda orgânica |
| Eventos do setor (ISP Summit, ABRINT) | CEO + Parceiro | Presença de marca |
| Módulo de gestão de assinatura interna | Tech | 10+ clientes pagantes |
| Biblioteca de templates prontos (fluxos + réguas) | PM + Copy | Reduz tempo de onboarding |
| Home personalizada por perfil | Tech | UX diferenciada |

---

## Métricas de acompanhamento (a revisar mensalmente)

| Métrica | Meta Fase 1 | Real (18/04) |
|---------|-------------|--------------|
| Clientes pagantes | 15 até jun/26 | 2 reais (Megalink, Nuvyon) |
| MRR (receita recorrente mensal) | R$ 20–30k até jun/26 | A medir após Nuvyon ativar |
| NPS do próprio Hubtrix com clientes | Estabelecer baseline | ⏳ Feature pendente |
| Time de go-live (contratação → produção) | < 30 dias | Nuvyon: em medição |
| Taxa de recomendação (cliente indicaria?) | > 70% | ⏳ A medir |

---

## Linha do tempo resumida

```
Q1/2026   Fase 0: Fundação (produto + GTM + 1º cliente)
          ↓
Abr/2026  Fase 1 começa — validação comercial
          (18/04: 2 clientes reais, material GTM robusto)
          ↓
Jun/2026  Checkpoint da Fase 1 (meta revisada pra 5–10 clientes)
          ↓
Jul/2026  Fase 2: Escala inicial — site público, outbound, HubSoft
          ↓
Q4/2026   Fase 3: Crescimento — novos ERPs, inbound, novos módulos
```

---

## Decisões estratégicas em aberto

- [ ] **Quando lançar site público?** Trade-off: esperar logo vs liberar versão MVP sem branding perfeito. Tendência atual: MVP em 4 semanas mesmo sem logo final.
- [ ] **Estratégia com HubSoft:** buscar parceria formal agora ou esperar 10+ clientes? Cada caminho tem risco diferente.
- [ ] **Expansão pra SGP:** quando começar? Cada mês sem SGP = fatia do mercado perdida.
- [ ] **Dogfooding:** prioridade 1 ou 2 da Fase 2?

---

## Referências

- Backlog de tarefas em `context/tarefas/backlog/` — 25 pendentes, várias vinculadas ao roadmap
- Visão do produto em `PRODUTO/VISAO.md` — jornadas detalhadas e princípios
- Clientes ativos em `context/clientes/` — Megalink, Fatepi, Nuvyon
- Posicionamento por JTBD em `GTM/posicionamento/` — 3 docs prontos
