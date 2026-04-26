# Integrações HubSoft

Documento técnico que mapeia todos os pontos de integração entre a AuroraISP e o ERP HubSoft. Essencial para onboarding de novos provedores e alinhamento técnico com a equipe HubSoft do cliente.

---

## Visão Geral

A AuroraISP se integra com o HubSoft de duas formas:

| Método | Usado por | Motivo |
|--------|-----------|--------|
| **API REST (OAuth2)** | Comercial, Cadastro | Endpoints disponíveis na API oficial |
| **Conexão direta ao banco PostgreSQL** | CS / Clube de Benefícios | API não expõe os dados necessários (recorrência, app, pagamentos) |

---

## Requisitos de Onboarding

Para ativar a integração HubSoft de um novo provedor, são necessários:

### API REST (obrigatório para o módulo Comercial)

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `HUBSOFT_BASE_URL` | URL base da API HubSoft do provedor | `https://provedor.hubsoft.com.br` |
| `HUBSOFT_CLIENT_ID` | Client ID do OAuth2 | Fornecido pelo HubSoft |
| `HUBSOFT_CLIENT_SECRET` | Client Secret do OAuth2 | Fornecido pelo HubSoft |
| `HUBSOFT_USERNAME` | Usuário da API | Fornecido pelo provedor |
| `HUBSOFT_PASSWORD` | Senha da API | Fornecido pelo provedor |

Configuração via management command:
```bash
python manage.py setup_hubsoft
```

**OU pelo painel** (desde 04/26): `/configuracoes/integracoes/<pk>/` — pagina de detalhe permite editar todos os 5 campos diretamente (URL, Client ID, Client Secret, Username, Password). Ver [05-SGP.md](05-SGP.md) pra detalhes da pagina de detalhe (a mesma pagina serve HubSoft + SGP, com campos condicionais por tipo).

Pagina de detalhe inclui:
- Stats (chamadas/erros 24h, total logs, clientes sincronizados)
- Credenciais editaveis (5 campos OAuth2 do HubSoft)
- Modos de sincronizacao (3 features: enviar_lead, sincronizar_cliente, sincronizar_servicos)
- Logs das ultimas 20 chamadas
- Botao "testar conexao" (chama `obter_token()`)

### Conexão direta ao banco (necessário apenas para CS / Clube)

| Variável | Descrição |
|----------|-----------|
| `HUBSOFT_DB_HOST` | Host do PostgreSQL HubSoft |
| `HUBSOFT_DB_PORT` | Porta (padrão: 5432) |
| `HUBSOFT_DB_NAME` | Nome do banco |
| `HUBSOFT_DB_USER` | Usuário com permissão de leitura |
| `HUBSOFT_DB_PASS` | Senha do usuário |

**Importante:** o usuário do banco precisa apenas de permissão `SELECT`. Nenhuma escrita é feita diretamente no banco do HubSoft.

### Webhook N8N (necessário para CS / Clube)

| Variável | Descrição |
|----------|-----------|
| URL do webhook | `https://automation-n8n.v4riem.easypanel.host/webhook/roletaconsultarcliente` |

Esse webhook é acionado pelo Clube para consultar dados do cliente por CPF via N8N.

---

## Mapa de Integrações por Módulo

### 1. Comercial — Envio de Leads

**Fluxo:** Lead cadastrado no WhatsApp -> AuroraISP salva -> envia automaticamente para HubSoft como prospecto.

| Item | Detalhe |
|------|---------|
| **Trigger** | Signal `post_save` no model `LeadProspecto` (quando `status_api='pendente'`) |
| **Endpoint** | `POST /api/v1/integracao/prospecto` |
| **Autenticação** | OAuth2 Bearer Token |
| **Dados enviados** | Nome, CPF/CNPJ, telefone, email, endereço, plano, dia de vencimento |
| **Retorno** | `id_prospecto` da HubSoft (salvo em `lead.id_hubsoft`) |
| **Status** | `status_api` atualizado para `processado` (sucesso) ou `erro` (falha) |
| **Arquivo** | `apps/integracoes/signals.py` |
| **Service** | `apps/integracoes/services/hubsoft.py` → `cadastrar_prospecto()` |

