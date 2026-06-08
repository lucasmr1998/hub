---
titulo: "Sessão Brand Design System — paleta nova, páginas DS, downloads, Instagram"
data: 27/04/2026
participantes: ["Lucas", "Claude (Tech Lead + PMM + PM)"]
decisoes_chave: ["paleta_oficial_preto_laranja_branco", "cobalto_aposentado", "tinta_atualizada_252020", "ds_brand_completo", "ig_simulacao_com_download"]
---

# Sessão Brand Design System — 27/04/2026

**Duração:** sessão longa (continuação da sessão de 26/04 sobre brand)
**Status final:** 🟢 Brand system v1 completo no design system + 2 sites prontos pra escolha

---

## Contexto

Continuação direta da sessão Paper.design de 26/04/2026 (registrada em `BRAND/10-SESSAO_PAPER_26-04-2026.md`). Naquela ficaram definidas as direções iniciais de marca (logo direção 1, paleta cobalto + burnt sienna). Hoje a paleta foi reavaliada visualmente e mudada significativamente.

---

## Decisões principais

### 1. Paleta oficial mudou: cobalto APOSENTADO

**Antes:** cobalto `#1D4ED8` + burnt sienna `#E76F51` + tinta `#0B1220` + neutros
**Depois:** **tinta `#252020` + burnt sienna `#E76F51` + branco** (3 cores oficiais)

**Por que:**
- Cobalto azul é a cor de qualquer SaaS B2B (Pipedrive, RD, HubSpot). Não diferenciava.
- Anti-cara-de-IA radical: sem azul saturado.
- Burnt sienna assume protagonismo total como única cor "viva".
- Marca passa a ser descritível como "a do laranja queimado e preto" — única no mercado.

**O que foi removido da paleta:**
- Cobalto base `#1D4ED8`, hover `#1E40AF`, suave `#DBEAFE`
- Azul info `#3B82F6`

**O que ficou:**
- 3 cores principais: tinta + sienna + branco
- 3 neutros de apoio: grafite (`#475569`), off-white (`#F8FAFC`), borda (`#E2E8F0`)
- 3 status (verde/amarelo/vermelho — inalterados)

### 2. Tinta atualizada: `#0B1220` → `#252020`

Usuário testou visualmente `rgb(37,32,32)` = `#252020` e validou que ficou melhor que o tinta antigo `#0B1220`. **Mais quente** (puxa pra marrom escuro), bate melhor com burnt sienna na linha editorial.

### 3. Direções do logo confirmadas

Da sessão Paper de 26/04, **2 direções viraram oficiais:**
- **Direção 01 — Wordmark puro `hubtrix`** (Inter Tight 800)
- **Direção 04 — Quadrado H** (h branco em quadrado tinta + dot sienna no canto inferior direito)

**Direções 02 (H matriz) e 03 (Pontos conectados) foram descartadas** — não correspondem à direção editorial.

### 4. Site oficial = variante preto+sienna+branco

`site/index_preto.html` virou a versão de referência. `site/index.html` (variante cobalto) fica de histórico/comparação.

---

## Entregas concretas

### Páginas do design system criadas/atualizadas

Todas em `templates/design_system_brand_*.html` + URLs em `gerenciador_vendas/urls.py`:

| Página | URL | Status |
|--------|-----|--------|
| Overview (8 cards) | `/design-system/brand/` | ✅ |
| Logo | `/design-system/brand/logo/` | ✅ Reescrita com paleta nova + downloads SVG/PNG |
| Cores | `/design-system/brand/cores/` | ✅ Reescrita |
| Tipografia | `/design-system/brand/tipografia/` | ✅ |
| **Voz e tom** | `/design-system/brand/voz-e-tom/` | ✅ Nova |
| **Marginalia** | `/design-system/brand/marginalia/` | ✅ Nova |
| **Aplicações** | `/design-system/brand/aplicacoes/` | ✅ Nova (8 mock-ups) |
| **Instagram** | `/design-system/brand/instagram/` | ✅ Nova (perfil + 6 posts + downloads) |
| **Assinatura de e-mail** | `/design-system/brand/assinatura-email/` | ✅ Nova (editor + copy/download HTML) |

### Sites em código

- `site/index.html` — variante cobalto (legado, histórico)
- `site/index_preto.html` — **variante oficial** (preto + sienna + branco)
- Estrutura final: Hero → Problemas (off-white) → Módulos (white) → Integrações (off-white) → Case (white) → CTA (tinta) → Footer (white)
- FAQ removida; Módulos reordenados; ícones nos cards de problema (Bootstrap Icons em sienna pleno)
- Logo em todos os lugares: ícone "h" branco em quadrado tinta + dot sienna

### Sistema de downloads no DS

