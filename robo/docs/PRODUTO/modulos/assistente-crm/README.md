# Assistente CRM (via WhatsApp)

**Status:** Funcional (Engine standalone + Fluxo)
**App:** `apps/assistente/` + reusa engine de [atendimento/](../atendimento/)

Agente IA operacional acessivel via WhatsApp que permite usuarios do sistema executarem acoes no CRM por conversa natural. Funciona como "copilot" para vendedores em campo ou no celular.

```
Vendedor (WhatsApp) → Numero dedicado Hubtrix → Uazapi → Webhook
    → Identifica usuario por telefone (PerfilUsuario)
    → Cria/continua Conversa no Inbox (modo_atendimento='assistente')
    → Busca FluxoAtendimento vinculado ao canal
    → Engine de fluxo processa (ia_agente com tools CRM)
    → Resposta salva no Inbox + enviada via WhatsApp
    → Fallback: engine standalone se nao tem fluxo
```

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [configuracao.md](configuracao.md) | ConfiguracaoAssistenteGlobal + Tenant + FluxoAtendimento vinculado |
| [tools.md](tools.md) | 15 tools CRM disponiveis no ia_agente |

---

## Arquitetura

### App `apps/assistente/`

| Arquivo | Funcao |
|---------|--------|
| `views.py` | Webhook, identificacao, orquestrador Inbox + Fluxo |
| `engine.py` | Engine standalone (fallback se nao tem fluxo) |
| `tools.py` | 15 tools CRM (`TOOLS_ASSISTENTE` dict) |
| `models.py` | ConfiguracaoAssistenteGlobal, ConfiguracaoAssistenteTenant |

### Fluxo de processamento

1. **Webhook** (`/assistente/webhook/<api_token>/`) recebe mensagem do Uazapi
2. **Identificacao**: busca PerfilUsuario por telefone (match exato + limpo)
3. **Validacao**: `ConfiguracaoAssistenteGlobal.ativo` + `ConfiguracaoAssistenteTenant.ativo`
4. **Inbox**: cria/busca Conversa no tenant Aurora HQ com `modo_atendimento='assistente'`
5. **Engine de fluxo** (prioridade):
   - Busca FluxoAtendimento vinculado ao CanalInbox ou por nome
   - Busca/cria AtendimentoFluxo sem lead (`lead=NULL`)
   - Armazena contexto em `dados_respostas`: `_assistente_usuario_id`, `_assistente_tenant_id`, `_conversa_id`, `_telefone`
   - Chama engine: `iniciar_fluxo_visual` (primeira msg) ou `processar_resposta_ia_agente` (continuacao)
6. **Fallback standalone** (se nao tem fluxo): chama `engine.processar_mensagem()` diretamente
7. **Resposta**: salva no Inbox + envia via Uazapi

---

## Decisoes de design

- **AtendimentoFluxo.lead e nullable** — o assistente nao tem lead, tem usuario
- **Dados persistidos em `dados_respostas`** — `_assistente_usuario_id`, `_assistente_tenant_id` para recuperar contexto entre requests
- **Cross-tenant** — fluxo roda no tenant Aurora HQ, tools CRM operam no tenant do vendedor
- **`_skip_automacao=True`** — mensagens do assistente nao disparam signals do Inbox (evita criar leads fantasma)
- **`_obter_integracao_ia` com fallback** — busca sem filtro de tenant se nao achar no tenant do fluxo
- **One-shot support** — `_executar_ia_agente_inicial` checa `{sair: true}` para agentes que classificam e saem imediatamente

---

## Principios

1. **Numero dedicado:** nao e o numero comercial do provedor. E um numero separado so para o assistente.
2. **Acesso restrito:** so usuarios do sistema (identificados por telefone) podem usar.
3. **Conversa natural:** o vendedor fala como falaria com um colega. A IA interpreta e executa.
4. **Auditoria total:** cada acao gera log com quem fez, o que fez e quando.
5. **Tenant isolado:** cada usuario so ve/modifica dados do seu tenant.

---

## Seguranca

| Camada | Mecanismo |
|--------|-----------|
| Autenticacao | Telefone do remetente = `PerfilUsuario.telefone` |
| Autorizacao | Todas as queries filtradas por tenant do usuario |
| Auditoria | LogSistema com categoria 'assistente' |
| Isolamento | `TenantMixin` em todas as operacoes |
| Webhook | `api_token` na URL, validado contra `IntegracaoAPI` |

---

## Numero WhatsApp

- Numero: 553181167572
- Webhook: `https://app.hubtrix.com.br/assistente/webhook/<api_token>/`
- Middleware exempt: `assistente/webhook/` em `_EXEMPT_PATTERNS`

---

## Fases de desenvolvimento

| Fase | Escopo | Status |
|------|--------|--------|
| 1 | Infraestrutura (webhook, identificacao, inbox) | Concluido |
| 2 | Engine standalone + 15 tools CRM | Concluido |
| 3 | Integracao com engine de fluxo (AtendimentoFluxo sem lead) | Concluido |
| 4 | Fluxo visual configurado em producao | Pendente |
| 5 | Expansao (Inbox, Suporte, Marketing tools) | Futuro |
