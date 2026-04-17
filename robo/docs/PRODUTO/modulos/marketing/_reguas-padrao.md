# 11. Marketing — Réguas Padrão

**Status:** 📋 Especificação para desenvolvimento
**Última atualização:** 26/03/2026

---

## Contexto

O módulo de Marketing é o motor de automação do hub AuroraISP. Além de permitir que o provedor crie fluxos customizados, ele entrega **réguas padrão prontas** organizadas por jornada — o provedor ativa, configura os dados básicos e começa a usar.

Canais disponíveis: **WhatsApp** e **E-mail**

---

## Arquitetura das réguas

```
Gatilho (trigger)
      ↓
Condição (filtro opcional)
      ↓
Ação (mensagem WhatsApp / e-mail / tag / notificação interna)
      ↓
Aguardar (tempo ou evento)
      ↓
Próxima ação ou fim do fluxo
```

---

## Réguas do Comercial

Fluxos de automação para a etapa de atração e conversão de leads.

---

### C01 — Boas-vindas ao Lead
**Gatilho:** Lead cadastrado na plataforma
**Canal:** WhatsApp
**Objetivo:** Confirmar recebimento e iniciar qualificação

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Enviar mensagem de boas-vindas com nome do lead | Imediato |
| 2 | Iniciar fluxo de qualificação (bot) | Imediato |

---

### C02 — Follow-up de Lead Sem Resposta
**Gatilho:** Lead qualificado sem resposta após X horas
**Canal:** WhatsApp
**Objetivo:** Reengajar lead que parou de responder

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Enviar mensagem de follow-up (tom leve) | 4h sem resposta |
| 2 | Enviar segunda tentativa | 24h sem resposta |
| 3 | Notificar vendedor para contato manual | 48h sem resposta |
| 4 | Mover lead para status "Frio" | 72h sem resposta |

---

### C03 — Lembrete de Documentos Pendentes
**Gatilho:** Lead com documentos solicitados e não enviados após X horas
**Canal:** WhatsApp
**Objetivo:** Reduzir abandono na etapa de documentação

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Lembrete amigável de documentos pendentes | 2h sem envio |
| 2 | Segundo lembrete com lista dos docs faltantes | 24h sem envio |
| 3 | Notificar vendedor | 48h sem envio |

---

### C04 — Nutrição de Lead Frio
**Gatilho:** Lead marcado como "Frio" sem conversão
**Canal:** WhatsApp + E-mail
**Objetivo:** Manter relacionamento e reativar interesse

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Enviar conteúdo de valor (dica, novidade do provedor) | 7 dias |
| 2 | Enviar oferta ou promoção ativa | 15 dias |
| 3 | Última tentativa de reativação | 30 dias |
| 4 | Arquivar lead se sem resposta | 45 dias |

---

### C05 — Recuperação de Lead Perdido
**Gatilho:** Lead marcado como "Perdido" no CRM
**Canal:** WhatsApp
**Objetivo:** Reabrir oportunidade após período de descanso

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Pausa no contato | 30 dias |
| 2 | Recontato com nova abordagem ou oferta | 30 dias |
| 3 | Se sem resposta, arquivar definitivamente | 15 dias após recontato |

---

### C06 — Confirmação de Instalação Agendada
**Gatilho:** Instalação agendada no HubSoft
**Canal:** WhatsApp
**Objetivo:** Reduzir no-show e preparar o cliente

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Confirmação do agendamento com data e hora | Imediato |
| 2 | Lembrete 1 dia antes | D-1 |
| 3 | Lembrete 2h antes | D0 -2h |

---

## Réguas do CS

Fluxos de automação para a etapa de retenção e fidelização pós-venda. Rodam via Marketing.

---

### CS01 — Boas-vindas Pós-Ativação
**Gatilho:** Cliente ativado no HubSoft
**Canal:** WhatsApp + E-mail
**Objetivo:** Onboarding do novo cliente, reduzir churn nos primeiros 30 dias

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Mensagem de boas-vindas com dados do plano | Imediato |
| 2 | Dicas de uso do serviço | D+3 |
| 3 | Verificação de satisfação (está tudo funcionando?) | D+7 |
| 4 | Convite para o Clube de Benefícios | D+15 |

---

### CS02 — NPS — Pesquisa de Satisfação
**Gatilho:** X dias após ativação ou em data recorrente
**Canal:** WhatsApp
**Objetivo:** Medir satisfação e identificar clientes insatisfeitos antes do churn

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Enviar pergunta NPS (nota de 0 a 10) | D+30 após ativação |
| 2a | Se nota 9-10: pedir indicação | Imediato |
| 2b | Se nota 7-8: agradecer e monitorar | Imediato |
| 2c | Se nota 0-6: notificar CS para contato urgente | Imediato |
| 3 | Repetir a cada 90 dias | Recorrente |

---

### CS03 — Prevenção de Churn
**Gatilho:** Cliente com fatura em atraso há X dias ou NPS baixo
**Canal:** WhatsApp
**Objetivo:** Intervir antes do cancelamento

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Mensagem de suporte proativo (tudo bem?) | 1 dia após gatilho |
| 2 | Oferta de negociação ou plano alternativo | 3 dias |
| 3 | Notificar CS para contato humano | 5 dias |

---

