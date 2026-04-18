---
name: "JTBD-03: Reter o cliente ativo, engajar pós-venda e transformá-lo em vetor de crescimento"
description: "Posicionamento do modulo CS por Job to be Done. Cobre: Clube de beneficios, Parceiros, Indicacoes, Carteirinha, NPS, Retencao, Automacoes pos-venda"
tipo: posicionamento_jtbd
modulos_cobertos: [cs, clube, parceiros, indicacoes, carteirinha, nps, retencao, suporte]
ordem_funil: 3
---

# JTBD-03 — Reter o cliente ativo, engajar pós-venda e transformá-lo em vetor de crescimento

> **Módulo Hubtrix:** CS (Starter / Pro / Advanced) + Suporte (complementar)
> **Ordem no funil:** 3º (pós-venda — fidelização e expansão)
> **Funcionalidades cobertas:** Clube de Benefícios (gamificação, roleta, missões, níveis) · Parceiros e cupons · Programa de Indicações · Carteirinha digital · NPS · Scanner de retenção (alertas de churn) · Régua de pós-venda · Suporte com SLA

---

## 1. O problema real do ISP

O ISP gasta fortunas pra **adquirir** um cliente (anúncio, time comercial, setup técnico), mas depois que ele ativa, **acontece o nada**. A base vira um lago parado — ninguém engaja, ninguém indica, ninguém percebe que o cliente ficou insatisfeito até ele cancelar.

Três sintomas clássicos:

- **Churn silencioso:** cliente está há 2 meses sem usar direito, ficou insatisfeito, um dia liga no concorrente e cancela. O provedor só descobre na hora de desligar.
- **Indicação desperdiçada:** cliente satisfeito elogiaria se perguntassem. Mas ninguém pergunta, ninguém oferece código, ninguém dá incentivo. Crescimento por indicação = 0.
- **Upsell perdido:** cliente pagando plano de 100MB há 2 anos poderia estar no 500MB (disposto a pagar mais), mas ninguém ofereceu.

**CAC é caro. LTV é barato se você trabalha.** A maioria dos ISPs paga caro pra adquirir e deixa LTV na mesa.

### A dor por porte

- **Pequeno (até 10k):** "Tenho 3.000 clientes ativos. Não mando NADA pra eles. Nem 'obrigado' na ativação. Churn quando rola é surpresa." → dor é **silêncio total pós-venda**
- **Médio (10k–30k):** "Tenho base grande, mas não tenho visão — quem é promotor? quem vai sair? quem paga pouco e poderia pagar mais? Minha base é um buraco preto." → dor é **ausência de inteligência sobre o cliente ativo**
- **Grande (+30k):** "Churn de 1% ao mês significa perder R$ 300k/mês em receita recorrente. Preciso de NPS estruturado, prevenção ativa com IA, programas de fidelização que escalem." → dor é **impacto financeiro material do churn**

---

## 2. Quem sente esse problema

| Porte | Quem sofre | Quem decide |
|-------|------------|--------------|
| Pequeno | Dono (vê o cliente indo embora e não sabe o que fazer) | Dono |
| Médio | Gerente de CS (se existir) + diretor (perde receita) | Diretor + dono |
| Grande | Head de CS + CFO (vê impacto no MRR) + CMO (vê indicação baixa) | CFO + CEO (churn ≠ é estratégico) |

Em todos os portes o **CFO do ISP é um aliado silencioso** — churn atinge a margem, fidelização aumenta LTV. Quando o CS é bem feito, o CFO defende o investimento.

---

## 3. Como resolviam antes

