# Guia de Implementação — Novo Cliente AuroraISP

**Última atualização:** 04/04/2026
**Responsável:** Operações / Tech Lead

---

## Resumo

Este documento mapeia tudo que precisa ser configurado para ativar um novo provedor na plataforma AuroraISP. O processo é dividido em 9 fases, da criação do tenant ao go-live.

**Tempo estimado:** 2 a 4 horas (dependendo da complexidade da integração HubSoft).

---

## Pré-requisitos

Antes de iniciar, coletar com o provedor:

| Item | Descrição | Obrigatório |
|------|-----------|-------------|
| Nome da empresa | Razão social ou nome fantasia | Sim |
| CNPJ | Formatado (XX.XXX.XXX/XXXX-XX) | Sim |
| Slug | Identificador URL-friendly (ex: megalink, provnet) | Sim |
| Plano contratado | Módulos + tier (ex: Comercial Pro + CS Start) | Sim |
| ERP do provedor | Qual ERP usa + credenciais de API | Sim |
| Plataforma de atendimento | Qual plataforma WhatsApp usa + credenciais | Sim |
| Logo | Imagem PNG/SVG (mínimo 200x200px) | Sim |
| Cores da marca | Primária e secundária (hex) | Sim |
| Planos de internet | Nome, velocidade, preço de cada plano | Sim |
| Dias de vencimento | Quais dias o provedor oferece (ex: 5, 10, 15, 20) | Sim |
| Admin do provedor | Nome, e-mail, telefone, senha desejada | Sim |
| Equipe de vendas | Nomes e e-mails dos vendedores (se CRM) | Se plano Pro |
| Contrato/Termos | Texto do contrato de adesão (se usar cadastro público) | Opcional |
| WhatsApp suporte | Número do WhatsApp de atendimento | Opcional |

---

## Fase 1 — Criar Tenant

### Via comando (recomendado)

```bash
cd robo/dashboard_comercial/gerenciador_vendas

python manage.py criar_tenant \
  --nome "Nome do Provedor" \
  --slug "slug-provedor" \
  --cnpj "12.345.678/0001-90" \
  --plano comercial_pro \
  --admin-user admin_provedor \
  --admin-email admin@provedor.com \
  --admin-senha SenhaSegura123 \
  --admin-telefone "85988881234" \
  --trial \
  --settings=gerenciador_vendas.settings_local
```

**Opções de plano:**

| Flag | Módulos | Tier |
|------|---------|------|
| `comercial_starter` | Comercial | Starter |
| `comercial_start` | Comercial | Start |
| `comercial_pro` | Comercial | Pro |
| `full_start` | Comercial + Marketing + CS | Start |
| `full_pro` | Comercial + Marketing + CS | Pro |

**O que o comando cria automaticamente:**
- Registro do Tenant
- Usuário admin (Django User)
- PerfilUsuario vinculando usuário ao tenant
- ConfiguracaoEmpresa (config visual básica)

### Via Admin Aurora

URL: `/aurora-admin/tenants/criar/`
Acesso: superuser only. Formulário web com validação de slug e username.

### Campos do Tenant

| Campo | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `nome` | CharField(200) | — | Nome do provedor |
| `cnpj` | CharField(18) | — | CNPJ (unique) |
| `slug` | SlugField | — | Identificador URL (unique) |
| `modulo_comercial` | Boolean | True | Habilita módulo Comercial |
| `modulo_marketing` | Boolean | False | Habilita módulo Marketing |
| `modulo_cs` | Boolean | False | Habilita módulo CS |
| `plano_comercial` | CharField | starter | starter, start, pro |
| `plano_marketing` | CharField | starter | starter, start, pro |
| `plano_cs` | CharField | starter | starter, start, pro |
| `hubspot_url` | URLField | — | URL base da API HubSoft |
| `em_trial` | Boolean | False | Se está em trial |
| `trial_inicio` / `trial_fim` | DateField | — | Período do trial |
| `ativo` | Boolean | True | Ativo/inativo |

---

## Fase 2 — Variáveis de Ambiente

Configurar no `.env` do servidor (ou painel de deploy):

### Obrigatórias

```env
# Django
SECRET_KEY=django-insecure-gerar-chave-unica-aqui
DEBUG=False
ALLOWED_HOSTS=dominio-provedor.com.br,localhost

# Banco de dados
DB_NAME=robovendas
DB_USER=admin
DB_PASSWORD=senha-forte
DB_HOST=localhost
DB_PORT=5432

# Segurança
WEBHOOK_SECRET_TOKEN=token-longo-aleatorio
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Site
SITE_URL=https://dominio-provedor.com.br
```

