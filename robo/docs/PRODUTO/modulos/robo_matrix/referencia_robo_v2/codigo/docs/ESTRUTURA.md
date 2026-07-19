# Estrutura do repositório `new_robo`

Árvore anotada. Legenda:
🟢 **load-bearing** (carregado por serviço em produção — não mover sem cuidado) ·
🔧 dev/ops (utilitário, deploy) · 📄 doc/dados · 🚫 git-ignored

```
new_robo/
├── README.md                         📄 visão geral do repo (2 serviços)
├── .gitignore                        🔧 ignora venvs, *.service, *.conf, media, sqlite...
│
├── docs/                             📄 documentação a NÍVEL DE REPO
│   ├── ESTRUTURA.md                  📄 este arquivo
│   ├── ARQUITETURA.md                📄 fluxos determinístico vs conversacional
│   ├── DOCUMENTACAO_CRM.md           📄 referência do CRM/Django
│   ├── DOCUMENTACAO_FLOW_COMERCIAL.md 📄 fluxo comercial detalhado
│   ├── PROPOSTA_FLUXO_IDEAL.md       📄 proposta de fluxo
│   └── RELATORIO_SEMANA_*.md         📄 relatório
│
├── ia_validacao/                     ══ SERVIÇO FastAPI (IA Validação · uvicorn :8090) ══
│   ├── src/                          🟢 código-fonte (pacote `src`)
│   │   ├── app.py                    🟢 entrypoint FastAPI (monta os routers)
│   │   ├── config.py                 🟢 config (env: OPENAI_API_KEY, ROBOVENDAS_API_URL...)
│   │   ├── onboarding.py             🟢 fluxo DETERMINÍSTICO: decidir_proximo_passo + sequências
│   │   ├── conversa.py               🟢 contexto/planos (PLANOS espelho)
│   │   ├── regras/                   🟢 engine de validação determinístico
│   │   │   ├── engine.py             🟢   validar_por_regra (valida+persiste+hooks)
│   │   │   ├── client.py             🟢   RegrasClient (cache das RegraValidacao do Django)
│   │   │   └── alvo.py               🟢   _alvo: roteia escrita lead vs NewService
│   │   ├── extractors/               🟢 validadores PUROS (cpf, cep+ViaCEP, nome, data...)
│   │   ├── integracoes/              🟢 robovendas (HTTP→Django), openai_imagens, logs
│   │   ├── contexto/                 🟢 memória de contexto do determinístico
│   │   ├── ia/                       🟢 helpers de IA
│   │   └── conversacional/           🟢 ── CAMADA CONVERSACIONAL (/conv/turno) ──
│   │       ├── rotas.py              🟢   APIRouter /conv + contrato de resposta (modos)
│   │       ├── orquestrador.py       🟢   processar_turno → _rotear / _validar
│   │       ├── memoria.py            🟢   estado+histórico por telefone (isolado)
│   │       ├── fluxo.py / motor.py   🟢   sequência própria + decide próximo passo
│   │       ├── validacao.py          🟢   valida reusando os extractors puros
│   │       ├── planos.py             🟢   resolve plano por preço/velocidade
│   │       ├── respostas.py          🟢   mensagem específica por tipo de erro
│   │       ├── acoes.py              🟢   hooks de negócio (Hubsoft, agendamento...)
│   │       ├── retomada.py           🟢   retomar/recomeçar (exclusivo do conv)
│   │       ├── extrator.py           🟢   IA: extrai campos/intenção da mensagem
│   │       ├── faq.py / humanizador.py 🟢 IA: responde dúvida / humaniza
│   │       ├── cliente_llm.py        🟢   wrapper OpenAI
│   │       └── config.py             🟢   flags da camada conversacional
│   ├── tests/                        🔧 suíte offline (test_conv_simulacao.py)
│   ├── tools/                        🔧 migração de flow (migrar_flow*.py, patch_flow_v5.py)
│   ├── fluxos/                       📄 exports de flow do Matrix (.json) + vendas_megalink.yaml
│   │   ├── flow.json                 📄   export bruto do Matrix (entrada dos tools)
│   │   ├── flow_matrix_conversacional.json 📄 flow do /conv/turno (atual)
│   │   └── flow_v*.json / flow_dinamico*.json 📄 versões migradas
│   ├── docs/                         📄 docs específicas da API IA (API_REFERENCE, ARQUITETURA...)
│   ├── requirements.txt              🟢 deps da FastAPI
│   ├── Dockerfile / docker-compose.yml 🔧 container
│   ├── ia-validacao.service          🔧 systemd (deploy)
│   ├── .env / .env.example           🟢/📄 config (.env é git-ignored)
│   └── .venv/                        🚫 virtualenv da FastAPI
│
└── dashboard_comercial/             ══ SERVIÇO Django (CRM + API de dados · gunicorn) ══
    ├── requirements.txt             🟢 deps (nível wrapper)
    ├── popular_fluxo_vendas.py      🔧 seed (script manual)
    ├── n_env/                       🚫 virtualenv do Django (usado pelo serviço)
    └── gerenciador_vendas/          🟢 projeto Django
        ├── manage.py                🟢 entrypoint Django
        ├── gerenciador_vendas/      🟢 settings, urls, wsgi
        ├── crm/                     🟢 app: pipeline kanban, tarefas, retenção
        ├── ia_validador/            🟢 app: RegraValidacao + LogInteracaoIA (config das regras)
        ├── integracoes/             🟢 app: HubSoft, NewService, agendamento
        ├── vendas_web/              🟢 app: LeadProspecto, imagens, painel de vendas
        ├── templates/ static/ staticfiles/ 🟢/🚫 front + assets
        ├── media/                   🚫 uploads (git-ignored)
        ├── db.sqlite3               🚫 banco local (git-ignored; prod usa PostgreSQL)
        ├── dados_iniciais_cadastro.py / popular_fluxo.py 🔧 seeds (scripts manuais)
        ├── nginx_robovendas.conf    🔧 nginx (git-ignored)
        ├── gunicorn*.conf.py        🔧 gunicorn (git-ignored)
        ├── robovendas-gunicorn.service 🔧 systemd (git-ignored)
        └── README.md                📄 docs do Django
```

## Notas

- **Não mover** o que está marcado 🟢 dentro de `src/` ou dos apps Django: são
  pacotes/módulos importados pelos serviços em execução.
- **Arquivos de deploy** (🔧 `*.service`, `nginx_*.conf`, `gunicorn*`) são
  git-ignored e referenciados pelo systemd/nginx do servidor — mexer neles afeta os
  serviços ativos.
- Os **flows** ficam todos em `ia_validacao/fluxos/`. Os tools em `ia_validacao/tools/`
  leem `fluxos/flow.json` (export bruto) e geram versões migradas na mesma pasta.
- A **fonte de verdade das regras de validação** (`RegraValidacao`) é o Django (app
  `ia_validador`); a FastAPI consome via `src/regras/client.py` (cache).