1. **Nada (60% do mercado):** cliente ativa e some. Provedor só fala com ele quando ele reclama ou quando a fatura vence.
2. **Programa manual de indicação:** "indica e ganha R$ 50". Funciona mal porque depende de lembrar de oferecer, processar indicação manualmente, pagar bônus manualmente. Resultado: 0,5% da base indica.
3. **NPS pontual por e-mail:** contrata SurveyMonkey, dispara pesquisa uma vez, lê os piores scores, esquece. Não vira processo.
4. **"Meu cliente gosta de mim, não precisa disso":** isso é ilusão — cliente gosta até o concorrente oferecer R$ 20 a menos com 100MB a mais.
5. **CRM genérico (RD Station, Salesforce):** tem features de CS mas adaptar pra ISP exige consultoria cara + ainda fica desconectado do ERP.
6. **ISPRO AI:** tem módulo de cobrança e algumas automações, mas não tem Clube de Benefícios completo com gamificação/roleta.

---

## 4. Como o Hubtrix resolve

O módulo **CS** + **Suporte** cobre 5 eixos:

### 4a. Clube de Benefícios com gamificação

Cliente vira **Membro do Clube**. Ganha pontos por ativação, tempo de casa, pagamento em dia. Usa pontos na **roleta** (prêmios), resgata **cupons de parceiros** (academia local, pizzaria, farmácia). Ganha níveis (Bronze → Prata → Ouro → Diamante) que destravam benefícios maiores. **Clube é ferramenta de retenção e engajamento — não é brinquedo.**

### 4b. Programa de Indicações automatizado

Cada membro tem **código único** e uma **página pública personalizada** (`/roleta/indicar/ABC123`). Manda o link pro amigo, amigo preenche, converte? Indicador ganha pontos automaticamente (via `GamificationService`). Tudo rastreado, sem operação manual.

### 4c. Scanner de Retenção (prevenção de churn)

Sistema analisa contratos do HubSoft e identifica sinais de churn:

- **Contrato expirando** (≤30 dias = crítico, ≤60 = alto, ≤90 = médio)
- **Inadimplência** ativa
- **Downgrade** de plano
- **Sem uso** do serviço
- **Reclamação** recorrente

Cria **AlertaRetencao** classificado por nível de risco. Time de CS age antes do cliente cancelar.

### 4d. NPS estruturado + Régua de relacionamento

Pesquisa de NPS automatizada (cron mensal, trimestral). Resposta detrata → cria alerta automático de risco + dispara régua de recuperação. Resposta promotor → oferece programa de indicação. Tudo sem trabalho manual.

### 4e. Carteirinha digital + Parceiros locais

Cliente recebe **carteirinha** (virtual) com QR code. Em parceiros locais (academia, restaurante), apresenta pro desconto. Cria **senso de pertencimento** além da internet.

### + Suporte com SLA (módulo complementar)

Tickets com SLA por plano. Problema técnico vira ticket automático (ou manual). Dashboard mostra tickets abertos, SLA breach, categoria. Não é CS, mas casa com ele.

---

## 5. Prova

### Argumento numérico — redução de churn

Considere um ISP médio (20k clientes):

```
Base: 20.000 clientes × R$ 99/mês = R$ 1.980.000/mês de MRR
Churn mensal tipico: 1,5% = 300 clientes cancelando/mes
Impacto mensal: R$ 29.700/mes em receita perdida
Impacto anual: R$ 356.400/ano

Se reduzir churn em 0,5pp (de 1,5% → 1,0%):
100 clientes retidos/mes × R$ 99 = R$ 9.900/mes = R$ 118.800/ano
```

**Custo do CS Advanced (stack completo):** R$ 2.997/mês = R$ 36k/ano
**Retorno mínimo necessário:** 30 clientes retidos/ano (0,15%)
**Retorno realista:** 100+ clientes retidos/ano (0,5%) = **3x ROI** só em retenção.

Isso **sem contar** upsell, cross-sell e indicação.

### Argumento de indicação

```
Se 5% da base indica 1 cliente/ano (benchmark com programa formal):
20.000 × 5% = 1.000 indicações/ano
Conversão tipica: 30% = 300 novos clientes por ano via indicação
CAC de indicação: pontos do clube ~= R$ 20 de valor percebido
CAC tradicional (Google Ads): R$ 150-300 por cliente fechado

Economia anual: R$ 300 - R$ 20 = R$ 280 por cliente × 300 = R$ 84.000/ano
```