### Integrações

```env
# HubSoft API (OAuth)
HUBSOFT_BASE_URL=https://api.hubsoft.com.br/v1
HUBSOFT_CLIENT_ID=id-do-cliente
HUBSOFT_CLIENT_SECRET=secret-do-cliente
HUBSOFT_USERNAME=usuario-api
HUBSOFT_PASSWORD=senha-api

# HubSoft Database (read-only, para CS)
HUBSOFT_DB_USER=readonly_user
HUBSOFT_DB_PASSWORD=senha-db
HUBSOFT_DB_HOST=ip-do-hubsoft
HUBSOFT_DB_PORT=9432
HUBSOFT_DB_NAME=hubsoft

# N8N (automações)
N8N_WEBHOOK_URL=https://n8n.aurora.consulteplus.com/webhook/notifications
N8N_API_KEY=chave-api-n8n

# Matrix (WhatsApp)
MATRIX_API_URL=https://provedor.matrixdobrasil.ai/rest/v1/atendimento
MATRIX_API_TOKEN=token-matrix
```

---

## Fase 3 — Dados Iniciais (Seed)

### 3.1 Planos e Features (obrigatório, uma vez por instância)

```bash
python manage.py seed_planos --settings=gerenciador_vendas.settings_local
```

Cria 9 planos (3 por módulo) com 115 features mapeadas.

### 3.2 Planos de Internet do provedor

Cadastrar via Django Admin ou popular_sistema_completo.py:

| Campo | Exemplo |
|-------|---------|
| nome | Fibra 400MB |
| velocidade_download | 400 |
| velocidade_upload | 200 |
| valor_mensal | 99.90 |
| destaque | popular |
| id_sistema_externo | ID do plano no HubSoft |
| ordem_exibicao | 2 |

### 3.3 Opções de Vencimento

| Campo | Exemplo |
|-------|---------|
| dia | 10 |
| descricao | 10º dia de cada mês |
| id_sistema_externo | ID no HubSoft |
| ativo | True |

### 3.4 Pipeline de Vendas (CRM)

Criar pipeline padrão com estágios:

| Ordem | Nome | Tipo | Probabilidade | Final? |
|-------|------|------|---------------|--------|
| 1 | Novo Lead | novo | 10% | — |
| 2 | Qualificado | qualificacao | 30% | — |
| 3 | Documentação | negociacao | 60% | — |
| 4 | Contrato | fechamento | 85% | — |
| 5 | Ativado HubSoft | cliente | 100% | Ganho |
| 6 | Perdido | perdido | 0% | Perdido |

### 3.5 CS — Níveis do Clube (se módulo CS ativo)

| Ordem | Nome | XP Necessário |
|-------|------|---------------|
| 1 | Iniciante | 0 |
| 2 | Bronze | 100 |
| 3 | Prata | 500 |
| 4 | Ouro | 1.000 |
| 5 | Diamante | 5.000 |

### 3.6 CS — Regras de Pontuação

| Gatilho | Nome | Saldo | XP | Limite |
|---------|------|-------|----|----|
| cadastro | Bônus de Boas Vindas | 20 | 10 | 1× |
| telefone_verificado | Telefone Verificado | 10 | 5 | 1× |
| indicacao_convertida | Indicação Convertida | 30 | 15 | Ilimitado |

### 3.7 Seed completo (dev/demonstração)

```bash
python popular_sistema_completo.py
```

Cria dados de demonstração: 5 planos, 5 vencimentos, campanhas, pipeline + estágios, tags CRM, equipe de vendas, 30 leads, oportunidades, tarefas, membros do clube, tickets de suporte.

---

## Fase 4 — Configurações por Módulo

### 4.1 Comercial — ConfiguracaoCRM

Acessível em: Configurações do CRM (painel) ou Django Admin.

| Campo | O que configurar | Default |
|-------|------------------|---------|
| `pipeline_padrao` | Pipeline principal de vendas | **Obrigatório** |
| `estagio_inicial_padrao` | Estágio onde novos leads entram | **Obrigatório** |
| `criar_oportunidade_automatico` | Auto-criar oportunidade quando lead qualifica | True |
| `score_minimo_auto_criacao` | Score mínimo para auto-criação | 7 |
| `sla_alerta_horas_padrao` | SLA em horas | 48 |
| `webhook_n8n_nova_oportunidade` | URL do webhook N8N | Opcional |
| `webhook_n8n_mudanca_estagio` | URL do webhook N8N | Opcional |
| `webhook_n8n_tarefa_vencida` | URL do webhook N8N | Opcional |

### 4.2 Comercial — ConfiguracaoCadastro

