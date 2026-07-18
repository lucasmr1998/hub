"""
Motor do checklist configurável: monta o roteiro elegível, acha a próxima
pergunta e registra respostas. Funções puras (sem HTTP, sem `request`) — quem
fala com o bot externo (Matrix) é a API da Fase 2, que só chama daqui.

`entidade_tipo` + `entidade_id` (em vez de FK direta) porque o mesmo checklist
pode ancorar em lead, oportunidade ou qualquer entidade futura sem migration nova.
"""
import logging

from apps.automacao.models import RespostaChecklist

logger = logging.getLogger(__name__)

# Operadores suportados em `ItemChecklist.condicao`.
_OPERADOR_EXISTE = 'existe'
_OPERADOR_NAO_EXISTE = 'nao_existe'
_OPERADOR_DIFERENTE = 'diferente'
_OPERADOR_IGUAL = 'igual'


def _condicao_bate(condicao, respostas):
    """Avalia a `condicao` de um item contra o dict de respostas já dadas
    (chave -> valor). Sem `condicao`, o item é sempre elegível.

    Operadores:
    - igual (default): respostas[chave] == valor
    - diferente: respostas[chave] != valor
    - existe: chave está no dict (independente do valor)
    - nao_existe: chave NÃO está no dict
    """
    if not condicao:
        return True
    chave = condicao.get('chave')
    operador = condicao.get('operador') or _OPERADOR_IGUAL
    tem_resposta = chave in respostas

    if operador == _OPERADOR_EXISTE:
        return tem_resposta
    if operador == _OPERADOR_NAO_EXISTE:
        return not tem_resposta
    if operador == _OPERADOR_DIFERENTE:
        return respostas.get(chave) != condicao.get('valor')
    return respostas.get(chave) == condicao.get('valor')


def itens_elegiveis(checklist, respostas_por_chave):
    """Itens ativos do checklist, na ordem, filtrando os cuja `condicao` não
    bate contra `respostas_por_chave` (dict chave -> valor já respondido)."""
    itens = checklist.itens.filter(ativo=True).order_by('ordem', 'id')
    return [item for item in itens if _condicao_bate(item.condicao, respostas_por_chave)]


def respostas_da_entidade(checklist, entidade_tipo, entidade_id):
    """Dict {chave_do_item: valor} com a resposta corrente de cada item já
    respondido pra essa entidade. Prefere `valor_processado` (normalizado)
    quando existe; cai pro `valor` bruto senão — é o que a condicao de outros
    itens e o cálculo de progresso comparam."""
    respostas = (
        RespostaChecklist.objects
        .filter(checklist=checklist, entidade_tipo=entidade_tipo, entidade_id=entidade_id)
        .select_related('item')
    )
    return {
        r.item.chave: (r.valor_processado if r.valor_processado is not None else r.valor)
        for r in respostas
    }


def proximo_item(checklist, entidade_tipo, entidade_id):
    """Primeiro item elegível ainda SEM resposta pra essa entidade. `None` =
    checklist completo (nada elegível ficou de fora)."""
    respostas = respostas_da_entidade(checklist, entidade_tipo, entidade_id)
    for item in itens_elegiveis(checklist, respostas):
        if item.chave not in respostas:
            return item
    return None


def _espelhar_em_dados_custom(item, entidade_tipo, entidade_id, valor):
    """Grava a resposta em `dados_custom[campo.slug]` da entidade, quando o
    item tem `campo` configurado. Import local (evita ciclo entre apps) e
    filtro explícito por tenant (fora de request não há auto-filtro)."""
    if entidade_tipo == 'lead':
        from apps.comercial.leads.models import LeadProspecto as Modelo
    elif entidade_tipo == 'oportunidade':
        from apps.comercial.crm.models import OportunidadeVenda as Modelo
    else:
        return

    entidade = Modelo.all_tenants.filter(pk=entidade_id, tenant_id=item.tenant_id).first()
    if entidade is None:
        return
    slug = item.campo.slug
    entidade.dados_custom = {**(entidade.dados_custom or {}), slug: valor}
    entidade.save(update_fields=['dados_custom'])


def registrar_resposta(checklist, item, entidade_tipo, entidade_id, valor, valor_processado=None, origem='bot'):
    """Grava (ou atualiza) a resposta de `item` pra essa entidade — idempotente
    pela `unique_together` (item, entidade_tipo, entidade_id): responder de
    novo é UPDATE, não linha nova."""
    resposta, _criada = RespostaChecklist.objects.update_or_create(
        item=item, entidade_tipo=entidade_tipo, entidade_id=entidade_id,
        defaults={
            'checklist': checklist,
            'tenant': checklist.tenant,
            'valor': '' if valor is None else str(valor),
            'valor_processado': valor_processado,
            'origem': origem,
        },
    )

    if item.campo_id and entidade_tipo in ('lead', 'oportunidade'):
        # Espelhar é conveniência (aparece no painel de dados do CRM), nunca pode
        # derrubar o registro da resposta em si — por isso blindado.
        try:
            _espelhar_em_dados_custom(
                item, entidade_tipo, entidade_id,
                valor_processado if valor_processado is not None else resposta.valor,
            )
        except Exception:
            logger.exception(
                'Falha ao espelhar resposta do checklist em dados_custom (item=%s, entidade=%s#%s)',
                item.pk, entidade_tipo, entidade_id,
            )

    return resposta


def progresso(checklist, entidade_tipo, entidade_id):
    """Resumo do andamento, considerando só itens OBRIGATÓRIOS elegíveis (item
    condicional que não bateu a condição não conta pra faltar)."""
    respostas = respostas_da_entidade(checklist, entidade_tipo, entidade_id)
    obrigatorios = [item for item in itens_elegiveis(checklist, respostas) if item.obrigatorio]
    faltando = [item.chave for item in obrigatorios if item.chave not in respostas]
    total = len(obrigatorios)
    respondidos = total - len(faltando)
    return {
        'total': total,
        'respondidos': respondidos,
        'faltando': faltando,
        'completo': not faltando,
        'percentual': int(round(100 * respondidos / total)) if total else 100,
    }
