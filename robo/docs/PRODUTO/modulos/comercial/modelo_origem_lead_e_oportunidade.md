# Modelo de origem do Lead e da Oportunidade

Definicao conceitual de como representamos "de onde veio um lead" e
"de onde veio uma oportunidade" no Hubtrix. Aplicado em
`apps/comercial/leads/LeadProspecto` e
`apps/comercial/crm/OportunidadeVenda`.

Objetivo: separar claramente CANAL (meio fisico de chegada) de FONTE
(quem trouxe o trafego), MEIO (tipo de trafego), CAMPANHA (acao
especifica) e CONTEUDO (creative).

**Lead = first-touch** (de onde a pessoa veio na primeira vez, nunca muda).
**Oportunidade = last-touch** (de onde a negociacao especifica veio, pode
diferir do lead em casos de reativacao por nova campanha).

Padrao inspirado em Hubspot + RD Station + UTM Google Analytics.

---

## 1. Conceitos

### CANAL — "Por onde o lead chegou?"
Meio fisico/tecnico de chegada do lead ate nos. So existem alguns:

| Canal | Quando usar |
|---|---|
| `whatsapp` | Mandou mensagem via WhatsApp |
| `telefone` | Ligou |
| `email` | Mandou email |
| `site` | Submeteu formulario no nosso site |
| `sms` | Mandou SMS |
| `loja_fisica` | Cadastrado presencialmente |
| `manual` | Operador cadastrou direto no CRM |

Lista pequena e fechada. So canais reais de chegada.

### FONTE — "De qual plataforma o trafego veio?"
Quem mandou o lead pra gente.

| Fonte | Quando usar |
|---|---|
| `facebook` | Tráfego veio do Facebook (Meta) |
| `instagram` | Tráfego veio do Instagram |
| `google` | Veio do Google (busca ou Ads) |
| `tiktok` | Veio do TikTok |
| `youtube` | Veio do YouTube |
| `linkedin` | Veio do LinkedIn |
| `indicacao` | Cliente atual indicou |
| `parceiro` | Veio de parceiro/revenda |
| `organico` | Veio sozinho (lembrou do nome, achou no buscador organico) |
| `email_mkt` | Veio de campanha de email nossa |
| `direto` | Digitou URL/numero direto sem rastreamento |
| `outros` | Quando nao se encaixa em nenhuma anterior |

### MEIO — "Que tipo de trafego e?"
Categoriza o trafego em ads pago vs organico vs outros.

| Meio | Significado |
|---|---|
| `ads` | Trafego pago (Facebook Ads, Google Ads, TikTok Ads) |
| `social` | Post organico em rede social |
| `search` | Busca (organico ou pago — pago marca tambem `ads`) |
| `referral` | Indicacao de cliente/parceiro |
| `email` | Campanha de email |
| `direct` | Digitou direto (sem source) |

### CAMPANHA — "Qual acao especifica trouxe o lead?"
Eh a "Campanha de Trafego" no Hubtrix (FK pra
`apps/marketing/campanhas/CampanhaTrafego`). Nome legivel pelo time
de marketing.

Exemplos:
- "Entre em Contato e Aproveite!" (Meta Ads)
- "Black Friday 2025" (multi-canal)
- "Indicacao Cliente Carteirinha" (programa de indicacao)
- "Operacao Porta a Porta Jul25" (campo)

### CONTEUDO — "Qual variacao dentro da campanha?"
Criativo especifico do ad. Util quando o ad set tem N criativos rodando.

Exemplos:
- "video_v3_oferta_119,90"
- "imagem_ana_clientes_dec25"
- "carrosel_familia_setembro"

Guardado em `metadata_campanhas.utm_content` (JSONField, nao precisa
schema rigido).

### TERMO — "Que palavra-chave?" (so busca paga)
Util pra Google Ads. Guardado em `metadata_campanhas.utm_term`.

---

## 2. Relacao entre os conceitos

```
        LEAD
         │
   ┌─────┴──────┐
   │            │
 CANAL       ORIGEM
 (fisico)    (rastreamento)
              │
    ┌─────────┼─────────┐
    │         │         │
  FONTE     MEIO     TERMO
    │
    └─── CAMPANHA
              │
              └─── CONTEUDO
```

CANAL eh independente — o lead **sempre** chega por algum canal
fisico (WhatsApp, telefone, etc).
ORIGEM eh o pacote de rastreamento UTM-like.
FONTE + MEIO + CAMPANHA + CONTEUDO + TERMO compoem ORIGEM completa.

---

## 2b. Lead vs Oportunidade (first-touch vs last-touch)