Acessível em: Marketing > Configurações > Cadastro (painel).

| Grupo | O que configurar |
|-------|------------------|
| **Visual** | titulo_pagina, subtitulo, logo_url, cores (primary, secondary, success, error), background_type |
| **Contato** | telefone_suporte, whatsapp_suporte, email_suporte |
| **Campos** | cpf_obrigatorio, email_obrigatorio, telefone_obrigatorio, endereco_obrigatorio |
| **Validações** | validar_cep (ViaCEP), validar_cpf |
| **Documentação** | solicitar_documentacao, textos de instrução, tamanho_max_arquivo_mb, formatos_aceitos |
| **Contrato** | exibir_contrato, titulo_contrato, texto_contrato, tempo_minimo_leitura_segundos |
| **IDs externos** | id_origem (HubSoft), id_origem_servico, id_vendedor (RP) |
| **Fluxo** | criar_lead_automatico, numero_etapas, mostrar_progress_bar |

### 4.3 Marketing — Campanhas

Criar campanhas de tráfego conforme canais usados pelo provedor:

| Campo | Exemplo |
|-------|---------|
| nome | Google Ads Institucional |
| codigo | google-institucional |
| palavra_chave | google-institucional |
| tipo_match | parcial |
| plataforma | google_ads |
| prioridade | 5 |

### 4.4 CS — RoletaConfig

| Campo | O que configurar | Default |
|-------|------------------|---------|
| `nome_clube` | Nome do programa de fidelidade | "Clube MegaLink" |
| `custo_giro` | Pontos para girar a roleta | 10 |
| `xp_por_giro` | XP ganho por giro | 5 |
| `limite_giros_por_membro` | Máximo de giros (0 = ilimitado) | 0 |
| `periodo_limite` | Janela do limite | total |

### 4.5 CS — LandingConfig

| Campo | O que configurar |
|-------|------------------|
| `titulo` / `subtitulo` | Textos da landing page pública |
| `cor_primaria` / `cor_secundaria` | Cores da marca |
| `logo` | Logo do clube |
| `whatsapp_numero` | WhatsApp de suporte |
| `texto_como_funciona` | Seção explicativa (markdown) |

### 4.6 CS — IndicacaoConfig

| Campo | O que configurar |
|-------|------------------|
| `titulo` / `subtitulo` | Textos da página de indicação |
| `texto_indicador` | "Você foi indicado por" |
| `cor_fundo` / `cor_botao` | Cores da marca |
| `logo` / `imagem_fundo` | Visuais |
| `mostrar_campo_cpf` / `mostrar_campo_cidade` | Campos opcionais |

---

## Fase 5 — Integração com ERP

> Documentação completa: `docs/PRODUTO/10-INTEGRACOES.md`

### 5.1 Perguntar ao provedor

1. **Qual ERP?** (HubSoft, MK Solutions, IXCSoft, SGP, Controllr, outro)
2. **Credenciais de API** (URL base, método de auth, client_id/secret ou token)
3. **IDs de mapeamento** (id_origem do lead, id_vendedor padrão, id_serviço)
4. **Contato técnico** para resolver credenciais e testes

### 5.2 O que o Aurora precisa consumir do ERP

| Dado | Criticidade | Usado em |
|------|-------------|----------|
| Consultar cliente por CPF (nome, telefone, endereço, cidade) | Alta | Clube CS, cadastro de lead |
| ID do cliente no ERP | Alta | Rastreabilidade |
| Planos disponíveis (nome, velocidade, preço) | Média | Cadastro público |
| Status do contrato (ativo, dias restantes) | Média | Alertas de retenção/churn |
| Situação financeira (inadimplência, recorrência) | Baixa | Pontuação extra no Clube |

### 5.3 O que o Aurora envia para o ERP

| Dado | Criticidade | Quando |
|------|-------------|--------|
| Novo prospecto/lead (dados + documentos) | Alta | Lead qualificado |
| Contrato aceito (IP, timestamp) | Alta | Cadastro público |
| Status do processamento | Média | Webhook de confirmação |

### 5.4 Configurar credenciais

**Via painel (primeiro login):**
O admin do provedor é redirecionado para `/setup/` onde preenche as credenciais. Salva em IntegracaoAPI (campos sensíveis criptografados).

**Via comando (HubSoft):**
```bash
export HUBSOFT_BASE_URL="https://api.hubsoft.com.br/v1"
export HUBSOFT_CLIENT_ID="id"
export HUBSOFT_CLIENT_SECRET="secret"
export HUBSOFT_USERNAME="user"
export HUBSOFT_PASSWORD="pass"

python manage.py setup_hubsoft --settings=gerenciador_vendas.settings_local
```

