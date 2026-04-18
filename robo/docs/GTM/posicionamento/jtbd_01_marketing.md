---
name: "JTBD-01: Atrair leads qualificados e nutrir relacionamento sem aumentar o time"
description: "Posicionamento do modulo Marketing por Job to be Done. Cobre: campanhas com deteccao UTM, automacoes, reguas, segmentos dinamicos, disparo em massa"
tipo: posicionamento_jtbd
modulos_cobertos: [marketing, campanhas, automacoes, segmentos]
ordem_funil: 1
---

# JTBD-01 — Atrair leads qualificados e nutrir relacionamento sem aumentar o time

> **Módulo Hubtrix:** Marketing (Starter / Pro / Advanced)
> **Ordem no funil:** 1º (topo — pré-comercial)
> **Funcionalidades cobertas:** Campanhas UTM · Detecção por palavra-chave · Automações · Segmentos dinâmicos · Régua de relacionamento · Disparo em massa · Programa de indicações

---

## 1. O problema real do ISP

O provedor **recebe leads**, mas não sabe o que fazer com eles depois do primeiro contato. Três cenários reais:

- Lead chega no WhatsApp com "cupom50", vai pro vendedor, ninguém sabe que aquele lead veio da campanha do Instagram que custou R$ 5.000 no mês. ROI dessa campanha = impossível calcular.
- Cliente ativo há 1 ano nunca recebeu comunicação do provedor. Nem "obrigado pela parceria", nem "upgrade disponível", nem "NPS". Está esquecido na base.
- O time comercial perde dia fazendo follow-up manual ("oi, tudo bem? ainda tem interesse?"). Quando o time cresce em leads, precisa crescer em pessoas pra dar conta.

**A dor muda por porte:**

- **Pequeno (até 10k assinantes):** "Tô cansado de mandar mensagem na mão. Meus leads somem e não sei o que aconteceu." → dor é **dispersão**
- **Médio (10k–30k):** "Gasto com tráfego pago mas não sei o que converte. Minha base de 15 mil clientes está parada, sem comunicação nenhuma." → dor é **falta de método e visibilidade**
- **Grande (+30k):** "Preciso de atribuição por canal, régua por segmento, e automação que escale com a base crescendo. Time de marketing não pode crescer na mesma velocidade." → dor é **escala sem proporcionalidade com headcount**

---

## 2. Quem sente esse problema

Dependendo do porte, o decisor muda:

| Porte | Quem sofre | Quem decide |
|-------|------------|--------------|
| Pequeno | Dono (faz tudo, não tem fôlego pra marketing) | Dono |
| Médio | Gerente comercial ou coordenador de marketing (se tiver) | Diretor/gerente influencia, dono decide |
| Grande | Head de Marketing ou CMO | Múltiplos stakeholders (CMO + CFO + CTO) |

Em todos os portes, o sintoma imediato é o mesmo: **"estou gastando em marketing e não sei o resultado"** ou **"minha base é grande mas está morta"**.

---

## 3. Como resolviam antes

Hierarquia típica do que ISPs fazem hoje:

1. **Nada (50% do mercado):** "Marketing é só Instagram que eu posto e indicação. Base cadastrada eu tenho, mas não mando nada pra ela."
2. **Planilha + broadcast manual:** junta lista num WhatsApp business e manda mensagem igual pra todo mundo. Sem segmentação, sem régua, sem medição.
3. **RD Station / HubSpot adaptado:** tentaram usar ferramenta genérica, gastaram caro no plano, bateram em "não integra com HubSoft" e abandonaram.
4. **N8N + Google Sheet + API WhatsApp:** solução engenhosa de TI próprio, funciona pra quem tem técnico dedicado, mas é frágil e ninguém entende quando quebra.
5. **ISPRO AI (concorrente direto):** foco em IA genérica, mas sem os módulos operacionais completos e sem integração nativa com HubSoft.

---

## 4. Como o Hubtrix resolve

O módulo **Marketing** do Hubtrix ataca 4 eixos ao mesmo tempo:

### 4a. Rastreio: toda origem identificada

