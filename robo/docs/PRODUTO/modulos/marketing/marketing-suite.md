---
modulo: Marketing — Suite (visão integrada)
status: 🟢 Operacional (LP em discovery)
data: 13/06/2026
---

# Marketing Suite — visão integrada

Visão de como os 4 sub-apps de marketing do Hubtrix se conectam pra entregar **captação → nutrição → conversão → atribuição**.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│  CAPTAÇÃO (geração de lead novo)                                │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  WhatsApp    │  │   Inbox      │  │   Landing Page       │  │
│  │  via N8N     │  │   widget     │  │   (📋 discovery)     │  │
│  │              │  │   embed      │  │                       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                  │                     │              │
│         └──────────────────┴─────────────────────┘              │
│                            │                                    │
│           ┌────────────────▼────────────────┐                  │
│           │   DETECÇÃO DE CAMPANHA           │                  │
│           │   (palavra-chave / UTM)         │                  │
│           │   apps/marketing/campanhas/     │                  │
│           └────────────────┬────────────────┘                  │
└────────────────────────────┼────────────────────────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │   LeadProspecto      │
                  │  + campanha_origem   │
                  └──────────┬───────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│  NUTRIÇÃO                  │                                    │
│                            ▼                                    │
│              ┌──────────────────────┐                          │
│              │   SEGMENTOS          │                          │
│              │   (agrupamento       │                          │
│              │    dinâmico)         │                          │
│              └──────────┬───────────┘                          │
│                         │                                       │
│              ┌──────────▼───────────┐                          │
│              │   AUTOMAÇÕES         │                          │
│              │   (engine BFS +      │                          │
│              │    editor Drawflow)  │                          │
│              └──────┬─────┬────┬────┘                          │
│                     │     │    │                                │
│              ┌──────┘     │    └──────┐                        │
│              ▼            ▼            ▼                        │
│        ┌─────────┐  ┌─────────┐  ┌─────────┐                  │
│        │ EMAIL   │  │WhatsApp │  │ CRM/Pts │                  │
│        │ Resend  │  │ N8N     │  │ tarefas │                  │
│        └─────────┘  └─────────┘  └─────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│  CONVERSÃO + ATRIBUIÇÃO    ▼                                    │
│              ┌──────────────────────┐                          │
│              │   CRM Pipeline       │                          │
│              │   (estágios + regras)│                          │
│              └──────────┬───────────┘                          │
│                         │                                       │
│              ┌──────────▼───────────┐                          │
│              │  Oportunidade ganha  │                          │
│              │  → campanha.roi      │                          │
│              └──────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Sub-apps

| Sub-app | Status | Doc |
|---|---|---|
| `campanhas/` | 🟢 Implementado | [campanhas.md](campanhas.md) |
| `segmentos` (URL no marketing/, model em comercial/crm) | 🟢 Implementado | [segmentos.md](segmentos.md) |
| `automacoes/` | 🟢 Implementado | [automacoes/](automacoes/) |
| `emails/` | 🟢 Implementado (DNS, editor, envio, tracking) | [emails-dominios-remetentes.md](emails-dominios-remetentes.md) + [emails-templates-renderer.md](emails-templates-renderer.md) |
| `landing_pages/` | 📋 Discovery (não implementado) | [landing-pages.md](landing-pages.md) |

## Camadas + responsabilidade

| Camada | App(s) | Responsabilidade |
|---|---|---|
| **Captação** | inbox/widget + N8N + (futuro) landing_pages/ | Receber lead novo de qualquer canal |
| **Atribuição** | marketing/campanhas/ | Detectar palavra-chave / UTM e ligar lead à campanha |
| **Segmentação** | crm (model) + marketing (URLs) | Agrupar leads por critério dinâmico (cidade, plano interesse, momento da jornada) |
| **Automação** | marketing/automacoes/ | Engine BFS — quando lead entra em segmento ou bate condição, dispara ações |
| **Comunicação outbound** | marketing/emails/ + N8N (WhatsApp) | Email com DNS próprio do tenant, WhatsApp via uazapi |
| **Conversão** | comercial/crm/ | Pipeline + regras de estágio (já documentado fora deste módulo) |

## Fluxos canônicos

### 1. Lead novo via Google Ads → cliente comprou

```
1. Anúncio Google Ads com UTM "campanha=fibra-1gb-junho"
2. Clique → Landing Page do tenant (futuro)
3. Form submetido → LeadProspecto criado
4. CampanhaTrafego(codigo='fibra-1gb-junho') vincula via campanha_origem
5. Signal lead_criado → RegraAutomacao "Boas-vindas LP"
6. Automação dispara:
   - send_email(template='boas_vindas_lp')
   - delay 1h
   - send_whatsapp(template='ola_voce_se_interessou')
7. Lead responde no WhatsApp → cai no flow Brayo/Vero
8. Vai pelo cadastro → vira Oportunidade no CRM
9. Vendedor fecha → Oportunidade.status='ganho'
10. CampanhaTrafego.roi recalculado (receita - orçamento)
```

