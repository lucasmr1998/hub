# Visao do Produto — Hubtrix

**Status:** Em construcao (17/04/2026)
**Proposito:** Documento fundacional. Toda decisao de produto, marketing e roadmap deve se apoiar nele.

Este doc responde 4 perguntas, em ordem do concreto ao abstrato:

- **A. Jornada end-to-end** — quem passa pelo Hubtrix, em que ordem, em que estados
  - A2. Jornada do consumidor (cliente-do-cliente)
  - A1. Jornada do ISP usando o Hubtrix
- **B. Modelo mental do usuario** — como o operador do Hubtrix pensa no dia a dia
- **C. Como os modulos se conectam** — fluxo de dados e eventos entre as partes
- **D. Principios** — o que o Hubtrix E, o que NAO E

Cada secao e conversada, validada com o time e atualizada conforme o produto evolui.

---

## A. Jornada end-to-end

### A2. Jornada do consumidor (cliente-do-cliente)

> Em construcao — sessao 17/04/2026.
>
> **Nota:** estagios 5-6 (Fechamento e Ativacao) usam a arquitetura de integracao
> com ERP definida em [secao C](#c-como-os-modulos-se-conectam) e [secao D](#d-principios-do-produto).

### A1. Jornada do ISP usando o Hubtrix

> Pendente. Depois de A2.

---

## B. Modelo mental do usuario

> Pendente.

---

## C. Como os modulos se conectam

> Secao em construcao. Decisoes batidas ate agora:

### Integracao com ERPs

Hubtrix nao fala com um ERP "generico". Cada ERP tem seu proprio servico dedicado em `apps/integracoes/<erp>/`, com liberdade de modelar o ERP do jeito que ele e (sem interface comum forte que forca abstracao vazante).

**Topologia:**

```
Oportunidade ganha
    │
    ▼
Dispatcher por tenant.erp_ativo
    │
    ├─ hubsoft → apps/integracoes/hubsoft/  (pronto)
    ├─ sgp     → apps/integracoes/sgp/      (proximo)
    ├─ ixc     → apps/integracoes/ixc/      (futuro)
    └─ mk      → apps/integracoes/mk/       (futuro)
```

**Entrada (venda → ERP):** dispatcher encaminha payload normalizado ao servico correto; servico chama API do ERP pra criar cliente/contrato.

**Retorno (ERP → Hubtrix):**

- Webhook dedicado por ERP pra confirmacao pontual (ex: contrato criado, `contrato_<erp>_id` preenchido)
- Sync periodico em 3 camadas (ver abaixo) pra manter espelho atualizado

### Espelho do cliente ativo

Depois que a venda vira contrato no ERP, Hubtrix **mantem um espelho completo** dos dados do cliente. Espelho e **passivo**: ERP e a fonte da verdade, Hubtrix so le. Qualquer edicao de contrato/cobranca passa pelo ERP, nao pelo Hubtrix.

**Sync em 3 camadas com frequencias diferentes:**

| Camada | Conteudo | Frequencia | Justificativa |
|--------|----------|-------------|---------------|
| **Core** | Nome, contato, plano ativo, status, vencimento, inadimplencia | Cron 15min | Dashboard e alertas precisam de dado fresco |
| **Contratual** | Contratos, alteracoes de plano, mudanca de endereco | Cron 1h | Muda pouco, defasagem aceitavel |
| **Historico** | Faturas, tickets ERP, logs, consumo | Cron diario (noturno) ou on-demand | Volume alto, uso pontual |

**Regras de sync:**

- **Delta sync obrigatorio** — cada cron pega so o que mudou desde o ultimo
- **Primeira carga de tenant novo** e batch completo (pode levar horas)
- **Sem webhook primario** como caminho de sync — so webhooks pontuais em eventos criticos (contrato criado). Futuramente da pra adicionar webhook pra Core se defasagem de 15min virar problema.

### Modelo `Cliente` no Hubtrix

Novo model que surge dessa decisao: `Cliente` (distinto de `LeadProspecto`). Lead vira Cliente quando a venda fecha e o ERP confirma o contrato. Lead e "pre-venda"; Cliente e "pos-venda" espelhado do ERP.

---

## D. Principios do produto

> Secao em construcao. Principios batidos ate agora:

### 1. Hubtrix e front-office; ERP e back-office

Hubtrix cuida da jornada pre-venda (lead, atendimento, qualificacao, CRM, fechamento) e do relacionamento pos-venda (atendimento continuo, retencao, clube, indicacao). **Nao substitui o ERP** e nao assume funcoes de back-office (cobranca, provisionamento tecnico, contratacao fiscal). Hubtrix orquestra o que vem antes e ao lado do ERP.

### 2. Apos o contrato, a verdade vive no ERP

O ERP e fonte da verdade sobre o cliente ativo. Hubtrix espelha passivamente — le, exibe, analisa. Nao edita dados contratuais/fiscais fora do ERP. Quem quer mudar plano ou endereco passa pelo ERP; Hubtrix sincroniza o resultado.

### 3. Servico dedicado por ERP (sem abstracao universal)

ERPs sao muito diferentes entre si (HubSoft, SGP, IXC, MK, Voalle, ...). Forcar uma interface comum gera abstracoes vazantes e bugs sutis. Cada ERP ganha seu proprio modulo com liberdade de modelar do jeito que ele e. A "interface comum" fica so no ponto de entrada: "qual ERP este tenant usa? chama o servico correspondente."

### 4. Espelho completo, mas em camadas

Hubtrix espelha tudo do cliente ativo do ERP (contratual, faturas, tickets, historico). Mas sync e organizado em camadas: Core (15min), Contratual (1h), Historico (diario). Delta sync obrigatorio. Isso evita sobrecarga mantendo a promessa de dashboard rico sem depender de chamar o ERP toda hora.

### 5. Multi-tenant por natureza

Tudo no Hubtrix e multi-tenant. Nenhum dado vaza entre tenants. Isso e invariante, nao feature.
