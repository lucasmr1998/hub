"""Base compartilhada dos nós `checklist_*`.

Os 3 nós (`checklist_proximo_item`, `checklist_validar`, `checklist_progresso`)
são a ponte fina entre o checklist configurável (dado, em `models.py` +
`services/checklist.py`) e o grafo do editor (decisão de arquitetura: a
orquestração do bot de vendas vira FLUXO, não serviço Python). Aqui só mora o
que os 3 repetiam: resolver `checklist` e `entidade` da config + do `Contexto`.
"""
from ..models import Checklist

_ENTIDADES_VALIDAS = ('lead', 'oportunidade')


def campo_checklist():
    """Campo "checklist": dropdown das opções ativas do tenant (fonte `checklists`,
    ver `opcoes.py`; value = slug, não pk, porque o `slug` já é o identificador
    estável reservado pelo model pra referência externa)."""
    return {'nome': 'checklist', 'label': 'Checklist', 'tipo': 'select',
            'fonte': 'checklists', 'obrigatorio': True}


def campo_entidade():
    """Campo "entidade": em qual entidade do `Contexto` ancorar (lead ou
    oportunidade). Sem valor, o nó assume 'lead' (o caso mais comum: bot de
    vendas conversando com um lead antes de virar oportunidade)."""
    return {'nome': 'entidade', 'label': 'Entidade', 'tipo': 'select',
            'opcoes': list(_ENTIDADES_VALIDAS),
            'ajuda': 'Padrão: lead.'}


def entidade_de(config, contexto):
    """Resolve (entidade_tipo, objeto) a partir da config + `Contexto`. Tipo
    desconhecido ou vazio cai pro default 'lead'. Objeto vem `None` quando o
    `Contexto` não carrega essa entidade (gatilho errado ou fluxo mal ligado);
    quem chama decide o branch de erro."""
    tipo = (config.get('entidade') or 'lead').strip()
    if tipo not in _ENTIDADES_VALIDAS:
        tipo = 'lead'
    entidade = contexto.lead if tipo == 'lead' else contexto.oportunidade
    return tipo, entidade


def carregar_checklist(tenant, config, contexto):
    """Resolve o slug do config (aceita `{{...}}`) e carrega o `Checklist` do
    tenant. Levanta `Checklist.DoesNotExist` quando não acha; quem chama decide
    o branch de erro (a mensagem com o slug fica mais útil montada lá, com o
    valor bruto do config em mãos)."""
    slug = str(contexto.resolver(config.get('checklist', '')) or '').strip()
    return Checklist.all_tenants.get(tenant=tenant, slug=slug)