**O CS se paga sozinho pela indicação.** Retenção é bônus.

---

## 6. Pitch de 30 segundos

> "Você investe pra trazer cliente, mas o que acontece depois que ele ativa? Nada, né? Na média, o ISP perde 1 a 2% dos clientes por mês e não sabe de quem. E o cliente satisfeito nunca indica ninguém porque você nunca pediu. O Hubtrix CS tem Clube de Benefícios com gamificação, programa de indicação automatizado e scanner de churn que avisa antes do cliente sair. Reduzir churn em 0,5% numa base de 20 mil assinantes vale R$ 118 mil por ano. O módulo custa menos de R$ 3 mil por mês."

---

## 7. Pitch de 2 minutos

**Gancho (15s):**
"Posso te perguntar 2 coisas? Um: você sabe quantos dos seus clientes estão insatisfeitos hoje? Dois: quantos dos seus clientes indicaram alguém esse ano?"

*(Normalmente: "não sei" e "poucos/nenhum".)*

**Diagnóstico (30s):**
"Essa é a situação de 90% dos ISPs. Depois que o cliente ativa, acontece o nada — nenhuma comunicação, nenhuma medição de satisfação, nenhum incentivo pra indicar amigo. O resultado é previsível: churn vira surpresa e crescimento por indicação é quase zero. **Isso é dinheiro caindo no chão.**"

**Solução (60s):**
"O Hubtrix CS ataca isso com 3 coisas:

1. **Clube de Benefícios com gamificação real** — cliente vira membro, ganha pontos por tempo de casa e pagamento em dia, gira roleta por prêmios, resgata cupons em parceiros locais. Cria senso de pertencimento. Aumenta NPS e reduz churn.

2. **Programa de indicação automatizado** — cada cliente tem código único, página pública personalizada, sistema credita pontos sozinho quando amigo vira cliente. Um provedor médio com 20 mil assinantes consegue 300 novos clientes por ano via indicação — a um CAC 10x menor que Google Ads.

3. **Scanner de retenção (prevenção de churn)** — sistema olha seu HubSoft, identifica contrato expirando, inadimplência, downgrade, sem uso. Cria alertas classificados por risco. Seu time age **antes** do cliente cancelar, não depois."

**Prova (15s):**
"Numa base de 20 mil clientes, reduzir churn em 0,5% vale R$ 118 mil/ano. O CS Advanced custa R$ 36k/ano. ROI de 3x só em retenção, sem contar indicação e upsell."

**Fechamento (15s):**
"Planos de R$ 497 a R$ 1.497/mês + R$ 0,15 por cliente ativo no clube. A partir do Starter você já tem Clube e indicações. No Advanced tem NPS + scanner de churn com IA. Qual porte da sua base?"

---

## 8. Objeções comuns + respostas

### "Meus clientes não precisam de clube, eles só querem internet boa"

> "Concordo em 80%. Mas quando o concorrente oferece internet boa + R$ 10 a menos, o que segura o cliente é o custo de trocar. O Clube aumenta esse custo emocional: cliente tem pontos acumulados, carteirinha, parceiros onde já ganha desconto. Não é substituto da qualidade da internet, é complemento. E a parte de scanner de churn funciona sem o Clube — olha dados duros do HubSoft."

### "Programa de indicação já tentei e ninguém indicou"

> "Tentou manual (oferecer verbalmente + pagar bônus)? Isso quase nunca funciona em escala porque depende de lembrar. O Hubtrix automatiza: cada cliente já tem código, link, página. Você pode disparar 'você tem 500 pontos, que tal indicar um amigo?' sem operação nenhuma. E se ele indicar e converter, os pontos caem sozinhos. Benchmark com programa formal é 5% da base indicando por ano."

