---
name: "Biblioteca de templates prontos (fluxos + réguas + automações)"
description: "Pack de templates pre-configurados pra ISPs comecarem a operar rapido sem precisar montar tudo do zero"
prioridade: "🟡 Média"
responsavel: "PM + Tech + Copy"
---

# Biblioteca de templates prontos — 17/04/2026

**Data:** 17/04/2026
**Responsável:** PM + Tech + Copy
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Descrição

Durante a jornada de A2, vários estágios apontaram "infra existe, mas cliente precisa configurar a régua/fluxo/automação do zero". Isso é atrito de onboarding e barreira pra tirar valor do produto.

Solução: **biblioteca de templates oficiais do Hubtrix** — o cliente escolhe do catálogo, clica "importar", customiza o que for necessário. Zero do zero.

Surgiu de A2 estágios 7 (Onboarding), 9 (Retenção), 10 (Upsell) em `PRODUTO/VISAO.md`.

---

## Templates identificados como faltantes

### Fluxos de atendimento

- Qualificação genérica de lead (nome, cidade, plano, viabilidade) — substitui o "fluxo do zero"
- Bot de suporte (FAQ + transferência pra humano se não resolveu)
- Captação de indicação (lead que veio de member-get-member)
- Pós-venda / welcome (após contrato fechado)

### Réguas de automação (marketing/automacoes)

- Boas-vindas pós-ativação (5 mensagens ao longo de 30 dias)
- Lembrete de documentos pendentes (quando lead fica parado em cadastro)
- Follow-up de lead sem resposta (3 tentativas em 7 dias)
- Aniversário de contrato (1 ano, 2 anos de cliente)
- Retenção pra inadimplência (grace period)
- Upsell: cliente em plano básico há > 6 meses

### Segmentos padrão (CRM)

- Leads quentes (score ≥ 7, últimos 30 dias)
- Leads frios (sem contato há > 60 dias)
- Clientes VIP (ticket acima da média)
- Clientes em risco de churn (score < 40)

---

## Tarefas

### Infraestrutura
- [ ] Modelo `TemplateBiblioteca` (tipo: fluxo/regua/segmento, nome, descrição, autor)
- [ ] UI de "Catálogo de templates" em cada módulo (botão "Importar de template")
- [ ] Import que clona nodos/conexões/regras dentro do tenant do cliente (preservando customização futura)
- [ ] Versionamento de templates (o Hubtrix atualiza o template oficial, cliente decide se atualiza o próprio)
- [ ] Possibilidade do cliente publicar templates próprios como privados do tenant

### Conteúdo
- [ ] Escrever os 4 fluxos de atendimento iniciais (PM + Copy)
- [ ] Escrever as 6 réguas de automação (PM + Copy)
- [ ] Escrever os 4 segmentos padrão
- [ ] Revisão de mensagens pra alinhar com o [OPERACIONAL/materiais/reguas/](../OPERACIONAL/materiais/reguas/) já existente

### Onboarding
- [ ] Wizard de primeira configuração: "escolha o que quer importar" no primeiro login
- [ ] Botão "Importar templates recomendados" no dashboard do admin

---

## Impacto esperado

- Tempo de primeira operação reduzido drasticamente
- Cliente tira valor do produto no primeiro dia em vez de no primeiro mês
- Redução de ticket de suporte tipo "como configurar X"
- Hubtrix captura expertise (melhores práticas acumuladas) e distribui
