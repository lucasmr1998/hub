# Checklist Completo GTM — AuroraISP

**Última atualização:** 29/03/2026

Legenda: ✅ Feito — 🟡 Parcial/Rascunho — 🔧 Em andamento — ⏳ Não iniciado

---

## 1. Estratégia de Mercado

| Item | Status | Referência |
|------|--------|------------|
| Pesquisa de mercado | 🟡 | 01-PESQUISA_MERCADO.md |
| Tamanho do mercado (TAM/SAM/SOM) | ⏳ | — |
| ICP definido | ✅ | 02-ICP.md |
| Personas mapeadas (4) | ✅ | 02-ICP.md |
| Análise de concorrentes | ✅ | 03-CONCORRENTES.md |
| Proposta de valor por persona | ✅ | 04-PROPOSTA_VALOR.md |
| Posicionamento e tagline | ✅ | 05-POSICIONAMENTO.md |
| Mensagens chave por módulo | ✅ | 06-MENSAGENS_CHAVE.md |
| Objeções e respostas | 🟡 | 06-MENSAGENS_CHAVE.md |

---

## 2. Produto e Precificação

| Item | Status | Referência |
|------|--------|------------|
| Definição dos módulos (Comercial, Marketing, CS) | ✅ | CLAUDE.md |
| Funcionalidades por plano (Starter/Start/Pro) | ✅ | 08-PRECIFICACAO.md |
| Precificação aprovada | ✅ | 08-PRECIFICACAO.md |
| Modelo transacional definido | ✅ | 08-PRECIFICACAO.md |
| Simulações de ROI por porte | ✅ | 08-PRECIFICACAO.md |
| Política de trial | ✅ | 08-PRECIFICACAO.md |
| Política de bundle/desconto | ⏳ | — |
| Roadmap do produto | ✅ | 10-ROADMAP_GTM.md, PRODUTO/02-ROADMAP_PRODUTO.md |
| Réguas padrão especificadas (16 fluxos) | ✅ | PRODUTO/01-REGUAS_PADRAO.md |
| Refatoração em apps por módulo | ✅ | 10 apps criados (29/03/2026) |
| Multi-tenancy implementado | ✅ | Tenant, TenantMixin, TenantManager, TenantMiddleware (29/03/2026) |
| Segurança: secrets removidos do código | ✅ | Variáveis de ambiente (29/03/2026) |
| Módulo CS integrado ao hub | ✅ | 4 apps migrados do megaroleta (29/03/2026) |
| Estrutura CRM do parceiro definida | ✅ | 5 estágios, exports/drafts/fluxos/crm_parceiro.md |
| Painel Admin Aurora para gestão SaaS | ✅ | /aurora-admin/ com tenants, planos, features (29/03/2026) |
| Sistema de planos com features | ✅ | 9 planos, 115 features, seed_planos command (29/03/2026) |

---

## 3. Brand e Identidade Visual

| Item | Status | Referência |
|------|--------|------------|
| Tom de voz | ✅ | BRAND/07-TOM_DE_VOZ.md |
| Paleta de cores | ✅ | BRAND/08-BRANDBOOK.md |
| Tipografia | ✅ | BRAND/08-BRANDBOOK.md |
| Padrão de interface (light/dark) | ✅ | BRAND/08-BRANDBOOK.md |
| Logo | ⏳ | — (CEO) |
| Brandbook completo | 🔧 | BRAND/08-BRANDBOOK.md (aguarda logo) |
| Guia de aplicação da marca | ✅ | BRAND/09-GUIA_APLICACAO.md |

---

## 4. Canais e Distribuição

| Item | Status | Referência |
|------|--------|------------|
| Canais de aquisição mapeados | ✅ | 07-CANAIS.md |
| Modelo de parceria (sócio comercial) | ✅ | 07-CANAIS.md |
| Estratégia de comunidades ISP | ✅ | 07-CANAIS.md |
| Mapeamento de grupos WhatsApp/Telegram | ⏳ | Tarefa: grupos_provedores |
| Estratégia de outbound | 🟡 | 07-CANAIS.md |
| Estratégia de eventos | 🟡 | 07-CANAIS.md |
| Estratégia inbound (blog, YouTube, LinkedIn) | ⏳ | — |
| Estratégia de SEO | ⏳ | — |
| Estratégia de tráfego pago | ⏳ | — |

---

## 5. Materiais de Vendas

