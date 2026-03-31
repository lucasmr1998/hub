# CLAUDE.md

## Permissões

- **NÃO editar** o projeto `megaroleta/`. Apenas leitura.
- **`robo/` liberado para edição.** Refatoração concluída. Estrutura modular em `apps/` é a fonte da verdade. `vendas_web` está desativado (código morto).
- **NUNCA rodar comandos que afetem o banco de produção.** Sempre usar `--settings=gerenciador_vendas.settings_local` (SQLite local). Isso inclui: `migrate`, `makemigrations`, `createsuperuser`, `flush`, `loaddata`, `dumpdata`, `dbshell`, ou qualquer script que conecte ao PostgreSQL de produção.

---

## Hub de Documentos

O arquivo `exports/hub.html` é o gestor visual unificado de documentos e backlog.

**Regra:** sempre que um arquivo `.md` for criado ou modificado em `docs/` ou `exports/drafts/`, ou uma tarefa for criada/atualizada em `docs/context/tarefas/`, rodar automaticamente:

```
python scripts/gerar_hub.py
```

Isso garante que o hub reflita sempre o estado atual do workspace.

---

## Context — Reuniões e Tarefas

### Reuniões
Ao final de conversas relevantes ou quando o usuário solicitar, salvar um resumo em:

```
docs/context/reunioes/assunto_DD-MM-AAAA.md
```

Template em `docs/context/reunioes/TEMPLATE.md`.
Exemplo: `gtm_posicionamento_26-03-2026.md`

### Tarefas
Registrar tarefas ativas, pendentes ou concluídas em:

```
docs/context/tarefas/assunto_DD-MM-AAAA.md
```

Template em `docs/context/tarefas/TEMPLATE.md`.
Exemplo: `criar_logo_26-03-2026.md`

---

## Gestão de Tarefas

Toda implementação deve estar vinculada a uma tarefa em `docs/context/tarefas/`. Se o usuário solicitar algo que não tenha tarefa correspondente, **criar a tarefa antes de começar a implementar**. Isso garante rastreabilidade e controle do backlog.

- Tarefas pendentes ficam em `docs/context/tarefas/backlog/`
- Tarefas concluídas ficam em `docs/context/tarefas/finalizadas/`
- Template em `docs/context/tarefas/TEMPLATE.md`
- Ao finalizar uma tarefa, mover o arquivo para `finalizadas/` e rodar `python scripts/gerar_hub.py`

---

## Regras de Escrita

- **Não usar traço/hífen** (`-`) como elemento de pontuação em frases e textos de marketing. Usar ponto, vírgula ou reescrever a frase.
- Aplicar em todos os documentos GTM, Brand e Agentes.

---

## Contexto Geral

Este workspace (`hub/`) centraliza a estratégia e documentação da **AuroraISP** — hub de tecnologia com IA para provedores de internet.

Os projetos de código ficam em pastas separadas e não devem ser editados sem autorização. A documentação estratégica fica em `docs/`.

---

## Projetos de Código

### robo/
Módulo principal da AuroraISP (Comercial + CS + Marketing). Em produção na Megalink Telecom.
- Stack: Python 3.11, Django 5.2, DRF, PostgreSQL, Gunicorn, Nginx
- Integrações: HubSoft API, N8N, Matrix API, ViaCEP, WeasyPrint
- Projeto Django: `robo/dashboard_comercial/gerenciador_vendas/`
- **`vendas_web` desativado.** Removido do INSTALLED_APPS. Todos os models, views, templates, URLs, admin e signals migrados para `apps/`. O código em `vendas_web/` é morto e não deve ser referenciado.
- **Estrutura modular (15 apps) em `apps/`:**
  - `apps/sistema/` — Tenant, PerfilUsuario, configs do SaaS, base.html, static files, decorators, validators, logging filters
  - `apps/comercial/leads/`, `apps/comercial/atendimento/`, `apps/comercial/cadastro/`, `apps/comercial/viabilidade/`, `apps/comercial/crm/`
  - `apps/marketing/campanhas/`
  - `apps/cs/clube/`, `apps/cs/parceiros/`, `apps/cs/indicacoes/`, `apps/cs/carteirinha/`
  - `apps/dashboard/`, `apps/notificacoes/`, `apps/integracoes/`
  - `apps/admin_aurora/` — Painel de gestão do SaaS (/aurora-admin/)
