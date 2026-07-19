# 🤖 API de Validação Dinâmica com IA — Megalink Robo Vendas

Sistema de validação inteligente de respostas para fluxos de atendimento Matrix, substituindo o webhook N8N por uma API própria com IA conversacional.

## 🎯 Objetivo

- Substituir o webhook N8N (`automation-n8n.v4riem.easypanel.host/webhook/...DynamicValidator`) por uma API dedicada
- Validação **dinâmica** adaptável a qualquer pergunta/contexto do fluxo
- IA com persona humanizada (cliente não percebe que é uma IA)
- Reaproveitável para qualquer fluxo de atendimento futuro

## 📐 Arquitetura proposta

```
Cliente (WhatsApp)
   ↓
Matrix (fluxo de atendimento)
   ↓ webhook
API IA Validação (este projeto)
   ↓
OpenAI (GPT-4o/4o-mini)
   ↓
Resposta estruturada (JSON)
   ↓ retorna ao Matrix
Decisão de fluxo (avançar/repetir/transferir)
```

## 📂 Estrutura

```
ia_validacao/
├── src/
│   ├── app.py                  # Servidor Flask/FastAPI
│   ├── ia/
│   │   ├── openai_client.py    # Cliente OpenAI com retry
│   │   ├── prompts.py          # Prompts base + persona
│   │   └── validador.py        # Lógica de validação dinâmica
│   ├── contexto/
│   │   ├── conversa.py         # Mantém histórico por telefone
│   │   └── fluxo.py            # Definições de cada pergunta/etapa
│   ├── extractors/             # Extrai dados estruturados (CPF, CEP, etc)
│   │   ├── cpf.py
│   │   ├── cep.py
│   │   ├── endereco.py
│   │   ├── nome.py
│   │   └── data_nascimento.py
│   └── utils/
├── fluxos/
│   ├── vendas_megalink.yaml    # Definição do fluxo de vendas em YAML
│   └── README.md
├── tests/
├── docs/
│   ├── ARQUITETURA.md
│   ├── PROMPTS.md
│   ├── INTEGRACAO_MATRIX.md
│   └── ROADMAP.md
├── requirements.txt
├── .env.example                # Variáveis (OPENAI_API_KEY, etc)
└── docker-compose.yml
```

## 🚀 Quick start

### Modo desenvolvimento

```bash
cd ia_validacao
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configurar credenciais
cp .env.example .env
# Editar .env e adicionar OPENAI_API_KEY=sk-...

# Rodar
uvicorn src.app:app --host 0.0.0.0 --port 8090 --reload
```

### Modo produção (Docker)

```bash
cp .env.example .env  # adicione OPENAI_API_KEY
docker compose up -d --build
# health check
curl http://localhost:8090/
```

### Modo produção (systemd)

```bash
sudo cp ia-validacao.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ia-validacao
sudo systemctl status ia-validacao
```

## 🔄 Migrar o fluxo do Matrix

Para gerar uma cópia do `flow.json` original já com a nova API:

```bash
python tools/migrar_flow.py \
  --entrada ../flow.json \
  --saida fluxos/flow_megalink_v2.json \
  --api-url https://robovendas.megalinkpiaui.com.br:8090
```

Importe o arquivo gerado no Matrix como **fluxo de teste** antes de substituir o de produção.

## 📊 Status atual

✅ **Fase 1 (Fundação) concluída** — ver [`docs/ROADMAP.md`](docs/ROADMAP.md) para próximas fases.

Pronto para receber a chave OpenAI e começar a operar.

## 🔗 Documentação

- [Arquitetura completa](docs/ARQUITETURA.md)
- [Engenharia de prompts](docs/PROMPTS.md)
- [Integração com Matrix](docs/INTEGRACAO_MATRIX.md)
- [Roadmap detalhado](docs/ROADMAP.md)
