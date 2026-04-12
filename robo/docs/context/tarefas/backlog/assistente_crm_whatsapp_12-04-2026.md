---
name: "Assistente CRM via WhatsApp"
description: "Agente IA operacional que permite usuarios do sistema executar acoes no CRM via WhatsApp"
prioridade: "🔴 Alta"
responsavel: "Tech Lead + PM"
---

# Assistente CRM via WhatsApp — 12/04/2026

**Data:** 12/04/2026
**Responsavel:** Tech Lead + PM
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

Numero de WhatsApp dedicado (nao comercial) conectado via Uazapi que funciona como assistente operacional para usuarios do sistema. O vendedor manda mensagem e o agente IA executa acoes dentro do CRM: mover oportunidades, criar notas, consultar pipeline, etc.

---

## Arquitetura

```
Vendedor manda WhatsApp (numero dedicado do assistente)
    |
    v
Uazapi recebe -> Webhook -> Inbox
    |
    v
Identifica usuario pelo telefone (PerfilUsuario.telefone)
    |
    +-- NAO encontrou usuario -> "Acesso restrito a usuarios do sistema"
    |
    +-- Encontrou usuario ativo ->
            |
            v
        Roteia para fluxo "Assistente CRM"
        (canal dedicado com fluxo ia_agente)
            |
            v
        Agente IA com tools do CRM
            |
            v
        Executa acao no banco -> Responde confirmando
        (respeitando tenant do usuario)
```

---

## Infraestrutura

### Canal dedicado
- Numero WhatsApp separado (nao o comercial do provedor)
- Canal no Inbox tipo "whatsapp" com provedor "uazapi"
- Integracao Uazapi separada para esse numero
- Fluxo de atendimento vinculado ao canal

### Identificacao do usuario
- Quando mensagem chega no webhook, antes de criar lead:
  - Buscar `PerfilUsuario.telefone` que bate com o remetente
  - Se encontrou usuario ativo: rotear para fluxo do assistente
  - Se nao encontrou: responder "Acesso restrito" e encerrar
- O `request.user` / contexto do agente = usuario identificado
- Tenant = tenant do usuario (via perfil)

### Fluxo de atendimento
- Fluxo normal com no `ia_agente`
- System prompt orientado para assistente operacional
- Tools do sistema habilitadas (novas tools de CRM)
- Pode usar o mesmo engine `_chamar_llm_com_tools`

---

## Tools do Agente (Fase 1 — CRM)

| Tool | Parametros | Acao |
|------|-----------|------|
| `consultar_lead` | nome ou telefone | Busca lead e retorna dados principais |
| `listar_oportunidades` | filtro (estagio, responsavel, status) | Lista oportunidades do pipeline |
| `mover_oportunidade` | lead (nome/telefone), estagio_destino | Move oportunidade para outro estagio |
| `criar_nota` | lead (nome/telefone), texto | Cria nota interna na oportunidade |
| `criar_tarefa` | lead (nome/telefone), titulo, vencimento | Cria tarefa no CRM |
| `atualizar_lead` | lead (nome/telefone), campo, valor | Atualiza campo do lead |
| `resumo_pipeline` | (sem parametros) | Retorna metricas: total por estagio, valor total |

### Exemplos de uso

```
Vendedor: "Quantas oportunidades tenho em negociacao?"
Assistente: "Voce tem 3 oportunidades em Negociacao, totalizando R$ 15.400,00:
  1. Maria Silva — R$ 5.200
  2. Empresa ABC — R$ 7.000
  3. Joao Souza — R$ 3.200"

Vendedor: "Move a Maria Silva para Proposta Enviada"
Assistente: "Pronto! Oportunidade de Maria Silva movida para Proposta Enviada."

Vendedor: "Cria uma nota na Maria: Cliente pediu desconto de 10%"
Assistente: "Nota salva na oportunidade de Maria Silva."

Vendedor: "Cria uma tarefa pro Joao Souza: ligar amanha as 10h"
Assistente: "Tarefa criada: 'ligar amanha as 10h' para Joao Souza, vencimento 13/04/2026."
```

---

## Seguranca

- **Autenticacao:** telefone do remetente deve bater com PerfilUsuario.telefone de usuario ativo
- **Autorizacao:** cada acao filtra pelo tenant do usuario (TenantMixin)
- **Auditoria:** todas as acoes geram LogSistema (categoria 'assistente')
- **Isolamento:** usuario so ve/modifica dados do proprio tenant
- **Rate limit:** considerar limite de acoes por minuto

---

## Tarefas de Implementacao

### Fase 1: Infraestrutura
- [ ] Criar logica de identificacao de usuario por telefone no webhook do inbox
- [ ] Criar canal dedicado "Assistente CRM" no Inbox
- [ ] Criar fluxo de atendimento com no ia_agente configurado
- [ ] System prompt do assistente operacional
- [ ] Tratar caso de usuario nao encontrado (mensagem de acesso restrito)

### Fase 2: Tools do CRM
- [ ] Tool `consultar_lead` no engine
- [ ] Tool `listar_oportunidades` no engine
- [ ] Tool `mover_oportunidade` no engine (com historico de estagio)
- [ ] Tool `criar_nota` no engine
- [ ] Tool `criar_tarefa` no engine
- [ ] Tool `atualizar_lead` (ja existe, adaptar)
- [ ] Tool `resumo_pipeline` no engine

### Fase 3: UX e Polish
- [ ] Mensagem de boas vindas personalizada ("Ola [nome], sou o assistente Hubtrix")
- [ ] Tratamento de erros amigavel ("Nao encontrei nenhum lead com esse nome")
- [ ] Confirmacao antes de acoes destrutivas (mover, atualizar)
- [ ] Historico de conversa persistente por usuario

### Fase 4: Expansao (futuro)
- [ ] Tools de Inbox (transferir conversa, ver fila)
- [ ] Tools de Suporte (abrir ticket, consultar status)
- [ ] Tools de Marketing (disparar campanha, ver metricas)
- [ ] Dashboard de uso do assistente (acoes executadas, usuarios ativos)
- [ ] Comandos rapidos via botoes WhatsApp

---

## Contexto e referencias

- Engine IA: `apps/comercial/atendimento/engine.py`
- Webhook Inbox: `apps/inbox/signals.py` (on_mensagem_recebida_atendimento)
- Tools existentes: `atualizar_lead`, `consultar_base_conhecimento`
- Perfil usuario: `apps/sistema/models.py` (PerfilUsuario.telefone)
- Uazapi service: `apps/integracoes/services/uazapi.py`
- Provider: `apps/inbox/providers/uazapi.py`

---

## Resultado esperado

Vendedor consegue operar o CRM pelo WhatsApp: consultar leads, mover oportunidades, criar notas e tarefas, tudo via conversa natural com o agente IA. Acesso restrito a usuarios do sistema, com auditoria completa.
