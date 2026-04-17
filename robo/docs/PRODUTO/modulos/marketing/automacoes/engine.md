# Automacoes — Engine

Arquivo: `apps/marketing/automacoes/engine.py`

O engine e o coracao do modulo. Processa eventos em dois modos: **linear legado** e **BFS em grafo visual**.

---

## Fluxo de execucao

```
Signal dispara evento
    │
    ▼
disparar_evento(evento, contexto, tenant)
    │
    ├── Busca regras ativas para o evento
    ├── Para cada regra:
    │       ├── _verificar_controles() → rate limit / cooldown
    │       ├── Se modo_fluxo=True:
    │       │       └── _processar_fluxo() → BFS no grafo
    │       └── Se modo_fluxo=False:
    │               └── _processar_regra_legacy() → linear
    │
    └── Atualiza contadores (sucesso/erro)
```

---

## Modo visual (BFS)

```
Trigger Node (0 inputs, 1 output)
    │ default
    ▼
Condition Node (1 input, 2 outputs)
    ├── true → Action Node → ...
    └── false → Action Node → ...
         │
    Delay Node → ExecucaoPendente → cron retoma
```

`_executar_nodo_e_seguir(regra, nodo, contexto, lead)`:

- **trigger:** passa para saida default
- **condition:** avalia campo/operador/valor, segue true ou false
- **delay:** cria `ExecucaoPendente` com `data_agendada`, para (cron retoma)
- **action:** executa, segue para saida default

---

## Modo legado (linear)

1. Avalia TODAS as condicoes (logica AND)
2. Se alguma falha, interrompe
3. Executa acoes sequencialmente
4. Se acao tem delay, agenda via `ExecucaoPendente`

---

## 8 tipos de acao

| Tipo | O que faz | Config |
|------|-----------|--------|
| `enviar_whatsapp` | Envia WhatsApp via N8N webhook | Template com `{{variaveis}}` |
| `enviar_email` | Envia e-mail via N8N | Assunto + corpo com `{{variaveis}}` |
| `notificacao_sistema` | Cria notificacao no painel | Mensagem |
| `criar_tarefa` | Cria `TarefaCRM` | Titulo, tipo, prioridade |
| `mover_estagio` | Move `OportunidadeVenda` | Pipeline slug + estagio slug |
| `atribuir_responsavel` | Atribui vendedor | Responsavel (auto round-robin) |
| `dar_pontos` | Da pontos no Clube de Beneficios | Pontos + motivo |
| `webhook` | Chama webhook externo | URL, metodo (GET/POST), headers |

Todas as acoes suportam variaveis de contexto: `{{lead_nome}}`, `{{lead_telefone}}`, `{{oportunidade_titulo}}`, etc.

---

## Substituicao de variaveis nos templates

| Variavel | Tipo | Disponivel em |
|----------|------|---------------|
| `lead` | Objeto LeadProspecto | Todos (exceto indicacao) |
| `lead_nome` | String | Todos |
| `lead_telefone` | String | lead_criado, lead_sem_contato |
| `lead_email` | String | lead_criado |
| `lead_origem` | String | lead_criado |
| `lead_score` | Integer | lead_criado, lead_qualificado |
| `lead_valor` | String | lead_criado |
| `telefone` | String (alias) | Todos |
| `nome` | String (alias) | Todos |
| `estagio` | String (**slug** do estagio) | oportunidade_movida |
| `estagio_nome` | String (nome amigavel) | oportunidade_movida |
| `pipeline` | String (slug) | oportunidade_movida |
| `pipeline_nome` | String (nome amigavel) | oportunidade_movida |
| `oportunidade` | Objeto | oportunidade_movida |
| `oportunidade_titulo` | String | oportunidade_movida |
| `responsavel` | String (nome completo) | oportunidade_movida |
| `dias_sem_contato` | Integer | lead_sem_contato (cron) |
| `indicacao` | Objeto | indicacao_convertida |
| `nome_indicado` | String | indicacao_convertida |
| `telefone_indicado` | String | indicacao_convertida |
| `membro_indicador` | String | indicacao_convertida |
| `segmento` | Objeto | lead_entrou_segmento |
| `segmento_nome` | String | lead_entrou_segmento |

---

## Campos disponiveis para condicoes (editor visual)

| Campo | Chave no contexto | Quando usar |
|-------|-------------------|-------------|
| Origem | `lead.origem` | lead_criado |
| Score | `lead.score_qualificacao` | lead_criado, lead_qualificado |
| Cidade | `lead.cidade` | lead_criado |
| Estado | `lead.estado` | lead_criado |
| Valor | `lead.valor` | lead_criado |
| Campanha | `lead.campanha` | lead_criado |
| Estagio | `estagio` | oportunidade_movida (slug: `demo-agendada`) |
| Estagio (CRM) | `crm.estagio` | Alias, resolve para `estagio` |
| Pipeline | `crm.pipeline` | oportunidade_movida |
| Responsavel | `crm.responsavel` | oportunidade_movida |
| Dias sem contato | `dias_sem_contato` | lead_sem_contato (cron) |
| Dias como cliente | `cliente.dias_ativo` | cliente_aniversario |
| Plano | `cliente.plano` | venda_aprovada |

---

## Controles de execucao (rate limiting)

`_verificar_controles(regra, lead)` retorna False se:

- `max_execucoes_por_lead > 0` e `total_execucoes_periodo >= max_execucoes_por_lead` dentro da janela de `periodo_limite_horas`
- `cooldown_horas > 0` e ultima execucao foi ha menos de `cooldown_horas`

Quando retorna False, a execucao e pulada com `status=bloqueado_rate_limit` no log.

---

## Adaptador NodoFluxo → AcaoRegra

No modo visual, os nodos de action sao convertidos internamente para `AcaoRegra` para reutilizar o codigo de execucao. Isso mantem uma so implementacao das 8 acoes.
