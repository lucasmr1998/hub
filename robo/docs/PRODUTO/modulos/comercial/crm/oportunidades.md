# CRM — Oportunidades

## OportunidadeVenda

**Tabela:** `crm_oportunidades`

Entidade central do CRM. Cada lead qualificado tem uma oportunidade (1:1).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `pipeline` | FK Pipeline | Pipeline |
| `lead` | OneToOne LeadProspecto | Lead (1:1) |
| `estagio` | FK PipelineEstagio | Estagio atual |
| `responsavel` | FK User | Vendedor responsavel |
| `titulo` | CharField(255) | Titulo da oportunidade |
| `valor_estimado` | Decimal(12,2) | Valor estimado |
| `probabilidade` | Integer(50) | % de probabilidade |
| `prioridade` | CharField | baixa / normal / alta / urgente |
| `tags` | M2M TagCRM | Tags visuais |
| `plano_interesse` | FK PlanoInternet | Plano de interesse (legado, usar itens) |
| `origem_crm` | CharField | automatico / manual / importacao |
| `data_entrada_estagio` | DateTime | Para calculo de SLA |
| `motivo_perda` / `concorrente_perdido` | Text / Char | Se perdeu |
| `contrato_hubsoft_id` | CharField(100) | ID do contrato no HubSoft |
| `churn_risk_score` | Integer(0-100) | Score de risco de churn |

**Propriedades:** `dias_no_estagio`, `sla_vencido`, `valor_total_itens`
**Metodos:** `recalcular_valor()` — atualiza `valor_estimado` com soma dos itens

**Indices:** `(estagio, ativo)`, `(responsavel, estagio)`, `(data_fechamento_previsto)`, `(churn_risk_score)`

---

## ItemOportunidade

**Tabela:** `crm_itens_oportunidade`

Vincula produtos a oportunidades (N:N com quantidade e valor).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `oportunidade` | FK OportunidadeVenda | Oportunidade |
| `produto` | FK ProdutoServico | Produto/Servico |
| `quantidade` | PositiveInteger | Quantidade |
| `valor_unitario` | Decimal(10,2) | Valor unitario |
| `desconto` | Decimal(10,2) | Desconto |
| `observacao` | CharField(255) | Observacao |

**Propriedade:** `subtotal = (quantidade * valor_unitario) - desconto`

---

## Ciclo de vida

```
Lead criado (score >= 7)
    ↓
  signal auto-cria OportunidadeVenda no pipeline_padrao/estagio_inicial
    ↓
  Vendedor atribui responsavel, adiciona itens, move entre estagios
    ↓
  Chega em estagio com is_final_ganho=True
    ↓
  Envia webhook para N8N → HubSoft cria contrato
    ↓
  webhook_hubsoft_contrato retorna → preenche contrato_hubsoft_id
```

Ver [oportunidade_detalhe.html](oportunidade_detalhe) e [pipeline.html](pipeline) para as telas correspondentes.

---

## Pagina de detalhe `/crm/oportunidades/<id>/`

Layout segue padrao HubSpot/RD (hibrido), validado em 15/06/2026.

**Header**
- Avatar + nome do lead + meta-row (telefone com link wa.me, email, cadastro, origem)
- **Stage progress bar horizontal**: todos os estagios do pipeline atual em sequencia. Click em estagio nao-final move direto; click em final perdido abre modal pra capturar motivo
- Resumo numerico: Valor (inline edit), Probabilidade, Responsavel (com lapis pra trocar), Tempo no estagio
- Quick actions: Tarefa, Nota, WhatsApp, Conversa (Inbox)
- **CTAs contextuais** calculados na view:
  - `cta_proximo` — primeiro estagio nao-final apos o atual na ordem → botao primario "Avancar pra [Nome]"
  - `cta_ganho` — estagio `is_final_ganho` do pipeline → botao verde "Marcar venda" (some se ja esta em ganho)
  - `cta_perdido` — estagio `is_final_perdido` → botao vermelho outline "Marcar perda" (some se ja perdido)

**Card "Proxima acao"** (so quando ha `TarefaCRM` pendente/em_andamento/vencida)
- Cor amarela ou vermelha (se vencida) · titulo · vencimento relativo · botao "Concluir"

**Sidebar** (ordem fixa)
1. **Oportunidade** — valor inline editavel, probabilidade, origem, fechamento previsto, entrada no estagio, tags, motivo perda; botao "Editar" abre modal completo
2. **Atendimento do bot** (so quando `dados_custom.atendimento_estado` presente)
3. **Dados do lead** — email, telefone, CPF/CNPJ, cidade, estado, empresa, status API; botao "Editar" abre modal completo
4. **O.S.** (so quando `OrdemServicoTentativa.objects.filter(lead=...)` retorna algo) — lista compacta com badge de status, link pra `/comercial/ordens-servico/<grupo>/`
5. **Contratos** (so quando `ContratoTentativa.objects.filter(lead=...)` retorna algo) — lista com acao + status, link pra `/comercial/contratos/<grupo>/`
6. **Documentos** (so quando ha `DocumentoLead` ou anexos em ContratoTentativa) — consolida ambos com icone, tipo, tamanho, badge de status
7. **Hubsoft** (so quando `ClienteHubsoft.objects.filter(lead=...)` existe)

