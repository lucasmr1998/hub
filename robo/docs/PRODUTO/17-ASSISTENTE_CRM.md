# Assistente CRM via WhatsApp — Hubtrix

**Ultima atualizacao:** 12/04/2026
**Status:** 📋 Planejado
**Localizacao:** `apps/comercial/atendimento/engine.py` + `apps/inbox/`

---

## Visao Geral

Agente IA operacional acessivel via WhatsApp que permite usuarios do sistema executar acoes no CRM por conversa natural. Funciona como um "copilot" para vendedores que estao em campo ou no celular.

```
Vendedor (WhatsApp) → Numero dedicado → Uazapi → Inbox
    → Identifica usuario por telefone
    → Roteia para fluxo Assistente CRM (ia_agente)
    → Agente IA com tools de CRM
    → Executa acao → Responde
```

---

## Principios

1. **Numero dedicado:** nao e o numero comercial do provedor. E um numero separado so para o assistente.
2. **Acesso restrito:** so usuarios do sistema (identificados por telefone) podem usar.
3. **Conversa natural:** o vendedor fala como falaria com um colega. A IA interpreta e executa.
4. **Auditoria total:** cada acao gera log com quem fez, o que fez e quando.
5. **Tenant isolado:** cada usuario so ve/modifica dados do seu tenant.

---

## Fluxo de Identificacao

```
Mensagem chega no webhook
    |
    v
Buscar PerfilUsuario onde telefone = remetente
    |
    +-- Encontrou usuario ativo
    |       → Setar contexto (user, tenant)
    |       → Rotear para fluxo do Assistente CRM
    |
    +-- Nao encontrou
            → Responder: "Este numero e de uso exclusivo para
               usuarios do sistema Hubtrix."
            → Encerrar (nao cria lead)
```

---

## Tools Disponíveis (Fase 1)

### consultar_lead
- **Input:** nome ou telefone (busca parcial)
- **Output:** dados do lead (nome, telefone, email, score, status, oportunidade)
- **Exemplo:** "Busca o lead Maria" → retorna dados da Maria

### listar_oportunidades
- **Input:** filtro opcional (estagio, responsavel)
- **Output:** lista de oportunidades com nome, valor, estagio
- **Exemplo:** "Minhas oportunidades em negociacao"

### mover_oportunidade
- **Input:** identificador do lead + estagio destino
- **Output:** confirmacao + cria HistoricoPipelineEstagio
- **Exemplo:** "Move Maria para Proposta Enviada"

### criar_nota
- **Input:** identificador do lead + texto da nota
- **Output:** confirmacao
- **Exemplo:** "Nota na Maria: pediu desconto de 10%"

### criar_tarefa
- **Input:** identificador do lead + titulo + vencimento (opcional)
- **Output:** confirmacao com data
- **Exemplo:** "Tarefa pro Joao: ligar amanha 10h"

### atualizar_lead
- **Input:** identificador do lead + campo + valor
- **Output:** confirmacao
- **Exemplo:** "Atualiza email do Joao para joao@empresa.com"

### resumo_pipeline
- **Input:** nenhum
- **Output:** metricas do pipeline (oportunidades por estagio, valor total)
- **Exemplo:** "Como esta meu pipeline?"

---

## Seguranca

| Camada | Mecanismo |
|--------|-----------|
| Autenticacao | Telefone do remetente = PerfilUsuario.telefone |
| Autorizacao | Todas as queries filtradas por tenant do usuario |
| Auditoria | LogSistema com categoria 'assistente' |
| Isolamento | TenantMixin em todas as operacoes |

---

## Fases de Desenvolvimento

| Fase | Escopo | Status |
|------|--------|--------|
| 1 | Infraestrutura (canal, identificacao, fluxo) | 📋 Planejado |
| 2 | Tools CRM (7 tools) | 📋 Planejado |
| 3 | UX (boas vindas, erros, confirmacoes) | 📋 Planejado |
| 4 | Expansao (Inbox, Suporte, Marketing) | 📋 Futuro |

---

## Decisoes Tecnicas

- **Engine:** reutiliza `_chamar_llm_com_tools` do engine de atendimento
- **Canal:** canal Inbox dedicado com integracao Uazapi separada
- **Fluxo:** fluxo de atendimento normal com no ia_agente
- **Identificacao:** logica no webhook do Inbox, antes de criar lead
- **Tools:** registradas como tools do sistema no engine (mesmo padrao de atualizar_lead)
