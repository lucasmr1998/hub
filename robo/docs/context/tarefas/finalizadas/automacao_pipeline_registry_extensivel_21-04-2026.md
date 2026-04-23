---
name: "Automações do Pipeline — registry extensível de tipos de condição"
description: "Transformar os 7 tipos de condição (tag, historico_status, etc.) num registry de classes plugáveis. Adicionar tipo novo deixa de exigir tocar no engine e vira só 'registrar uma classe'."
prioridade: "🟡 Média"
responsavel: "Tech"
---

# Automações do Pipeline — registry de tipos de condição — 21/04/2026

**Data:** 21/04/2026
**Responsável:** Tech
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Contexto

Hoje, em `apps/comercial/crm/services/automacao_pipeline.py::_condicao_bate`, a lógica de cada tipo de condição é um `if/elif` hardcoded:

```python
if tipo == 'tag':
    return _comparar_conjunto(contexto['tags'], operador, valor)
if tipo == 'historico_status':
    return _comparar_conjunto(contexto['historico_statuses'], operador, valor)
if tipo == 'imagem_status':
    # 6 operadores diferentes...
```

Adicionar um tipo novo (ex: `segmento_dinamico`, `score_churn`, `campo_customizado`) exige:
1. Adicionar em `automacao_constantes.TIPOS_CONDICAO`
2. Adicionar branch no `_condicao_bate` do engine
3. Adicionar coleta no `_construir_contexto`

Três pontos pra tocar a cada novo tipo. Desencoraja experimentação.

---

## Proposta

Transformar cada tipo em uma classe que se registra num registry:

```python
# services/automacao_condicoes.py
class CondicaoTag:
    slug = 'tag'
    label = 'Tag'

    def coletar_contexto(self, oportunidade, contexto):
        contexto['tags'] = set(oportunidade.tags.values_list('nome', flat=True))

    def avaliar(self, operador, valor, contexto):
        return _comparar_conjunto(contexto['tags'], operador, valor)


REGISTRY = {}

def registrar(cls):
    REGISTRY[cls.slug] = cls()
    return cls

@registrar
class CondicaoTag: ...
```

Engine passa a iterar sobre `REGISTRY` pra construir contexto e delega avaliação ao handler certo.

Ganhos:
- Tipo novo = 1 classe nova + `@registrar`. Zero mudança no engine.
- Habilita plugins internos (cada módulo pode registrar tipos próprios).
- Facilita teste unitário por tipo.
- Abre caminho pra editor visual mais rico no futuro (cada tipo pode declarar campos dinâmicos pro form).

## Tarefas

- [ ] Criar `apps/comercial/crm/services/automacao_condicoes.py` com classe base + decorator `@registrar`
- [ ] Migrar os 7 tipos existentes pra classes:
  - `CondicaoTag`, `CondicaoHistoricoStatus`, `CondicaoLeadStatusApi`, `CondicaoLeadCampo`, `CondicaoServicoStatus`, `CondicaoConverteuVenda`, `CondicaoImagemStatus`
- [ ] Refatorar `automacao_pipeline.py::_condicao_bate` pra usar o registry
- [ ] Refatorar `_construir_contexto` pra delegar a cada handler
- [ ] Manter a API pública estável (sinais e endpoints não mudam)
- [ ] Testes unitários por tipo (um test file por condição ou suite parametrizada)
- [ ] Doc atualizada em `PRODUTO/modulos/comercial/crm/automacoes-pipeline.md` explicando como registrar tipo novo

## Critério de aceite

- Nenhum `if tipo == 'X'` sobra no engine principal
- Os 14 testes existentes continuam passando sem alteração
- Novo tipo demo (ex: `CondicaoExemplo`) pode ser adicionado em 1 arquivo sem tocar no engine
- Performance equivalente (registry é dict lookup O(1))

## Dependências / bloqueia

- Depende: feature Automações do Pipeline (Fases 1-3) — ✅ concluídas
- Depende: tarefa `automacao_pipeline_preview_configuravel` é independente (pode ir antes ou depois)
- Bloqueia: futuros tipos de condição (ex: integração com scoring de IA, campos customizados por tenant)

---

## Referências

- Arquivo a refatorar: `apps/comercial/crm/services/automacao_pipeline.py` (funções `_condicao_bate` e `_construir_contexto`)
- Fonte única atual: `apps/comercial/crm/services/automacao_constantes.py`
- Doc: `robo/docs/PRODUTO/modulos/comercial/crm/automacoes-pipeline.md`
- Tarefa origem: `automacao_pipeline_crm_21-04-2026.md` (Fase 3 incompleta)