### 2. Cliente atual recebe campanha de upsell

```
1. Tenant cria Segmento: "Clientes com plano 400 Mega há +6 meses"
2. Tenant cria RegraAutomacao "Oferta upgrade 1Gb"
   - Trigger: lead_entrou_segmento(<id>)
   - Ações:
     - send_email(template='oferta_upgrade_1gb')
     - delay 3 dias
     - SE clicou_email → send_whatsapp(template='vamos_conversar')
     - SE NÃO clicou → fim
3. Diariamente engine avalia segmento → identifica novos membros
4. Pra cada membro novo, dispara automação
5. Email sai do dominio_remetente do tenant (atendimento@meuprovedor.com.br)
6. Tracking Resend captura abertura/clique → status_envio atualizado
7. Cliente que clicou recebe WhatsApp 3 dias depois
```

### 3. Lead frio do Instagram via N8N

```
1. Mensagem WhatsApp chega: "vi seu insta, qual o preço?"
2. N8N → /api/public/n8n/inbox/mensagem/
3. apps.marketing.campanhas detecta "insta" (palavra-chave da campanha "Instagram orgânico")
4. LeadProspecto criado com campanha_origem
5. Bot do flow processa pedido normalmente (Brayo)
6. Vira venda → ROI da campanha "Instagram orgânico" atualiza
```

## Integrações externas

| Provedor | Uso | App |
|---|---|---|
| **Resend** | Envio + DNS + webhook | `marketing/emails/services/resend_service.py` |
| **N8N** | WhatsApp + detecção de campanha | webhook em `/api/public/n8n/*` |
| **Drawflow.js** | Editor visual de automações | CDN v0.0.59 |
| **Chart.js** | Gráficos no dashboard | CDN |
| **uazapi** | Provedor WhatsApp do tenant | configurado em `IntegracaoAPI` |
| **Caddy** (futuro) | Reverse proxy + Let's Encrypt pra domínio custom de LP | Fase 3 de LP |
| **GA4 / Meta Pixel / TikTok Pixel** (futuro) | Tracking da LP | Pixels configuráveis por LP |

## Dados centralizados (single source of truth)

| Entidade | Dono | Vive em |
|---|---|---|
| Lead | comercial/leads | `LeadProspecto` |
| Campanha (UTM/palavra) | marketing/campanhas | `CampanhaTrafego` |
| Segmento | crm | `Segmento` |
| Template de email | marketing/emails | `TemplateEmail` |
| Domínio remetente | marketing/emails | `DominioRemetente` |
| Regra de automação | marketing/automacoes | `RegraAutomacao` |
| Execução de automação | marketing/automacoes | `LogExecucao` |
| Envio individual de email | marketing/emails | `EnvioEmail` |
| Detecção de campanha | marketing/campanhas | `DeteccaoCampanha` |
| Pipeline + oportunidade | crm | `OportunidadeVenda` |
| Landing Page (futuro) | marketing/landing_pages | `LandingPage` |
| Submissão de LP (futuro) | marketing/landing_pages | `LandingSubmissao` |

## Multi-tenancy

**Todo modelo da suite herda `TenantMixin`** — `.objects` retorna só dados do tenant via thread-local. Cross-tenant impossível por construção.

DNS de domínio remetente (`DominioRemetente`) e domínio custom de LP (`LandingDominioCustom` futuro) **são por tenant** — cada tenant configura o próprio.

## Estado atual (resumo executivo)

| Capacidade | Tenant pode fazer hoje? | Onde |
|---|---|---|
| Disparar email personalizado pro próprio domínio | ✅ Sim — após configurar DNS no Resend via UI | `/marketing/emails/dominios/` |
| Criar template visual de email | ✅ Sim | `/marketing/emails/` (editor de blocos) |
| Tracking de abertura/clique/bounce | ✅ Sim — via webhook Resend | `EnvioEmail.status` |
| Automatizar regras (signal → ação) | ✅ Sim | `/marketing/automacoes/` (editor Drawflow) |
| Detectar campanha por palavra-chave/UTM | ✅ Sim | `/marketing/campanhas/` |
| Criar segmento dinâmico | ✅ Sim | rota URL marketing/ + model em crm |
| **Criar landing page no Hubtrix** | ❌ **Não — em discovery** | (futuro) `/marketing/landing-pages/` |
| Domínio personalizado pra LP | ❌ Não | (futuro fase 3) |

## Próximas evoluções priorizadas

1. **Landing Pages MVP** — fase 1 do plano (3-5 dias). Subdomínio único + editor reusado.
2. **Renderer Django Template completo no email** — habilitar `{% for %}` e filters
3. **A/B test em automações** — variar template baseado em hash do lead
4. **Dashboard agregado** — visitas LP + envios email + execuções automação + leads gerados num só lugar
5. **Webhooks de saída** — tenant configura URL pra receber `lead_criado` em sistema dele