### "Não vou gastar com CS, prefiro investir em Comercial pra trazer mais lead"

> "Faz contas comigo: CAC de Google Ads pra ISP está entre R$ 150 e R$ 300 por cliente fechado. Cliente retido custa 1/10 disso. Reduzir churn em 0,5% vale R$ 118k/ano pra uma base de 20k clientes. Pra trazer esse mesmo dinheiro via aquisição, você precisa gastar R$ 40-50k em mídia. CS é investimento menor com retorno maior."

### "Minha base é pequena, não compensa"

> "Qual seu tamanho?" (espera resposta)
> Se 2-5k: "No Starter o CS custa R$ 497 + R$ 0,15 por cliente = R$ 847/mês pra base de 2.300 membros. Se retiver 1 cliente que cancelaria, paga R$ 99 × 24 meses = R$ 2.376. Já pagou 3 meses do módulo. E o programa de indicação começa a render desde o dia 1."

### "Tenho medo de parecer que estou enrolando cliente"

> "O Clube só funciona se entrega valor real — cupom de verdade, prêmio de verdade. Não é 'enrolação', é 'reconhecimento'. Cliente que fica 2 anos pagando merece um benefício. A maioria dos ISPs **nunca reconhece** seus clientes de longo prazo, é essa lacuna que o Clube preenche."

### "Não tenho parceiros locais pra cupons"

> "O Hubtrix ajuda você a recrutar. A gente ensina como fazer a abordagem no comércio local ('sua academia ganha divulgação pros meus 5 mil assinantes'). Parceiro não paga nada, ganha divulgação. E muitas parcerias saem fechadas com 2-3 reuniões. Tem template de abordagem pronto."

### "Funciona com HubSoft?"

> "Funciona nativamente. O scanner de retenção olha os contratos direto no HubSoft — expiração, inadimplência, status. Cliente ativo no clube = cliente ativo no HubSoft, sincronizado. Esse é exatamente nosso ponto forte vs concorrentes genéricos."

---

## 9. Como usar este posicionamento

- **SDR / Vendedor:** **o melhor gancho é o churn**. Frase: "você sabe hoje quais clientes vão cancelar esse mês?" — ninguém sabe, e é dor real.
- **Demo:** mostra primeiro o Clube (visual, wow), depois o scanner de retenção (dor quantificável), termina com indicação (ROI claro).
- **Proposta:** sempre inclui calculadora de ROI com o volume do prospect. Indicação + retenção combinadas quase sempre dão 3x+ de ROI.
- **Outbound:** usa estatística — "ISPs perdem 1,5% da base por mês em média, isso vale R$X na sua operação".

## 10. Dependências e próximos JTBDs

Este JTBD-03 é a **terceira etapa do funil** — fidelização e transformação do cliente em vetor de crescimento.

Conecta com:

- **JTBD-01 (Marketing)** — indicações convertidas viram leads que o Marketing nutre. **Ciclo fecha.**
- **JTBD-02 (Comercial)** — upsell detectado via alerta de retenção vira nova OportunidadeVenda.

**Ciclo completo do funil:**

```
JTBD-01 Marketing   ──(leads)──▶   JTBD-02 Comercial   ──(clientes)──▶   JTBD-03 CS
        ▲                                                                       │
        └───────────────(indicacoes)────────────────────────────────────────────┘
```

CS realimenta o Marketing. É assim que SaaS/ISP saudável cresce com CAC decrescente.

---

## 11. Posicionamento conjunto dos 3 JTBDs

Quando vender o stack completo:

> "Marketing atrai leads qualificados e nutre a base. Comercial converte esses leads em contratos sem re-digitação. CS retém o cliente ativo e transforma ele em vetor de crescimento via indicação. Os 3 se realimentam: CS gera indicações que voltam pro Marketing, que gera leads pro Comercial, que gera clientes pro CS. É um ciclo — não 3 ferramentas soltas. Stack completo sai a partir de R$ 1.881/mês (Starter)."
