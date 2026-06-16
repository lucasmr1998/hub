# Automações do Pipeline

Módulo que permite configurar **regras que movem oportunidades automaticamente entre estágios do pipeline**, baseado em eventos como tags adicionadas, histórico de contato, status de documentos e integração HubSoft.

**Diferencia de Automações de Marketing:**
- Automações de Marketing → mensagens e réguas
- Automações do Pipeline → movimentação de oportunidades no funil

---

## Como funciona

1. Cada **regra** vive em um **estágio de destino** e tem uma lista de condições.
2. Condições dentro da mesma regra são avaliadas em **AND** (todas devem bater).
3. Múltiplas regras dentro do mesmo estágio são **OR** (qualquer uma basta).
4. Estágios são avaliados **dos mais avançados pros menos** (ordem DESC). O primeiro match ganha e a oportunidade é movida.
5. Estágios **finais** (`is_final_ganho` ou `is_final_perdido`) não são reavaliados.
6. A movimentação registra linha em `HistoricoPipelineEstagio` com `motivo="Regra automática: <nome>"` e dispara log de auditoria.

### Gatilhos

O motor é acionado quando:
- Uma tag é adicionada/removida em `OportunidadeVenda.tags` (signal `m2m_changed`)
- Um `HistoricoContato` é criado (signal `post_save`)
- Uma `ImagemLeadProspecto` muda de status (signal `post_save`)
- Um `ServicoClienteHubsoft` é atualizado (signal `post_save`)
- O `LeadProspecto` é salvo (signal `post_save`)

### Flag de segurança
Sempre que o engine move uma oportunidade, seta `_skip_rules_evaluation = True` antes do `save` pra evitar loop infinito de signals.

---

## Tipos de condição

| Tipo | Descrição |
|---|---|
| `tag` | Nome de tag presente em `OportunidadeVenda.tags` |
| `historico_status` | Status de qualquer `HistoricoContato` do lead |
| `lead_status_api` | Campo `status_api` do `LeadProspecto` |
| `lead_campo` | Qualquer campo do `LeadProspecto` (via nome de campo) |
| `servico_status` | `status_prefixo` de `ServicoClienteHubsoft` relacionado |
| `converteu_venda` | Existe algum `HistoricoContato` com `converteu_venda=True` |
| `imagem_status` | Status de validação das `ImagemLeadProspecto` do lead |

### Como adicionar um tipo novo

Tipos vivem em `apps/comercial/crm/services/automacao_condicoes.py` como classes. Pra adicionar um novo, basta criar uma classe com `slug`, `label`, `coletar_contexto` e `avaliar`, e decorar com `@registrar`:

```python
@registrar
class CondicaoScoreChurn:
    slug = 'score_churn'
    label = 'Score de churn'

    def coletar_contexto(self, oportunidade, contexto):
        contexto['score_churn'] = oportunidade.churn_risk_score or 0

    def avaliar(self, operador, valor, campo, contexto):
        return comparar_valor(contexto['score_churn'], operador, int(valor))
```

O registry detecta automaticamente — a UI do editor, o admin Django e o JSON das regras passam a aceitar o novo tipo sem tocar no engine nem em views.

## Operadores

| Operador | Uso |
|---|---|
| `igual` | Valor exatamente igual (ou contido em conjunto) |
| `diferente` | Valor diferente |
| `existe` | Campo/conjunto é verdadeiro/não vazio |
| `nao_existe` | Campo/conjunto é falso/vazio |
| `todas_iguais` | (`imagem_status`) TODAS as imagens com esse status |
| `nenhuma_com` | (`imagem_status`) NENHUMA imagem com esse status |

---

## Ações de automação

Além de mover a oportunidade de estágio, uma regra pode executar **ações** (campo `acoes` no `RegraPipelineEstagio`, JSON array). Cada ação é `{tipo, config}`. O dispatcher `_EXECUTORES_ACAO` (`automacao_pipeline.py`) resolve o `tipo` numa função `(oportunidade, config) -> bool` (True = efetivou, False = pulou por idempotência).

> Regra **só com ação** (sem mover estágio): deixe `estagio = null`. Regra que move estágio executa as ações no mesmo disparo.

