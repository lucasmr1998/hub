# Régua de Conversão do Trial — AuroraISP
**Canal:** WhatsApp, E-mail, Notificação no sistema
**Duração:** 14 dias
**Lógica:** Orientada por comportamento. Dois trilhos a partir do D+1.
**Objetivo:** Fazer o cliente usar a ferramenta, mostrar resultados e converter para pagante.

---

## Etapa comum — todos os prospects

| Dia | Gatilho | Objetivo | Canal |
|-----|---------|----------|-------|
| D+0 | Trial ativado | Boas-vindas, orientar primeiro passo, criar expectativa dos 14 dias | E-mail |

---

## Bifurcação — D+1

```
D+0 — E-mail de boas-vindas (todos)
         ↓
D+1 — Primeiro acesso detectado?
    ├── SIM → Trilho Ativo
    └── NÃO → Trilho Inativo
```

---

## Trilho Ativo — usou o sistema

| Dia | Gatilho | Objetivo | Canal |
|-----|---------|----------|-------|
| D+0 | Trial ativado | Boas-vindas e orientação inicial | E-mail |
| D+1 ⚡ | Primeiro lead processado | Celebrar, mostrar o dado gerado em tempo real | Notificação no sistema |
| D+3 | Usando ativamente | Relatório: leads processados, conversões, tempo economizado | E-mail |
| D+7 | Usando | Mostrar funcionalidade que ainda não usou. Ampliar valor percebido | E-mail |
| D+10 | — | "Você já viu o resultado. Vamos garantir a continuidade?" | WhatsApp (parceiro) |
| D+12 | — | Oferta de fechamento com urgência | WhatsApp (parceiro) + E-mail |
| D+14 | — | Encerramento formal. Proposta de contrato | E-mail + Notificação |

---

## Trilho Inativo — não usou o sistema

| Dia | Gatilho | Objetivo | Canal |
|-----|---------|----------|-------|
| D+0 | Trial ativado | Boas-vindas e orientação inicial | E-mail |
| D+1 | Não logou | Verificar se teve algum problema técnico para começar | WhatsApp (PMM) |
| D+3 | Ainda inativo | Oferecer sessão de ativação assistida ao vivo | WhatsApp (PMM) |
| D+5 | Ainda inativo | Entender o motivo — pergunta direta e sem julgamento | WhatsApp (PMM) |
| D+7 | Ainda inativo | Última tentativa de ativação com argumento de urgência | E-mail + WhatsApp (PMM) |
| D+10 | — | Parceiro entra para entender, desbloquear e tentar salvar | WhatsApp (parceiro) |

---

## Convergência — D+10 em diante (ambos os trilhos)

| Dia | Objetivo | Canal |
|-----|----------|-------|
| D+10 | Parceiro faz contato comercial. Ativo: fechar. Inativo: entender e desbloquear | WhatsApp (parceiro) |
| D+12 | Urgência. 2 dias restantes. Oferta de fechamento | WhatsApp (parceiro) + E-mail |
| D+14 | Encerramento. Converter ou mover para nurturing de longo prazo | E-mail + Notificação |

---

## Pós-trial — não converteu

Quem chega ao D+14 sem converter entra na **Régua de Recuperação Pós-Trial** (a definir separadamente).

> A oferta especial é reservada para o pós-trial. Durante os 14 dias o foco é ativação e valor, não desconto. Quem já conhece o produto e não converteu é o candidato ideal para uma oferta de reentrada.

---

## Pendências

- [ ] Escrever os textos de cada mensagem por canal
- [ ] Definir ferramenta que detecta uso/não uso para bifurcar os trilhos
- [ ] Criar Régua de Recuperação Pós-Trial com oferta especial