**Tabs centrais**
- **Timeline** (default) — feed unico cronologico com **chips de filtro**: Tudo, Notas, Conversas, Estagios, Tarefas, O.S., Contratos, Vendas, Automacoes. Eventos incluidos:
  - `estagio` — transicoes (HistoricoPipelineEstagio)
  - `contato` — HistoricoContato
  - `conversa_aberta` / `conversa_resolvida` — Conversa (Inbox)
  - `venda_criada` — Venda
  - `os` — OrdemServicoTentativa (com status e motivo de falha)
  - `contrato` — ContratoTentativa
  - `tarefa` — TarefaCRM (com link "marcar concluida")
  - `nota` — NotaInterna
  - `automacao` — LogExecucao do motor de automacao (regra, acao, resultado)
- **Notas** — form de adicao + lista
- **Conversas** — chat container com mensagens do Inbox

**Modais novos**
- **Editar oportunidade**: Titulo, Valor, Probabilidade, Prioridade, Origem CRM, Data fechamento previsto + secao de perda
- **Editar lead**: Identificacao (nome, email, telefone, CPF, RG, data nascimento, empresa) + Endereco + Origem/Canal/Score + Observacoes
- **Nova tarefa**: tipo, titulo, vencimento, prioridade, descricao
- Tudo salva via `PUT /crm/oportunidades/<pk>/editar/` (`api_editar_oportunidade`)

**Campos editaveis aceitos pela API**
- Oportunidade: `titulo, valor_estimado, probabilidade, prioridade, origem_crm, data_fechamento_previsto, motivo_perda, motivo_perda_categoria, motivo_ganho_categoria, concorrente_perdido` + qualquer chave `dados_custom.<key>` + `motivo_perda_ref`
- Lead: `nome_razaosocial, email, telefone, cpf_cnpj, rg, data_nascimento, cidade, estado, cep, rua, numero_residencia, bairro, empresa, observacoes, origem, canal_entrada, score_qualificacao`

**Inline edit (sidebar)**
- Elementos `.editable[data-field=...]` viram input no click; blur salva via PUT; Enter salva; Esc cancela. Auto-save por campo com toast de feedback.

**Permissoes**
- `comercial.excluir_oportunidade` controla botao "Excluir" no header
- `comercial.editar_valor_oportunidade` (adicionada em 16/06) gateia edicao inline dos campos financeiros: `valor_estimado` e `probabilidade`. Sem essa permissao, o `.editable` desses campos eh removido no template e a `api_editar_oportunidade` rejeita o campo. Superuser bypassa. Cadeado visual no label sinaliza usuario sem permissao.

**Stage bar responsiva** — media queries em 1200px (estagios estreitos com `is-current` flex maior pra destacar atual) e 900px (overflow-x: auto + min-width fixo nos steps pra rolar horizontal em mobile). Resolve "estoura com pipeline 8+ estagios".

---

## Score externo (gate para HubSoft)

Campo `LeadProspecto.score_status` (`nao_consultado / pendente / aprovado / reprovado`) + `score_atualizado_em` + `score_atualizado_por`. Usado como **trava dupla** (engine + executor) pra evitar que leads sem score aprovado disparem contrato/OS no HubSoft.

**UI** — secao "Score externo" no card "Dados do lead" da pagina de detalhe da oportunidade. Botoes:
- Aprovar (verde, gate aberto)
- Reprovar (vermelho, lead nao avanca)
- Reabrir analise (volta a `pendente`)

Salva via PUT `/crm/oportunidades/<pk>/editar/` (`api_editar_oportunidade`). Audit automatico em `score_atualizado_em` + `score_atualizado_por` quando o status muda.

**Engine de automacao (nivel 1)** — tipo de condicao novo registrado em `apps/comercial/crm/services/automacao_condicoes.py`:
- slug: `score_externo`
- operadores: `igual`, `diferente`
- coletor: le `oportunidade.lead.score_status`

Regras que tenham acoes `gerar_contrato_hubsoft`, `assinar_contrato_hubsoft` ou `abrir_os_hubsoft` devem incluir condicao `score_externo igual aprovado`. A **migration `crm/0021_score_externo_gate_nuvyon.py`** adiciona automaticamente essa condicao em todas as regras ativas do tenant Nuvyon que tenham essas acoes — idempotente (nao duplica).

**Executor (nivel 2 — defensivo)** — Trava redundante dentro do codigo das acoes pra cobrir caminhos que pulam a engine (retentar manual, signals diretos, chamada Matrix direta):
- `_acao_gerar_contrato_hubsoft` em `apps/comercial/crm/services/automacao_pipeline.py:332` — early return se `lead.score_status != 'aprovado'`
- `_acao_assinar_contrato_hubsoft` em `apps/comercial/crm/services/automacao_pipeline.py:505` — idem
- `abrir_os` em `apps/integracoes/views_matrix_os.py:193` — retorna **HTTP 409** `{motivo: 'score_bloqueado', score_status}` quando bloqueia. Garante que mesmo se o Matrix chamar direto, o HubSoft nao recebe a chamada

Combinacao protege contra:
- Fluxo normal (engine + executor)
- Retentar manual no painel `/comercial/contratos/` e `/comercial/ordens-servico/` (executor)
- Endpoint Matrix `/api/public/n8n/matrix/abrir-os/` (executor)
- Regras criadas no futuro sem condicao de score (executor)

**Por que binario** — operador da Nuvyon faz a analise externa e marca aprovado/reprovado no Hubtrix. Sem score numerico (decisao deliberada para simplificar o fluxo).

