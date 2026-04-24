# Integrações — Gigamax

Este documento registra os **IDs específicos do tenant Gigamax** nos sistemas integrados. É a folha de configuração do onboarding técnico — separada da especificação geral do ERP, que fica em [../../../PRODUTO/integracoes/05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md).

**Status geral:** 🟡 Discovery parcial concluído. Token compartilhado pelo João Ferreira em 23/04/2026 (guardado em `.env.prod_readonly`, fora do repo). URL base e IDs padrão pendentes.

---

## ERP — SGP (inSystem)

**Adapter:** ⏳ `SGPService` ainda não existe. Ver [guia de nova integração](../../../PRODUTO/integracoes/04-GUIA-NOVA-INTEGRACAO-ERP.md) e [spec 05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md).

### Credenciais

**Método de auth confirmado:** `app + token` (preferencial para integrações).

| Campo Hubtrix | Campo SGP | Onde guardar | Status |
|---------------|-----------|--------------|--------|
| `IntegracaoAPI.base_url` | URL base (ex: `https://gigamax.sgp.net.br`) | Banco, criptografado | ❓ A confirmar com João |
| `IntegracaoAPI.client_id` | `app` (nome do aplicativo cadastrado no SGP) | Banco, criptografado | ❓ A confirmar com João |
| `IntegracaoAPI.access_token` | `token` (gerado em `Sistema → Ferramentas → Painel Admin → Tokens`) | Banco, criptografado | ✅ Recebido 23/04 (em `.env.prod_readonly`) |
| `IntegracaoAPI.grant_type` | — | Campo livre, valor `token_app` | — |

**Fallback (Basic Auth):** se por algum motivo o cliente não puder gerar token de app, podemos usar `username + password` de um usuário SGP dedicado. Menos recomendado.

> ⚠️ **Token atual** (compartilhado pelo João em 23/04): guardado em `.env.prod_readonly` localmente. **Nunca** colar no chat ou versionar. Será movido para `IntegracaoAPI.access_token` (criptografado) quando o tenant da Gigamax for provisionado.

### IDs customizados do tenant (`configuracoes_extras` JSONField)

Diferente do HubSoft, o SGP **não** exige IDs fixos pra todas as chamadas. Os IDs abaixo são apenas **valores padrão** que o Hubtrix usa ao criar leads/prospectos automaticamente via WhatsApp:

| Chave | Descrição | Como descobrir | Valor Gigamax |
|-------|-----------|----------------|----------------|
| `pop_id_padrao` | POP default ao criar prospecto | `POST /api/ura/pops/` → pegar ID da cidade-sede | ❓ pós-credencial |
| `plano_id_padrao` | Plano sugerido pra lead não-qualificado | `POST /api/ura/consultaplano/` → escolher com o comercial | ❓ pós-credencial |
| `portador_id_padrao` | Portador financeiro default (obrigatório ao criar contrato) | `POST /api/ura/portador/` | ❓ pós-credencial |
| `vendedor_id_padrao` | Vendedor default (leads via WhatsApp) | `POST /api/precadastro/vendedor/list` | ❓ pós-credencial |
| `forma_cobranca_id_padrao` | Forma de cobrança default (1=Dinheiro, 4=Cartão de Crédito, 6=PIX, etc) | Valores fixos na doc SGP | ❓ preferência Gigamax |

**Como preencher:** depois que `SGPService` estiver implementado, rodar endpoints de listagem com as credenciais da Gigamax e confirmar com o comercial/administrativo quais IDs usar como default.

### Modos de sync (`configuracoes_extras.modos_sync`)

| Feature | Modo inicial | Observação |
|---------|--------------|------------|
| `enviar_lead` | `desativado` | Ligar só após adapter implementado e homologado |
| `sincronizar_cliente` | `desativado` | Idem |
| `sincronizar_servicos` | `desativado` | Idem |
| `sincronizar_titulos` | `desativado` | Novo — SGP expõe faturas via API, HubSoft não expunha |

---

## WhatsApp

- **Provider:** (a confirmar — Uazapi / Evolution / Matrix)
- **Instância:** (a preencher)
- **Token de sessão:** (gerenciado via `IntegracaoAPI` depois de escolher provider)

---

## IA

- **Provider:** (a confirmar — OpenAI / Anthropic / Groq / Google AI)
- **API key:** (gerenciada via `IntegracaoAPI.api_key`)

---

## Webhooks reversos (SGP/N8N → Hubtrix)

Endpoints do Hubtrix prontos para receber callbacks, se a Gigamax quiser orquestrar via N8N:

- `/api/v1/venda/aprovar/` — protegido por `api_token` do tenant. Chamado pelo N8N/SGP quando venda é aprovada. Token será gerado no provisionamento do tenant.

**Pendente:** confirmar com João se o SGP emite webhooks nativos (a Postman collection não expõe essa funcionalidade).

---

## Checklist de ativação

- [x] Método de auth identificado (`app + token`)
- [x] Token de acesso recebido (guardado fora do repo)
- [ ] `app` (nome do aplicativo) recebido
- [ ] URL base da instância Gigamax recebida
- [ ] Discovery técnico finalizado ([05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md) está em estado 🟡)
- [ ] Tenant provisionado no Hubtrix com slug `gigamax`
- [ ] `SGPService` implementado (fase 2)
- [ ] `IntegracaoAPI` criada via `setup_sgp` (command a implementar)
- [ ] Credenciais validadas via `GET /api/auth/info/` (log com status 200 em `LogIntegracao`)
- [ ] IDs padrão (`pop_id`, `plano_id`, `portador_id`, `vendedor_id`) descobertos e gravados em `configuracoes_extras`
- [ ] Lead de teste enviado com sucesso
- [ ] Cliente de teste sincronizado com sucesso
- [ ] Modos de sync habilitados em produção