**Logo (`/design-system/brand/logo/`):**
- 7 variações disponíveis
- Botão "↓ SVG" em cada card → SVG vetorial limpo
- Botão "PNG" em cada card → bitmap 4x via html2canvas

**Instagram (`/design-system/brand/instagram/`):**
- "↓ PNG" individual em cada post (1080×1080)
- "Baixar todos (6)" em batch
- Avatar com download SVG + PNG (1080×1080) — dot posicionado em (820,820) com r=70 pra não cortar no crop circular do IG

**Assinatura de e-mail:**
- Editor de nome/cargo/telefone/email com preview ao vivo
- "Copiar HTML" (clipboard + fallback execCommand)
- "Baixar .html" (Blob + download tag)
- Instruções pra Gmail e Outlook

### Tech notes

- **html2canvas** via CDN pra capturar elementos como PNG escalados
- **Canvas API direto** pra gerar avatar (mais limpo que html2canvas pra elementos simples)
- **SVG inline gerado em JS** — texto Inter Tight como `<text>`, fundo como `<rect>`, dot como `<circle>`
- Todos os botões de download usam padrão `appendChild` + `setTimeout` revoke pra compatibilidade entre browsers

---

## Pendências do brandbook ainda não propagadas

Atualizei as **páginas DS** com a paleta nova. Mas estes arquivos ainda têm cobalto/`#0B1220`:

- [ ] `robo/docs/BRAND/08-BRANDBOOK.md` — atualizar paleta principal
- [ ] `robo/docs/BRAND/09-GUIA_APLICACAO.md` — atualizar uso de cores por canal
- [ ] `robo/docs/BRAND/11-HOME_SPEC_26-04-2026.md` — refletir paleta final (estava com cobalto)
- [ ] `templates/layouts/base.html` — tokens CSS globais (`--color-primary` etc) — propagaria pro sistema inteiro, alto impacto, validar antes
- [ ] Memória do projeto `project_brand_hubtrix.md` — atualizar com decisão de cobalto aposentado

Não fiz tokens CSS globais ainda porque mudaria o sistema inteiro (botões, links, foco, dashboards). Decisão de quando adotar é separada.

### Materiais que precisam refazer com paleta nova (ficaram com cobalto)

- 5 emails no Paper (boas-vindas + 4 módulos)
- Post IA "5 etapas" no Paper
- Outros artboards no Paper

Refazer quando o limite do Paper resetar (~4 dias).

---

## Aprendizados visuais

1. **Cobalto sólido bonito ≠ cobalto certo pra marca.** O brandbook pode estar tecnicamente "ok" e a marca ainda não ter alma. Paleta restrita força criatividade.

2. **3 cores é melhor que 5.** Paleta de 5+ cores (mesmo "completa") gera ambiguidade — não fica claro qual é "a cor da marca". 3 elimina a dúvida.

3. **Burnt sienna funciona como única cor "viva"** desde que não compita com outras. Cobalto roubava o protagonismo dela.

4. **Tinta tem que ser warm.** `#0B1220` (cool blue) virou `#252020` (warm brown-black). Pequena mudança de hex, grande mudança de sensação. Aproxima do magazine/livro, afasta do tech-bro.

5. **Detalhe do dot sienna no logo é assinatura.** Ele resolveu o impasse entre "logo só wordmark" vs "logo com símbolo" — vira o ponto de identificação único.

6. **Crop circular do Instagram corta cantos.** PNG 1080×1080 com elementos no canto inferior direito ficam cortados ao virarem foto de perfil. Calcular distância do centro pra garantir margem.

---

## Próximas frentes (em standby)

1. **Cards sociais 1080×1080 por módulo** (4 PNGs separados — Atendimento/CRM/Fidelização/Automação)
2. **Carrosséis fixados** (3 carrosséis × 5 slides = 15 PNGs)
3. **Refazer no Paper** quando o limite resetar (Home, emails, posts)
4. **Propagar tokens CSS globais** no sistema (alto impacto, alinhar antes)
5. **Atualizar markdown do brandbook** (`08-BRANDBOOK.md`, `09-GUIA_APLICACAO.md`)
6. **Site oficial em produção** (decidir stack: Next.js + Tailwind + Vercel é a proposta)

---

## Referência cruzada

- [BRAND/08-BRANDBOOK.md](../../BRAND/08-BRANDBOOK.md) — brandbook (paleta antiga, atualizar)
- [BRAND/10-SESSAO_PAPER_26-04-2026.md](../../BRAND/10-SESSAO_PAPER_26-04-2026.md) — sessão anterior
- [BRAND/11-HOME_SPEC_26-04-2026.md](../../BRAND/11-HOME_SPEC_26-04-2026.md) — spec da Home (refletir paleta nova)
- `site/index.html` — variante cobalto (histórico)
- `site/index_preto.html` — **variante oficial**
- `templates/design_system_brand_*.html` — 9 páginas DS Brand
