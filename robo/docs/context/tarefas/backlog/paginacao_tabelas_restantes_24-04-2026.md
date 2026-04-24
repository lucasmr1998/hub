---
name: "Paginar tabelas restantes (tarefas, fluxos, automacoes, integracoes, inbox)"
description: "Auditoria de 24/04 revelou 9 tabelas sem paginacao. 3 ja corrigidas (notificacoes, logs auditoria, usuarios). Restam 6"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Paginacao — tabelas restantes — 24/04/2026

**Data:** 24/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ⏳ Pendente

---

## Contexto

Componente `components/pagination.html` ja existe e envolve `django.core.paginator.Paginator`. Padrao ja usado em oportunidades, segmentos, campanhas, suporte.

Auditoria 24/04:
- ✅ Minhas notificacoes (corrigido — 25/pagina)
- ✅ Logs auditoria (corrigido — 50/pagina)
- ✅ Usuarios (corrigido — 25/pagina)
- ⏳ **Tarefas** (`apps/comercial/crm/views.py::tarefas_lista`): carrega tudo e agrupa em "hoje/semana/vencidas/todas"
- ⏳ **Fluxos de atendimento** (`apps/comercial/atendimento/views.py:141`): sem paginacao
- ⏳ **Inbox conversas** (`apps/inbox/views.py:42`): sem paginacao (risco: polling + WebSocket pode complicar paginacao no scroll)
- ⏳ **Automacoes** (`apps/marketing/automacoes/views.py:25`): sem paginacao
- ⏳ **Integracoes** (`apps/integracoes/views.py:288`): sem paginacao
- ⏳ **Leads template** — API ja pagina, mas renderizacao JS nao mostra controles de paginacao

## Proposta

### Simples (3 tabelas — ~1h total)
- `automacoes_lista` → 20/pagina
- `integracoes` → 25/pagina
- `fluxos_atendimento` → 20/pagina

Padrao:
```python
from django.core.paginator import Paginator
paginator = Paginator(qs, 20)
page_obj = paginator.get_page(request.GET.get('page'))
context = {'lista': page_obj.object_list, 'page_obj': page_obj, 'query': request.GET.copy().pop('page', None).urlencode()}
```

```django
{% include "components/pagination.html" with page_obj=page_obj query=query %}
```

### Tarefas (medio — ~1h)
Tem view que monta 4 grupos: hoje, semana, vencidas, todas. Opcoes:
- **A**: Paginar so 'todas' (outros grupos sao sempre pequenos por natureza)
- **B**: Remover os grupos e deixar uma lista so com filtro de status/data

Recomendo A — menos mudanca.

### Inbox (medio-grande — ~2h)
Pagina tem polling + WebSocket. Paginar por infinite scroll OU limitar a ultimas 50 conversas e adicionar filtro de data/status pro resto. Nao usar pagination.html tradicional — UX melhor com scroll lazy.

### Leads JS (medio — ~1h)
API ja retorna `page`, `total_pages`, `count`. Falta renderizar controles em JS. Melhor: criar variante JS do componente pagination.

## Tarefas

- [ ] Automacoes de marketing (paginator simples)
- [ ] Integracoes (paginator simples)
- [ ] Fluxos de atendimento (paginator simples)
- [ ] Tarefas CRM (paginar so grupo 'todas')
- [ ] Inbox (infinite scroll ou limite + filtro)
- [ ] Leads JS (adicionar controles de paginacao ao render)

## Criterios de aceite

- Cada pagina com paginator mostra controle no rodape
- Filtros preservados nos links de paginacao (query param)
- Carga inicial < 500ms mesmo com 10k+ registros no banco
- Testes de view passam sem regressao

## Referencias

- Componente: `templates/components/pagination.html`
- Padrao em uso: `apps/comercial/crm/views.py:378` (oportunidades)
