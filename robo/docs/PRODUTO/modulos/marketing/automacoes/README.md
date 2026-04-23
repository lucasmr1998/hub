# Marketing — Automacoes

**App:** `apps/marketing/automacoes/`

Motor de automacao do hub. Define regras que reagem a eventos do sistema e executam acoes automaticamente. Os eventos sao disparados de duas formas: **signals** (tempo real) e **cron** (periodico, a cada 5 minutos).

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [models.md](models.md) | 7 models (RegraAutomacao, NodoFluxo, ConexaoNodo, ExecucaoPendente, ControleExecucao, LogExecucao, CondicaoRegra, AcaoRegra) |
| [engine.md](engine.md) | Engine completo: BFS visual + linear legado + 8 tipos de acao + interpolacao de variaveis |
| [signals.md](signals.md) | Signals e eventos disparados |
| [editor-visual.md](editor-visual.md) | Editor Drawflow (distinto do editor de fluxos de atendimento) |
| [endpoints.md](endpoints.md) | APIs + management command + testes E2E + admin |
| [reguas-padrao.md](reguas-padrao.md) | Catalogo de reguas padrao sugeridas (templates prontos) |
| [exemplo-automacao.md](exemplo-automacao.md) | Regua C02 comentada + debug playbook (6 queries) + armadilhas conhecidas |

---

## Dois modos

| Modo | Uso | Flag |
|------|-----|------|
| **Visual (node-based)** | Recomendado — editor Drawflow com grafo de nodos | `RegraAutomacao.modo_fluxo=True` |
| **Linear (legado)** | Condicoes AND → acoes sequenciais (simples) | `RegraAutomacao.modo_fluxo=False` |

Os dois modos coexistem. Regras antigas permanecem no modo legado; novas usam visual.

---

## Arquitetura de alto nivel

```
═══════════════════════════════════════════════════════════════
  TEMPO REAL (Signals Django — post_save)
═══════════════════════════════════════════════════════════════

  Lead salvo (created=True)
      │  signal: on_lead_criado
      ▼
  engine.disparar_evento('lead_criado', contexto, tenant)
      │
      ├── Busca regras ativas com evento='lead_criado'
      ├── Para cada regra:
      │       ├── Verifica controles (rate limit, cooldown)
      │       └── _processar_fluxo() → BFS no grafo Drawflow
      │               │
      │               ├── Trigger Node → segue default
      │               ├── Condition Node → avalia campo/operador/valor
      │               │       ├── true → segue saida 1
      │               │       └── false → segue saida 2
      │               ├── Action Node → executa acao
      │               │       └── 8 tipos (ver engine.md)
      │               └── Delay Node → cria ExecucaoPendente (cron retoma)
      │
      └── Registra LogExecucao + atualiza contadores


═══════════════════════════════════════════════════════════════
  PERIODICO (Cron — executar_automacoes_cron, a cada 5 min)
═══════════════════════════════════════════════════════════════

  1. Processar delays pendentes (ExecucaoPendente)
  2. Lead sem contato (X dias sem HistoricoContato)
  3. Tarefa vencida (TarefaCRM.data_vencimento < now)
  4. Disparo por segmento (regras com segmento FK)
```

Ver [signals.md](signals.md) e [engine.md](engine.md) para detalhes.
