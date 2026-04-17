# Automacoes — Endpoints

## APIs (11 endpoints)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/marketing/automacoes/` | GET | Lista de automacoes |
| `/marketing/automacoes/criar/` | GET/POST | Criar (nome/desc) → redireciona para editor visual |
| `/marketing/automacoes/dashboard/` | GET | Dashboard central com KPIs e grafico 30 dias |
| `/marketing/automacoes/<pk>/editar/` | GET/POST | Editar nome/descricao |
| `/marketing/automacoes/<pk>/fluxo/` | GET | Editor visual Drawflow (ver [editor-visual.md](editor-visual.md)) |
| `/marketing/automacoes/<pk>/salvar-fluxo/` | POST | Salvar fluxograma (nodos + conexoes) |
| `/marketing/automacoes/<pk>/toggle/` | POST | Ativar/desativar |
| `/marketing/automacoes/<pk>/excluir/` | POST | Excluir |
| `/marketing/automacoes/<pk>/historico/` | GET | Historico de execucoes |
| `/marketing/automacoes/api/lead/<pk>/timeline/` | GET | Timeline de automacoes do lead (JSON) |

---

## Templates (5)

| Template | Descricao |
|----------|-----------|
| `lista.html` | Lista com filtros (ativas/pausadas), search, KPIs, cards por regra |
| `criar.html` | Formulario simples (nome + descricao) + aviso do editor visual |
| `editor_fluxo.html` | Editor visual Drawflow |
| `dashboard.html` | Dashboard com Chart.js (execucoes 30 dias), top regras, erros recentes, log completo |
| `historico.html` | Tabela de execucoes por regra (status, lead, resultado, timestamp) |

---

## Management command

```bash
# Executar todas as verificacoes periodicas
python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings_local

# Dry-run (apenas simula)
python manage.py executar_automacoes_cron --dry-run

# Tenant especifico
python manage.py executar_automacoes_cron --tenant megalink
```

**Executado a cada 5 minutos.** Responsabilidades:

1. **Processar delays:** busca `ExecucaoPendente` com `status=pendente` e `data_agendada <= now`, retoma execucao
2. **Lead sem contato:** busca leads sem `HistoricoContato` ha X dias, dispara `lead_sem_contato`
3. **Tarefa vencida:** busca `TarefaCRM` pendente/em_andamento com `data_vencimento` vencida, dispara `tarefa_vencida`
4. **Disparo por segmento:** busca regras com segmento vinculado, aplica `regras_filtro`, dispara `disparo_segmento` para cada lead

Detalhes do cron em [ops/02-CRON.md](../../../ops/02-CRON.md).

---

## Testes E2E

Management command `testar_automacoes` valida todos os componentes end-to-end:

```bash
python manage.py testar_automacoes --settings=gerenciador_vendas.settings_local
```

18 testes cobrindo:

- **T1:** Gatilho via signal real (cria lead → dispara → verifica notificacao no banco + lead no log)
- **T2:** Condicao com branching (score > 5 → branch TRUE executa, FALSE nao)
- **T3:** Acao notificacao (verifica criacao no banco com variaveis substituidas)
- **T4:** Acao criar tarefa (verifica no CRM: titulo, lead, responsavel)
- **T5:** Delay + pendentes (cria pendente → verifica que acao NAO executa → simula tempo → executa → verifica resultado)
- **T6:** Rate limit (2 permitidas, 3a bloqueada)
- **T7:** Fluxo completo E2E (trigger → condicao cidade=Recife → TRUE cria tarefa → FALSE nao executa)
- **T8:** Substituicao de variaveis (simples e de objeto)

---

## Admin

**RegraAutomacaoAdmin:** list com nome/evento/ativa/execucoes/taxa_sucesso. Inlines: CondicaoInline, AcaoInline (TabularInline).

**LogExecucaoAdmin:** list com regra/acao/status/data. Readonly fields. Filtros por status e regra.
