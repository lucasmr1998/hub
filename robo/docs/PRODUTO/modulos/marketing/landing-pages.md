---
modulo: Marketing — Landing Pages
status: 📋 Discovery (não implementado)
data: 13/06/2026
---

# Marketing — Landing Pages

**Status atual:** discovery. Nenhum código escrito ainda. Esta doc é o **alinhamento de escopo** antes da implementação.

## Por que

Hoje o tenant captura lead via:
- **Inbox/widget** ([widget-chat.md](../inbox/widget-chat.md)) embedável em site próprio dele (precisa ter site)
- **WhatsApp / N8N** (lead chega por mensagem)
- **Cadastro manual** no Hubtrix

**Faltando:** uma página pública que o **próprio Hubtrix hospede** pro tenant, com form que cria `LeadProspecto` automaticamente — útil pra campanhas de tráfego pago quando o ISP não tem site/dev pra colocar form.

## O que já temos reutilizável

| Asset | Onde | Reuso na LP |
|---|---|---|
| **Renderer de blocos** (12 tipos) | `apps/marketing/emails/renderer.py` | Mesmo motor monta a LP (sem inline styles obrigatórios — pode usar `<style>` no `<head>`) |
| **Editor visual** | `templates/emails/editor.html` | Reuso direto: mesma palette + canvas + props inspector |
| **`LeadProspecto`** | `apps/comercial/leads/models.py` | Destino do form da LP |
| **`CampanhaTrafego.campanha_origem`** | `apps/marketing/campanhas/models.py` | Liga LP → campanha (UTM/parâmetro na URL) |
| **`DominioRemetente`** | `apps/marketing/emails/models.py` | Inspiração pro `LandingDominioCustom` (mesmo padrão de DNS verification) |

## Models propostos

### `LandingPage(TenantMixin)`

| Campo | Tipo | Função |
|---|---|---|
| `nome` | char(200) | interno |
| `slug` | slug(80) | parte da URL — unique por tenant |
| `dominio_custom` FK | nullable | apontar pra `LandingDominioCustom` quando o tenant tem domínio próprio |
| `status` | choice | rascunho / publicada / arquivada |
| `config_json` | jsonb | globais visuais (largura, cor_fundo, fonte) — formato igual ao TemplateEmail |
| `blocos_json` | jsonb | array de blocos (mesma estrutura do renderer email) |
| `html_compilado` | text | cache do render |
| `seo_title` | char(200) | `<title>` |
| `seo_description` | char(300) | meta description |
| `og_image` | ImageField | OpenGraph |
| `pixels` | jsonb | `{google_analytics: 'G-XXX', meta_pixel: '...', tiktok_pixel: '...'}` |
| `form_config` | jsonb | campos do form (nome, telefone, email obrigatórios?), texto do botão, URL de redirect pós-submit |
| `campanha_padrao` FK CampanhaTrafego | nullable | LP sem UTM ainda atribui essa campanha |
| `criado_por` FK User | | auditoria |
| `criado_em`, `atualizado_em`, `publicado_em` | datetime | |

**Constraint:** `unique(tenant, slug)`

### `LandingDominioCustom(TenantMixin)`

Mesmo padrão do `DominioRemetente`, mas pra serving HTTP da LP (não email).