### 5.5 Mapear IDs do ERP

| ID | Onde configurar | Descrição |
|----|-----------------|-----------|
| `id_origem` | ConfiguracaoCadastro | De onde vem o lead (ex: "site", "whatsapp") |
| `id_origem_servico` | ConfiguracaoCadastro | Qual serviço originou |
| `id_vendedor` | ConfiguracaoCadastro | Vendedor padrão para leads automáticos |
| `id_vendedor_hubsoft` | PerfilVendedor (por vendedor) | ID de cada vendedor no ERP |

### 5.6 Validar conexão

- `/aurora-admin/` → card do tenant → status da integração
- `/aurora-admin/monitoramento/` → logs de integração (últimas 20 chamadas)

---

## Fase 6 — Integração com Atendimento + N8N

> Documentação completa: `docs/PRODUTO/10-INTEGRACOES.md`

### 6.1 Perguntar ao provedor

1. **Qual plataforma de WhatsApp?** (Matrix, Evolution API, Z-API, Twilio, outro)
2. **Já têm N8N?** (self-hosted ou cloud)
3. **Webhook de envio** (URL para onde o Aurora manda mensagens)
4. **Token de autenticação** da plataforma

### 6.2 O que o Aurora envia para a plataforma

| Dado | Quando |
|------|--------|
| Mensagens do agente | Resposta no Inbox |
| Mensagens automáticas (boas-vindas, follow-up) | Automações |
| OTP de verificação | Cadastro no Clube |
| Notificações (tarefa vencida, nova oportunidade) | CRM webhooks |

### 6.3 O que a plataforma envia para o Aurora

| Dado | Webhook destino |
|------|-----------------|
| Mensagem recebida do cliente | `/inbox/api/n8n/mensagem-recebida/` |
| Status de entrega/leitura | `/inbox/api/n8n/status-mensagem/` |

### 6.4 Fluxos N8N necessários

| Fluxo | O que faz |
|-------|-----------|
| **Bot de atendimento** | Mensagem → consulta fluxo na API Aurora → responde ao cliente |
| **Detecção de campanha** | Mensagem → API `/marketing/api/campanhas/detectar/` → atribui lead |
| **Envio de OTP** | Recebe CPF + código → envia via WhatsApp |
| **Consulta cliente ERP** | Recebe CPF → consulta no ERP → retorna dados |
| **Notificações CRM** | Nova oportunidade, mudança de estágio, tarefa vencida |

### 6.5 Configurar webhooks no CRM

Em Configurações do CRM, preencher:
- `webhook_n8n_nova_oportunidade`
- `webhook_n8n_mudanca_estagio`
- `webhook_n8n_tarefa_vencida`

### 6.6 Configurar canal no Inbox

Em Inbox > Configurações > Canais, preencher o webhook de envio (URL da plataforma de atendimento).

### 6.7 Gerar token de API

```bash
python manage.py drf_create_token admin_provedor --settings=gerenciador_vendas.settings_local
```

O token é usado pelo N8N e pela plataforma no header: `Authorization: Token <token>`

---

## Fase 7 — Usuários e Equipe

### 7.1 Criar usuários adicionais

Para cada pessoa do provedor que vai usar o sistema:

```python
# Via Django shell ou script
from django.contrib.auth.models import User
from apps.sistema.models import PerfilUsuario, Tenant

tenant = Tenant.objects.get(slug='slug-provedor')

user = User.objects.create_user(
    username='vendedor1',
    email='vendedor1@provedor.com',
    password='SenhaSegura123',
    first_name='João',
    last_name='Silva'
)
PerfilUsuario.objects.create(user=user, tenant=tenant, telefone='85988881234')
```

### 7.2 Configurar equipe de vendas (CRM Pro)

1. Criar EquipeVendas (nome, líder, cor)
2. Criar PerfilVendedor para cada vendedor:

| Campo | Descrição |
|-------|-----------|
| `user` | OneToOne com User |
| `equipe` | FK EquipeVendas |
| `cargo` | vendedor, supervisor, gerente |
| `id_vendedor_hubsoft` | ID no HubSoft |

### 7.3 Permissões

| Tipo | Acesso |
|------|--------|
| **Superuser** | Tudo + Admin Aurora |
| **Staff** | Django Admin + painel do tenant |
| **Usuário normal** | Apenas painel do tenant |
| **Vendedor (não superuser)** | Vê apenas suas oportunidades + não atribuídas |

---

## Fase 8 — Branding e Visual

### 8.1 ConfiguracaoEmpresa