- **Multi-tenancy implementado:** Tenant model, TenantMixin (em TODOS os models incluindo CRM), TenantManager, TenantMiddleware. Isolamento de dados por provedor. Pendente deploy em produção.
- **Admin Aurora:** Painel /aurora-admin/ para gerenciar tenants, planos (9 planos, 115 features) e monitorar o SaaS.
- **CS migrado do megaroleta:** apps clube, parceiros, indicacoes e carteirinha integrados ao hub.
- **API REST:** DRF com TokenAuth + SessionAuth. Endpoints em `/api/v1/`. Swagger em `/api/docs/`.
- **Segurança:** 5 vulnerabilidades críticas e 12 altas/médias corrigidas. Secrets em variáveis de ambiente. `@api_token_required` para N8N, `@login_required` para painel. PIIFilter no logging. Validação de uploads. Isolamento de tenant em uploads.
- **Testes:** 225 testes passando, 10 arquivos de teste, 28+ factories. CI/CD com GitHub Actions.
- **Migrations:** limpas e regeneradas do zero para todos os apps.

### megaroleta/
Módulo **CS / Clube de Benefícios** da AuroraISP. **Legacy.** Os apps principais (clube, parceiros, indicacoes, carteirinha) foram migrados para `robo/apps/cs/`.
- Stack: Python 3.11, Django
- Apps restantes: `gestao` (17 models, agentes IA). Não migrado.
- Docs em `megaroleta/docs/`

---

## AuroraISP — Visão Geral

**Tagline:** Vende mais. Perde menos. Fideliza sempre.
**Subtítulo:** Do lead ao cliente fidelizado com inteligência.
**Posicionamento:** Hub de tecnologia com IA para provedores de internet.

### Módulos do Hub

| Módulo | Planos | Status | O que faz |
|--------|--------|--------|-----------|
| **Comercial** | Start / Pro | ✅ Em produção | Lead no WhatsApp → docs → contrato → HubSoft. Pro inclui CRM Kanban. |
| **Marketing** | Start / Pro | 🔧 A desenvolver | Motor de automação do hub. E-mail, WhatsApp, réguas padrão, tráfego pago com IA. |
| **CS** | Start / Pro | 🔧 Em desenvolvimento | Clube de Benefícios migrado do megaroleta. Prevenção de churn, NPS, upsell a desenvolver. |

### Modelo de Precificação

- Mensalidade fixa por módulo (Start ou Pro)
- Transacional variável mensal por módulo:
  - **Marketing:** tamanho da base de leads
  - **Comercial:** venda finalizada e validada no ERP
  - **CS:** cliente ativo no clube
- Sem limite de volume — o transacional substitui os limites

### Diferencial central
Integração HubSoft nativa e profunda. Nenhum concorrente faz isso.

### ICP
Provedores regionais de internet com HubSoft. 500 a 50.000 clientes ativos. 2 a 20 vendedores.

### Case de produção (anônimo)
Provedor com 30.000 clientes. 1.000 leads/mês. 400 vendas digitais/mês. Ticket R$ 99,90.
2 pessoas fazem o que 8 faziam. Economia de R$ 284.400/ano em pessoal.

### Concorrente principal
ISPRO AI (isproai.com.br) — sem case real, sem integração HubSoft profunda, sem preço público.

---

## Estrutura de Documentação