| Campo | Tipo | Função |
|---|---|---|
| `dominio` | char(255) | `promo.meuprovedor.com.br` |
| `status` | choice | pendente_dns / validando / verificado / falhou |
| `registros_dns` | jsonb | 1 CNAME (`promo.meuprovedor.com.br → page.hubtrix.com.br`) ou A record |
| `ssl_status` | choice | pendente / emitido / falhou (Let's Encrypt) |
| `ssl_expira_em` | datetime | renovação automática a 30d |
| `validado_em`, `ultima_verificacao`, `falha_motivo` | | mesmo padrão DominioRemetente |

### `LandingSubmissao(TenantMixin)`

Cada submissão do form da LP vira lead. Salvamos a submissão crua pra debug/duplicação.

| Campo | Tipo | Função |
|---|---|---|
| `landing` FK | | LP que originou |
| `lead` FK LeadProspecto | nullable | criado automaticamente |
| `dados_form` | jsonb | payload completo do form |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` | char | capturados da URL |
| `ip_origem` | char | rastreio |
| `user_agent` | char | rastreio |
| `referrer` | text | URL anterior |
| `enviado_em` | datetime | |

## Roteamento HTTP

### MVP — subdomínio único do Hubtrix

```
https://page.hubtrix.com.br/<tenant_slug>/<landing_slug>/
```

- Wildcard SSL já existente (Let's Encrypt no Caddy)
- Sem custo adicional de DNS por tenant
- Tenant vê URL feia, mas funciona pra começar

### V2 — domínio personalizado

```
https://promo.meuprovedor.com.br/
```

Tenant cadastra `LandingDominioCustom`:
1. Hubtrix mostra o CNAME a configurar (`promo.meuprovedor.com.br CNAME page.hubtrix.com.br`)
2. Tenant configura no DNS dele (Cloudflare/Registro.br)
3. Hubtrix faz `dig` periódico — quando o CNAME bate, marca `verificado`
4. **Caddy** (reverse proxy) gera certificado Let's Encrypt automaticamente via ACME — sem intervenção manual
5. LP atende pelo domínio custom

Custo: configurar Caddy + on-demand TLS apontado pra arquivo dinâmico de hosts autorizados.

## Fluxo UX

1. Tenant entra em `/marketing/landing-pages/` → clica "Criar LP"
2. Escolhe **template base** (sistema oferece 3-5 templates prontos por categoria: captura simples, oferta de plano, evento, indicação)
3. Vai pro editor (mesmo do email, com 1-2 blocos extras: `form`, `hero`)
4. Edita textos, troca cores, adiciona/remove blocos
5. Configura form (quais campos, validações)
6. Configura SEO + pixels
7. Define URL: `/p/promo-fibra-1gb/` (slug)
8. Vincula a uma `CampanhaTrafego` (opcional — pra atribuir leads automaticamente)
9. Publica → URL fica `https://page.hubtrix.com.br/<tenant>/promo-fibra-1gb/`
10. Tenant pega URL e usa em Google Ads / Meta Ads / link bio Instagram

## Captura → Lead

```
Form submetido
   ↓
View pública valida + dedupe (mesmo telefone na última hora = atualiza, não cria duplicado)
   ↓
cria LeadProspecto:
  - nome, telefone, email do form
  - origem='landing_page'
  - campanha_origem=landing.campanha_padrao (se UTM presente, sobrescreve por match na CampanhaTrafego)
  - dados_custom={landing_id, landing_slug, utm_*, referrer, dados_form_extras}
   ↓
cria LandingSubmissao
   ↓
dispara signal lead_criado → engine de automação (regras de boas-vindas etc.)
   ↓
redireciona pra URL de obrigado configurada (ou exibe msg inline)
```

## Blocos novos pra LP

| Bloco | Função |
|---|---|
| `hero` | título + subtítulo + imagem de fundo + CTA proeminente |
| `form` | renderiza formulário com campos configuráveis. Submete via fetch + valida no servidor |
| `video` | embed YouTube/Vimeo responsivo |
| `faq` | accordion de perguntas/respostas |
| `prova_social` | logos/contadores ("Mais de 5.000 clientes") |
| `mapa` | embed do Google Maps (área de cobertura do ISP) |

Os 12 blocos atuais de email continuam funcionando (texto, imagem, botão, etc.) — só perdem `cabecalho` que vira `hero`.

## SEO + Pixels

- **SEO:** `<title>`, `<meta description>`, `<meta og:*>`, `<link rel="canonical">`. Slug controla URL.
- **Pixels (configurável por LP):**
  - Google Analytics 4 (`G-XXX`)
  - Meta Pixel (`fbq('init', '...')`)
  - TikTok Pixel
  - Google Ads conversion tag (chamada após submit OK)
  - Custom (script tag arbitrário no `<head>`)

## Multi-tenancy + segurança

- Todas as queries da LP filtram `tenant=request_tenant` (via slug do path ou Host header)
- Submissões fazem rate-limit (max 5/min/IP por landing)
- Captcha invisível (hCaptcha ou Cloudflare Turnstile) se taxa de spam subir
- CORS configurado pra aceitar só do próprio domínio

## Estatística + dashboard

- **Por LP:** visitas (analytics), submissões, taxa de conversão, leads gerados, oportunidades, vendas (atribuição via Campanha)
- **Cohort/dia:** linha temporal de visitas + submissões
- **A/B test (v2):** duplicar LP, variar bloco, sistema distribui 50/50

## Fases de entrega

| Fase | Esforço | Entrega |
|---|---|---|
| **1 — MVP subdomínio** | 3-5 dias | Models, editor reusado, 3 templates base, form básico (nome/tel/email), publicar em `page.hubtrix.com.br/<tenant>/<slug>/`, leads chegando no CRM |
| **2 — Pixels + SEO + analytics** | 2 dias | Tracking GA4/Meta/Google Ads, A/B test, dashboard de visitas |
| **3 — Domínio personalizado** | 5-7 dias | Caddy on-demand TLS, modelo `LandingDominioCustom`, UI de verificação DNS, renovação automática |
| **4 — Blocos especializados** | 2-3 dias | Hero, FAQ, prova social, mapa de cobertura, vídeo |

## Integrações

| Sistema | Conexão |
|---|---|
| **Leads** | LP cria `LeadProspecto` direto |
| **Campanhas** | UTM da URL → `campanha_origem`; LP atrelada a campanha padrão |
| **Automações** | Signal `lead_criado(origem='landing_page')` dispara regra de boas-vindas |
| **Email** | Lead da LP recebe email automático com confirmação (template) |
| **Inbox** | Opcional: ao submeter, opa cria conversa no Inbox tipo "Lead via LP — aguardando contato" |
| **CRM** | Lead vira oportunidade no estágio inicial do pipeline configurado |

## Riscos

| Risco | Mitigação |
|---|---|
| Latência da LP afeta conversão | Render server-side cacheado (HTML pré-compilado) + CDN edge cache |
| Spam no form | rate-limit + captcha invisível |
| LP fora do ar = perde lead | health-check + alerta admin; redirect fallback pra WhatsApp |
| Tenant abandona LP publicada (URL fica órfã) | Após 90 dias sem visita, mover pra arquivada (UI mostra warning) |

## Decisões pendentes (precisa user)

1. **Editor visual:** reuso completo do editor de email ou cria editor próprio pra LP?
2. **Domínio personalizado:** entra na Fase 1 ou só Fase 3 (~1 semana extra)?
3. **Pixels:** todos os 4 padrão (GA/Meta/TikTok/Google Ads) ou começa só com GA + Meta?
4. **A/B test:** entra na Fase 2 ou fica pra V3 quando tiver dados de uso?
5. **Templates base do sistema:** quantos e quais categorias? (sugestão: 5 — captura simples, oferta de plano, evento, indicação, manutenção/aviso)
