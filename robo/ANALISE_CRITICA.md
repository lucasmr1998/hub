# Analise Critica — Rob-Vendas

> Revisao arquitetural e de seguranca do projeto Rob-Vendas (Megalink Telecom)
> Data: 24/03/2026

---

## 1. ARQUITETURA: God App

O app `vendas_web` e um **monolito dentro do monolito**. Um unico app Django concentra:

- **27 models** em um unico `models.py` (5.349 linhas)
- **128 funcoes** em `views.py` (7.464 linhas)
- **222 rotas** em `urls.py`
- **3.676 linhas** de admin customizado

### Dominios misturados no mesmo app

| Dominio | Models |
|---------|--------|
| Leads/CRM | LeadProspecto, Prospecto, ImagemLeadProspecto |
| Atendimento | FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, RespostaQuestao, TentativaResposta |
| Cadastro de Clientes | CadastroCliente, DocumentoLead, ConfiguracaoCadastro |
| Notificacoes | TipoNotificacao, CanalNotificacao, PreferenciaNotificacao, Notificacao, TemplateNotificacao |
| Campanhas | CampanhaTrafego, DeteccaoCampanha |
| Configuracao | ConfiguracaoSistema, ConfiguracaoEmpresa, ConfiguracaoRecontato, PlanoInternet, OpcaoVencimento |
| Viabilidade | CidadeViabilidade |
| Logs | LogSistema, StatusConfiguravel |

### Proposta de separacao em apps

```
apps/
├── leads/              # LeadProspecto, ImagemLeadProspecto, Prospecto
├── atendimento/        # FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, RespostaQuestao, TentativaResposta
├── cadastro/           # CadastroCliente, DocumentoLead, ConfiguracaoCadastro
├── notificacoes/       # TipoNotificacao, CanalNotificacao, PreferenciaNotificacao, Notificacao, TemplateNotificacao
├── campanhas/          # CampanhaTrafego, DeteccaoCampanha
├── viabilidade/        # CidadeViabilidade
├── configuracao/       # ConfiguracaoSistema, ConfiguracaoEmpresa, ConfiguracaoRecontato, PlanoInternet, OpcaoVencimento
├── core/               # StatusConfiguravel, LogSistema, middleware, context_processors
└── integracoes/        # (ja existe) IntegracaoAPI, ClienteHubsoft, ServicoClienteHubsoft, LogIntegracao
```

---

## 2. SEGURANCA — Problemas Graves

### 2.1 Senha do banco de dados no codigo-fonte

**Arquivo:** `gerenciador_vendas/settings.py:117`

```python
'PASSWORD': os.environ.get('DB_PASSWORD', 'qualidade@trunks.57'),
```

A senha real do PostgreSQL esta como fallback no codigo versionado em repositorio **publico** no GitHub. Qualquer pessoa com acesso ao repo tem acesso direto ao banco de dados.

**Correcao:** Remover todos os fallbacks de credenciais. Usar apenas variaveis de ambiente sem valores padrao, falhando de forma explicita se nao configuradas.

### 2.2 SECRET_KEY hardcoded

**Arquivo:** `gerenciador_vendas/settings.py:24`

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-a2by4jf(!)4jho+09#...')
```

A SECRET_KEY e usada para assinar sessoes, tokens CSRF e cookies. Comprometida, permite falsificar sessoes de admin.

**Correcao:** Remover o fallback. Gerar nova SECRET_KEY e configurar apenas via variavel de ambiente.

### 2.3 DEBUG = True em producao

**Arquivo:** `gerenciador_vendas/settings.py:27`

Com DEBUG ativo, qualquer erro 500 expoe stack traces completos com variaveis locais, caminhos de arquivos, configuracoes e queries SQL para qualquer visitante.

**Correcao:** `DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'`

### 2.4 Token de API externo hardcoded

**Arquivo:** `vendas_web/services/atendimento_service.py:16`

```python
API_TOKEN = "X2P2-kNWE-3d82-ZWeh-IFD7-euDj-gzT1-5y6h"
```

