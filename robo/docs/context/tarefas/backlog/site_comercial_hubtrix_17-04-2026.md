---
name: "Site comercial público do Hubtrix + SEO + request-a-demo"
description: "Criar presença comercial pública pra captar ISPs interessados no topo do funil"
prioridade: "🟡 Média"
responsavel: "Marketing + Tech"
---

# Site comercial do Hubtrix — 17/04/2026

**Data:** 17/04/2026
**Última atualização:** 26/04/2026
**Responsável:** Marketing + Tech
**Prioridade:** 🟡 Média
**Status:** 🟡 Em andamento — designs prontos no Paper, aguardando build em código

---

## Atualização 26/04/2026 — sessão Paper.design

Sessão de design no Paper.design via MCP gerou base visual completa do Hubtrix. Detalhes em [BRAND/10-SESSAO_PAPER_26-04-2026.md](../../../BRAND/10-SESSAO_PAPER_26-04-2026.md).

**Decisões da sessão:**
- Estética **editorial + marginalia** (anti cara-de-IA). Inspiração HubSpot/Kommo
- Logo **direção 01** (wordmark `hubtrix` em Inter Tight 800)
- Paleta **cobalto `#1D4ED8` + burnt sienna `#E76F51`**
- Tipografia **Inter Tight + Inter**
- Stack proposta (não confirmada): **Paper → React/Tailwind → Next.js + Vercel**

**Designs prontos no Paper (~18 artboards):**
- Site: Home, Produto, Demo
- Logo: 6 direções exploradas (escolhida direção 01)
- Redes sociais: 4 cards quadrados (Comercial, Marketing, CS, Suporte) + 3 carrosséis fixados (10 slides)
- Proposta: 4 das 14 páginas

**Brand System consolidado em Markdown:**
- [BRAND/08-BRANDBOOK.md](../../../BRAND/08-BRANDBOOK.md)
- [BRAND/09-GUIA_APLICACAO.md](../../../BRAND/09-GUIA_APLICACAO.md)

**Bloqueio atual:** Paper MCP atingiu limite semanal. Reset em 7 dias.

---

## Atualização 26/04/2026 (parte 2) — refino da Home

Após revisar o design da Home no Paper, dois ajustes:

### 1. Remover bloco de Preços da Home
Preços é meio/fundo de funil. Sai da Home, vai pra página dedicada `/precos`.
No lugar, ou um CTA "Ver preços →" no fim da página, ou só o CTA de demo.

### 2. Reposicionar o hero (categoria-first, IA como substância)
Hero antigo ("Pare de perder lead no WhatsApp do seu provedor") reduzia o produto a 1 dos 4 módulos. Novo hero cobre o produto inteiro e usa a tagline na primeira dobra.

**H1 (definitivo):**
> A plataforma do provedor que vende mais, perde menos e fideliza sempre.

**Subtítulo (definitivo):**
> IA que qualifica lead, organiza CRM e segura cliente. Integrada a todos os seus sistemas.

**Por que:**
- Tagline vira H1 — fixa a marca e cobre os 3 pilares (vender/CS/atendimento)
- "Plataforma do provedor" estabelece categoria sem buzzword ("hub de tecnologia" estava redundante)
- Subtítulo coloca IA como substância (não decoração visual — coerente com o anti-cara-de-IA)
- Três verbos concretos no subtítulo (qualifica lead / organiza CRM / segura cliente) são mais memoráveis que adjetivos
- "Integrada a todos os seus sistemas" cobre ERP (HubSoft, SGP, MK-Auth) + ferramentas de chat + integrações futuras, mantendo o efeito de matar a objeção #1 (não vai substituir o que ele já tem)

**Marginalia:** sublinhar "fideliza sempre" em burnt sienna (verbo mais raro = mais memorável).

**Aplicar quando Paper resetar (em ~6 dias) ou quando upgradar/deslogar.**

### 3. Remover logos e nomes de clientes (sem autorização)
- Remover bloco "PROVEDORES QUE RODAM NO HUBTRIX" (FATEPI, Megalink, Nuvyon, Gigamax)
- Anonimizar case "Rafael Santos / FATEPI Internet" → "Diretor comercial, provedor regional ~10k assinantes"
- Substituir bloco de logos por texto genérico: **"Provedores em 4 estados já rodam no Hubtrix"** (sem nomear)
- **Pendência:** colher autorização escrita de FATEPI/Megalink/Nuvyon/Gigamax pra reativar logos e cases nominais

### 4. Substituir bloco de Preços (removido) por Integrações + FAQ
Fluxo final da Home:
```
Hero → Problemas (3 cards) → Módulos (4 cards) → Case anonimizado
→ [NOVO] Integrações (logos de ERP/canais)
→ [NOVO] FAQ (5 perguntas)
→ CTA final
```

