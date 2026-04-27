---
name: "CS — NPS + Retenção unificada (apps/cs/retencao + apps/cs/nps)"
description: "Resolver o legado de retenção duplicada (CRM vs CS) E implementar NPS + Retenção como módulos CS adultos. Consolida tarefas anteriores cs_nps_retencao + retencao_unificar_cs."
prioridade: "🟡 Média"
responsavel: "PM (escopo) + Tech Lead (implementação)"
---

# CS — NPS e Retenção (decidir e fechar) — 26/04/2026

**Data:** 26/04/2026
**Responsável:** PM (escopo) + Tech Lead (implementação)
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando decisão de escopo

---

## Contexto

Na auditoria de paridade CS megaroleta vs robo (26/04/2026), foram identificados 2 submódulos com pasta criada em `apps/cs/` mas **sem implementação**:

1. **`apps/cs/nps/`** — pasta existe, `urls.py` e `views.py` vazios. Não aparece no menu hoje.
2. **`apps/cs/retencao/`** — pasta existe, vazia. **Aparece no menu** (item "Retenção"), mas o link aponta pra `/crm/retencao/` (rota Comercial) e não pra `/cs/retencao/`.

**Ambos não vieram do megaroleta** — são propostas novas que ficaram só com a casca.

---

## Decisão necessária

Pra cada submódulo, decidir entre:

**A) Implementar agora** (definir escopo + dev + entrega)
**B) Remover do menu** (esconder até ter algo real pra mostrar)
**C) Manter no menu como "Em breve"** (placeholder visual com aviso de roadmap)

**Risco da inação:** quem clica em "Retenção" hoje cai numa view inexistente ou em algo de Comercial que não tem nada a ver. Compromete confiança no produto.

---

## NPS — proposta de escopo (se for implementar)

### O que faz
Programa de coleta + análise de NPS automatizado, integrado ao fluxo do cliente.

### Funcionalidades mínimas (MVP)
- [ ] Régua automática de envio de NPS (ex: 30 dias após ativação, depois trimestral)
- [ ] Pergunta padrão "De 0 a 10, o quanto você indicaria nossa internet pra um amigo?" + comentário aberto
- [ ] Canal de envio: WhatsApp via integração de canais existente
- [ ] Dashboard com:
  - Score NPS atual (% promotores - % detratores)
  - Distribuição (promotor / neutro / detrator)
  - Evolução temporal (linha)
  - Comentários recentes
  - Filtros por período, plano, cidade
- [ ] Hook automático: detrator (nota 0-6) cria ticket de retenção no módulo Retenção
- [ ] Hook automático: promotor (nota 9-10) entra na régua de indicação

### Arquivos a criar
- `apps/cs/nps/models.py` — `RespostaNPS`, `CampanhaNPS`
- `apps/cs/nps/views.py` — dashboard + API de coleta
- `apps/cs/nps/urls.py` — rotas
- `apps/cs/nps/templates/nps/` — dashboard, detalhe
- `apps/cs/nps/services.py` — disparo, classificação, hook em Retenção/Indicação

### Permissões novas
- `cs.nps.ver` — ver dashboard
- `cs.nps.configurar` — alterar campanha/régua

---

## Retenção — proposta de escopo (se for implementar)

### O que faz
Programa de retenção preditiva: identifica clientes em risco de churn antes que cancelem e dispara ações.

### Funcionalidades mínimas (MVP)
- [ ] Score de risco de churn por cliente (modelo simples baseado em sinais: chamado de suporte recente, atraso no pagamento, NPS detrator, queda de uso)
- [ ] Lista priorizada "Clientes em risco" com filtros
- [ ] Ações pré-configuradas (ofertar upgrade, conceder desconto, agendar visita técnica)
- [ ] Histórico de ações por cliente
- [ ] Hook automático com NPS detrator → entra na lista
- [ ] Hook automático com chamado de suporte > 7 dias sem resolução → entra na lista
- [ ] Dashboard com:
  - Total de clientes em risco
  - Distribuição por motivo
  - Taxa de recuperação (cliente que entrou na lista e foi salvo)