A **pessoa** (lead) tem origem unica — a primeira que trouxe ela ate nos.
A **negociacao especifica** (oportunidade) pode ter origem diferente,
em casos de reativacao.

### Exemplo do Joao

| Quando | Evento | Lead.fonte / campanha | Op criada / fonte / campanha |
|---|---|---|---|
| Jan/2026 | Ve ad FB, manda WhatsApp | Joao criado, fonte=facebook, campanha="Promo Jan" | Op1: fonte=facebook, campanha="Promo Jan" -> PERDIDA |
| Mai/2026 | Ve ad Insta, manda WhatsApp de novo | Lead Joao NAO muda (fica facebook/"Promo Jan") | Op2: fonte=instagram, campanha="Black Friday Antecipada" |
| Jun/2026 | Amigo indica, ele liga | Lead Joao NAO muda | Op3: fonte=indicacao, campanha=null |

### Pergunta -> onde olhar

| Pergunta | Onde |
|---|---|
| "Quantas pessoas novas vieram do Facebook?" | Lead.fonte |
| "Quantas vendas o Facebook gerou?" | Op.fonte |
| "Joao veio de onde primeiro?" | Lead = facebook |
| "Op2 do Joao veio de onde?" | Op2 = instagram |
| "Qual campanha trouxe mais leads?" | Lead.campanha_origem |
| "Qual campanha fechou mais vendas?" | Op.campanha_atribuicao |
| "CAC por campanha" | Op.campanha_atribuicao / gasto da campanha |

### Regra de ouro

- Lead nunca tem `canal/fonte/campanha` sobrescrito apos criado. Eh
  imutavel — representa o primeiro toque.
- Op herda do lead na criacao automatica (Op = mesma fonte do Lead).
- Op pode ter `canal/fonte/campanha_atribuicao` ALTERADO se foi
  reativada por uma nova campanha (operador edita, ou bot detecta
  novo evento de ad apontando pra mesmo telefone).

---

## 3. Cenarios reais

| # | Lead chegou via... | canal | fonte | meio | campanha | conteudo |
|---|---|---|---|---|---|---|
| 1 | Clicou ad no Insta, mandou WhatsApp | whatsapp | instagram | ads | "Entre em Contato e Aproveite!" | "video_v3" |
| 2 | Pesquisou no Google e ligou | telefone | google | search | "Nuvyon 600 Mega" | "anuncio_lateral" |
| 3 | Amigo indicou, ligou direto | telefone | indicacao | referral | "Indicacao Cliente Clube" | — |
| 4 | Buscou organico no Google, mandou WhatsApp pelo site | whatsapp | google | organico | — | — |
| 5 | Operadora cadastrou na rua | loja_fisica | direto | direct | "Porta a Porta Jul25" | — |
| 6 | Email de aniversario, clicou pra WhatsApp | whatsapp | email_mkt | email | "Aniversario Set/25" | — |
| 7 | Ad TikTok, baixou app, mandou WhatsApp | whatsapp | tiktok | ads | "Black Friday TikTok" | "video_oferta_30s" |
| 8 | Atendente cadastrou no CRM manualmente | manual | direto | direct | — | — |

---

## 4. Estado atual no codigo (problemas)

| Campo atual | Problema |
|---|---|
| `origem` (CharField com `ORIGEM_CHOICES`) | Mistura canal (WhatsApp, Telefone, Email) com fonte (Facebook, Google, Instagram). Bagunca conceitual. |
| `canal_entrada` (CharField, **mesmas choices**) | Duplicado de `origem`. Redundante. |
| `tipo_entrada` (CharField) | OK, mas eh tipo de evento (`contato_whatsapp`, `cadastro_site`), nao canal. Manter sem mexer. |
| `campanha_origem` (FK CampanhaTrafego) | OK. Manter. |
| `campanha_conversao` (FK CampanhaTrafego) | OK. Manter (representa campanha que converteu, separada da que trouxe). |
| `metadata_campanhas` (JSONField) | OK. Vai concentrar utm_medium, utm_content, utm_term, protocolo, data_acesso. |
| `total_campanhas_detectadas` (Integer) | OK. Counter de quantas campanhas o lead apareceu (em re-cruzamentos). |
| (nao existe) **MEIO** | Adicionar como campo do model `CampanhaTrafego` (`meio` choices). Lead herda via FK. |
| (nao existe) **CONTEUDO** | Guardar em `metadata_campanhas.utm_content`. |

---

## 5. Proposta de refactor (consolidacao)

### Nomes finais do schema em LeadProspecto (first-touch)