**Bloco Integrações:**
- Headline: "Conecta no que você já usa."
- Subtítulo: "Sem migração, sem mexer no seu ERP, sem trocar canal de atendimento."
- Logos: HubSoft, SGP, MK-Auth, IXC, WhatsApp, Instagram, Facebook, Telegram

**Bloco FAQ (5 perguntas):**
1. Quanto tempo pra ativar? → 15 min, sem migração
2. Funciona com meu ERP? → Sim (lista principais)
3. Preciso treinar a equipe? → Onboarding incluso, 1 sessão
4. Meus dados ficam onde? → LGPD, servidor BR
5. E se eu não gostar? → Sem fidelidade, sai quando quiser

### 5. Reframe do bloco de Módulos (foco em IA que vende, não chat unificado)
Card "Atendimento" estava vendendo Inbox ("Todo WhatsApp, chat do site e Instagram num lugar só") — não é diferenciador. Reposicionar pra **IA que conversa, qualifica e vende** (que é o que o módulo Atendimento realmente é no produto: engine, sessões, recontato).

**Card 1 — Atendimento**
> 01 — ATENDIMENTO
> A IA que conversa, qualifica e vende pelo seu time.
> Conecta na plataforma de atendimento que seu provedor já usa. A IA treinada pra ISP responde WhatsApp, qualifica lead com 8 perguntas, agenda visita técnica e recontata sozinho quando o cliente some. Seu atendente só recebe quem tá pronto pra fechar.

**Princípio (consistente com toda a Home):** Hubtrix é camada de IA que se pluga. **Não substitui** ERP, **não substitui** plataforma de atendimento. Conecta no que o provedor já tem.

**Card 2 — CRM Comercial** (mantém)
> Pipeline que entende viabilidade, CTO e plano combo.

**Card 3 — Fidelização** (mantém)
> Clube, NPS e indicação que trazem cliente todo mês.

**Card 4 — Automação** (mantém, afina copy)
> Editor visual de fluxos com IA treinada no seu provedor.

**Inbox sai dos 4 cards principais.** Vira menção curta dentro do Card 1 ("Quando a IA precisa subir pro humano, todos os canais caem no mesmo Inbox") ou linha no bloco de Integrações.

**Mapeamento dos 4 cards com o subtítulo do hero:**
- Card 1 (IA que vende) ↔ "qualifica lead"
- Card 2 (CRM) ↔ "organiza CRM"
- Card 3 (Fidelização) ↔ "segura cliente"
- Card 4 (Automação) = transversal, conecta os 3

---

## Descrição

O domínio `hubtrix.com.br` está reservado mas não há site público. Toda descoberta hoje depende de indicação de cliente existente ou outbound direto do time. Sem site, não há captação inbound organizada.

Surgiu no detalhamento do estágio 1 de A1 (Contratação — Descoberta e avaliação) em `PRODUTO/VISAO.md`.

---

## Tarefas

### Design (Paper.design)
- [x] Definir estética (editorial + marginalia, anti cara-de-IA)
- [x] Definir paleta e tipografia
- [x] Logo (direção 01 escolhida)
- [x] Home, Produto, Demo desenhados no Paper
- [x] 4 cards de redes sociais (1080×1080)
- [x] 3 carrosséis fixados (LinkedIn + Instagram)
- [x] Proposta comercial: piloto de 4 páginas (faltam 10)
- [ ] Versão mobile da Home, Produto, Demo (quando Paper resetar)
- [ ] Página de Cases
- [ ] Página de Preços completa
- [ ] Brand System consolidado em artboard no Paper

### Conteúdo
- [x] Definir estrutura mínima do site (landing, pricing, cases, docs, blog, request-a-demo)
- [ ] Copy alinhado com mensagens-chave já definidas em GTM/06-MENSAGENS_CHAVE.md
- [ ] Substituir placeholders (depoimento Rafael Santos, números +18%/-64%/7→1, preços) por dados reais

### Build / código
- [ ] Confirmar stack (proposta: Next.js + Tailwind + Vercel)
- [ ] Exportar designs do Paper para HTML/React
- [ ] Hospedagem definida
- [ ] Deploy inicial com 1 página de landing como MVP
- [ ] Integração "request-a-demo" com o próprio Hubtrix (ver tarefa de dogfooding)
- [ ] SEO básico (sitemap, meta tags, structured data)
- [ ] Favicon a partir do "h" do wordmark

### Marketing
- [ ] Análise de palavras-chave pra ISPs (concorrentes, intenção de compra)
- [ ] Conteúdo de topo de funil (blog ou YouTube) a partir de M+1
- [ ] Publicar 4 cards de módulo no LinkedIn + Instagram
- [ ] Fixar 3 carrosséis no perfil (LinkedIn + Instagram)

---

## Impacto esperado

- Captação inbound mensurável (MQLs por canal)
- Redução de dependência de outbound direto
- Narrativa pública do produto (mercado enxergar o Hubtrix como categoria, não como projeto)