**Retry:** leads com `status_api='erro'` podem ser reprocessados via:
```bash
python manage.py processar_pendentes
```

---

### 2. Comercial — Sincronização de Clientes

**Fluxo:** Após o lead virar cliente no HubSoft, a Aurora sincroniza os dados do cliente e seus serviços/planos.

| Item | Detalhe |
|------|---------|
| **Trigger** | Automático após cadastro de prospecto, ou manual via command |
| **Endpoint** | `GET /api/v1/integracao/cliente?cpf_cnpj={cpf}` |
| **Dados sincronizados** | Nome, CPF/CNPJ, telefones, emails, endereço, RG, data de nascimento |
| **Serviços** | Plano, valor, velocidade, status, PPPoE, datas de habilitação/cancelamento |
| **Models** | `ClienteHubsoft`, `ServicoClienteHubsoft` |
| **Detecção de alterações** | Campo `houve_alteracao` e `historico_alteracoes` em JSON |
| **Arquivo** | `apps/integracoes/services/hubsoft.py` → `sincronizar_cliente()` |

**Sincronização em massa:**
```bash
python manage.py sincronizar_clientes --todos
```

---

### 3. Cadastro — Contratos e Documentos

**Fluxo:** Após validação dos documentos do lead (fotos do RG, comprovante), a Aurora anexa automaticamente ao contrato no HubSoft e aceita o contrato.

| Item | Detalhe |
|------|---------|
| **Trigger** | Signal `post_save` no model `ImagemLeadProspecto` (quando status = validado) |
| **Etapa 1** | Buscar ID do contrato via Matrix API |
| **Etapa 2** | `POST /api/v1/integracao/cliente/contrato/adicionar_anexo_contrato/{id_contrato}` |
| **Etapa 3** | `PUT /api/v1/integracao/cliente/contrato/aceitar_contrato` |
| **Dados enviados** | Imagens dos documentos (base64), ID do contrato |
| **Arquivo** | `apps/comercial/cadastro/services/contrato_service.py` |
| **Signal** | `apps/comercial/cadastro/signals.py` → `gerar_pdf_quando_documentos_validados()` |

---

### 4. CS / Clube de Benefícios — Consultas ao Banco

**Por que conexão direta?** A API REST da HubSoft não expõe endpoints para:
- Verificar recorrência de pagamento (faturas em dia)
- Verificar se o cliente pagou adiantado
- Verificar se o app do provedor está instalado
- Listar clientes por cidade (para análise de penetração)

Esses dados são essenciais para o sistema de gamificação (pontos, XP, roleta).

| Consulta | O que faz | Usado em |
|----------|-----------|----------|
| `checar_pontos_extras_cpf(cpf)` | Verifica recorrência, pagamento adiantado e app instalado | Gamificação (pontos automáticos) |
| `consultar_cidade_cliente_cpf(cpf)` | Retorna a cidade do cliente por CPF | Filtro de prêmios por cidade |
| `consultar_clientes_por_cidade(cidade)` | Lista clientes ativos numa cidade | Relatório de penetração de mercado |
| Webhook N8N `/roletaconsultarcliente` | Consulta dados do cliente por CPF via N8N | Validação de membro no Clube |

**Arquivo:** `apps/cs/clube/services/hubsoft_service.py`

**Regras de pontuação automática (via banco):**

| Gatilho | Condição verificada no banco HubSoft | Pontos |
|---------|--------------------------------------|--------|
| `hubsoft_recorrencia` | Cliente com faturas em dia nos últimos X meses | Configurável por regra |
| `hubsoft_adiantado` | Fatura paga antes do vencimento | Configurável por regra |
| `hubsoft_app` | App do provedor instalado (campo no HubSoft) | Configurável por regra |

---

## Models de Integração

