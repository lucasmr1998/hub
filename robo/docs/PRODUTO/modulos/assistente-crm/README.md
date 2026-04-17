# Assistente CRM via WhatsApp — Hubtrix

**Ultima atualizacao:** 14/04/2026
**Status:** Funcional (Engine standalone + Fluxo)
**Localizacao:** `apps/assistente/` + `apps/comercial/atendimento/engine.py`

---

## Visao Geral

Agente IA operacional acessivel via WhatsApp que permite usuarios do sistema executar acoes no CRM por conversa natural. Funciona como um "copilot" para vendedores que estao em campo ou no celular.

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

## Arquitetura

### App `apps/assistente/`

| Arquivo | Funcao |
|---------|--------|
| `views.py` | Webhook, identificacao, orquestrador Inbox + Fluxo |
| `engine.py` | Engine standalone (fallback se nao tem fluxo) |
| `tools.py` | 15 tools CRM (TOOLS_ASSISTENTE dict) |
| `models.py` | ConfiguracaoAssistenteGlobal, ConfiguracaoAssistenteTenant |

### Fluxo de processamento

1. **Webhook** (`/assistente/webhook/<api_token>/`) recebe mensagem do Uazapi
2. **Identificacao**: busca PerfilUsuario por telefone (match exato + limpo)
3. **Validacao**: ConfiguracaoAssistenteGlobal.ativo + ConfiguracaoAssistenteTenant.ativo
4. **Inbox**: cria/busca Conversa no tenant Aurora HQ com modo_atendimento='assistente'
5. **Engine de fluxo** (prioridade):
   - Busca FluxoAtendimento vinculado ao CanalInbox ou por nome
   - Busca/cria AtendimentoFluxo sem lead (lead=NULL)
   - Armazena contexto em dados_respostas: `_assistente_usuario_id`, `_assistente_tenant_id`, `_conversa_id`, `_telefone`
   - Chama engine: `iniciar_fluxo_visual` (primeira msg) ou `processar_resposta_ia_agente` (continuacao)
6. **Fallback standalone** (se nao tem fluxo): chama `engine.processar_mensagem()` diretamente
7. **Resposta**: salva no Inbox + envia via Uazapi

### Decisoes de design

- **AtendimentoFluxo.lead e nullable**: o assistente nao tem lead, tem usuario
- **Dados persistidos em dados_respostas**: `_assistente_usuario_id`, `_assistente_tenant_id` para recuperar contexto entre requests
- **Cross-tenant**: fluxo roda no tenant Aurora HQ, tools CRM operam no tenant do vendedor
- **_skip_automacao=True**: mensagens do assistente nao disparam signals do Inbox (evita criar leads fantasma)
- **_obter_integracao_ia com fallback**: busca sem filtro de tenant se nao achar no tenant do fluxo
- **One-shot support**: `_executar_ia_agente_inicial` agora checa `{sair: true}` para agentes que classificam e saem imediatamente

---

## Principios

1. **Numero dedicado:** nao e o numero comercial do provedor. E um numero separado so para o assistente.
2. **Acesso restrito:** so usuarios do sistema (identificados por telefone) podem usar.
3. **Conversa natural:** o vendedor fala como falaria com um colega. A IA interpreta e executa.
4. **Auditoria total:** cada acao gera log com quem fez, o que fez e quando.
5. **Tenant isolado:** cada usuario so ve/modifica dados do seu tenant.

---

## Configuracao

### ConfiguracaoAssistenteGlobal (singleton)
- `integracao_whatsapp`: IntegracaoAPI do numero Hubtrix (Uazapi)
- `ativo`: toggle global
- `mensagem_boas_vindas`: template com {nome}
- `mensagem_acesso_restrito`: resposta para numeros nao cadastrados

### ConfiguracaoAssistenteTenant (por tenant)
- `integracao_ia`: provider IA (OpenAI, Anthropic, Groq)
- `modelo_ia`: modelo (default: gpt-4o-mini)
- `ativo`: toggle por tenant

### FluxoAtendimento
- Fluxo de atendimento no tenant Aurora HQ
- Pode ser vinculado ao CanalInbox (`canal.fluxo`) ou encontrado por nome (icontains 'assistente')
- Nodo ia_agente com tools CRM habilitadas via checkboxes [CRM]

---

## Tools Disponiveis (15)

| Tool | Funcao |
|------|--------|
| `consultar_lead` | Busca lead por nome/telefone |
| `listar_oportunidades` | Lista oportunidades (filtro por estagio) |
| `mover_oportunidade` | Move oportunidade para outro estagio |
| `criar_nota` | Cria nota no lead |
| `criar_tarefa` | Cria tarefa com vencimento |
| `atualizar_lead` | Atualiza campo do lead |
| `resumo_pipeline` | Metricas do pipeline |
| `listar_tarefas` | Lista tarefas pendentes |
| `proxima_tarefa` | Proxima tarefa a vencer |
| `agendar_followup` | Agenda followup (nota + tarefa) |
| `buscar_historico` | Historico de interacoes do lead |
| `marcar_perda` | Marca oportunidade como perdida |
| `marcar_ganho` | Marca oportunidade como ganha |
| `agenda_do_dia` | Tarefas e followups do dia |
| `ver_comandos` | Lista de comandos disponiveis |

Cada tool recebe `(tenant, usuario, args)` e retorna string. Todas filtram por tenant do vendedor.

---

## Seguranca

| Camada | Mecanismo |
|--------|-----------|
| Autenticacao | Telefone do remetente = PerfilUsuario.telefone |
| Autorizacao | Todas as queries filtradas por tenant do usuario |
| Auditoria | LogSistema com categoria 'assistente' |
| Isolamento | TenantMixin em todas as operacoes |
| Webhook | api_token na URL, validado contra IntegracaoAPI |

---

## Numero WhatsApp

- Numero: 553181167572
- Webhook: `https://app.hubtrix.com.br/assistente/webhook/<api_token>/`
- Middleware exempt: `assistente/webhook/` em _EXEMPT_PATTERNS

---

## Fases de Desenvolvimento

| Fase | Escopo | Status |
|------|--------|--------|
| 1 | Infraestrutura (webhook, identificacao, inbox) | Concluido |
| 2 | Engine standalone + 15 tools CRM | Concluido |
| 3 | Integracao com engine de fluxo (AtendimentoFluxo sem lead) | Concluido |
| 4 | Fluxo visual configurado em producao | Pendente |
| 5 | Expansao (Inbox, Suporte, Marketing tools) | Futuro |