### Arquivos a criar
- `apps/cs/retencao/models.py` — `ClienteRisco`, `AcaoRetencao`, `MotivoRisco`
- `apps/cs/retencao/views.py` — dashboard + lista + detalhe
- `apps/cs/retencao/services.py` — score, hooks, regras
- `apps/cs/retencao/urls.py` — rotas próprias
- `apps/cs/retencao/templates/retencao/` — dashboard, lista, detalhe
- **Importante:** mover o link do menu de `/crm/retencao/` (errado) pra `/cs/retencao/` (correto) em [partials/sidebar_subnav.html](robo/dashboard_comercial/gerenciador_vendas/templates/partials/sidebar_subnav.html#L141)

### Permissões novas
- `cs.retencao.ver` — ver lista e dashboard
- `cs.retencao.agir` — criar/aprovar ação
- `cs.retencao.configurar` — alterar regras de risco

---

## Caminho mais curto pra fechar a UX (se a decisão for B "remover")

Se a decisão for adiar a implementação (B), o quick-fix é:
1. Remover o item "Retenção" de [partials/sidebar_subnav.html](robo/dashboard_comercial/gerenciador_vendas/templates/partials/sidebar_subnav.html) (linhas 141-143)
2. Manter as pastas `apps/cs/nps/` e `apps/cs/retencao/` (placeholder pro futuro) ou deletar pra limpar
3. Atualizar `core/00-STATUS.md` registrando "NPS e Retenção: planejados, sem ETA"

5 minutos de trabalho.

---

## Recomendação

**Implementar NPS primeiro (MVP enxuto), Retenção depois.** Razões:
- NPS é input pro Retenção (detrator vira lead de risco). Sem NPS, Retenção opera no escuro.
- NPS é mais simples de validar (1 pergunta, 1 score, 1 dashboard).
- O dado de NPS já dá valor isoladamente (gestor vê satisfação).

---

## Trabalho técnico de unificação (absorvido de `retencao_unificar_cs_20-04-2026`)

Antes de implementar Retenção do zero, precisa **resolver duplicação existente**:

### Hoje há 2 apps de retenção:

1. **`apps/comercial/crm/`** — implementação em uso:
   - Model `AlertaRetencao` em `crm/models.py`
   - View `retencao_view` em `crm/views.py:1177`
   - Template `crm/templates/crm/retencao.html` (migrado pro DS em 2026-04-20)
   - URL `/crm/retencao/`

2. **`apps/cs/retencao/`** — app embrionário criado mas não implementado:
   - Models novos: `ScoreCliente` (health score 0-100), `AlertaChurn` (alerta de cancelamento)
   - `views.py` com 2 linhas, `urls.py` com 5 linhas — sem view funcional

**Problema:** retenção é função CS (pós-venda), não CRM (pré-venda). Código está no app errado.

### Tarefas de unificação (pré-implementação)

- [ ] **Decidir produto:** `AlertaRetencao` (CRM atual) e `AlertaChurn` (CS embrionário) são a mesma entidade com nomes diferentes, ou conceitos coexistentes? Decidir antes de mexer no código.
- [ ] **Mover model:** `AlertaRetencao` sai de `crm/models.py` e vai pra `cs/retencao/models.py`. Migration com `db_table` override pra manter mesma tabela no PostgreSQL (senão precisa renomear em prod — risco).
- [ ] **Mover view + URL:** `retencao_view` sai de `crm/views.py` e vai pra `cs/retencao/views.py`. URL passa de `/crm/retencao/` pra `/cs/retencao/`. **Adicionar redirect** `/crm/retencao/ → /cs/retencao/` pra não quebrar bookmarks.
- [ ] **Mover template:** `crm/templates/crm/retencao.html` + `_retencao_row.html` → `cs/retencao/templates/retencao/`.
- [ ] **Atualizar imports:** 13 arquivos referenciam `AlertaRetencao` ou rota retenção:
  - `apps/comercial/crm/admin.py`
  - `apps/integracoes/management/commands/seed_demo_vendas.py`
  - `apps/sistema/management/commands/seed_planos.py`
  - Signals, management commands, crons que usam o model.
- [ ] **Atualizar sidebar:** `partials/sidebar_subnav.html` — trocar `/crm/retencao/` por `/cs/retencao/` no link CS.
- [ ] **Migrations:** testar local antes de prod.
- [ ] **Tests:** garantir tests existentes passam após o move; smoke test da nova URL.
- [ ] **Doc:** atualizar `robo/docs/PRODUTO/modulos/cs/`.

### Sequência sugerida

1. **Unificação técnica** (mover model+view+template do CRM pro CS, redirect, migrations)
2. **Implementar NPS** (apps/cs/nps/) — MVP enxuto
3. **Expandir Retenção** com hooks de NPS e tickets de suporte (já no app correto após passo 1)

---

## Histórico

- **20/04/2026:** tarefa `retencao_unificar_cs` criada (refactor técnico)
- **26/04/2026:** auditoria de paridade CS revelou também NPS embrionário; tarefa `cs_nps_retencao` criada
- **26/04/2026:** as duas tarefas foram consolidadas nesta — faz mais sentido fazer unificação + implementação num movimento único do que separar refactor de feature

**Stretch:** se o tempo apertar, cortar Retenção pra v2 e remover do menu enquanto isso. Não tem sentido manter visível algo que não existe.

---

## Bloqueador

**Decidir A vs B vs C antes de qualquer linha de código.** Sem essa decisão, vira retrabalho.

---

## Referência cruzada

- [PRODUTO/modulos/cs/](../../../PRODUTO/modulos/cs/) — spec do módulo
- [Auditoria CS megaroleta vs robo, 26/04/2026](../../reunioes/) — contexto
- Commit `744d323` — adicionou demais itens CS ao menu