| Model | Tabela | Descrição |
|-------|--------|-----------|
| `IntegracaoAPI` | `integracoes_integracaoapi` | Credenciais OAuth2, URL base, token cacheado |
| `LogIntegracao` | `integracoes_logintegracao` | Audit trail de chamadas à API (endpoint, payload, response, status) |
| `ClienteHubsoft` | `integracoes_clientehubsoft` | Espelho local do cliente HubSoft (dados pessoais, sync status) |
| `ServicoClienteHubsoft` | `integracoes_servicoclientehubsoft` | Planos/serviços ativos do cliente (velocidade, valor, PPPoE) |

---

## Endpoints Internos (API Aurora)

Endpoints da Aurora que expõem dados sincronizados da HubSoft:

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/integracoes/api/clientes/` | GET | Lista clientes HubSoft sincronizados (paginado, com filtros) |
| `/integracoes/api/lead/hubsoft-status/` | GET | Status de um lead específico na HubSoft |

---

## Fluxo Completo: Lead ao Cliente Ativado

```
1. Lead chega via WhatsApp (N8N)
2. Aurora salva o LeadProspecto (status_api='pendente')
3. Signal envia para HubSoft → POST /prospecto
4. Lead vira prospecto no HubSoft (id_hubsoft salvo)
5. Vendedor qualifica e coleta documentos
6. Documentos validados → Signal anexa ao contrato HubSoft
7. Contrato aceito automaticamente na HubSoft
8. Sync de cliente → ClienteHubsoft espelhado localmente
9. Se módulo CS ativo: membro do Clube criado automaticamente
```

---

## Checklist de Onboarding

Para cada novo provedor, validar:

- [ ] Credenciais da API HubSoft configuradas (`setup_hubsoft`)
- [ ] Token OAuth2 funcionando (testar via admin)
- [ ] Envio de lead de teste (`processar_pendentes --lead-id X --dry-run`)
- [ ] Sincronização de cliente de teste (`sincronizar_clientes --lead-id X --dry-run`)
- [ ] (Se CS ativo) Conexão ao banco PostgreSQL do HubSoft testada
- [ ] (Se CS ativo) Webhook N8N configurado e respondendo
- [ ] Logs de integração sendo registrados (`LogIntegracao`)

---

## Limitações Conhecidas

1. **API HubSoft expõe sim faturas e renegociação** — `GET /api/v1/integracao/cliente/financeiro` e `POST /api/v1/integracao/financeiro/renegociacao/*`. A premissa antiga (de que a API não cobria pagamento) **não é mais verdade**. O Clube hoje acessa via banco direto por motivo histórico, mas existe caminho REST equivalente. Migrar pra REST está no plano de paridade (`paridade_integracao_hubsoft_26-04-2026.md`).

2. **Token OAuth2 tem expiração.** O sistema faz cache em `IntegracaoAPI.access_token` + `token_expira_em` e renova automaticamente.

3. **Sincronização não é em tempo real.** Clientes são sincronizados sob demanda (após cadastro de prospecto) ou via command (`sincronizar_clientes`). Não há webhook do HubSoft para a Aurora.

4. **Cada provedor tem sua própria instância HubSoft.** As credenciais REST são por tenant (`IntegracaoAPI` usa `TenantMixin`). **Mas a camada de banco direto e a API Matrix não são multi-tenant** — ver "Débitos técnicos" abaixo.

---

## Cobertura real da API HubSoft

A Postman collection oficial expõe **185 endpoints**. Hoje o Hubtrix consome **5** (~3%):

| Endpoint | Método nosso | Status |
|---|---|---|
| `POST /oauth/token` | `HubsoftService.obter_token` | ativo |
| `POST /api/v1/integracao/prospecto` | `HubsoftService.cadastrar_prospecto` | ativo |
| `GET  /api/v1/integracao/cliente?busca=cpf_cnpj` | `HubsoftService.consultar_cliente` / `sincronizar_cliente` | ativo |
| `POST /api/v1/integracao/cliente/contrato/adicionar_anexo_contrato/{id}` | `cadastro/contrato_service.adicionar_anexo` | ativo (legado, fora do `HubsoftService`) |
| `PUT  /api/v1/integracao/cliente/contrato/aceitar_contrato` | `cadastro/contrato_service.aceitar_contrato` | ativo (idem) |

Endpoints relevantes ainda não consumidos: catálogos (`/configuracao/*`), financeiro (`/cliente/financeiro`, `/financeiro/renegociacao/*`), operacional (`/cliente/cliente_servico/{ativar,suspender,habilitar}`, `/cliente/desbloqueio_confianca`, `/cliente/reset_mac_addr`), atendimento bidirecional (`/atendimento`, `/ordem_servico/abrir_os`), viabilidade (`/mapeamento/viabilidade/consultar`, `/prospecto/create?cep=`).

Plano de fechamento dessas lacunas: `robo/docs/context/tarefas/backlog/paridade_integracao_hubsoft_26-04-2026.md`.

---

## Débitos técnicos

> **Bloco H1 concluído (26/04/2026):** itens 1, 2 e 5 abaixo foram resolvidos. Detalhes em `paridade_integracao_hubsoft_26-04-2026.md`.

1. ~~**`contrato_service` reimplementa boilerplate de auth/log do zero.**~~ ✅ Resolvido em H1. As chamadas HTTP (`anexar_arquivos_contrato`, `aceitar_contrato`) agora moram em `HubsoftService`. `contrato_service` ficou só com a orquestração (resolver Matrix, baixar imagens, gerar PDF da conversa).

2. ~~**API Matrix com `MATRIX_EMPRESA = "megalink"` hardcoded.**~~ ✅ Resolvido em H1. `buscar_id_contrato` agora aceita `integracao=...` e lê `configuracoes_extras['matrix']` (`url`, `empresa`). Fallback Megalink mantido pra compatibilidade.

3. **Acesso ao banco PostgreSQL HubSoft não é multi-tenant.** `apps/cs/clube/services/hubsoft_service.py` lê de `os.getenv('HUBSOFT_DB_*')` global. Funciona porque só Megalink usa Clube + HubSoft. Vira blocker no momento que um 2º provedor HubSoft assinar Clube. Ou migra pra credencial por tenant em `IntegracaoAPI`, ou aposenta em favor da API REST (limitação 1).

4. **Webhook N8N hardcoded.** URL `https://automation-n8n.v4riem.easypanel.host/webhook/roletaconsultarcliente` está fixa em `cs/clube/services/hubsoft_service.py`. Mesmo problema multi-tenant.

5. ~~**`HubsoftService` não tem `_request` único.**~~ ✅ Resolvido em H1. Centralizado em `_request(metodo, endpoint, json=, params=, files=, autenticar=, log_payload=, timeout=, lead=)`. Helpers `_get`, `_post`, `_put` por cima. `_payload_seguro` mascara `password`, `client_secret`, `token`, `access_token` em qualquer log.

6. ~~**Defaults da integração editados manualmente no JSONField.**~~ ✅ Resolvido em H2 (backend + UI). `HubsoftService` expõe `sincronizar_servicos_catalogo`, `sincronizar_vencimentos` e `sincronizar_catalogo_cacheado(<chave>)` para 9 catálogos (vendedores, origens_cliente/contato, meios_pagamento, grupos_cliente, motivos_contratacao, tipos_servico, servico_status, servicos_tecnologia). Wrapper `sincronizar_configuracoes` dispara tudo. Management command: `python manage.py sincronizar_catalogo_hubsoft [--categoria=todos|<chave>] [--integracao-id] [--tenant] [--dry-run]`. UI no painel `/configuracoes/integracoes/<pk>/` com selects de plano/vendedor/vencimento/origens populados pelo cache + botão "Sincronizar tudo".

7. **Cobertura de testes baixa.** `SGPService` tem 27 testes (commit `528da1b`). `HubsoftService` quase não tem. **Endereçado no bloco H7.**
