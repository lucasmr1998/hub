# Assistente CRM — Configuracao

Tres camadas de configuracao: global (HQ), por tenant (cliente), e o fluxo vinculado.

---

## ConfiguracaoAssistenteGlobal (singleton)

Configuracao do numero Hubtrix. Compartilhada entre todos os tenants.

| Campo | Descricao |
|-------|-----------|
| `integracao_whatsapp` | `IntegracaoAPI` do numero Hubtrix (Uazapi) |
| `ativo` | Toggle global |
| `mensagem_boas_vindas` | Template com `{nome}` |
| `mensagem_acesso_restrito` | Resposta para numeros nao cadastrados |

---

## ConfiguracaoAssistenteTenant (por tenant)

Configuracao especifica do tenant que habilita o assistente para seus vendedores.

| Campo | Descricao |
|-------|-----------|
| `integracao_ia` | Provider IA (OpenAI, Anthropic, Groq) |
| `modelo_ia` | Modelo (default: `gpt-4o-mini`) |
| `ativo` | Toggle por tenant |

---

## FluxoAtendimento vinculado

O fluxo de atendimento que o assistente executa:

- Fluxo de atendimento **no tenant Aurora HQ** (nao no tenant do vendedor)
- Pode ser vinculado ao `CanalInbox` via `canal.fluxo`
- Alternativa: encontrado por nome (icontains 'assistente')
- Deve conter um nodo `ia_agente` com tools CRM habilitadas via checkboxes `[CRM]`

Ver [fluxos/](../fluxos/) para como configurar o fluxo e [tools.md](tools.md) para quais tools habilitar.
