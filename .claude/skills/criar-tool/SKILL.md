---
name: criar-tool
description: Cria uma tool de agente nova no registry da engine (apps/automacao/services/ia_tools.py), com tipo + categoria, atualizando o catalogo TOOLS.md. Use quando precisar dar uma capacidade nova a um agente (consultar algo ou executar uma acao).
---

# Criar tool de agente

Receita pra criar uma **tool** (capacidade que o LLM do agente pode chamar via function-calling) no registry da engine. NAO improvise: catalogo + 1 exemplo antes de escrever.

## 0. Procure se ja existe (OBRIGATORIO)
Abra **`robo/docs/PRODUTO/modulos/automacao/TOOLS.md`** (o catalogo gerado do registry) e procure se ja existe uma tool que faz o que voce precisa.
- Existe e serve → **use ela, nao duplique**.
- Existe parecida → **estenda** (novo parametro) em vez de criar outra.
- So crie nova se realmente nao houver.

## 1. Leia o contrato (1 tool de referencia)
Em `apps/automacao/services/ia_tools.py`:
- o decorator `@_tool(chave, descricao, parametros, obrigatorios, tipo=, categoria=)` e o mapa `_CLASSIFICACAO`
- `despachar` (como a tool roda) + `TETO_RESULTADO` (o retorno e cortado em 1200 chars)
- uma tool **parecida** com a sua:
  - **conhecimento** (le/consulta, read-only) → `status_pipeline`, `listar_documentos`, `consultar_base_conhecimento`
  - **executavel** (faz/escreve, efeito colateral) → `criar_tarefa`, `salvar_documento`, `abrir_ticket`

## 2. Defina a spec
- `chave`: slug unico snake_case (ex: `atualizar_tarefa`)
- `descricao`: 1-2 frases — **o que faz + QUANDO o agente deve usar** (o LLM le isso pra decidir chamar)
- `tipo`: `conhecimento` (read-only) | `executavel` (efeito colateral)
- `categoria`: uma das do `TOOLS.md` (`dados`, `workspace`, `crm`, `atendimento`, `suporte`, `conhecimento`, `governanca`) ou uma nova, se fizer sentido
- `parametros`: dict JSON-schema `{nome: {type, description}}` (tipos: string, integer, number, boolean)
- `obrigatorios`: lista das chaves obrigatorias

## 3. Escreva a tool (co-localizada: tipo + categoria no decorator)
```python
@_tool(
    'minha_tool',
    'O que faz. Use quando ...',
    {'x': {'type': 'string', 'description': 'O que e x'}},
    ['x'],
    tipo='executavel', categoria='workspace',
)
def _minha_tool(contexto, args, agente=None):
    from apps.workspace.models import Algo  # import dentro da funcao, como as outras
    x = str(args.get('x') or '').strip()
    if not x:
        return 'x e obrigatorio.'
    obj = Algo(tenant=contexto.tenant, campo=x)   # tenant SEMPRE explicito
    obj.save()
    return f'feito: #{obj.pk}.'                    # texto curto pro LLM (nao JSON)
```
Invariantes:
- **Tenant explicito** (`contexto.tenant`), nunca thread-local. Toda query/escrita filtra por tenant (`Model.all_tenants.filter(tenant=contexto.tenant)` / `Model(tenant=contexto.tenant)`).
- Retorne **texto curto** (o cap corta em 1200). Nunca stack trace cru — trate erro e devolva mensagem.
- `executavel` arriscado/externo → considere usar `solicitar_aprovacao` (proposta) em vez de agir direto.
- Sem `print`/debug; sem imports/variaveis sobrando.

## 4. (Opcional) Habilite por padrao
Se a tool deve ir pros agentes executivos por padrao, adicione a `chave` em `TOOLS_AGENTE` no
`apps/workspace/management/commands/seed_agentes_workspace.py` e rode o seed. Senao, o usuario
liga por agente no editor (`/workspace/agentes/<id>/editar/`).

## 5. Atualize o catalogo
```bash
python manage.py gerar_catalogo_tools --settings=gerenciador_vendas.settings_local
```
Confira a tool nova no `TOOLS.md` (categoria + tipo + params corretos).

## 6. Teste (de `robo/dashboard_comercial/gerenciador_vendas/`)
```python
# python manage.py shell --settings=gerenciador_vendas.settings_local
from apps.automacao.nodes import Contexto
from apps.automacao.services.ia_tools import despachar
from apps.sistema.models import Tenant
ctx = Contexto(tenant=Tenant.objects.get(slug='aurora-hq'), variaveis={})
print(despachar('minha_tool', {'x': 'teste'}, ctx))
```
Gate: `manage.py check` limpo + a tool no `TOOLS.md` + o teste retorna o esperado + isolamento multi-tenant (tool de um tenant nunca enxerga outro).

## 7. Doc alterada → `python scripts/gerar_hub.py` (da raiz)
```

So pronto com check limpo + a tool no catalogo + teste verde.