| Campo | Descrição |
|-------|-----------|
| `nome_empresa` | Nome exibido no painel |
| `logo_empresa` | Logo (upload) |
| `cor_primaria` | Cor principal (hex) |
| `cor_secundaria` | Cor secundária (hex) |

### 8.2 Personalizar páginas públicas

| Página | Onde configurar |
|--------|----------------|
| Cadastro de cliente | ConfiguracaoCadastro (cores, logo, textos, contrato) |
| Landing do clube | LandingConfig (cores, logo, textos, banners) |
| Página de indicação | IndicacaoConfig (cores, logo, fundo, textos) |
| Carteirinha digital | ModeloCarteirinha (cores, fundo, logo, campos visíveis) |

---

## Fase 9 — Validação e Go-live

### Checklist de validação

#### Infraestrutura
- [ ] Servidor configurado (Gunicorn + Nginx)
- [ ] SSL/HTTPS ativo
- [ ] Variáveis de ambiente configuradas
- [ ] Banco de dados PostgreSQL criado
- [ ] Migrations aplicadas
- [ ] Collectstatic executado
- [ ] Backups automáticos configurados

#### Funcionalidades
- [ ] Login do admin funciona
- [ ] Dashboard carrega com dados
- [ ] Página de cadastro pública renderiza corretamente
- [ ] Validação de CEP funciona (ViaCEP)
- [ ] Leads podem ser criados (manual e via API)
- [ ] CRM pipeline mostra estágios corretos
- [ ] Drag-and-drop do Kanban funciona
- [ ] Tarefas CRM podem ser criadas e concluídas

#### Integrações
- [ ] HubSoft API responde (token OAuth válido)
- [ ] Sync de clientes HubSoft funciona
- [ ] N8N webhooks disparam corretamente
- [ ] Bot WhatsApp (Matrix) responde
- [ ] Detecção de campanha por palavra-chave funciona
- [ ] OTP do clube envia via WhatsApp

#### Multi-tenancy
- [ ] Dados isolados (admin só vê dados do próprio tenant)
- [ ] Uploads isolados por tenant
- [ ] Filtros automáticos funcionando em todas as views

#### CS (se ativo)
- [ ] Landing do clube renderiza
- [ ] Cadastro de membro funciona
- [ ] OTP valida corretamente
- [ ] Roleta gira e prêmios são entregues
- [ ] Cupons podem ser resgatados
- [ ] Indicações podem ser criadas
- [ ] Carteirinha digital renderiza

---

## Checklist Resumido (uma página)

```
FASE 1 — TENANT
  [ ] Tenant criado (criar_tenant ou Admin Aurora)
  [ ] Admin user criado
  [ ] Planos e features seedados (seed_planos)

FASE 2 — AMBIENTE
  [ ] .env configurado (DB, secrets, integrações)
  [ ] Migrations aplicadas
  [ ] Collectstatic executado

FASE 3 — DADOS INICIAIS
  [ ] Planos de internet cadastrados
  [ ] Opções de vencimento cadastradas
  [ ] Pipeline + estágios criados
  [ ] Níveis do clube criados (se CS)
  [ ] Regras de pontuação criadas (se CS)

FASE 4 — CONFIGURAÇÃO
  [ ] ConfiguracaoCRM (pipeline_padrao, estagio_inicial)
  [ ] ConfiguracaoCadastro (visual, campos, contrato)
  [ ] RoletaConfig + LandingConfig (se CS)
  [ ] IndicacaoConfig (se CS)

FASE 5 — ERP
  [ ] ERP identificado (HubSoft, MK, IXC, SGP, etc.)
  [ ] Credenciais de API obtidas
  [ ] Conexão validada (consulta cliente por CPF)
  [ ] IDs mapeados (id_origem, id_vendedor, id_servico)

FASE 6 — ATENDIMENTO + N8N
  [ ] Plataforma identificada (Matrix, Evolution, Z-API, etc.)
  [ ] Webhook de envio configurado
  [ ] Canal configurado no Inbox
  [ ] Fluxos N8N criados/duplicados
  [ ] Webhooks CRM configurados
  [ ] Token de API gerado

FASE 7 — USUÁRIOS
  [ ] Usuários criados com PerfilUsuario
  [ ] Equipe de vendas configurada (se CRM Pro)
  [ ] Permissões validadas

FASE 8 — VISUAL
  [ ] Logo e cores configurados
  [ ] Páginas públicas personalizadas
  [ ] Contrato/termos preenchidos

FASE 9 — GO-LIVE
  [ ] SSL ativo
  [ ] Funcionalidades validadas
  [ ] Integrações testadas
  [ ] Multi-tenancy verificado
  [ ] Backups configurados
```