| Item | Status | Referência |
|------|--------|------------|
| Script de pitch 2 minutos | 🟡 | 09-ENABLEMENT.md |
| Estrutura do one-pager | ✅ | exports/drafts/apresentacao/ |
| Estrutura do pre-demo deck (6 slides) | ✅ | exports/drafts/apresentacao/ |
| Estrutura do deck de apoio (10 slides) | ✅ | exports/drafts/apresentacao/ |
| Estrutura do deck do parceiro (10 slides) | ✅ | exports/drafts/apresentacao/ |
| One-pager visual (PPT/PDF) | ⏳ | Aguarda logo |
| Decks visuais (PPT/PDF) | ⏳ | Aguarda logo |
| Case anônimo em PDF | ⏳ | — |
| Tabela de preços (PDF) | ⏳ | Aguarda logo |
| Battle card de concorrentes | ⏳ | — |

---

## 6. Processo Comercial

| Item | Status | Referência |
|------|--------|------------|
| Fluxo comercial completo (7 etapas) | ✅ | 12-FLUXO_COMERCIAL.md |
| Diagnóstico do provedor | ✅ | 13-DIAGNOSTICO.md |
| Script de diagnóstico WhatsApp | ✅ | exports/drafts/scripts_vendas/ |
| Typeform de diagnóstico (inbound) | ⏳ | — |
| Checklist de qualificação | ✅ | 13-DIAGNOSTICO.md |
| Roteiro de demo ao vivo | 🟡 | exports/drafts/apresentacao/ |
| Ambiente de demo configurado | 🟡 | Multi-tenancy implementado localmente. Falta deploy em produção |
| Script de follow-up pós-demo | ⏳ | — |
| Proposta formal (template) | ⏳ | — |
| CRM do parceiro | 🟡 | Estrutura pronta (exports/drafts/fluxos/crm_parceiro.md). Falta configurar ferramenta |

---

## 7. Enablement do Parceiro

| Item | Status | Referência |
|------|--------|------------|
| Módulo 1 — Visão geral da AuroraISP | ⏳ | Tarefa: treinamento_parceiro |
| Módulo 2 — Comercial a fundo | ⏳ | Tarefa: treinamento_parceiro |
| Módulo 3 — Marketing e CS | ⏳ | Tarefa: treinamento_parceiro |
| Módulo 4 — Precificação e ROI | ⏳ | Tarefa: treinamento_parceiro |
| Módulo 5 — Objeções comuns | ⏳ | Tarefa: treinamento_parceiro |
| Módulo 6 — Demo hands-on | ⏳ | Aguarda ambiente de demo |
| Sessão de treinamento agendada | ⏳ | Primeira semana de abril |

---

## 8. Nurturing e Réguas

| Item | Status | Referência |
|------|--------|------------|
| Estrutura da régua de trial (D+0 a D+14) | ✅ | exports/drafts/reguas/ |
| Estrutura da régua de recuperação pós-trial (D+1 a D+30) | ✅ | exports/drafts/reguas/ |
| Textos da régua de trial | ⏳ | Tarefa: textos_regua_trial |
| Textos da régua de recuperação | ⏳ | Tarefa: textos_regua_recuperacao |
| Régua de pós-ativação | ⏳ | Tarefa: pos_ativacao |
| Régua de nutrição de longo prazo | ⏳ | — |
| Régua de indicação (NPS 9-10) | ⏳ | — |
| Régua de expansão (upsell de módulo) | ⏳ | — |

---

## 9. Presença Digital

| Item | Status | Referência |
|------|--------|------------|
| Domínio definido | ⏳ | Tarefa: lancamento_digital |
| Copy da landing page | ⏳ | Tarefa: lancamento_digital |
| Landing page no ar | ⏳ | Aguarda logo e copy |
| Instagram configurado | ⏳ | Aguarda logo |
| LinkedIn configurado | ⏳ | Aguarda logo |
| WhatsApp Business configurado | ⏳ | Tarefa: lancamento_digital |
| Estratégia de conteúdo | ⏳ | — |

---

## 10. Customer Success e Retenção

| Item | Status | Referência |
|------|--------|------------|
| Processo de onboarding definido | 🟡 | 12-FLUXO_COMERCIAL.md |
| Checklist de ativação | 🟡 | 12-FLUXO_COMERCIAL.md |
| SLA de ativação (prazo máximo) | ⏳ | — |
| Processo pós-ativação | ⏳ | Tarefa: pos_ativacao |
| NPS automatizado | ⏳ | — |
| Processo de churn prevention | ⏳ | — |
| Processo de expansão (upsell) | ⏳ | — |

---