```
docs/
├── GTM/                     — estratégia de go-to-market
│   ├── 00-README.md
│   ├── 01-PESQUISA_MERCADO.md
│   ├── 02-ICP.md
│   ├── 03-CONCORRENTES.md
│   ├── 04-PROPOSTA_VALOR.md
│   ├── 05-POSICIONAMENTO.md
│   ├── 06-MENSAGENS_CHAVE.md
│   ├── 07-CANAIS.md
│   ├── 08-PRECIFICACAO.md
│   ├── 09-ENABLEMENT.md
│   ├── 10-ROADMAP_GTM.md
│   └── 10-ROADMAP_GTM.md
├── PRODUTO/                 — especificação de produto
│   ├── 01-REGUAS_PADRAO.md
│   └── 02-ROADMAP_PRODUTO.md
├── BRAND/                   — identidade e comunicação
│   ├── 07-TOM_DE_VOZ.md
│   └── 08-BRANDBOOK.md
└── AGENTES/                 — agentes por função
    ├── README.md
    ├── executivo/           — CEO, CTO, CPO, CFO, CMO
    ├── produto/             — PMM, PM, UX
    ├── marketing/           — Growth, Copywriter, Performance, CRM/Automação, Conteúdo
    ├── comercial/           — Head de Vendas, CS, Parcerias
    ├── tech/                — Tech Lead, Data Analyst, Segurança, DevOps, QA
    └── operacoes/           — RevOps, Jurídico
```

---

## Agentes Disponíveis

Para adotar uma perspectiva específica, indicar o agente desejado. Cada agente tem contexto completo da AuroraISP.

| Área | Agentes |
|------|---------|
| Executivo | CEO, CTO, CPO, CFO, CMO |
| Produto | PMM, PM, UX |
| Marketing | Growth, Copywriter, Performance, CRM e Automação, Conteúdo e Comunidades |
| Comercial | Head de Vendas, CS, Parcerias |
| Tech | Tech Lead, Data Analyst, Segurança (AppSec), DevOps, QA |
| Operações | RevOps, Jurídico |

Definições completas em `docs/AGENTES/`.

### Identificação obrigatória do agente

**Em toda resposta**, a primeira linha deve identificar qual agente está respondendo, no formato:

> `Agente: [Nome do Agente]`

Exemplos: `Agente: PMM`, `Agente: Head de Vendas`, `Agente: CFO`.

Quando nenhum agente específico se aplica (perguntas gerais, tarefas técnicas do workspace), usar `Agente: Assistente`.

### Uso proativo dos agentes

O assistente deve alternar de perspectiva automaticamente conforme o tema da conversa, sem precisar ser solicitado. Ao mudar de agente, sinalizar brevemente qual perspectiva está sendo adotada e por quê.

Exemplos de quando alternar:

| Tema | Agente recomendado |
|------|--------------------|
| Precificação, margens, modelo de receita | CFO ou RevOps |
| Simulações, métricas, ROI | Data Analyst |
| Especificação de produto, fluxos, funcionalidades | PM |
| Posicionamento, mensagens, canais | PMM |
| Parceiro comercial, prospecção, objeções | Head de Vendas |
| Retenção, clube, NPS | CS |
| Arquitetura, stack, desenvolvimento | Tech Lead ou CTO |
| Contratos, compliance | Jurídico |
| Aquisição, funil, experimentos de crescimento | Growth Marketing |
| Textos de e-mail, WhatsApp, landing page, deck | Copywriter |
| Meta Ads, Google Ads, criativos pagos | Performance |
| Réguas de automação, N8N, segmentação de base | CRM e Automação |
| Blog, LinkedIn, YouTube, grupos de provedores | Conteúdo e Comunidades |
| Vulnerabilidades, LGPD, secrets, autenticação | Segurança (AppSec) |
| Deploy, CI/CD, monitoramento, infraestrutura | DevOps |
| Testes, cobertura, regressão, qualidade | QA |
