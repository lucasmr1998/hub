# Rob-Vendas — Sistema Comercial Megalink

Sistema de gestão de leads e vendas da Megalink Telecom, integrado com WhatsApp (via N8N), HubSoft ERP e API Matrix de atendimentos.

## Funcionalidades

- **Gestão de Leads** — cadastro, acompanhamento e funil de vendas
- **Validação de Documentos** — upload, aprovação e rejeição de imagens por lead
- **Conversa do Atendimento** — geração automática de HTML/PDF com o histórico do WhatsApp (API Matrix)
- **Integração HubSoft** — anexação de documentos validados ao contrato e aceite automático via API
- **Viabilidade Técnica** — cadastro de cidades/CEPs cobertos com API de consulta pública
- **Painel de Vendas** — listagem de clientes HubSoft com status de documentação e timer ao vivo
- **Logs de Integração** — rastreabilidade completa de todas as chamadas a APIs externas
- **Admin personalizado** — Django Admin com previews, badges e ações em lote

## Stack

| Tecnologia | Uso |
|-----------|-----|
| Python 3.11 | Linguagem principal |
| Django 4.x | Framework web |
| PostgreSQL | Banco de dados |
| Gunicorn + Nginx | Servidor de produção |
| WeasyPrint | Geração de PDF |
| Requests | Integração com APIs externas |

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/Megalink-Telecom/Rob-Vendas.git
cd Rob-Vendas/dashboard_comercial/gerenciador_vendas
```

### 2. Crie e ative o ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
cp .env.example .env
# Edite o .env com suas credenciais
```

### 5. Aplique as migrations

```bash
python manage.py migrate
```

### 6. Crie o superusuário

```bash
python manage.py createsuperuser
```

### 7. Inicie o servidor

```bash
python manage.py runserver
```

Acesse em `http://localhost:8000`

## Estrutura do Projeto

```
dashboard_comercial/gerenciador_vendas/
├── gerenciador_vendas/        # Configurações Django (settings, urls, wsgi)
├── vendas_web/                # App principal
│   ├── models.py              # LeadProspecto, ImagemLeadProspecto, CidadeViabilidade, etc.
│   ├── views.py               # Views e APIs
│   ├── admin.py               # Painel admin personalizado
│   ├── signals.py             # Signal: validação → HTML → HubSoft
│   ├── services/
│   │   ├── atendimento_service.py   # Geração de HTML da conversa (API Matrix)
│   │   └── contrato_service.py      # Integração HubSoft (anexos + aceite)
│   ├── templates/vendas_web/  # Templates HTML
│   └── migrations/            # Histórico de migrations
├── integracoes/               # App de integração com HubSoft
│   ├── models.py              # ClienteHubsoft, ServicoClienteHubsoft, LogIntegracao
│   ├── views.py               # API de clientes para a tela de vendas
│   └── services/hubsoft.py    # Serviço OAuth2 HubSoft
├── requirements.txt
└── .env.example
```

## APIs disponíveis

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/leads/atualizar/` | Atualiza status de um lead (N8N) |
| POST | `/api/leads/imagens/` | Adiciona imagens a um lead |
| POST | `/api/leads/imagens/validar/` | Aprova ou rejeita imagem |
| GET | `/api/leads/imagens/por-cliente/` | Imagens do lead de um cliente HubSoft |
| GET | `/api/viabilidade/` | Consulta cidades/CEPs com cobertura |
| GET | `/api/clientes/` | Lista clientes HubSoft com documentação |
| GET | `/leads/<id>/conversa/` | Visualiza HTML da conversa do atendimento |
| GET | `/leads/<id>/conversa/pdf/` | Baixa PDF da conversa do atendimento |

### Parâmetros da API de Viabilidade

```
GET /api/viabilidade/                    # Lista todas
GET /api/viabilidade/?cidade=teresina    # Filtra por cidade
GET /api/viabilidade/?uf=PI              # Filtra por estado
GET /api/viabilidade/?cep=64049700       # Consulta por CEP (+ ViaCEP)
```

## Variáveis de Ambiente

Veja o arquivo `.env.example` para a lista completa de variáveis necessárias.

## Licença

Uso interno — Megalink Telecom © 2026
