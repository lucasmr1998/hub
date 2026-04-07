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

1. **API HubSoft não expõe dados de pagamento/recorrência.** O Clube depende de conexão direta ao banco. Se a HubSoft liberar esses endpoints no futuro, migrar para API REST.

2. **Token OAuth2 tem expiração.** O sistema faz cache e renova automaticamente, mas se as credenciais mudarem no HubSoft, o `IntegracaoAPI` precisa ser atualizado.

3. **Sincronização não é em tempo real.** Clientes são sincronizados sob demanda (após cadastro de prospecto) ou via command (`sincronizar_clientes`). Não há webhook do HubSoft para a Aurora.

4. **Cada provedor tem sua própria instância HubSoft.** As credenciais são por tenant (model `IntegracaoAPI` usa `TenantMixin`).