Detecção automática de **campanha por palavra-chave** na primeira mensagem. Cliente digita "cupom50" → sistema marca o lead como vindo da campanha CUPOM50 → a partir daí o ROI dessa campanha é calculado automaticamente (leads gerados → vendas fechadas → receita). 9 plataformas suportadas nativamente (Google Ads, Meta, TikTok, etc.).

### 4b. Régua de relacionamento automática

Editor visual onde o marketing desenha: "quando evento X acontece → envia mensagem Y → espera N dias → se condição Z → manda W". Réguas padrão prontas (boas-vindas, lead frio, inadimplência, aniversário de contrato). Não precisa programador.

### 4c. Segmentos dinâmicos

Define grupos de clientes por critérios (origem, ticket, tempo de casa, cidade, score) e o sistema mantém o segmento atualizado sozinho. Cliente que muda de perfil entra/sai automaticamente do segmento.

### 4d. Disparo em massa com inteligência

Dispara campanha pra um segmento (ex: "clientes com mais de 2 anos elegíveis pra upgrade") com mensagens personalizadas — `{{lead_nome}}`, `{{cidade}}`, `{{plano_atual}}`.

### + Complemento: Programa de indicações (do módulo CS)

Cada cliente gera código de indicação + página pública personalizada. Amigo converte → cliente ganha pontos no Clube. Marketing alimenta a base; indicações convertem mais barato que tráfego pago.

---

## 5. Prova

### Números de referência (case 30k assinantes)

- **Redução de 70% do trabalho manual** no comercial quando Marketing + Comercial operam juntos
- **400 vendas/mês no canal digital** com base mantida em 2 pessoas no operacional
- **R$ 284.400/ano de economia** em pessoal

Ver [case completo](../cases/case_provedor_regional_30k.md).

### Argumento quantitativo genérico

O módulo Marketing custa **R$ 497–R$ 1.497/mês** de mensalidade fixa. Um ISP médio (20k assinantes) que paga R$ 997/mês + R$ 0,05 por lead cadastrado × 2.000 leads = **R$ 1.097/mês total**.

Mesmo recuperando **1 cliente por mês** que teria sumido sem régua automática, o módulo se paga:

```
R$ 99/mês × 24 meses de retenção média = R$ 2.376 de receita por cliente recuperado
Custo do modulo: R$ 1.097/mês
Payback: 1 cliente resgatado a cada 2 meses cobre o custo.
```

---

## 6. Pitch de 30 segundos

> "Você gasta em marketing mas não sabe o que converte? Sua base de clientes está parada, sem nenhuma comunicação? O Hubtrix Marketing detecta de qual campanha cada lead veio, automatiza as réguas de relacionamento com seus clientes e dispara campanhas segmentadas sem você precisar de programador. Um provedor com 30 mil assinantes reduziu 70% do trabalho manual do time comercial usando só essa combinação. A partir de R$ 497 por mês."

Usa em cold call, primeira mensagem de WhatsApp, linha 1 de e-mail de outbound.

---

## 7. Pitch de 2 minutos (demo / reunião inicial)

**Gancho (15s):**
"Deixa eu te fazer uma pergunta: você sabe hoje, com precisão, de qual campanha veio o último cliente que fechou com você? E quantos clientes da sua base você mandou uma mensagem personalizada nos últimos 30 dias?"

**Diagnóstico (30s):**
"Pela nossa experiência com outros provedores, a resposta costuma ser 'não sei' e 'zero'. Isso é normal, porque o stack de ferramentas de ISP não foi feito pra isso. WhatsApp Business não faz atribuição. Planilha não manda mensagem. HubSoft é ERP, não é marketing. E RD Station não integra com HubSoft."

**Solução (45s):**
"O Hubtrix Marketing resolve esses 3 problemas de uma vez:

- **Atribuição:** quando o cliente digita 'cupom50' no seu WhatsApp, a gente reconhece que veio da campanha X que você rodou no Instagram — e calcula o ROI dessa campanha automaticamente, até a venda fechar no HubSoft.
- **Régua automática:** você desenha uma vez no editor visual 'quando cliente completa 1 ano, mandar mensagem de obrigado + oferta de upgrade'. A partir daí roda sozinho pra sempre.
- **Segmentação dinâmica:** define 'clientes com mais de 2 anos, plano 200MB ou menos, sem reclamação aberta' e o sistema atualiza esse grupo automaticamente quando novos clientes entram no perfil."

