# Gigamax

**Status:** Onboarding — fase de discovery
**Data de abertura da pasta:** 23/04/2026
**Última atualização:** 23/04/2026

---

## Dados da empresa

- **Nome fantasia:** Gigamax
- **Razão social:** (a preencher)
- **CNPJ:** (a preencher)
- **Inscrição Estadual:** (a preencher)
- **Inscrição Municipal:** (a preencher)
- **Endereço:** (a preencher)
- **CEP:** (a preencher)
- **Site:** (a preencher)
- **Leads na base:** (a preencher)
- **Vendas digitais estimadas/mês:** (a preencher)

---

## Contato

- **E-mail:** (a preencher)
- **Telefone:** (a preencher)
- **Contato principal:** (nome + cargo — a preencher)
- **Contato técnico:** João Ferreira (responsável pela integração técnica SGP)

---

## Stack e integrações

- **ERP:** **SGP (inSystem)** — primeiro cliente Hubtrix com este ERP
- **Outros sistemas:** (a confirmar)
- **WhatsApp provider:** (Uazapi / Evolution / Matrix — a confirmar)
- **IA provider:** (OpenAI / Anthropic / Groq / Google AI — a confirmar)

> Detalhes técnicos da integração SGP em [integracoes.md](integracoes.md).
> Especificação do adapter em [../../../PRODUTO/integracoes/05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md).

---

## Plano e contratação

### Módulos contratados

- (a confirmar — definir quais módulos do Hubtrix fazem parte do escopo: Comercial, Marketing, CS, Inbox, Suporte)

### Valores negociados

- (a preencher após fechamento comercial)

### Variáveis

- (a preencher — modelo híbrido fixo + variável, seguindo padrão dos demais clientes)

### Total mensal estimado

- (a preencher)

- **Data de contratação:** (a preencher)
- **Prazo:** (a preencher)
- **Aviso prévio (rescisão):** (a preencher)
- **Primeiro pagamento:** (a preencher)
- **Ciclo de cobrança:** (a preencher)

---

## Configuração específica

- **Tenant slug:** `gigamax` (a confirmar no provisionamento)
- **Domínio do painel:** (a preencher, se houver)
- **Customizações feitas:** listar em [implementacoes/](implementacoes/)

---

## Histórico

- 23/04/2026 — Abertura da pasta. ERP identificado (SGP). Discovery técnico pendente.
- 23/04/2026 — João Ferreira (técnico Gigamax) compartilhou documentação da API SGP (Postman) e token de acesso. Token guardado fora do repo; endpoints em mapeamento.
- Reuniões → (criar subpasta `reunioes/` quando houver primeira call)
- Implementações → [implementacoes/](implementacoes/)

---

## Observações

- **Primeiro cliente Hubtrix com SGP (inSystem).** Toda a integração técnica será construída do zero seguindo o [guia de integração de novo ERP](../../../PRODUTO/integracoes/04-GUIA-NOVA-INTEGRACAO-ERP.md).
- Adapter `SGPService` ainda **não existe**. Discovery técnico precisa acontecer antes da implementação.
- Tarefa de discovery ativa: [discovery_sgp_gigamax_23-04-2026.md](../../tarefas/backlog/discovery_sgp_gigamax_23-04-2026.md).