Token da Matrix API exposto no codigo-fonte publico.

**Correcao:** Mover para variavel de ambiente.

### 2.5 APIs sem autenticacao

**Arquivo:** `vendas_web/middleware.py:14`

```python
re.compile(r"^api/"),          # TODAS as APIs isentas
re.compile(r"^integracoes/api/"),
```

O middleware isenta **todas** as rotas que comecam com `api/` da obrigatoriedade de login. Combinado com **50+ endpoints usando `@csrf_exempt`**, qualquer pessoa na internet pode:

- Criar e alterar leads
- Manipular atendimentos
- Enviar notificacoes
- Acessar dados de clientes
- Alterar configuracoes

**Correcao:**
- Remover a isencao geral de `^api/`
- Criar uma lista explicita de endpoints publicos (ex: apenas os do N8N com autenticacao por token)
- Implementar autenticacao por token (DRF TokenAuth ou JWT) para APIs consumidas por servicos externos
- Remover `@csrf_exempt` dos endpoints que sao chamados pelo frontend (usar CSRF token no JS)

---

## 3. CODIGO — Problemas Estruturais

### 3.1 Signal duplicado

**Arquivo:** `vendas_web/signals.py` linhas 9 e 40

A funcao `relate_prospecto_when_lead_has_hubsoft` esta registrada **duas vezes** com `@receiver(post_save, sender=LeadProspecto)`. A segunda definicao sobrescreve a primeira no escopo do modulo, mas o Django registra ambos os decorators — potencial de comportamento inesperado.

### 3.2 Chamadas HTTP sincronas em signals

**Arquivo:** `vendas_web/signals.py:60-110`

O signal `gerar_pdf_quando_documentos_validados` executa no `post_save` de `ImagemLeadProspecto` e faz:

1. Chamada HTTP para a Matrix API (buscar dados do atendimento)
2. Geracao de HTML
3. Chamada HTTP para o HubSoft (anexar documentos)
4. Chamada HTTP para o HubSoft (aceitar contrato)

Isso significa que **qualquer save de ImagemLeadProspecto pode travar por 30+ segundos** esperando APIs externas. Se a API estiver fora, o save do Django fica preso ate o timeout.

**Correcao:** Mover para uma task assincrona (Celery, Django-Q, ou no minimo um thread separado). O signal deve apenas enfileirar a tarefa.

### 3.3 Model LeadProspecto gigante (God Object)

O model LeadProspecto tem **460+ linhas** e **~50 campos**, misturando responsabilidades:

- Dados pessoais (nome, CPF, RG, email, telefone)
- Endereco completo (rua, numero, bairro, cidade, estado, CEP)
- Dados comerciais (valor, origem, campanha, score)
- Controle de documentacao (documentacao_completa, documentacao_validada)
- Controle de contrato (contrato_aceito, data_aceite, ip_aceite)
- Dados de PDF/HTML (url_pdf_conversa, html_conversa_path)
- Campanhas (campanha_origem, campanha_conversao, metadata_campanhas)
- Metodos de business logic (calcular_score, pode_reprocessar, etc.)

**Correcao:** Extrair em models menores relacionados:
- `EnderecoLead` (OneToOne) — dados de endereco
- `DocumentacaoLead` — controle de documentos e contrato
- `QualificacaoLead` — score, tentativas, custo aquisicao

### 3.4 Monkey-patching do model User

**Arquivo:** `vendas_web/models.py:9`

```python
User.add_to_class('telefone', models.CharField(...))
```

Adicionar campos ao model User do Django em runtime e uma pratica fragil que pode quebrar com atualizacoes do Django e nao gera migrations adequadas.

**Correcao:** Criar um model `PerfilUsuario` com `OneToOneField(User)` ou definir um `AUTH_USER_MODEL` customizado.

### 3.5 Sem serializers / Serializacao manual

Toda serializacao de dados para JSON e feita manualmente em funcoes como `_serialize_fluxo_atendimento()`, `_serialize_questao_fluxo()`, etc. Isso gera:

