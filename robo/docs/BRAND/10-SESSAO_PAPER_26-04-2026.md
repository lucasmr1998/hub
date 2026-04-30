# 10. Sessão Paper.design — Aprendizados e Inventário

**Data:** 26/04/2026
**Status:** 🟡 Pausado (limite semanal do Paper MCP atingido, reset em 7 dias)
**Responsável:** PMM + Copywriter + Tech Lead (futuro build)

---

## Objetivo da sessão

Construir a base visual do Hubtrix do zero usando **Paper.design via MCP**, com estética **editorial + marginalia** (anti cara-de-IA), gerando designs prontos para virar:
- Site comercial (hubtrix.com.br)
- Cards de redes sociais
- Carrosséis fixados (LinkedIn + Instagram)
- Logo
- Proposta comercial (redesign das 14 páginas existentes)

---

## Decisões tomadas

### 1. Estética
- **Editorial + marginalia.** Tipografia forte (Inter Tight) + detalhes desenhados à mão em **burnt sienna `#E76F51`**.
- **Anti cara-de-IA.** Sem gradiente roxo/rosa, sem astronauta 3D, sem AI sparkle.
- Inspiração: HubSpot, Kommo CRM. Direto, profissional, próximo.

### 2. Logo
- **Direção 01 escolhida:** wordmark puro `hubtrix` (tudo minúsculo).
- Inter Tight 800, tracking -0.02em.
- Outras 5 direções exploradas mantidas como referência (não usadas).

### 3. Paleta
- **Cobalto `#1D4ED8`** = ação (CTAs, links, foco). Não decoração.
- **Burnt sienna `#E76F51`** = assinatura editorial humana. Marginalia.
- **Tinta `#0B1220`** = texto principal. Substitui preto puro.
- Off-white `#F8FAFC`, borda `#E2E8F0`, grafite `#475569`.

### 4. Tipografia
- **Inter Tight** para display/títulos (700-800).
- **Inter** para corpo/UI (400-600).

### 5. Stack do site (proposta, não confirmada)
- Paper → export PNG/HTML → React/Tailwind → **Next.js + Vercel**.
- Decisão final adiada.

### 6. Estratégia de redes sociais
- **3 posts fixados** no perfil (LinkedIn + Instagram), padrão AIDA.
- **4 cards quadrados** (1080×1080), um por módulo (Comercial, Marketing, CS, Suporte).

---

## Inventário de artboards no Paper (~18 artboards)

Arquivo Paper: **"Hubtrix"** (página 1 + página "Branding")

### Site comercial
| Artboard | Status |
|----------|--------|
| Home (hero + módulos + prova + CTA) | ✅ Pronto |
| Produto (detalhe dos 4 módulos) | ✅ Pronto |
| Demo (formulário request-a-demo) | ✅ Pronto |

### Logos
| Artboard | Status |
|----------|--------|
| Logo Exploration (6 direções) | ✅ Pronto |
| Direção 01 escolhida (wordmark) | ✅ Definido |

### Cards de redes sociais (1080×1080)
| Artboard | Status |
|----------|--------|
| Card Comercial | ✅ Pronto |
| Card Marketing | ✅ Pronto |
| Card CS | ✅ Pronto |
| Card Suporte | ✅ Pronto |

### Carrosséis fixados (10 slides total entre 3 carrosséis)
| Artboard | Status |
|----------|--------|
| Carrossel 1 — capa + 3-4 slides | ✅ Pronto |
| Carrossel 2 — capa + 3-4 slides | ✅ Pronto |
| Carrossel 3 — capa + 2-3 slides | ✅ Pronto |

### Proposta comercial (1920×1080, 14 páginas total)
| Artboard | Status |
|----------|--------|
| Página 1 — capa | ✅ Pronto |
| Página 2 — problema | ✅ Pronto |
| Página 3 — solução | ✅ Pronto |
| Página 4 — módulos | ✅ Pronto |
| Páginas 5-14 | ⏳ Faltam |

---

## Aprendizados sobre o Paper.design

### O que funcionou
- **MCP HTTP local** (`http://127.0.0.1:29979/mcp`) integrou bem com Claude via `.mcp.json` no root do projeto.
- 21 ferramentas disponíveis (criar artboard, editar elementos, layout, etc.).
- Iteração rápida sobre tipografia editorial e composição.
- Boa resposta a comandos de marginalia (traços de mão livre em burnt sienna).

### Limitações encontradas
- **Limite semanal** do Paper MCP atingido 2 vezes na sessão. Segunda vez gera reset de 7 dias. Planejar uso em batch.
- Paper só faz **design estático**. Para animação, usar Canva (mas via PNG export, não AI generate).
- **Canva AI generate ≠ Paper editorial.** Os templates do Canva têm viés visual próprio. Caminho correto: Paper → exportar PNG → Canva `upload-asset-from-url` → animar.
- Imagens grandes acumuladas na sessão estouram limite de 2000px em conversas longas. Iniciar nova sessão se for trabalhar muito visual.

### Bugs/ajustes ao longo da sessão
- ERP pills com texto quebrando (`HubSof/t`) → resolvido com `flexShrink: 0` + `whiteSpace: nowrap`.
- Marginalia sobrepondo subtítulo no hero → reposicionada (top: 670, left: 80).
- Capa de proposta com hierarquia tipográfica fraca → escalado o H1 para 96px.

---

## Pendências (quando Paper resetar em 7 dias)

### Prioridade alta
- [ ] Completar 10 páginas restantes da proposta comercial (páginas 5-14)
- [ ] Criar artboard "Brand System" no Paper consolidando tudo
- [ ] Versão mobile da Home, Produto, Demo

### Prioridade média
- [ ] Página de Cases
- [ ] Página de Preços completa
- [ ] Template de e-mail
- [ ] Template de one-pager

### Prioridade baixa
- [ ] Capa de deck institucional
- [ ] Capa de relatório mensal

---

## Substituir conteúdo placeholder antes de publicar

Os designs no Paper usam dados fictícios. Antes de virar produção:
- [ ] Citação "Rafael Santos" → depoimento real de cliente
- [ ] Números +18% / -64% / 7→1 → métricas reais validadas
- [ ] Preços R$497 / R$997 / R$1.497 → preços oficiais (CFO)
- [ ] Logos de clientes reais com autorização

---

## Próximos passos imediatos (sem depender do Paper)

1. **Atualizar o backlog do site** (`robo/docs/context/tarefas/backlog/site_comercial_hubtrix_17-04-2026.md`) com decisões da sessão. ✅ feito junto com este doc
2. **Decidir stack do site** (Next.js + Vercel é proposta atual, falta confirmar com Tech Lead).
3. **Quando Paper voltar:** completar as 10 páginas da proposta + brand system artboard.

---

## Referência cruzada

- [08-BRANDBOOK.md](08-BRANDBOOK.md) — Sistema visual consolidado
- [09-GUIA_APLICACAO.md](09-GUIA_APLICACAO.md) — Como aplicar em cada canal
- [Backlog do site](../context/tarefas/backlog/site_comercial_hubtrix_17-04-2026.md) — Tarefa ativa
