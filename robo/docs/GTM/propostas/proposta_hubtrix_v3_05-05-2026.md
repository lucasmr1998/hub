---
nome: Proposta Comercial Hubtrix — v3
data_criacao: 05/05/2026
versao: 3.0
publico: ISP (cliente final), apresentado por parceiro
formato: PPTX editável + PDF
brand: v2 (tinta #252020 + sienna #E76F51 + branco)
posicionamento: O copiloto de IA do seu provedor
status: rascunho
modulos: 4 (Comercial, Atendimento, Marketing, CS)
---

# Proposta Comercial Hubtrix — v3

Documento estruturado slide-a-slide. Base pra gerar/atualizar o PPTX.

---

## CHANGELOG 07/05/2026 — decisões pendentes pro próximo build

> **Status:** edições parciais aplicadas no Paper (file `hubtrix` v3). Bloqueado por limite semanal MCP. Próximo passo: refazer em conta Paper nova como `hubtrix v3.1` com TODAS as decisões abaixo incorporadas desde o início.

### Mudanças estruturais

- **Total: 14 slides** (era 16). Remoções:
  - Slide 12 (Plano Enterprise standalone) → **DELETADO**. Substituído pelo novo modelo por módulo.
  - Slide 16 (Próximos passos + bloco contato) → **DELETADO**.

### Capa (slide 1)

- Remover placeholders do rodapé: `{{NOME_PARCEIRO}}`, `{{NOME_CLIENTE}}`, `{{DATA_PROPOSTA}}`. Capa fica limpa, sem rodapé.

### Modelo de pricing — voltou pro modelo "por módulo" da v2

- Cliente compra os 4 módulos (Comercial, Atendimento, Marketing, CS) **separadamente**, cada um em 3 níveis.
- **Mensalidade uniforme por módulo:**
  - Starter: **R$ 497/mês**
  - Pro: **R$ 997/mês**
  - Enterprise: **R$ 1.497/mês**
- **Setup:** R$ 697/módulo (único, igual v2).
- **Variáveis (volta pros valores v2):**
  - Vendas finalizadas (Comercial): R$ 10 → 8 → 7 → 6 (faixas 100/300/600). Cálculo escalonado.
  - Marketing: R$ 0,05/contato ativo/mês (flat).
  - CS (Clube): R$ 0,15/cliente ativo no clube/mês (flat).
  - **Atendimento: ISENTO por enquanto** (sem variável por conversa). Pode ser cobrado depois.

### Slides 10/11 — refazer (substituem os antigos 10/11/12)

- **Slide 10 — Matriz "Módulos × Níveis":** tabela única com 4 linhas (módulos) × 3 colunas (Starter/Pro/Enterprise). Em cada célula: preço + 3-5 features-chave daquele nível. Coluna Pro destacada (bg tinta).
- **Slide 11 — Combos sugeridos:** 3 perfis pré-montados, com preço total já calculado.
  - ISP até 3k clientes: Comercial Starter + CS Starter = **R$ 994/mês**
  - ISP 3k-15k clientes: Comercial Pro + Atendimento Pro + CS Starter = **R$ 2.491/mês**
  - ISP 15k+ clientes: 4 módulos no Enterprise = **R$ 5.988/mês**

### Features roadmap REMOVIDAS de todos os slides

| Feature | Onde estava | Substituída por |
|---|---|---|
| **Tráfego pago com IA** | Slide 4 (Marketing col), Slide 7 (feature 6) | Slide 4: `Templates prontos`. Slide 7: feature `Templates prontos` (biblioteca de réguas testadas). |
| **Upsell automatizado** | Slide 4 (CS col), Slide 8 (feature 5) | Slide 4: `Indicações com cashback`. Slide 8: feature `Indicações com cashback`. |
| **Atribuição multi-touch** | Slide 12 (Enterprise) | N/A — slide 12 deletado. |

### Features confirmadas que **PERMANECEM**

- **Contrato digital** (slide 5) — temos, mantém.
- **Modo Integrado** (slide 6) — temos via **Matrix** (em produção em Megalink e Nuvyon). Outras ferramentas via API sob demanda.

### Slide 6 — narrativa "2 caminhos" mantida, mas com tools corretas

- **Caminho A · Integrado** (card light):
  - Matrix — em produção (Megalink, Nuvyon)
  - Outras ferramentas via API — sob demanda, implementadas no kickoff
  - REMOVER os logos antigos: ❌ Chatwoot, ❌ Octadesk, ❌ Take Blip, ❌ BotConversa
- **Caminho B · Nativo** (card dark com badge "RECOMENDADO"): Inbox Hubtrix — sem mudança.

### Decisões pendentes (perguntar antes do próximo build)

1. **Setup R$ 697/módulo** — confirma esse valor? (v2 tinha esse mesmo)
2. **Variável Atendimento isenta** — só pra contratos novos ou pra todos sempre?
3. **Slide 15 (Cronograma 14 dias)** — confirmado que vale pra qualquer ERP (não só HubSoft).
4. **SGP e Voalle no roadmap** (slide 9) — mantém menção no diferencial.
5. **Eliminar slide 16 (contato)** — confirmado.
6. **Capa sem rodapé** — confirmado.

### Estado dos PNGs antigos

PNGs do v3.0 (com pricing errado) em `C:\Users\lucas\Downloads\Proposta · NN @2x.png`. **NÃO USAR.** Refazer build inteiro do zero amanhã.

---

## Tokens de marca (DS Hubtrix v2)

```
Tinta (texto/sidebar/CTA): #252020
Sienna (acentos):           #E76F51
Sienna soft:                #FED7AA
Off-white:                  #FAFAF9 / #F8FAFC
Slate (texto secundário):   #475569
Border:                     #E2E8F0
Success:                    #10B981
Danger:                     #DC2626

Tipografia:
- Títulos: Inter Tight (900 / 800)
- Corpo:   Inter (400 / 500 / 600)
- Notas:   Caveat (italic) — sutil, em "scribbles" decorativos
```

---

## SLIDE 1 — CAPA

**Eyebrow** (sienna, uppercase, tracking alto):
`PROPOSTA COMERCIAL`

**Headline** (Inter Tight, 64px, tinta):
> O copiloto de IA do
> seu provedor de internet

**Sub-headline** (Inter, 20px, slate):
> Vender mais, fidelizar mais e operar com mais clareza —
> da qualificação de lead à retenção pós-venda.

**Rodapé direito** (Inter, 12px, slate):
- Apresentado por: **{{NOME_PARCEIRO}}**
- Cliente: **{{NOME_CLIENTE}}**
- Data: **{{DATA_PROPOSTA}}**
- Validade: 30 dias

**Visual:** lado direito com forma quadrada rotacionada em sienna sobre fundo tinta (mesmo padrão do site v4).

---

## SLIDE 2 — SOBRE A HUBTRIX

**Eyebrow:** `SOBRE`

**Title:** O que é Hubtrix

**Texto principal** (parágrafo único, 18px):
> Hubtrix é o **copiloto de IA do provedor**. Uma plataforma única que conecta vendas, atendimento, marketing e pós-venda — com IA em cada ponto de contato e integração nativa com seu ERP.
>
> Da primeira mensagem do lead no WhatsApp até a fidelização do cliente fiel, o time inteiro trabalha num só lugar: vendedor não troca de aba, atendente vê histórico completo, gerente acompanha funil agregado, CS antecipa cancelamento.

**4 pilares em cards horizontais:**

| Vender mais | Atender melhor | Fidelizar mais | Operar com clareza |
|---|---|---|---|
| `bi-trophy-fill` | `bi-chat-square-text-fill` | `bi-heart-fill` | `bi-graph-up-arrow` |
| Qualificação por IA, distribuição inteligente, contrato digital | Inbox unificado ou integração, IA pós-venda, SLA | Clube, NPS, score de churn, retenção proativa | Dashboards por área, win/loss, métricas reais |

**Nota** (rodapé, slate 11px):
> Plataforma SaaS multi-tenant, hospedagem dedicada, dados isolados por cliente.

---

## SLIDE 3 — DORES DO PROVEDOR

**Eyebrow:** `O PROBLEMA`

**Title:** Seu provedor cresceu. Sua operação não acompanhou.

**Sub:** Vender internet virou vender relacionamento. Mas a maioria dos ISPs ainda opera com 7 ferramentas soltas de 2018.

**4 cards de dor** (cards brancos com left-border sienna 4px):

### 01 — Lead some no WhatsApp pessoal
Aquele que responde em 3 minutos ganha. Quem deixa passar 3 horas entrega o lead pro concorrente. Sem fila, sem distribuição, conversão depende de quem lembrar primeiro.

### 02 — Atendimento operacional desorganizado
Time atende o cliente em uma ferramenta, registra o caso em outra, passa pra técnico em uma terceira. Sem SLA, sem histórico unificado, cliente repete o problema 3 vezes.

### 03 — Pós-venda vira buraco negro
Cliente assinou, foco no próximo. Sem NPS, sem régua de relacionamento, sem clube de fidelidade. Quando reclama, o problema já tá no chão. Upsell vira sorte.

### 04 — Decisão por palpite
Sem dado de win/loss, ninguém sabe **por que** perde venda. Sem score de churn, ninguém sabe **quais** clientes vão cancelar. Operação roda no escuro.

---

## SLIDE 4 — SOLUÇÃO: VISÃO GERAL

**Eyebrow:** `A PLATAFORMA`

**Title:** Um copiloto. Quatro módulos. Dezenas de capacidades de IA.

**Sub:** Da captura do lead até a retenção do cliente. Você contrata o que precisa — pode começar com 1 e expandir.

**Visual:** Grid 4 colunas (mesmo do marquee do site, mas estático em PPTX):

**Coluna 1 — Comercial:**
- Bot de qualificação por IA
- Pipeline preditivo
- Score de risco inadimplência
- Win/Loss analytics
- Distribuição inteligente de leads
- Contrato digital + ativação ERP

**Coluna 2 — Atendimento:**
- Inbox multicanal **ou** integração
- Filas, distribuição, SLA
- Tickets + Base de Conhecimento
- Resumo IA de conversa
- CSAT pós-atendimento
- Notas internas + @menções

**Coluna 3 — Marketing:**
- Réguas automáticas
- Segmentação dinâmica
- Disparos multicanal
- Tráfego pago com IA
- Rastreamento de campanhas

**Coluna 4 — Sucesso do Cliente:**
- Detector de churn preditivo
- Clube + carteirinha
- NPS automático
- Upsell automatizado
- Sugestão próxima ação por IA

**Nota:** "Tudo em uma plataforma só, sem integração quebrada."

---

## SLIDE 5 — MÓDULO COMERCIAL

**Eyebrow:** `MÓDULO 01 · COMERCIAL`

**Title:** Comercial — vender mais sem ampliar time

**Sub:** Da captura do lead à ativação no ERP, com IA em cada etapa da jornada de venda.

**6 features em grid 2x3:**

| Feature | Descrição curta |
|---|---|
| **Bot de qualificação IA** | Responde WhatsApp, qualifica com 8 perguntas, agenda visita técnica. Funciona no Inbox Hubtrix **ou** integrado à sua ferramenta atual |
| **Pipeline visual + IA** | Kanban com viabilidade, CTO, plano combo · sugestão de próxima ação por oportunidade |
| **Win/Loss analytics** | Por que ganha, por que perde — com motivo categorizado e dashboard |
| **Score de risco** | Detecta venda problemática antes de aprovar (lead novo, histórico, plano alto valor) |
| **Contrato digital** | Assinatura integrada, sem precisar sair do sistema |
| **Ativação automática no ERP** | Lead vira cliente HubSoft/SGP em 4h, não 48h |

**Footnote:** "Integração nativa com HubSoft. SGP e Voalle no roadmap."

---

## SLIDE 6 — MÓDULO ATENDIMENTO

**Eyebrow:** `MÓDULO 02 · ATENDIMENTO`

**Title:** Atendimento — escolha integrar ou substituir

**Sub:** A inteligência da Hubtrix funciona dos 2 jeitos. Você escolhe.

### Visual: 2 colunas grandes lado a lado

**COLUNA A — Caminho Integrado**

`Mantenha sua ferramenta atual`

Conecta via API/webhook com:
- Chatwoot
- Octadesk
- Take Blip
- BotConversa
- *(outras sob consulta)*

**O que entra:**
- ✓ Bot IA classifica conversa
- ✓ Cria/atualiza lead automaticamente
- ✓ Resumo IA, sentimento, sugestões
- ✓ Tickets + Base de Conhecimento
- ✓ CSAT pós-atendimento
- ✓ Notas internas Hubtrix

**Pra quem:** ISP que já investiu em ferramenta de atendimento e não quer migrar.

---

**COLUNA B — Caminho Nativo**

`Use o Inbox Hubtrix completo`

**Canais nativos:**
- WhatsApp Business
- Widget do site
- E-mail
- Instagram DM *(roadmap)*

**O que entra (tudo do Integrado +):**
- ✓ Inbox multicanal unificado
- ✓ Filas, distribuição operacional
- ✓ SLA configurável
- ✓ Macros + respostas rápidas com variáveis
- ✓ Distribuição inteligente por skill+sentimento

**Pra quem:** ISP sem ferramenta consolidada (WhatsApp Web compartilhado, planilha) ou insatisfeito com a atual.

---

**Footnote sienna:** *"Não te obrigamos a migrar de ferramenta. Mas se quiser migrar, fazemos a transição."*

---

## SLIDE 7 — MÓDULO MARKETING

**Eyebrow:** `MÓDULO 03 · MARKETING`

**Title:** Marketing — gerar demanda sem agência terceirizada

**Sub:** Motor de automação completo, multicanal, com IA.

**6 features:**

| Feature | Descrição |
|---|---|
| **Réguas prontas** | Boas-vindas, follow-up, reengajamento — adaptadas a ISP |
| **Segmentação dinâmica** | Leads e clientes separados automaticamente por perfil/comportamento |
| **Disparos multicanal** | WhatsApp e e-mail em escala, com personalização |
| **Editor visual de fluxos** | Drag-and-drop estilo n8n — sem código |
| **Rastreamento e ROI** | Vê conversão e custo por canal, real-time |
| **Tráfego pago com IA** | Otimização automática de budget *(Enterprise)* |

---

## SLIDE 8 — MÓDULO SUCESSO DO CLIENTE

**Eyebrow:** `MÓDULO 04 · SUCESSO DO CLIENTE`

**Title:** Sucesso do Cliente — fidelizar e antecipar churn

**Sub:** O CS deixa de ser reativo. Vira proativo.

**6 features:**

| Feature | Descrição |
|---|---|
| **Clube de benefícios** | Carteirinha digital, parceiros locais, gamificação |
| **Detector de churn (IA)** | Score 0-100 por cliente baseado em sinais reais (rule-based, configurável por tenant) |
| **NPS automático** | Régua periódica, dashboard de saúde |
| **Sugestão de próxima ação** | IA sugere ação por cliente em risco |
| **Upsell automatizado** | Detecção de oportunidade + disparo automático *(Enterprise)* |
| **Retenção proativa** | Alertas antes de cancelar, não depois |

---

## SLIDE 9 — DIFERENCIAIS

**Eyebrow:** `POR QUE HUBTRIX`

**Title:** O que CRM ou ferramenta de atendimento isolada não tem

**Sub:** A diferença está em cada detalhe que produto-pra-todo-mundo nunca vai ter.

**4 diferenciais grandes:**

### ✦ Copiloto de IA, não só "automação"
Agentes inteligentes integrados em cada módulo. Resumo de conversa, sugestão de próxima ação, classificação de sentimento, score de churn — tudo nativo. Não é integração com outro sistema de IA.

### 🔌 Integração ERP nativa, não plugin
HubSoft conectado direto — viabilidade por CEP, ativação automática, sincronização de plano. Outros ERPs (SGP, Voalle, MK-Auth) no roadmap. Cliente não precisa migrar nada.

### 🎯 Feito pra ISP, não adaptado
Campos como viabilidade técnica, CTO, plano combo, fila de instalação, motivo típico de cancelamento — vêm prontos. Não é customização.

### 🔄 Não te obriga a migrar
Atendimento se integra com sua ferramenta atual (Chatwoot, Octadesk, Take Blip…) ou substitui pelo Inbox nativo. Você escolhe. Mesma inteligência nos dois caminhos.

---

## SLIDE 10 — PLANO STARTER

**Eyebrow:** `PLANO 01`

**Title:** **Starter** · Funcionalidades essenciais

**Sub:** 1 a 2 usuários · Suporte standard

### 4 colunas (Comercial / Atendimento / Marketing / CS):

#### Comercial — R$ 497/mês
*Por venda finalizada no ERP*
- ✓ Bot de qualificação (WhatsApp)
- ✓ CRM Kanban básico
- ✓ Coleta de documentos
- ✓ Contrato digital
- ✓ Ativação no ERP
- ✓ Relatórios básicos

`Variável: R$6 a R$10/venda`

#### Atendimento — R$ 297 (integrado) / R$ 497 (nativo)
*Por conversa atendida*
- ✓ Inbox OU integração
- ✓ Distribuição básica
- ✓ Notas internas
- ✓ Tickets simples

`Variável: R$0,30 (integrado) / R$0,50 (nativo) por conversa`

#### Marketing — R$ 497/mês
*Por contato ativo na base*
- ✓ Réguas prontas
- ✓ Segmentação básica
- ✓ Disparos WhatsApp e e-mail
- ✓ Rastreamento de campanhas

`Variável: R$0,05/contato/mês`

#### Sucesso do Cliente — R$ 497/mês
*Por cliente no clube*
- ✓ Clube de benefícios digital
- ✓ Carteirinha digital
- ✓ Réguas básicas de retenção
- ✓ NPS e pesquisas

`Variável: R$0,15/cliente/mês`

**Setup:** R$697 por módulo (único)

---

## SLIDE 11 — PLANO PRO

**Eyebrow:** `PLANO 02 · RECOMENDADO`

**Title:** **Pro** · Funcionalidades completas

**Sub:** Até 5 usuários · Suporte standard

### 4 colunas (cada uma com "Tudo do Starter +"):

#### Comercial — R$ 997/mês
- ✓ Fluxos visuais de atendimento
- ✓ Pipeline personalizável
- ✓ Win/Loss analytics
- ✓ Score de risco inadimplência
- ✓ Múltiplos funis

#### Atendimento — R$ 597 (integrado) / R$ 997 (nativo)
- ✓ Respostas rápidas com variáveis
- ✓ SLA configurável
- ✓ Base de Conhecimento
- ✓ CSAT pós-atendimento
- ✓ Macros automatizadas

#### Marketing — R$ 997/mês
- ✓ Segmentação dinâmica
- ✓ Fluxos personalizados de nutrição
- ✓ Follow-up automatizado
- ✓ Reengajamento inteligente

#### Sucesso do Cliente — R$ 997/mês
- ✓ Réguas avançadas
- ✓ Segmentação de saúde
- ✓ Detector de churn (rule-based)
- ✓ Relatórios avançados

**Setup:** R$697 por módulo (único)

---

## SLIDE 12 — PLANO ENTERPRISE

**Eyebrow:** `PLANO 03`

**Title:** **Enterprise** · IA avançada e usuários ilimitados

**Sub:** Usuários ilimitados · Suporte prioritário

### 4 colunas (cada uma com "Tudo do Pro +"):

#### Comercial — R$ 1.497/mês
- ✓ Agentes IA conversacional
- ✓ Sugestão de próxima ação por oportunidade
- ✓ Classificação e extração por IA
- ✓ Resumo automático de conversa
- ✓ Analytics avançado

#### Atendimento — R$ 897 (integrado) / R$ 1.497 (nativo)
- ✓ Resumo IA de conversa
- ✓ Sentimento por IA (CSAT)
- ✓ Distribuição inteligente por skill+sentimento
- ✓ Detector de detrator automático

#### Marketing — R$ 1.497/mês
- ✓ Otimização tráfego pago (IA)
- ✓ Segmentação preditiva
- ✓ A/B testing automatizado
- ✓ ROI por campanha

#### Sucesso do Cliente — R$ 1.497/mês
- ✓ Detector de churn preditivo (configurável)
- ✓ Upsell automatizado
- ✓ CSAT com sentimento por IA
- ✓ Retenção proativa

**Setup:** R$697 por módulo (único)

---

## SLIDE 13 — CUSTOS VARIÁVEIS

**Eyebrow:** `INVESTIMENTO`

**Title:** Você paga pelo que usa, escalonado por volume

### Comercial — por venda finalizada no ERP

| Faixa | Valor por venda |
|---|---|
| 1 a 100 | R$ 10,00 |
| 101 a 300 | R$ 8,00 |
| 301 a 600 | R$ 7,00 |
| 601+ | R$ 6,00 |

### Atendimento — por conversa atendida

| Faixa de conversas/mês | Integrado | Nativo |
|---|---|---|
| 1 a 500 | R$ 0,30 | R$ 0,50 |
| 501 a 2.000 | R$ 0,25 | R$ 0,40 |
| 2.001 a 5.000 | R$ 0,20 | R$ 0,30 |
| 5.001+ | R$ 0,15 | R$ 0,20 |

### Marketing e CS

| Evento | Valor |
|---|---|
| Contato ativo/mês (Marketing) | R$ 0,05 |
| Cliente no clube/mês (CS) | R$ 0,15 |

### Setup (implantação)
**R$ 697 por módulo contratado** — único, na assinatura.
Inclui: configuração, integração ERP, importação de base, treinamento, acompanhamento de 14 dias.

**Nota destaque:** *Cálculo escalonado é cumulativo. As primeiras 100 vendas custam R$10 cada, as próximas 200 custam R$8, e assim por diante. Quanto mais vende, menor o custo unitário.*

---

## SLIDE 14 — SIMULAÇÃO PRA {{CLIENTE}}

> **Slide template — parceiro adapta com dados reais do prospect.**

**Eyebrow:** `SIMULAÇÃO`

**Title:** Investimento estimado pra **{{NOME_CLIENTE}}**

**Lado esquerdo — Inputs do prospect:**
- Vendas digitais estimadas/mês: **{{X}}**
- Conversas de atendimento/mês: **{{W}}**
- Leads na base: **{{Y}}**
- Clientes no clube: **{{Z}}**
- Módulos contratados: **{{LISTA}}**
- Plano: **{{Starter | Pro | Enterprise}}**
- Atendimento: **{{Integrado | Nativo}}** *(se contratou Atendimento)*

**Lado direito — Investimento mensal:**

| Item | Valor |
|---|---|
| Mensalidade módulos | R$ {{calc}} |
| Variável Comercial | R$ {{calc}} |
| Variável Atendimento | R$ {{calc}} |
| Variável Marketing | R$ {{calc}} |
| Variável CS | R$ {{calc}} |
| **Total mensal** | **R$ {{calc}}** |
| Setup (único) | R$ {{calc}} |

**Footnote** (sienna, italic):
*Reajuste anual IPCA. Validade 30 dias. Setup pode ser parcelado em 3x sem juros.*

> **Instruções pro parceiro:**
> Use a planilha `simulacao_proposta.xlsx` (anexa) pra gerar os números corretos.
> Não calcule à mão — pricing escalonado é cumulativo (não fixo).

---

## SLIDE 15 — CRONOGRAMA DE IMPLANTAÇÃO

**Eyebrow:** `IMPLANTAÇÃO`

**Title:** Do contrato à primeira venda em 14 dias

**Timeline vertical com ícones:**

| Dia | Etapa | O que acontece |
|---|---|---|
| **D+1** | Kickoff | Reunião de alinhamento, acessos, levantamento de dados (parceiro + Hubtrix + cliente) |
| **D+2 a D+5** | Configuração | Setup ambiente, integração ERP, importação de base, conexão com ferramenta de atendimento (se Caminho Integrado). **Hubtrix** executa, **parceiro** acompanha |
| **D+6 a D+8** | Treinamento | Capacitação da equipe nos módulos contratados (sessões 2h cada) |
| **D+9** | Go-live | Ativação produção com plantão Hubtrix |
| **D+10 a D+14** | Acompanhamento | Suporte dedicado, ajustes finos, validação |

**Nota:** *Após D+14, atendimento entra em SLA padrão do plano contratado.*

---

## SLIDE 16 — PRÓXIMOS PASSOS

**Eyebrow:** `FECHAR`

**Title:** Vamos começar?

**4 passos numerados:**

1. **Aprovação desta proposta** — você nos confirma escolha de plano, módulos e caminho de Atendimento (Integrado/Nativo)
2. **Assinatura do contrato SaaS** — enviado por DocuSign
3. **Pagamento do setup** — único, libera o kickoff
4. **Início da implantação** — D+1 começa em até 5 dias úteis

**Bloco de contato (rodapé):**

```
HUBTRIX
{{NOME_RESPONSAVEL_PARCEIRO}}
{{TELEFONE}} · {{EMAIL}}

Apresentado por: {{NOME_PARCEIRO}} · {{SITE_PARCEIRO}}

Powered by Hubtrix · hubtrix.com.br
```

**Validade:** *30 dias a partir de {{DATA_PROPOSTA}}.*
**Reajuste:** *IPCA/IBGE anual.*
**Valores em BRL.*

---

## ✅ Checklist de mudanças vs proposta atual (PDF v2)

| Mudança | Onde |
|---|---|
| Paleta v1 (azul cobalto) → v2 (tinta + sienna) | Todos os slides |
| Posicionamento "automação" → "copiloto de IA" | Capa + slide 2 + slide 4 |
| Plano Start → Pro · Plano Pro → Enterprise | Slides 10-12 |
| **Adicionado: Módulo Atendimento (slide 6)** | Novo slide com 2 caminhos |
| **Adicionado: Coluna Atendimento nos planos** | Slides 10, 11, 12 |
| **Adicionado: Pricing variável Atendimento** | Slide 13 |
| **Adicionado: Diferencial "Não te obriga a migrar"** | Slide 9 |
| Removido slide "Resultados comprovados" (case oculto) | — |
| Removido "Plano Advanced" inexistente | Slide simulação |
| Simulação virou template editável (`{{X}}`) | Slide 14 |
| Cronograma deixa claro quem faz o quê (parceiro/Hubtrix) | Slide 15 |
| Capa com slot pra parceiro + cliente | Slide 1 |
| Próximos passos com co-branding parceiro | Slide 16 |
| Diferenciais 6 → 4 (IA virou moldura, não item) | Slide 9 |
| Mais ERPs mencionados (SGP/Voalle/MK no roadmap) | Slide 5 + diferencial 2 |
| Adicionado: Win/Loss + Score risco + Detector churn + Resumo IA + Sugestão IA + CSAT IA | Slides 5-8 |
| Pricing Atendimento diferenciado (Integrado ~40% menor) | Slides 10-13 |

## 📌 Próximos passos pra virar PPTX

1. Você revisa este markdown e me sinaliza ajustes de copy
2. **Reconectar Paper MCP** pra eu criar os 16 artboards
3. Anexar planilha `simulacao_proposta.xlsx` com cálculo escalonado correto

## 📌 Pendências externas

- Foto/screenshot do produto pra embelezar slide 4 (visão geral) — uso o hero animado do site?
- Definir cor de fundo padrão dos slides: tinta (`#252020`) ou off-white (`#FAFAF9`)?
- Logo Hubtrix em PNG transparente
- Lista oficial de ferramentas de atendimento integradas (slide 6 cita Chatwoot, Octadesk, Take Blip, BotConversa — confirmar quais já existem na infra)