- Codigo repetitivo e propenso a erros
- Sem validacao de entrada padronizada
- Dificuldade de manter consistencia entre endpoints

**Correcao:** Adotar Django REST Framework com Serializers, ViewSets e Routers.

### 3.6 Indices excessivos no banco

O LeadProspecto define **16 indices** (incluindo compostos) para uma tabela com ~123 registros. Cada indice adiciona overhead em operacoes de escrita (INSERT/UPDATE) e ocupa espaco em disco.

**Correcao:** Manter apenas os indices essenciais para as queries mais frequentes. Adicionar novos apenas quando houver problemas de performance comprovados.

---

## 4. TESTES — Inexistentes

O arquivo `vendas_web/tests.py` contem apenas o template padrao do Django:

```python
from django.test import TestCase
# Create your tests here.
```

**Zero testes** para **18.650 linhas de codigo**. Para um sistema que manipula contratos, dados financeiros e integracoes com APIs externas, a ausencia de testes e critica.

### O que testar primeiro (por prioridade)

1. **Services** (`contrato_service.py`, `atendimento_service.py`) — logica de integracao com APIs externas
2. **Signals** — validar que o fluxo de documentacao funciona corretamente
3. **APIs de leads** — criar, atualizar, consultar leads
4. **Validacao de imagens** — fluxo de aprovacao/rejeicao
5. **Views de dashboard** — dados corretos nas agregacoes

---

## 5. PADROES DE API — Inconsistentes

### 5.1 Verbos na URL (anti-pattern REST)

```
POST /api/leads/registrar/       # deveria ser POST /api/leads/
POST /api/leads/atualizar/       # deveria ser PUT /api/leads/{id}/
GET  /api/consultar/leads/       # deveria ser GET /api/leads/
```

### 5.2 Duplicacao de endpoints N8N

Os endpoints N8N (`/api/n8n/...`) duplicam logica dos endpoints normais com pequenas variacoes. Exemplo:

- `/api/atendimentos/criar/` vs `/api/n8n/atendimento/iniciar/`
- `/api/atendimentos/<id>/responder/` vs `/api/n8n/atendimento/<id>/responder/`

**Correcao:** Unificar os endpoints e diferenciar o comportamento via header ou parametro de autenticacao.

### 5.3 Rotas legado mantidas sem prazo

```python
# Rotas compativeis antigas (mantidas para compatibilidade)
path('api/consultar/fluxos/', ...)
path('api/consultar/questoes/', ...)
```

**Correcao:** Definir prazo de depreciacao e remover.

### 5.4 Sem versionamento

Nenhuma API usa versionamento (`/api/v1/...`). Qualquer mudanca breaking afeta todos os consumidores simultaneamente.

---

## 6. ESTRUTURA DE DIRETORIOS — Confusa

```
robo/                              # raiz do repo
├── dashboard_comercial/
│   └── gerenciador_vendas/        # projeto Django (manage.py aqui)
│       ├── gerenciador_vendas/    # settings do projeto (mesmo nome!)
│       ├── vendas_web/            # app principal
│       └── integracoes/           # app de integracoes
├── vendas_web/                    # pasta legado na raiz (??)
└── README.md
```

Problemas:

- **Nomes redundantes**: `gerenciador_vendas/gerenciador_vendas/` — confuso para navegar
- **Pasta legado na raiz**: `vendas_web/` na raiz parece ser codigo antigo abandonado
- **manage.py enterrado**: 2 niveis abaixo da raiz do repo

### Proposta de estrutura

