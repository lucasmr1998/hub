---
titulo: "Sessão 28/04: plataforma na paleta v2 + 6 posts feed + brief da proposta comercial"
data: 28/04/2026
participantes: ["Lucas", "Claude (Tech Lead + Copywriter + PMM)"]
decisoes_chave: [
  "plataforma_alinhada_paleta_v2_em_4_fases",
  "6_posts_feed_prontos_no_paper",
  "proposta_comercial_estrutura_aprovada_12_paginas",
  "4_dores_gerenciais_4_beneficios_pareados",
  "layout_b_2_paginas_dor_solucao_separadas"
]
---

# Sessão 28/04 — Paleta v2 na plataforma + 6 posts + brief da proposta

**Status:** 🟢 Plataforma migrada · 🟢 Posts criados · 🟡 Proposta com estrutura+copy aprovada, falta build no Paper

---

## 1. Plataforma Hubtrix migrada pra paleta v2

**4 fases executadas + Django check limpo:**

### Fase 1 — `templates/layouts/base.html` (tokens centrais)

| Var | Antes (indigo) | Depois (tinta) |
|-----|----------------|----------------|
| `--color-text` | `#0f172a` | **`#252020`** |
| `--color-primary` | `#4f46e5` | **`#252020`** |
| `--color-primary-hover` | `#4338ca` | **`#1A1717`** |
| `--color-primary-soft` | `#eef2ff` | **`#f8fafc`** |
| `--color-primary-text` | `#4338ca` | **`#252020`** |
| `--sidebar-bg` | `#1e293b` | **`#252020`** |
| `--sidebar-bg-hover` | `#2d3f55` | **`#1A1717`** |
| `--sidebar-bg-active` | `#3b4f6b` | **`#3a3434`** |

**Vars novas adicionadas:**
- `--color-accent: #E76F51` (sienna)
- `--color-accent-hover: #D85A3F`
- `--color-accent-soft: #FED7AA`

### Fase 2 — `apps/sistema/static/sistema/css/dashboard.css`

Vars do legado alinhadas com paleta v2:
- `--primary: #252020` (era cobalto `#3b82f6`)
- `--primary-dark: #1A1717`
- `--primary-light: #FED7AA` (sienna soft)
- `--text-main: #252020`

### Fase 3+4 — Templates com cores hardcoded

**`apps/dashboard/templates/dashboard/analise_atendimentos.html`:**
- 25+ hardcodes substituídos (gradientes purple/blue/red/green)
- Paleta JS de chart agora: tinta + sienna + grafites + neutros
- 8 cards de métricas com gradients trocados por sólidos da paleta v2

**`apps/dashboard/templates/dashboard/dashboard.html`:**
- 12 hardcodes (gradientes purple `#667eea→#764ba2`, etc.) → tinta sólido ou cor semântica
- Body bg purple → off-white

### Mapeamento aplicado em todo sistema

| Cor antiga | Nova |
|-----------|------|
| `#4f46e5` indigo / `#1F3D59` navy / `#3b82f6` cobalto / `#667eea` purple | **`#252020`** tinta |
| `#27ae60` / `#2ecc71` / `#56ab2f` (verdes) | `#16a34a` success oficial |
| `#f39c12` / `#e67e22` (ámbar) | `#d97706` warning oficial |
| `#e74c3c` / `#c0392b` (vermelhos) | `#dc2626` danger oficial |
| `#9b59b6` / `#f093fb` (roxo/rosa "destaque") | `#E76F51` sienna |
| `#3498db` (azul info) | `#252020` tinta |

### Validação
`python manage.py check --settings=gerenciador_vendas.settings_local` → limpo, só warning pré-existente de staticfiles.

### Próximas frentes (dívida menor)
- Outros templates com hardcoded em apps específicos (ainda não auditados)
- `dashboard.css` ainda duplica vars (poderia usar `var(--color-*)` direto). Refactor opcional.

---

## 2. Posts do feed Instagram — 6 prontos no Paper

Conta nova "hubtrix" (lowercase). Página: Page 1.

| # | Artboard | Bg dominante | Status |
|---|----------|--------------|--------|
| 1 | Post IA - 5 etapas | branco (cards tinta + 5ª etapa sienna) | ✅ atualizado pra paleta v2 |
| 2 | Post Case - 284k | **sienna pleno** | ✅ criado nova paleta v2 |
| 3 | Post Demo CTA | tinta | ✅ criado, copy: "15 minutos pra ver o Hubtrix funcionando de verdade" (palavra "funcionando" sienna) |
| 4 | Post 3 problemas | **tinta** | ✅ criado (cards off-white sobre tinta) |
| 5 | Post Conecta não substitui | branco | ✅ criado (visual ERPs↓Hubtrix camadas), H1 "Sem migrar. Sem trocar. Só ligar." |
| 6 | Post Manifesto 2027 | sienna pleno | ✅ criado, H1 "Em 2027, o provedor que dominar a rua não é o que tem mais cabo." |

### Distribuição cromática do feed (3×2)
```
Linha 1:  [W] [S] [T]    5 etapas | Case | Demo
Linha 2:  [T] [W] [S]    Problemas | Conecta | Manifesto
```
Sem adjacentes iguais. 2 brancos · 2 tintas · 2 siennas. Ritmo balanceado.

