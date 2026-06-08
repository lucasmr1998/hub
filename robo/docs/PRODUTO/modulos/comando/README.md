---
modulo: Comando
status: 🟡 Dormente — schema importado, sem UI
fase_atual: 1 — preservação de dados do megaroleta
ultima_atualizacao: 29/04/2026
mono_tenant: sim (operação interna Hubtrix)
---

# Comando — operação interna Hubtrix

App **mono-tenant** (não usa `TenantMixin`) que carrega a camada de IA herdada do `megaroleta/gestao/`. Existe pra dois propósitos:

1. **Preservar dados** (configurações de agentes, prompts, tools, FAQs) que custaram tempo pra construir.
2. **Permitir desligar o megaroleta** sem perda histórica.

**Status na fase 1: DORMENTE.** Sem views, sem URLs, sem templates, sem sidebar entry. Acesso apenas via:
- Django admin (`/admin/comando/`)
- `python manage.py shell`

Será ressuscitado na **fase 3** quando decidirmos a camada de IA do produto.

## Onde fica

- **App Django:** `apps/comando/`
- **Acesso:** Django admin + shell apenas
- **Tabelas DB:** `comando_*`

## 11 models

### Agentes & Tools
| Model | Propósito |
|-------|-----------|
| `Agente` | Agente IA configurável (slug, nome, time, prompt, prompt_autonomo, modelo) |
| `ToolAgente` | Tool disponível pra agentes (executável ou conhecimento) |
| `LogTool` | Log de execução de tools (sucesso, tempo_ms, resultado completo sem truncagem) |
| `MensagemChat` | Histórico de chat 1:1 com agente (role: user/assistant) |

### Reuniões multi-agente
| Model | Propósito |
|-------|-----------|
| `Reuniao` | Sessão com múltiplos agentes (lista CSV de IDs) |
| `MensagemReuniao` | Mensagem em reunião (tipo: ceo/agente/moderador) |

### Automações + Alertas + Propostas
| Model | Propósito |
|-------|-----------|
| `Automacao` | Trigger periódico (modo: tool/agente, intervalo_horas, encaminhar_para) |
| `Alerta` | Health/estoque/churn detectado (severidade: info/aviso/critico) |
| `Proposta` | Ação proposta por agente, fila de aprovação CEO (status: pendente/aprovada/rejeitada/executada) |

### FAQ
| Model | Propósito |
|-------|-----------|
| `FAQCategoria` | Agrupador de FAQs |
| `FAQItem` | FAQ gerado por IA com hash de dados fonte pra detecção de mudanças |

## Por que mono-tenant

Os agentes foram desenhados pra **operação interna do Hubtrix** (CEO, Marketing, Sucesso, etc.) — não pra serem replicados por cliente.

Quando virar feature de produto na fase 3, decisão necessária:
- Manter mono-tenant Hubtrix-only?
- Tornar multi-tenant (cada cliente cria seus agentes)?
- Híbrido (agentes "globais" do Hubtrix + agentes "locais" do tenant)?

Por isso ficou em app separado de Workspace (multi-tenant).

## Importação de dados do megaroleta

`apps/comando/management/commands/importar_megaroleta_gestao.py`

Dois modos:

```bash
# Conexão direta no Postgres do megaroleta
python manage.py importar_megaroleta_gestao \
    --source-db-url='postgresql://user:senha@host:5432/megasorteio'

# Ou via JSON exportado
python manage.py importar_megaroleta_gestao --from-json=/path/to/export.json
```

**Flags:**
- `--check` — só valida conexão e lista contagens
- `--dry-run` — conta sem gravar
- `--truncate` — apaga dados existentes em `comando_*` antes (cuidado)

**Idempotente:** PKs originais são preservadas. Se PK já existe, skip silencioso.

**Ordem de import (dependências):**
1. `Agente`, `ToolAgente`, `Reuniao`, `FAQCategoria` (sem FK)
2. `LogTool`, `MensagemChat`, `MensagemReuniao` (FKs nos do passo 1)
3. `Automacao`, `Alerta`, `Proposta`, `FAQItem` (FKs em vários)

## Links cruzados com Workspace

Workspace aponta pra Comando via FKs nullable:

```python
# apps/workspace/models.py
class Tarefa(TenantMixin, models.Model):
    criado_por_agente = models.ForeignKey('comando.Agente', null=True, ...)
    documento_processo = models.ForeignKey('workspace.Documento', null=True, ...)

class Documento(TenantMixin, models.Model):
    agente_origem = models.ForeignKey('comando.Agente', null=True, ...)
```

Na fase 1 essas FKs ficam nulas — ativam quando a fase 3 ressuscitar a IA layer.

## Plano de evolução

| Fase | O que muda em comando |
|------|----------------------|
| **Fase 1** (atual) | Schema + dados importados, dormente |
| **Fase 2** (futura) | Pode entrar Dashboard CEO usando dados de Comando + outros apps |
| **Fase 3** (decisão de produto) | Ressuscitação. Reescreve `ai_service`, `agent_actions`, OpenAI integration. Decisão multi-tenant. UI completa |

## Histórico de migrações

| Migração | O que faz |
|----------|-----------|
| `comando.0001_initial` | Cria 11 models — sem UI, sem URLs, dormente |

## Notas técnicas

- **Sem `TenantMixin`** — propositalmente. Usa apenas `models.Manager()` padrão.
- **Sem signals** — comportamento dormente, não dispara nada.
- **Sem tasks** — Automação fica `ativo=False` por default (não roda na fase 1).
- **Admin Django registrado** — pra debug rápido e cleanup manual.
- **`apps/comando/` é leve:** só `models.py`, `admin.py`, `management/commands/`. Sem `views.py`, `urls.py`, `templates/`, `static/`, `forms.py`, `signals.py`, `services/`.