| Campo final | Tipo | Choices |
|---|---|---|
| `canal` | CharField(20) | `CANAL_CHOICES` (whatsapp, telefone, email, site, sms, loja_fisica, manual) |
| `fonte` | CharField(30) | `FONTE_CHOICES` (facebook, instagram, google, tiktok, youtube, linkedin, indicacao, parceiro, organico, email_mkt, direto, outros) |
| `tipo_entrada` | CharField(50) | mantem como esta |
| `campanha_origem` | FK CampanhaTrafego | mantem (primeiro toque) |
| `metadata_campanhas` | JSONField | livre, chaves padronizadas: `utm_medium`, `utm_content`, `utm_term`, `protocolo`, `data_acesso`, `ad_account`, etc |

### Novos campos em OportunidadeVenda (last-touch)

| Campo novo | Tipo | Default |
|---|---|---|
| `canal_atribuicao` | CharField(20) | herda de `lead.canal` na criacao |
| `fonte_atribuicao` | CharField(30) | herda de `lead.fonte` na criacao |
| `campanha_atribuicao` | FK CampanhaTrafego | herda de `lead.campanha_origem` na criacao, pode ser alterado |
| `metadata_atribuicao` | JSONField | livre, utm_content / utm_term / protocolo da campanha que reativou |

### Migration de dados

- `origem` -> dividir em `canal` ou `fonte` conforme valor antigo:
  - `whatsapp, telefone, email` -> `canal`
  - `facebook, instagram, google, site, indicacao, outros` -> `fonte`
- `canal_entrada` -> remover (redundante)

### Em `CampanhaTrafego` (apps/marketing/campanhas)

Adicionar:
- `meio` CharField (ads, social, search, referral, email, direct)
- `fonte` CharField (a mesma do lead, herdada)

Lead acessa via `lead.campanha_origem.meio` e `lead.campanha_origem.fonte`.

---

## 6. Como o match com planilha de ads funciona

Pra cada linha da planilha (`tel + data_acesso + titulo_post + canal=whatsapp`):

**Match em 3 camadas:**

| Camada | Criterio | Confianca |
|---|---|---|
| 1️⃣ | Telefone normalizado (igual no CRM) | Necessaria |
| 2️⃣ | Lead criado em ±24h da `data_acesso` da planilha | Forte |
| 3️⃣ | `tipo_entrada=contato_whatsapp` (canal compativel) | Forte |

**Categorizacao:**

| Match | Criterios | Acao |
|---|---|---|
| Strong | 1 + 2 + 3 | Enriquece automatico |
| Medium | 1 + 2 OU 1 + 3 | Enriquece com flag "review" |
| Weak | so 1 | Mostra mas precisa confirmacao manual |

**Quando enriquece (Strong/Medium aprovado):**
- Preenche `canal` = "whatsapp"
- Cria/atualiza `CampanhaTrafego` com nome do titulo_post
- Preenche `campanha_origem` (FK)
- Adiciona em `metadata_campanhas`: `{ protocolo, data_acesso, ad_account, classificacao }`
- Incrementa `total_campanhas_detectadas`
- NAO sobrescreve `campanha_origem` se ja preenchida (adiciona em metadata como historico)

**Sem janela temporal:** evitar matches "frankenstein" tipo lead de janeiro recebendo campanha de junho.

---

## 7. Casos de fronteira

| Caso | Como tratar |
|---|---|
| Lead chegou por 2 canais diferentes (WhatsApp em jan, telefone em mar) | `canal` = ultimo. Historico em `historico_contatos`. |
| Mesma campanha bate em N leads | OK, FK eh many-to-one. |
| Lead chegou organicamente mas dps clicou em ad | `fonte=organico, campanha_conversao=ad` (separa origem de conversao). |
| Tenant nao usa ads | `fonte=direto` ou `manual`. `campanha_origem=null`. |
| Lead criado por bot Selenium (sem canal real) | `canal=manual`, `tipo_entrada=api_externa`. |

---

## 8. Proximos passos

| Sprint | Entrega |
|---|---|
| 1 | Refactor schema Lead: split `origem` -> `canal` + `fonte`, remover `canal_entrada`, migration |
| 2 | Adicionar campos last-touch em OportunidadeVenda (`canal_atribuicao`, `fonte_atribuicao`, `campanha_atribuicao`, `metadata_atribuicao`) + heranca Lead -> Op |
| 3 | Adicionar `meio` em `CampanhaTrafego` |
| 4 | Tela `/leads/importar-ads/` com upload CSV + match 3 camadas + dashboard |
| 5 | Filtros no kanban CRM por canal/fonte/meio/campanha |

Sprint 1 + 2 + 3 sao base. Sprint 4 entrega a ferramenta. Sprint 5 da
visibilidade no kanban.