**Prova (15s):**
"Um provedor de 30 mil assinantes usando isso reduziu o time comercial de 8 pra 2 pessoas. As outras 6 foram realocadas — economia de 284 mil reais por ano só em folha. Esse é um caso real em produção."

**Fechamento (15s):**
"A partir de R$ 497 por mês (plano Starter) até R$ 1.497 (Advanced com IA de otimização de tráfego). Posso te mostrar os 3 planos detalhados e fazer uma simulação com o seu volume?"

---

## 8. Objeções comuns + respostas

### "Já tenho RD Station / HubSpot, por que trocar?"

> "RD e HubSpot são ótimos pra empresa genérica, mas não conhecem o ISP. Eles não sabem que seu cliente tem um contrato no HubSoft, não olham inadimplência pra disparar régua de retenção, não integram com o scanner de contratos expirando. O Hubtrix foi feito pra atender o funil inteiro do provedor, do anúncio até a cobrança — e por isso custa 30–50% do que você paga no RD hoje."

### "Não tenho volume pra justificar"

> "Qual é o seu volume atual?" (espera resposta)
> Se < 200 leads/mês: "Nesse volume o plano Starter cobre tudo: R$ 497/mês fixo + R$ 10/mês de variável (200 × R$ 0,05). Menos que o custo de um estagiário por meio período. Se recuperar 1 cliente que teria sumido, já paga."
> Se > 500 leads/mês: "Nesse volume você tá perdendo dinheiro sem automação. Vou te mostrar o ROI pro seu caso exato."

### "E se o vendedor humano for melhor que o bot?"

> "É mais comum vendedor ser pior no primeiro contato porque ele cansa, esquece de perguntar coisa, responde devagar. O bot pergunta sempre, do mesmo jeito, em 2 segundos, 24 horas por dia. O vendedor humano volta a ser ótimo quando entra na negociação — e é pra isso que a gente te transfere quando o lead está qualificado. Bot qualifica, humano fecha."

### "Meu time de marketing já faz isso manualmente"

> "Quantas horas por semana eles gastam fazendo régua, disparo, segmentação? Se a resposta é mais de 4h/pessoa, o Hubtrix paga o salário da pessoa em eficiência. Se é menos, provavelmente vocês estão deixando de fazer — que é o caso real da maioria."

### "Preciso de aprovação de vários (grande)"

> "Faz sentido. Posso preparar materiais diferentes pra cada decisor — narrativa pro CEO, arquitetura técnica pro CTO, ROI e unit economics pro CFO. Quer que eu envie esses 3 documentos e marcamos uma sessão conjunta?"

### "Quanto tempo leva pra implementar?"

> "Depende do porte e do que você já tem. No Starter: 3 a 5 dias com setup gratuito. No Advanced: 2 a 4 semanas com integrações customizadas. Durante todo esse tempo seu time recebe treinamento e não paga nada — a cobrança só começa 30 dias depois do setup concluído."

---

## 9. Como usar este posicionamento

- **SDR / Vendedor:** usa os pitches 30s e 2min como base. Adapta pro porte do prospect.
- **Demo:** abre pelo problema (pergunta 1 da seção 7), não pela feature.
- **Proposta:** cita números do case (seção 5) + planos (seção 8).
- **Marketing:** usa o gancho "você sabe de qual campanha veio o último cliente?" em copy de e-mail, LinkedIn, anúncio.

## 10. Dependências e próximos JTBDs

Este JTBD-01 cobre a **primeira etapa do funil** (atrair + nutrir).

Conecta com:

- **JTBD-02 (Comercial)** — converter lead em contrato. O que o Marketing entrega é o input do JTBD-02.
- **JTBD-03 (CS)** — reter o cliente depois que fechou. Usa os mesmos conceitos de régua, mas aplicado pós-venda.

Próximo a escrever: **JTBD-02 Comercial**.
