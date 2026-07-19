# Fluxograma — Atendimento Determinístico (Robô de Vendas V2)

> Documentação do fluxo determinístico do robô de vendas conduzido pela API.
> Os diagramas estão em [Mermaid](https://mermaid.live) — renderizam direto no
> GitHub/GitLab/VS Code (extensão *Markdown Preview Mermaid*).
>
> Endpoints públicos (TecHub):
> `POST https://techub.megalinkpiaui.com.br/robo-v2/ia/proximo-passo`
> `POST https://techub.megalinkpiaui.com.br/robo-v2/ia/validar`

---

## 1. As 4 camadas e como se comunicam

> Versão em imagem (caso o Mermaid não renderize): [`img/01-visao-geral.png`](img/01-visao-geral.png)

```mermaid
flowchart LR
    Cliente["📱 Cliente<br/>WhatsApp"]
    Matrix["🤖 Matrix / n8n<br/>orquestra o fluxo"]
    API["🧠 FastAPI (IA)<br/>porta 8091<br/>/robo-v2/ia/*"]
    Django["🗄️ Django CRM<br/>porta 8104<br/>banco robovendas_v2"]
    Vision["👁️ OpenAI Vision<br/>valida documentos"]
    Ext["🏢 HubSoft ERP<br/>API Matrix<br/>cliente · OS · agenda"]

    Cliente <-->|mensagem| Matrix
    Matrix <-->|HTTP /proximo-passo<br/>e /validar| API
    API <-->|HTTP regras · leads<br/>tags · histórico| Django
    API -->|valida foto| Vision
    Django -->|consulta/abre OS| Ext

    classDef brain fill:#0022fa,color:#fff
    classDef data fill:#10b981,color:#fff
    class API brain
    class Django data
```

**Papel de cada camada:**

| Camada | Papel | Guarda estado? |
|---|---|---|
| **Matrix / n8n** | O maestro: mostra a pergunta, recebe a resposta e chama a API. Não tem lógica de fluxo. | Não |
| **FastAPI (IA)** | O cérebro: decide a próxima pergunta e valida cada resposta. Sem banco. | Não |
| **Django CRM** | A memória: lead, regras, histórico, tags, pipeline. | **Sim** |

> A "memória" do fluxo é o **próprio preenchimento do lead** no Django — não há
> máquina de estados à parte. O robô sabe onde parou olhando quais campos do
> cadastro ainda estão vazios.

---

## 2. O loop de 2 chamadas (o coração do fluxo)

Para **cada pergunta**, o Matrix faz sempre o mesmo par de chamadas:

```mermaid
sequenceDiagram
    participant C as 📱 Cliente
    participant M as 🤖 Matrix
    participant A as 🧠 FastAPI
    participant D as 🗄️ Django

    M->>A: (1) POST /proximo-passo
    A->>D: lê o lead (campos já preenchidos)
    D-->>A: dados do lead
    A-->>M: proxima_pergunta_id + mensagem
    M->>C: envia a pergunta no WhatsApp
    C->>M: responde (texto / opção / foto)
    M->>A: (2) POST /validar (answer)
    A->>D: carrega a RegraValidacao (cache)
    A->>A: roda o extrator + hooks
    alt resposta válida
        A-->>D: salva campo, tags, histórico (background)
        A-->>M: valido=true + msg_sucesso
        M->>A: volta ao passo (1) → próxima pergunta
    else inválida
        A-->>M: valido=false + msg_erro (tentativas+1)
        M->>C: repete a MESMA pergunta
        Note over A,M: após max_tentativas → transbordo=true
    end
```

---

## 3. A árvore de decisão do `/proximo-passo`

> Versão em imagem: [`img/03-arvore-decisao.png`](img/03-arvore-decisao.png)

```mermaid
flowchart TD
    Start([POST /proximo-passo]) --> HasLead{lead existe?}
    HasLead -->|não| New["registrar_lead()<br/>status = lead_novo"]
    New --> AskCPF[["pergunta: coleta_cpf<br/>◀── INÍCIO"]]

    HasLead -->|sim| Status[lê status_api do lead]

    Status --> NS{em_fluxo<br/>new_service?}
    NS -->|sim| NSflow["coleta campos do<br/>NOVO SERVIÇO<br/>(sem dados pessoais)"]
    NSflow --> NSend["ao finalizar →<br/>volta cliente_ativo"]

    Status --> UP{em_fluxo<br/>upgrade?}
    UP -->|sim| UPflow["turno_upgrade()<br/>mostra / responde"]
    UPflow --> UPend["ao finalizar →<br/>volta cliente_ativo"]

    Status --> Cli{cliente_ativo /<br/>instalacao_agendada?}
    Cli -->|sim| Menu[["MENU do cliente:<br/>1 Novo serviço<br/>2 Upgrade<br/>3 Acompanhar OS<br/>4 Atendente<br/>5 Finalizar"]]

    Status --> Rotas{status em<br/>STATUS_ROTAS?}
    Rotas -->|aguardando_assinatura| Wait[aguarda assinatura]
    Rotas -->|cancelado| Ret[transbordo retenção]
    Rotas -->|transbordo_atendente| Hum[transborda p/ atendente]

    Status --> Coleta["COLETA NORMAL:<br/>percorre a sequência e acha<br/>o 1º campo VAZIO → pergunta"]
    Coleta --> AllDone{todos os<br/>campos OK?}
    AllDone -->|não| AskNext[[faz a pergunta do campo vazio]]
    AllDone -->|sim| Done["transborda p/ atendente<br/>finalizar"]

    classDef inicio fill:#0022fa,color:#fff
    classDef menu fill:#f59e0b,color:#fff
    class AskCPF,AskNext inicio
    class Menu menu
```

---

## 4. Sequência canônica de coleta (cliente novo)

O `/proximo-passo` pergunta o **primeiro campo vazio** desta lista:

```mermaid
flowchart TD
    A[1· coleta_cpf] -->|verifica HubSoft| A1{é cliente?}
    A1 -->|sim| MENU([vira MENU do cliente])
    A1 -->|não| B[2· coleta_nome]
    B --> C[3· coleta_data_nascimento ≥18]
    C --> D[4· coleta_email]
    D --> E[5· tipo_imovel]
    E -->|empresa| TB([TRANSBORDA — só residencial])
    E -->|casa| F[6· coleta_cep · ViaCEP preenche]
    F --> G[7· confirmacao_endereco]
    G -->|negou| F2[limpa endereço e volta]
    G -->|ok| H[8-13· cidade, bairro, rua,<br/>número, tipo_residência, ref.]
    H --> I[14· escolha_plano · 620/1G/1G+ponto]
    I --> J[15· confirmacao_plano]
    J -->|negou| I
    J -->|ok| K[16· dia_vencimento · 1/5/15/20]
    K --> L[17· confirmacao_dados]
    L --> M[18-20· selfie, frente_doc, verso_doc]
    M -->|OpenAI Vision| M1{foto aprovada?}
    M1 -->|não| MR[pede REFOTO]
    M1 -->|sim| N[21· escolha_turno · manhã/tarde]
    N --> O[22· escolha_data]
    O --> P([dispara AGENDAMENTO + abre OS<br/>status → instalacao_agendada → MENU])

    classDef fim fill:#10b981,color:#fff
    classDef tb fill:#ef4444,color:#fff
    class P fim
    class TB,MR tb
```

---

## 5. O que acontece dentro do `/validar`

```mermaid
flowchart TD
    R([resposta do cliente]) --> L1["1· carrega a RegraValidacao<br/>(cache ← Django)"]
    L1 --> L2{"2· EXTRATOR<br/>cpf · cep · nome · email · data ·<br/>número · opção · confirmação · imagem · texto"}
    L2 -->|falhou| Err["msg_erro · tentativas+1<br/>(≥max → transbordo)"]
    L2 -->|extraiu OK| L3[3· HOOKS especiais]

    L3 --> H1["coleta_cpf → consulta HubSoft<br/>(é cliente? → cliente_ativo)"]
    L3 --> H2["menu → inicia novo serviço /<br/>upgrade / acompanhar / finalizar"]
    L3 --> H3["imagem → OpenAI Vision:<br/>aprova OU pede refoto"]
    L3 --> H4["escolha_data → resolve data +<br/>dispara agendamento + OS"]
    L3 --> H5["confirmação negada →<br/>limpa campos e faz voltar"]

    H1 & H2 & H3 & H4 & H5 --> L4

    L4["4· AÇÕES em background (thread):<br/>• atualizar campo do lead<br/>• atualizar status_api<br/>• adicionar tags ▶ CRM<br/>• registrar histórico ▶ move Kanban<br/>• registrar imagem"]
    L4 --> L5["5· devolve JSON:<br/>valido · message · extracted_data ·<br/>transbordo · tentativas · fim_fluxo"]
    L5 --> L6[6· log assíncrono · LogInteracaoIA]

    classDef act fill:#6366f1,color:#fff
    class L4 act
```

---

## 6. Conexão com o CRM (pipeline automático)

Cada etapa validada grava um `historico_status` no Django; as **regras de
pipeline** usam esse status para mover o card no Kanban automaticamente.

```mermaid
flowchart LR
    H1[cpf_validado /<br/>plano_selecionado] --> S1[Em Qualificação]
    H2[dados_confirmados] --> S2[Aguardando Assinatura]
    H3[cadastro_concluido] --> S3[Aguardando Instalação]
    H4[instalação agendada /<br/>HubSoft ativado] --> S4[Cliente Ativo ✅]
    H5[cancelou / desistiu] --> S5[Perdido ❌]

    classDef won fill:#10b981,color:#fff
    classDef lost fill:#ef4444,color:#fff
    class S4 won
    class S5 lost
```

---

## 7. /validar vs /proximo-passo

| | **/proximo-passo** | **/validar** |
|---|---|---|
| Pergunta que responde | "Qual pergunta eu faço agora?" | "Essa resposta serve?" |
| Quando o Matrix chama | Antes de mostrar a pergunta | Depois que o cliente responde |
| Lê | status + campos do lead | a RegraValidacao da pergunta |
| Efeito colateral | cria lead se não existe | salva dado, tags, histórico, status |
| Decide transbordo? | sim (fim do fluxo / status) | sim (após max_tentativas) |

**Corpo das requisições:**

```jsonc
// POST /robo-v2/ia/proximo-passo
{ "cellphone": "5586999990000", "lead_id": 123, "ultima_mensagem": "" }

// POST /robo-v2/ia/validar
{ "question_id": "coleta_cpf", "question": "Qual seu CPF?",
  "answer": "111.444.777-35", "cellphone": "5586999990000", "lead_id": 123 }
```

---

## 8. Principais endpoints Django consumidos pela FastAPI

| Endpoint Django | Quando |
|---|---|
| `GET /ia_validador/api/regras-validacao/` | Carrega as regras (cache 1h) |
| `GET /api/consultar/leads/` | Busca lead por telefone |
| `POST /api/leads/registrar/` | Cria lead novo |
| `POST /api/leads/atualizar/` | Salva campo do lead |
| `POST /api/leads/tags/` | Adiciona/remove tags (alimenta o CRM) |
| `POST /api/historicos/registrar/` | Grava histórico (move o pipeline) |
| `POST /api/leads/imagens/registrar/` | Registra documento validado |
| `POST /integracoes/api/lead/hubsoft-check/` | Verifica se o CPF é cliente |
| `POST /api/leads/agendar-ia/` | Dispara agendamento + abre OS |
| `POST /api/new-service/*` · `/api/upgrade-conversa/turno/` | Fluxos pós-venda |

---

## Resumo em uma frase

O Matrix pergunta **"o que faço agora?"** (`/proximo-passo`) e **"essa resposta
serve?"** (`/validar`); a FastAPI decide olhando os campos já preenchidos do lead
no Django, valida com extratores (e OpenAI Vision para fotos) e grava tudo de
volta — alimentando automaticamente o status, as tags e o pipeline do CRM.

---

### Arquivos de referência (código)

| Arquivo | Função |
|---|---|
| `ia_validacao/src/app.py` | endpoints `/validar` e `/proximo-passo` |
| `ia_validacao/src/onboarding.py` | `decidir_proximo_passo`, `SEQUENCIA_COLETA`, `STATUS_ROTAS` |
| `ia_validacao/src/regras/engine.py` | `validar_por_regra`, extratores, ações |
| `ia_validacao/src/acoes.py` | execução das ações no Django |
| `ia_validacao/src/integracoes/robovendas.py` | cliente HTTP do Django |