## 11. Operações e Jurídico

| Item | Status | Referência |
|------|--------|------------|
| Contrato de prestação de serviço | ⏳ | — |
| Termos de uso | ⏳ | — |
| Política de privacidade | ⏳ | — |
| Modelo de faturamento/cobrança | ⏳ | — |
| Processo de suporte ao cliente | ⏳ | — |
| Acordo com o sócio comercial | ⏳ | — |

---

## 12. Lançamento

| Item | Status | Referência |
|------|--------|------------|
| Roadmap GTM com datas | 🟡 | 10-ROADMAP_GTM.md |
| Meta Fase 1 (15 clientes até jun/2026) | ✅ | 10-ROADMAP_GTM.md |
| Checklist de lançamento | ✅ | 11-MATERIAIS_LANCAMENTO.md |
| Plano de PR e comunicação | ⏳ | — |
| Estratégia de eventos (ISP Summit, etc.) | ⏳ | — |
| Case público (com autorização do cliente) | ⏳ | — |

---

## 13. Desenvolvimento

| Item | Status | Referência |
|------|--------|------------|
| Migração de models para apps modulares | ⏳ | Tarefa: migracao_models_apps |
| Ativar apps CS: NPS e Retenção | ⏳ | Tarefa: apps_cs_nps_retencao |
| Migrar app gestão do megaroleta | ⏳ | Tarefa: migrar_gestao_megaroleta |
| Implementar Django REST Framework | ⏳ | Tarefa: api_rest_framework |
| Finalizar refatoração vendas_web | 🔧 | Tarefa: refatoracao_vendas_web |
| Padronizar frontend CS | 🔧 | Tarefa: padronizar_frontend_cs |

---

## 14. Infraestrutura

| Item | Status | Referência |
|------|--------|------------|
| Deploy multi-tenancy em produção | ⏳ | Tarefa: deploy_multitenancy |
| Docker e containerização | ⏳ | Tarefa: docker_containerizacao |
| Pipeline CI/CD | ⏳ | Tarefa: cicd_pipeline |
| Monitoramento e logging estruturado | ⏳ | Tarefa: monitoramento_logging |

---

## 15. Qualidade

| Item | Status | Referência |
|------|--------|------------|
| Cobertura de testes (meta: >60%) | ⏳ | Tarefa: cobertura_testes |
| Testes de isolamento tenant | ⏳ | Tarefa: testes_isolamento_tenant |
| Linting e qualidade de código | ⏳ | Tarefa: linting_qualidade_codigo |

---

## 16. Segurança

| Item | Status | Referência |
|------|--------|------------|
| Correção CSRF e segurança de endpoints | ⏳ | Tarefa: csrf_endpoints_seguranca |
| LGPD e privacidade de dados | ⏳ | Tarefa: lgpd_privacidade |
| Secrets removidos do código | ✅ | Concluído (29/03/2026) |

---

## 17. Produto (Desenvolvimento)

| Item | Status | Referência |
|------|--------|------------|
| Implementar réguas de automação (16 fluxos) | ⏳ | Tarefa: reguas_automacao_implementar |
| Desenvolver módulo Marketing | ⏳ | Tarefa: modulo_marketing |
| Réguas especificadas | ✅ | PRODUTO/01-REGUAS_PADRAO.md |

---

## Resumo por frente

| Frente | Feito | Parcial | Não iniciado |
|--------|-------|---------|--------------|
| Estratégia de mercado | 7 | 2 | 1 |
| Produto e precificação | 15 | 1 | 1 |
| Brand | 4 | 1 | 2 |
| Canais | 3 | 2 | 4 |
| Materiais de vendas | 5 | 1 | 5 |
| Processo comercial | 4 | 2 | 4 |
| Enablement do parceiro | 0 | 0 | 7 |
| Nurturing e réguas | 2 | 0 | 6 |
| Presença digital | 0 | 0 | 7 |
| Customer success | 0 | 2 | 5 |
| Operações e jurídico | 0 | 0 | 6 |
| Lançamento | 2 | 1 | 3 |
| **Desenvolvimento** | **0** | **2** | **4** |
| **Infraestrutura** | **0** | **0** | **4** |
| **Qualidade** | **0** | **0** | **3** |
| **Segurança** | **1** | **0** | **2** |
| **Produto (dev)** | **1** | **0** | **2** |
| **Total** | **44** | **14** | **64** |

> Atualizado em 30/03/2026. Adicionadas frentes de desenvolvimento, infraestrutura, qualidade, segurança e produto (dev).