| Ação (`tipo`) | O que faz | Config |
|---|---|---|
| `criar_venda` | Cria registro de Venda pro lead (idempotente) | — |
| `atribuir_agente` | Atribui um agente à oportunidade | — |
| `gerar_contrato_hubsoft` | Cria + anexa docs + aceita contrato no HubSoft (atômico). **Quebra "já existe" se o contrato é auto-criado** (caso Nuvyon) | `id_contrato_modelo`, `id_empresa`, ... |
| `assinar_contrato_hubsoft` | **Aceita o contrato JÁ EXISTENTE**: consulta com `incluir_contrato=sim` → pega o `id_cliente_servico_contrato` → `aceitar_contrato`. **Não cria** contrato. Pro Nuvyon (contrato auto-criado pelo HubSoft) | `ativar_servico_apos_aceite` ("sim" = chama `ativar_servico` após o aceite, pra testar destravar a OS) |
| `enviar_venda_whatsapp` | Envia resumo da venda + docs por WhatsApp (uazapi) | `telefone_destino` |

### Como adicionar uma ação nova

1. Escreva `_acao_<tipo>(oportunidade, config) -> bool` em `automacao_pipeline.py` (True se efetivou, False se pulou).
2. Registre em `_EXECUTORES_ACAO`.
3. Adicione um dict em `ACOES_DISPONIVEIS` (`crm/views.py`) com `tipo/label/descricao/icon` (+ `campos_extras` opcional `{name,label,type,help}`) — o form de regras renderiza sozinho.

**Trigger típico pro contrato:** condição `imagem_status / todas_iguais / documentos_validos` (dispara quando todas as imagens do lead são validadas).

> ⚠️ **Aceitar o contrato pode não mover o status do serviço** de "aguardando assinatura" (visto no lead 544). O `assinar_contrato_hubsoft` tem o flag `ativar_servico_apos_aceite` pra testar a ativação, mas `ativar_servico` é "pós-instalação" no HubSoft, então pode não ser o passo certo. A transição do serviço (assinatura -> instalação) ainda é ponto a confirmar com o HubSoft.

---

## Exemplo de regra (formato JSON armazenado em `condicoes`)

```json
[
  {"tipo": "tag", "operador": "igual", "valor": "Assinado"},
  {"tipo": "converteu_venda", "operador": "igual", "valor": true}
]
```

Essa regra só dispara se a oportunidade tiver a tag "Assinado" **E** algum histórico com `converteu_venda=True`.

---

## Seed de regras padrão

Management command pra criar o kit padrão num tenant:

```bash
python manage.py seed_regras_pipeline_padrao --tenant <slug|id>
python manage.py seed_regras_pipeline_padrao --all        # todos os tenants
python manage.py seed_regras_pipeline_padrao --tenant alpha --dry-run
```

Regras padrão criadas:
- **Ganho:** Histórico marcou `converteu_venda`
- **Ganho:** Tag "Assinado" foi adicionada
- **Cliente Ativo:** Serviço HubSoft com `status_prefixo=servico_habilitado`
- **Fechamento:** Todos os documentos com `status_validacao=documentos_validos`
- **Perdido:** Algum documento com `status_validacao=documentos_rejeitados`

As regras são vinculadas pelos **slugs** dos estágios: `ganho`, `cliente-ativo`, `fechamento`, `perdido`. Se o tenant não tiver um desses estágios, a regra correspondente é pulada.

---

## Endpoint `/api/leads/tags/`

Ponto de entrada externo (ex: Matrix) pra adicionar/remover tags e disparar o engine.

```http
POST /api/leads/tags/
Authorization: Bearer <api_token_do_tenant>
Content-Type: application/json

{
  "lead_id": 123,
  "tags_add": ["Comercial", "Assinado"],
  "tags_remove": []
}
```

**Retorno:**
```json
{
  "success": true,
  "lead_id": 123,
  "oportunidade_id": 45,
  "estagio_atual": "Ganho",
  "tags_adicionadas": ["Comercial", "Assinado"],
  "tags_removidas": [],
  "tags_atuais": ["Comercial", "Assinado"]
}
```

O campo `estagio_atual` já reflete o estado **após** o engine rodar — se uma regra disparou e moveu a oportunidade, o estágio retornado é o novo.

---

## UI

Módulo completo com CRUD visual:

- **Listagem:** `/crm/automacoes-pipeline/`
  - Regras agrupadas por estágio (respeita ordem dos estágios)
  - Cada regra mostra: prioridade, nome, condições em linguagem natural, disparos totais, última execução, status
  - Ações por regra: editar, ativar/desativar (toggle), duplicar, excluir
  - Botão "Nova regra" leva ao formulário