```
rob-vendas/
├── src/
│   ├── manage.py
│   ├── config/                    # settings, urls, wsgi, asgi
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── local.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── leads/
│   │   ├── atendimento/
│   │   ├── cadastro/
│   │   ├── notificacoes/
│   │   ├── campanhas/
│   │   ├── viabilidade/
│   │   ├── configuracao/
│   │   ├── integracoes/
│   │   └── core/
│   └── templates/
├── tests/
├── requirements/
│   ├── base.txt
│   ├── local.txt
│   └── production.txt
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## 7. DEPENDENCIAS — Faltando bibliotecas essenciais

### O que falta no `requirements.txt`

| Biblioteca | Finalidade |
|-----------|-----------|
| `djangorestframework` | APIs padronizadas com serializers, viewsets, autenticacao |
| `django-environ` ou `python-dotenv` | Gerenciamento de .env mais robusto |
| `celery` + `redis` | Tasks assincronas (emails, chamadas a APIs externas) |
| `django-cors-headers` | Controle de CORS para APIs |
| `pytest` + `pytest-django` | Framework de testes |
| `factory-boy` | Factories para testes |
| `sentry-sdk` | Monitoramento de erros em producao |
| `django-debug-toolbar` | Debug em desenvolvimento |

### WeasyPrint nao esta no requirements.txt

O sistema usa WeasyPrint para gerar PDFs, mas a biblioteca **nao esta listada** no `requirements.txt`.

---

## 8. TABELA DE PRIORIDADES

| Prioridade | Problema | Risco | Esforco |
|-----------|---------|-------|---------|
| **URGENTE** | Credenciais no codigo-fonte (DB + API tokens) | Comprometimento total do sistema | Baixo |
| **URGENTE** | APIs sem autenticacao (middleware isenta `^api/`) | Manipulacao de dados por qualquer pessoa | Medio |
| **URGENTE** | DEBUG=True em producao | Exposicao de informacoes sensiveis | Baixo |
| **ALTA** | Zero testes | Regressoes silenciosas, medo de refatorar | Alto |
| **ALTA** | Chamadas HTTP sincronas em signals | Travamento da aplicacao em saves | Medio |
| **MEDIA** | App monolitico (27 models em 1 app) | Manutencao cada vez mais dificil | Alto |
| **MEDIA** | Sem DRF / serializers | Codigo repetitivo e fragil | Medio |
| **MEDIA** | Signal duplicado | Bug latente | Baixo |
| **MEDIA** | Monkey-patching do User | Fragilidade com updates do Django | Baixo |
| **BAIXA** | Estrutura de diretorios confusa | Experiencia de desenvolvimento ruim | Alto |
| **BAIXA** | Indices excessivos | Overhead desnecessario em writes | Baixo |
| **BAIXA** | Rotas legado sem prazo de remocao | Divida tecnica crescente | Baixo |

---

## 9. PLANO DE ACAO SUGERIDO

### Fase 1 — Emergencial (1-2 dias)

- [ ] Remover todas as credenciais hardcoded do codigo
- [ ] Rotacionar senha do banco de dados (a atual esta comprometida)
- [ ] Rotacionar token da Matrix API
- [ ] Gerar nova SECRET_KEY
- [ ] Configurar DEBUG=False em producao
- [ ] Restringir acesso as APIs (remover isencao geral de `^api/`)

### Fase 2 — Seguranca (1 semana)

- [ ] Implementar autenticacao por token para APIs externas (N8N)
- [ ] Remover `@csrf_exempt` dos endpoints chamados pelo frontend
- [ ] Criar lista explicita de endpoints publicos
- [ ] Adicionar rate limiting nas APIs

### Fase 3 — Qualidade (2-3 semanas)

- [ ] Adicionar testes para services e signals
- [ ] Mover chamadas HTTP de signals para tasks assincronas
- [ ] Corrigir signal duplicado
- [ ] Substituir monkey-patching do User por PerfilUsuario

### Fase 4 — Refatoracao (4-6 semanas)

- [ ] Separar `vendas_web` em apps menores por dominio
- [ ] Adotar Django REST Framework
- [ ] Reorganizar estrutura de diretorios
- [ ] Versionar APIs (`/api/v1/...`)
- [ ] Remover rotas legado
- [ ] Remover pasta `vendas_web/` da raiz

---

> **Nota:** A Fase 1 deve ser executada imediatamente, pois as credenciais ja estao expostas no GitHub publico.
