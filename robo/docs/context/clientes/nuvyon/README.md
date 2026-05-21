# Nuvyon

**Status:** ✅ Contratado — em implementação
**Data de abertura da pasta:** 17/04/2026
**Última atualização:** 27/04/2026

---

## Dados da empresa

- **Nome fantasia:** Nuvyon
- **Razão social:** Nuvyon Telecomunicações Ltda
- **CNPJ:** 53.309.518/0001-78
- **Inscrição Estadual:** 453.180.099.112
- **Inscrição Municipal:** 9924693
- **Endereço:** Rod. SP-340, km 269, nº 04, Zona Rural — Mococa / SP
- **CEP:** 13749-899
- **Site:** (a preencher)
- **Leads na base:** 10.000
- **Vendas digitais estimadas/mês:** 150

---

## Contato

- **E-mail:** contato@nuvyon.com.br
- **Telefone:** (19) 3656-2753
- **Contato principal:** (nome + cargo — a preencher)
- **Contato técnico:** (se diferente)

---

## Stack e integrações

- **ERP:** HubSoft
- **Outros sistemas:** Matrix
- **WhatsApp provider:** (Uazapi / Evolution — a confirmar)
- **IA provider:** (OpenAI / Anthropic / Groq / Google AI — a confirmar)

---

## Plano e contratação

### Módulos contratados

- **Comercial:** plano **Advanced** (topo de linha)
- **Marketing:** plano **Pro** (tier intermediário)

### Valores negociados (desconto por upgrade de tier)

| Módulo | Plano real | Tabela do plano | Nuvyon paga | Desconto |
|--------|------------|------------------|--------------|----------|
| Comercial Advanced | Advanced | R$ 1.497 | **R$ 997** (preço Pro) | R$ 500 |
| Marketing Pro | Pro | R$ 997 | **R$ 497** (preço Starter) | R$ 500 |
| **Total mensalidade fixa** | | R$ 2.494 | **R$ 1.494** | R$ 1.000 |
| Setup (único) | | R$ 1.200 | **Gratuito** | R$ 1.200 |

> **Modelo de desconto:** cada módulo recebe o **tier acima** pagando o **preço do tier abaixo**. Comercial pega Advanced por preço de Pro, Marketing pega Pro por preço de Starter. Total de R$ 1.000/mês em desconto permanente enquanto vigente o contrato.

### Variáveis

- **Comercial:** R$ 10 por venda finalizada via IA
  - Estimativa: 150 vendas/mês × R$ 10 = **R$ 1.500/mês**
- **Marketing:** R$ 0,05 por **lead cadastrado na plataforma**, por mês
  - Estimativa: 10.000 leads × R$ 0,05 = **R$ 500/mês**

### Total mensal estimado

| Parcela | Valor |
|---------|-------|
| Mensalidade fixa (módulos) | R$ 1.494 |
| Variável Comercial | R$ 1.500 |
| Variável Marketing | R$ 500 |
| **TOTAL MENSAL ESTIMADO** | **R$ 3.494** |

- **Data de contratação:** (a preencher)
- **Prazo:** indeterminado, **sem fidelidade**
- **Aviso prévio (rescisão):** 30 dias
- **Primeiro pagamento:** 30 dias após a instalação/configuração inicial concluídas
- **Ciclo de cobrança:** mensal (ciclo iniciado no primeiro pagamento)

---

## Configuração específica

- **Tenant slug:** `nuvyon`
- **Módulos provisionados:** Comercial (tier `pro` = "Advanced" comercial) + Marketing (tier `start` = "Pro" comercial). CS não contratado.
- **Provisionamento dev:** ✅ feito em 27/04/2026 (tenant id 10 no `aurora_dev`)
- **Provisionamento produção:** ⏳ pendente — rodar os comandos da seção "Provisionamento" abaixo no console do EasyPanel
- **Integração inbound Matrix:** `IntegracaoAPI` tipo `outro`, nome "Matrix Nuvyon". O `api_token` Bearer é gerado pelo comando `gerar_token_api` — **não fica versionado** (credencial). Token de dev e de produção são distintos.
- **Domínio do painel:** (a preencher, se houver)
- **Customizações feitas:** listar em [implementacoes/](implementacoes/)

> ⚠️ **Mapeamento de tier:** o sistema Hubtrix só tem 3 tiers técnicos (`starter`, `start`, `pro`). O vocabulário comercial (Starter / Pro / Advanced) não bate 1:1. Convenção adotada: **"Advanced" comercial = `pro` técnico**; **"Pro" comercial = `start` técnico**. Por isso a Nuvyon foi provisionada com `plano_comercial='pro'` e `plano_marketing='start'`.

### Provisionamento (comandos)

Rodar no console do EasyPanel (produção) — `python manage.py` funciona direto no container do app.

```bash
# 1. Cria tenant + user admin + perfil + ConfiguracaoEmpresa
python manage.py criar_tenant \
    --nome "Nuvyon" --slug "nuvyon" --cnpj "53.309.518/0001-78" \
    --modulos comercial,marketing \
    --tier-comercial pro --tier-marketing start \
    --admin-user admin_nuvyon --admin-email contato@nuvyon.com.br \
    --admin-senha "<DEFINIR_SENHA_FORTE>"

# 2. Gera o token de API inbound pro Matrix consumir as APIs Hubtrix
python manage.py gerar_token_api \
    --tenant nuvyon --nome "Matrix Nuvyon" --tipo outro
```

O passo 2 imprime o `API TOKEN`. Esse token vai no header `Authorization: Bearer <token>` de toda chamada do Matrix ao Hubtrix. Guardar em local seguro (gerenciador de senhas) — **não colar em doc versionada nem em chat**.

---

## Histórico

- Reuniões → [reunioes/](reunioes/)
- Implementações → [implementacoes/](implementacoes/)

---

## Observações

- Proposta contempla os 2 módulos comerciais principais do Hubtrix (Comercial + Marketing), com cada módulo recebendo **o tier superior ao que paga** (Comercial Advanced pelo valor Pro; Marketing Pro pelo valor Starter).
- Setup gratuito. Desconto permanente de R$ 1.000/mês na mensalidade fixa enquanto vigente.
- Modelo híbrido (fixo + variável) significa que **o faturamento cresce conforme o uso real do cliente**: quanto mais vendas a IA fecha e mais leads cadastrados, maior a receita do Hubtrix.
- **Contrato sem fidelidade.** Rescisão por qualquer parte com aviso prévio de 30 dias.
- **Variável Marketing:** a base de cobrança são **leads cadastrados na plataforma** (não contatos em WhatsApp genérico ou assinantes ativos).

---

## 🚨 Correção pendente no contrato

O contrato gerado pelo Jurídico AI descreveu os planos **invertidos**:

- ❌ Cláusula 2.2.1 diz "Comercial — plano **PRO**" → deveria ser "plano **Advanced**"
- ❌ Cláusula 2.2.2 diz "Marketing — plano **Advanced**" → deveria ser "plano **Pro**"

Antes de assinar, corrigir essas cláusulas + adicionar cláusula de desconto promocional deixando claro:
- Comercial Advanced pago como Pro (R$ 500 de desconto)
- Marketing Pro pago como Starter (R$ 500 de desconto)
- Descontos mantidos enquanto vigente; em renovação/alteração retornam à tabela cheia.