### CS04 — Upsell de Plano
**Gatilho:** Cliente no plano básico há X meses sem reclamação
**Canal:** WhatsApp + E-mail
**Objetivo:** Aumentar ticket médio de clientes satisfeitos

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Mensagem apresentando plano superior com benefícios | 90 dias após ativação |
| 2 | Follow-up com oferta especial (desconto por tempo limitado) | 7 dias depois |
| 3 | Última chamada para upgrade | 7 dias depois |

---

### CS05 — Venda de SVA (Serviços de Valor Agregado)
**Gatilho:** Cliente ativo há X dias sem SVA contratado
**Canal:** WhatsApp
**Objetivo:** Aumentar receita por cliente com serviços adicionais (streaming, antivírus, backup, etc.)

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Apresentar SVA disponível com benefício claro | 60 dias após ativação |
| 2 | Follow-up com período de teste grátis (se disponível) | 7 dias depois |
| 3 | Lembrete de encerramento do período de teste | D-2 do fim do teste |

---

### CS06 — Reativação de Cliente Cancelado
**Gatilho:** Contrato cancelado no HubSoft
**Canal:** WhatsApp
**Objetivo:** Recuperar cliente cancelado após período de respiro

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Pausa — sem contato | 30 dias |
| 2 | Mensagem de recontato com oferta especial | D+30 |
| 3 | Follow-up final | 7 dias depois |
| 4 | Arquivar se sem resposta | 15 dias depois |

---

### CS07 — Programa de Indicação
**Gatilho:** Cliente com NPS 9 ou 10, ou X meses ativo sem reclamação
**Canal:** WhatsApp
**Objetivo:** Gerar leads via base de clientes satisfeitos

| Passo | Ação | Tempo |
|-------|------|-------|
| 1 | Convidar para programa de indicação com benefício claro | Imediato após gatilho |
| 2 | Enviar link ou código de indicação | Imediato |
| 3 | Notificar quando indicação converter | Automático |
| 4 | Entregar benefício ao indicador | Automático após ativação do indicado |

---

## Réguas de Marketing (campanhas e tráfego)

---

### M01 — Rastreamento de Origem de Lead
**Gatilho:** Lead captado via campanha (Facebook, Google, Instagram, etc.)
**Ação:** Tag automática de origem + campanha + UTM no cadastro do lead
**Objetivo:** Atribuição correta para otimização com IA

---

### M02 — Alerta de Performance de Campanha
**Gatilho:** Campanha com CPL acima do benchmark ou taxa de conversão abaixo do esperado
**Canal:** Notificação interna + E-mail para responsável
**Objetivo:** Alertar gestor para ajuste de campanha com sugestão da IA

---

### M03 — Campanha Sazonal
**Gatilho:** Data configurada (Black Friday, volta às aulas, etc.)
**Canal:** WhatsApp + E-mail
**Objetivo:** Disparo em massa para base segmentada com oferta sazonal

---

## Resumo das réguas

| Código | Nome | Módulo | Canal | Status |
|--------|------|--------|-------|--------|
| C01 | Boas-vindas ao Lead | Comercial | WhatsApp | 📋 A desenvolver |
| C02 | Follow-up Sem Resposta | Comercial | WhatsApp | 📋 A desenvolver |
| C03 | Documentos Pendentes | Comercial | WhatsApp | 📋 A desenvolver |
| C04 | Nutrição de Lead Frio | Comercial | WhatsApp + E-mail | 📋 A desenvolver |
| C05 | Recuperação de Lead Perdido | Comercial | WhatsApp | 📋 A desenvolver |
| C06 | Confirmação de Instalação | Comercial | WhatsApp | 📋 A desenvolver |
| CS01 | Boas-vindas Pós-Ativação | CS | WhatsApp + E-mail | 📋 A desenvolver |
| CS02 | NPS | CS | WhatsApp | 📋 A desenvolver |
| CS03 | Prevenção de Churn | CS | WhatsApp | 📋 A desenvolver |
| CS04 | Upsell de Plano | CS | WhatsApp + E-mail | 📋 A desenvolver |
| CS05 | Venda de SVA | CS | WhatsApp | 📋 A desenvolver |
| CS06 | Reativação de Cancelado | CS | WhatsApp | 📋 A desenvolver |
| CS07 | Programa de Indicação | CS | WhatsApp | 📋 A desenvolver |
| M01 | Rastreamento de Origem | Marketing | Interno | 📋 A desenvolver |
| M02 | Alerta de Performance | Marketing | Notificação + E-mail | 📋 A desenvolver |
| M03 | Campanha Sazonal | Marketing | WhatsApp + E-mail | 📋 A desenvolver |

---

## SVAs suportados (CS05)

Serviços de valor agregado que os provedores costumam oferecer:

- Streaming (Netflix, Paramount, etc.)
- Antivírus
- Backup em nuvem
- Segurança kids (controle parental)
- Rastreamento veicular
- Energia solar
- Plano de saúde

---

## Configurações do administrador

- **Benefício do programa de indicação (CS07):** configurável pelo administrador do provedor
- **Aprovação humana nos fluxos:** configurável por etapa. Alguns passos exigem intervenção humana. O sistema deve suportar esse controle por fluxo.

---

## Pendências

- [ ] Definir tempo padrão de atraso que aciona a prevenção de churn (CS03)
- [ ] Mapear quais etapas de cada fluxo precisam de aprovação humana por padrão