### Avatar Instagram
Disponível em `/design-system/brand/instagram/` com download SVG/PNG 1080×1080. Dot sienna posicionado em (820,820) r=70 pra não cortar no crop circular do IG.

---

## 3. Proposta Comercial — brief aprovado, build pendente

Reescrita da proposta em PDF (14 páginas legacy em paleta cobalto/navy → 12 páginas em paleta v2).

### Estrutura aprovada (12 páginas)

| # | Página | O que tem |
|---|--------|-----------|
| 1 | **Capa** | "Proposta · [Cliente]" + tagline "Vende mais. Perde menos. Fideliza sempre." Bg tinta, ícone "h" sienna |
| 2 | **Em 30 segundos** | 3 números + 1 frase. Pra quem só lê 1 página |
| 3 | **O problema** | 4 dores em bg tinta, dramatização |
| 4 | **O que muda com Hubtrix** | 4 benefícios pareados em bg branco, alívio |
| 5 | **Como funciona** | 4 módulos (Atendimento IA, CRM, Marketing, CS) num diagrama de fluxo |
| 6 | **Caso real** | "Provedor regional 30k assinantes" + 4 números + quote |
| 7 | **Diferenciais** | 3 (não 6): integração ERP nativa, IA treinada pra ISP, conecta-não-substitui |
| 8 | **Planos** | Tabela única comparativa Starter/Start/Pro |
| 9 | **Custos variáveis + Setup** | Tabela comercial + Mkt + CS + Setup |
| 10 | **Simulação pra [Cliente]** | Calculadora baseada no perfil dele |
| 11 | **Implantação** | Cronograma 14 dias |
| 12 | **Garantias** + **Próximos passos** | Sem fidelidade · Exit policy · LGPD + 4 passos + contato |

### 4 Dores (gerenciais, B2B) com 4 Benefícios pareados

| Dor (página 3) | Benefício (página 4) |
|----------------|----------------------|
| **Vender vira gargalo de gente.** | A IA fecha venda sozinha. Time vira backoffice estratégico. |
| **Time comercial cresce mais que receita.** | Corte de 75% no time. Mesmo volume. R$284k/ano de volta no caixa. |
| **Da venda à ativação leva 48h.** | Da venda ao ERP em 4h. Sem retrabalho, sem ligação. |
| **Cliente cancela e você descobre tarde demais.** | IA detecta risco antes do cliente saber. Clube fideliza no automático. |

### Layout escolhido

**Opção B — 2 páginas separadas (dor → solução)**, em vez de 1 página densa. Cria narrativa editorial: dor primeiro (bg tinta, dramatização), solução depois (bg branco, alívio).

### Formato/dimensões
- Artboards 1920×1080 no Paper
- Paleta v2: tinta `#252020` + sienna `#E76F51` + branco
- Logo: ícone "h" tinta + dot sienna + wordmark
- Tipografia: Inter Tight 800 nos títulos + Inter no corpo

### Pendências de execução

- [ ] Criar 12 artboards no Paper.design (conta nova "hubtrix")
- [ ] Validar copy + visual com usuário antes de exportar
- [ ] Exportar PNG/PDF de cada página
- [ ] Substituir `[Cliente]` por nome real (Nuvyon Telecom era exemplo legacy — confirmar se é prospect real ou substituir)

---

## 4. Decisões pendentes pra próxima sessão

1. **Confirmar copy das 4 dores e 4 benefícios** já refinada (acima)
2. **Ajustar conteúdo página 5 (4 módulos):** Atendimento IA, CRM, Marketing, CS — descrição curta de cada
3. **Página 7 (3 diferenciais):** copy curta de cada (integração nativa, IA pra ISP, conecta-não-substitui)
4. **Página 8 (planos):** copy clean dos 3 planos em tabela, sem repetir "Tudo do Starter +" 3x — talvez visual de tabela com checkmark/cross
5. **Página 12 (garantias):** copy dos 4 itens (sem fidelidade, exit policy, LGPD, suporte)

---

## 5. Source of truth pra próxima sessão

- Brandbook v2: [robo/docs/BRAND/08-BRANDBOOK.md](robo/docs/BRAND/08-BRANDBOOK.md)
- Guia aplicação v2: [robo/docs/BRAND/09-GUIA_APLICACAO.md](robo/docs/BRAND/09-GUIA_APLICACAO.md)
- Site oficial: [site/index_preto.html](site/index_preto.html)
- Páginas DS Brand: `/design-system/brand/*`
- Sessão Paper passada: [robo/docs/BRAND/10-SESSAO_PAPER_26-04-2026.md](robo/docs/BRAND/10-SESSAO_PAPER_26-04-2026.md)
- Sessão Brand 27/04: [brand_design_system_27-04-2026.md](robo/docs/context/reunioes/brand_design_system_27-04-2026.md)
- Case oficial: [robo/docs/GTM/cases/case_provedor_regional_30k.md](robo/docs/GTM/cases/case_provedor_regional_30k.md)
- Proposta legacy referência: PDF 14 páginas anexado pelo usuário em 28/04
