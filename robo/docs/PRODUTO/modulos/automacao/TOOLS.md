# Catalogo de tools dos agentes

> GERADO de `apps/automacao/services/ia_tools.py` via
> `python manage.py gerar_catalogo_tools`. **Nao edite a mao** — rode o comando.
> **Antes de criar uma tool nova, procure aqui** se ja existe uma que faca o que voce precisa.

> `tipo`: **Conhecimento** = le/consulta (read-only) · **Executavel** = faz/escreve (efeito colateral).

Total: **18 tools** em **7 categorias**.

| Categoria | Tools |
|---|---|
| **atendimento** | `marcar_cliente`, `marcar_intencao`, `marcar_intencao_energia`, `registrar_feedback` |
| **conhecimento** | `consultar_base_conhecimento` |
| **crm** | `criar_oportunidade` |
| **dados** | `churn_clientes`, `resumo_leads`, `status_pipeline`, `tickets_abertos`, `vendas_periodo` |
| **governanca** | `solicitar_aprovacao` |
| **suporte** | `abrir_ticket` |
| **workspace** | `listar_documentos`, `criar_etapa`, `criar_projeto`, `criar_tarefa`, `salvar_documento` |

## atendimento

### `marcar_cliente` — Executavel

Registre se o contato JÁ é cliente da Megalink. Use quando o cliente disser que é (ou não é) cliente.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `e_cliente` | boolean | sim | true se já é cliente da Megalink |

### `marcar_intencao` — Executavel

Registre a intenção de compra do contato. Use quando ele demonstrar (ou negar) interesse em contratar.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `tem_intencao` | boolean | sim | true se demonstrou intenção de compra |

### `marcar_intencao_energia` — Executavel

Registre o interesse do contato no produto Mega Energia. Use só depois de o cliente aceitar ouvir sobre o Mega Energia.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `tem_interesse` | boolean | sim | true se interessado no Mega Energia |

### `registrar_feedback` — Executavel

Salve a avaliação do cliente (nota de 0 a 10 e comentário). Use quando o cliente avaliar o atendimento ou o serviço.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `nota` | integer | sim | Nota de 0 a 10 |
| `comentario` | string | nao | Comentário do cliente (opcional) |

## conhecimento

### `consultar_base_conhecimento` — Conhecimento

Consulte a base de conhecimento da empresa (produtos, serviços, procedimentos, dúvidas frequentes). Use SEMPRE que o cliente fizer uma pergunta que pode ter resposta na base.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `pergunta` | string | sim | A pergunta ou tema a buscar na base |

## crm

### `criar_oportunidade` — Executavel

Crie uma oportunidade no funil para o lead atual. Use quando o cliente demonstrar interesse claro em comprar/contratar.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `titulo` | string | sim | Título curto da oportunidade |
| `valor` | number | nao | Valor estimado em reais (opcional) |

## dados

### `churn_clientes` — Conhecimento

Clientes ativos em risco de churn (churn_score alto) na base HubSoft espelhada. Use para responder sobre risco de cancelamento ou retencao.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `score_minimo` | integer | nao | Churn score minimo para considerar em risco (0 a 100, padrao 70) |

### `resumo_leads` — Conhecimento

Resumo dos leads do funil: total, novos no periodo e principais origens. Use para responder quantos leads existem ou de onde vem os leads.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `dias` | integer | nao | Janela em dias para os leads novos (padrao 30) |

### `status_pipeline` — Conhecimento

Resumo do funil comercial: quantidade de oportunidades por estagio. Use para responder sobre o pipeline ou o funil de vendas.

_Sem parametros._

### `tickets_abertos` — Conhecimento

Tickets de suporte ainda nao resolvidos, por status. Use para responder sobre a fila de suporte ou quantos chamados estao abertos.

_Sem parametros._

### `vendas_periodo` — Conhecimento

Vendas registradas no periodo: quantidade e valor total. Use para responder quanto foi vendido (vendas do mes, da semana, etc).

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `dias` | integer | nao | Janela em dias (padrao 30) |

## governanca

### `solicitar_aprovacao` — Executavel

Registre uma PROPOSTA de acao para aprovacao humana, em vez de executar direto. Use quando recomendar algo que precisa do aval de uma pessoa antes (uma decisao, um gasto, uma mudanca importante). De um titulo objetivo e uma descricao com o racional e a acao que voce sugere. Prioridade: baixa, media, alta ou critica.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `titulo` | string | sim | Titulo curto da proposta |
| `descricao` | string | sim | Racional + acao sugerida, com contexto |
| `prioridade` | string | nao | baixa | media | alta | critica (padrao media) |

## suporte

### `abrir_ticket` — Executavel

Abra um ticket de suporte pro time humano resolver. Use quando o cliente reportar um problema/bug, ou quando você não conseguir resolver e precisar escalar. Dê um título objetivo e uma descrição com o MÁXIMO de contexto (o que aconteceu, quando, passos pra reproduzir, o que era esperado) — quanto melhor a descrição, mais rápido o time resolve.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `titulo` | string | sim | Título curto e objetivo do problema |
| `descricao` | string | sim | Descrição detalhada: o que aconteceu, quando, passos pra reproduzir e o que era esperado |
| `categoria` | string | nao | Categoria do chamado (ex: Bug, Dúvida, Financeiro). Opcional. |
| `prioridade` | string | nao | Prioridade do chamado. Opcional (padrão: normal). |

## workspace

### `listar_documentos` — Conhecimento

Liste documentos do Workspace (id + titulo + categoria), opcionalmente filtrando por um termo no titulo. Use pra achar um documento antes de consultar.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `busca` | string | nao | Termo pra filtrar no titulo (opcional) |

### `criar_etapa` — Executavel

Crie uma etapa (fase) dentro de um projeto do Workspace.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `projeto_id` | integer | sim | ID do projeto |
| `nome` | string | sim | Nome da etapa |

### `criar_projeto` — Executavel

Crie um projeto no Workspace (uma frente de trabalho com objetivo). Use pra organizar um conjunto de tarefas sob uma iniciativa.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `nome` | string | sim | Nome do projeto |
| `objetivo` | string | nao | Objetivo do projeto (opcional) |

### `criar_tarefa` — Executavel

Crie uma tarefa no Workspace. Use pra registrar um trabalho a fazer. Sem projeto_id, a tarefa cai na "Caixa dos agentes".

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `titulo` | string | sim | Titulo da tarefa |
| `descricao` | string | nao | O que fazer (opcional) |
| `prioridade` | string | nao | baixa | media | alta | critica (padrao media) |
| `projeto_id` | integer | nao | ID do projeto (opcional) |

### `salvar_documento` — Executavel

Salve um documento (markdown) no Workspace. Use pra registrar uma analise, ata, plano ou qualquer texto que deva ficar guardado e consultavel depois.

| Parametro | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `titulo` | string | sim | Titulo do documento |
| `conteudo` | string | sim | Conteudo em markdown |
| `categoria` | string | nao | estrategia | relatorio | decisoes | processo | outro (opcional) |