- **Formulário de criação/edição:** `/crm/automacoes-pipeline/nova/` e `/crm/automacoes-pipeline/<id>/editar/`
  - Campos: nome, estágio destino (select), prioridade, ativa
  - Editor dinâmico de condições — cada linha tem tipo/campo/operador/valor com dropdowns
  - Botão "Adicionar condição" clona linha via JS
  - Botão "Remover" em cada linha
  - Na edição, botão **Rodar preview** mostra quantas oportunidades atuais bateriam com a regra
- **Django admin:** continua disponível em `/admin/crm/regrapipelineestagio/` como fallback

---

## Multi-tenant

Todo o mecanismo é multi-tenant por design:
- `RegraPipelineEstagio` herda `TenantMixin`
- Engine filtra regras pelo `tenant` da oportunidade
- Endpoint `/api/leads/tags/` identifica tenant pelo Bearer token
- Regra do Tenant A **nunca** afeta oportunidade do Tenant B

---

## Modelos

### `RegraPipelineEstagio`
Campos principais:
- `tenant` (FK, via `TenantMixin`)
- `estagio` (FK PipelineEstagio) — estágio destino quando a regra bate
- `nome` — descrição curta ("Tag Assinado")
- `condicoes` — JSON array com as condições AND
- `ativo` (bool)
- `prioridade` (int) — menor valor avalia primeiro dentro do mesmo estágio
- `total_disparos` (int) — contador incrementado a cada movimentação bem-sucedida
- `ultima_execucao` (datetime) — marcada quando a regra dispara
- `criado_em`, `atualizado_em` (auto)

Tabela: `crm_regras_pipeline_estagio`.

## Métricas e preview

- **`total_disparos` e `ultima_execucao`** são incrementados dentro de `_mover_por_regra` após o save da oportunidade
- **Preview** (`POST /crm/automacoes-pipeline/<id>/preview/`) roda o engine em memória contra até 500 oportunidades ativas (fora de estágio final) e retorna `{ oportunidades_que_bateriam, total_avaliado }` sem movê-las
- Exibidos na listagem como stat card "Disparos totais" e coluna por regra

---

## Pagina `/crm/automacoes-pipeline/`

Layout segue padrao do DS — visualmente alinhado com `/vendas/`, `/crm/tarefas/` e demais telas.

**Header**
- Titulo + subtitulo
- Botao `?` (popover ancorado) com "Como funciona" — clique abre, click fora fecha
- "Configuracoes CRM" + "Nova regra"

**Stat cards** (4) — Regras totais (primary), Regras ativas (success), Estagios com regra (info), Disparos totais (warning).

**Filtros** — `components/list_filters.html` MODO B (grid) colapsado por default. Campos:
- Pipeline (select)
- Status (Todas / Ativas / Inativas)
- Buscar (input texto, substring case-insensitive em `regra.nome`)

Query params suportados pela view: `?pipeline=<id>&status=ativa|inativa&q=<termo>`. `active_filters_count` mostra badge no header colapsado quando ha filtros aplicados.

**Lista de pipelines** — accordion (`<details>`). Cada pipeline e um card branco com sombra leve (`.pipeline-accordion`).

**Estagios sem regras**:
- Estagios normais: linha dashed com "+ Criar regra aqui"
- Estagios finais (`is_final_ganho` / `is_final_perdido`): opacity 0.55, sem botao, texto "estagio final — regras nao reavaliadas" (engine pula esses)

**Estagios com regras** — card branco contendo `data-table` com colunas: Prio., Nome, Condicoes (AND), Executa, Acoes (efetivas/avaliacoes), Status, Ultima execucao, Acoes (toggle/duplicar/excluir).

## Referências

- Código do engine: `apps/comercial/crm/services/automacao_pipeline.py`
- Signals: `apps/comercial/crm/signals.py`
- Endpoint: `apps/comercial/leads/views.py:api_lead_tags`
- Tela read-only: `apps/comercial/crm/views.py:automacoes_pipeline_view`
- Template: `templates/crm/automacoes_pipeline.html`
- Seed command: `apps/comercial/crm/management/commands/seed_regras_pipeline_padrao.py`
- Testes: `tests/test_automacao_pipeline.py`
- Origem do design: robovendas da Megalink (sistema legado) — motor portado e adaptado pra multi-tenant
