"""Registry de propriedades escreviveis da oportunidade.

Principio do catalogo: escrever uma propriedade da oportunidade e UM no so
(`nodes/definir_propriedade_oportunidade.py`) com a propriedade escolhida em
dropdown, nunca um no dedicado por atributo. No dedicado fica reservado pra
COMPORTAMENTO (mover estagio, reabrir, atribuir responsavel, criar nota...),
onde a acao em si e o que importa, nao um par chave/valor.

Espelha o padrao de `varreduras.py`: cada propriedade e uma funcao
`fn(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True) -> dict`
que devolve `{'aplicado': bool, 'motivo_skip': str|None, 'detalhe': str}`.

Contrato de erro: handler NUNCA levanta excecao pra caso de negocio (motivo
fora do catalogo, oportunidade fora de estagio perdido, valor invalido, campo
ja preenchido...). Isso e sempre `aplicado=False` com `motivo_skip`, so bug
real (ORM quebrado, etc) sobe como excecao de verdade. Motivo: um erro
deterministico (a mesma config sempre falha do mesmo jeito) nunca deve
acionar retry, reexecutar não muda o resultado, so gasta tentativa. Achado
do piloto real do fluxo 25: o agente IA classificou uma perda com um motivo
que nao existia no catalogo do tenant e o no antigo (`definir_motivo_perda`)
levantava `ValueError`, o que fazia o runtime tratar como falha
transitoria e reexecutar à toa.

Adicionar uma propriedade nova = uma funcao + entrada em `PROPRIEDADES` (+
label, usado por `opcoes_propriedades`). Zero no novo.
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone


def _motivo_perda(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True):
    """Vincula um `MotivoPerda` ativo do tenant (por nome, case insensitive) em
    `oportunidade.motivo_perda_ref`. So mexe na FK do catalogo, o texto livre
    de detalhe fica na propriedade `detalhe_perda`.

    Rede de seguranca (achado do piloto fluxo 25): motivo de perda so se
    aplica em oportunidade que esta em estagio `is_final_perdido`. Sem essa
    trava, um agente IA classificando "perdido" incorretamente (ou rodando
    numa oportunidade que reabriu entre a varredura e a execucao) poluiria o
    dado de uma op aberta com um motivo de perda.
    """
    from apps.comercial.crm.models import MotivoPerda

    if not (oportunidade.estagio and oportunidade.estagio.is_final_perdido):
        return {
            'aplicado': False, 'motivo_skip': 'op_nao_perdida',
            'detalhe': 'Oportunidade nao esta em estagio de perda; motivo de perda nao aplicado.',
        }

    nome = (valor or '').strip()
    motivo = (
        MotivoPerda.all_tenants.filter(tenant=tenant, ativo=True, nome__iexact=nome).first()
        if nome else None
    )
    if motivo is None:
        disponiveis = ', '.join(
            MotivoPerda.all_tenants.filter(tenant=tenant, ativo=True)
            .order_by('ordem').values_list('nome', flat=True)
        ) or 'nenhum cadastrado'
        return {
            'aplicado': False, 'motivo_skip': 'motivo_nao_encontrado',
            'detalhe': f'Motivo "{valor}" nao encontrado no catalogo. Disponiveis: {disponiveis}.',
        }

    if somente_se_vazio and oportunidade.motivo_perda_ref_id:
        return {
            'aplicado': False, 'motivo_skip': 'ja_tinha',
            'detalhe': f'Oportunidade ja tem motivo de perda: {oportunidade.motivo_perda_ref.nome}.',
        }

    oportunidade.motivo_perda_ref = motivo
    oportunidade.save(update_fields=['motivo_perda_ref'])
    return {'aplicado': True, 'motivo_skip': None, 'detalhe': f'Motivo de perda definido: {motivo.nome}.'}


def _detalhe_perda(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True):
    """Texto livre do motivo de perda (`oportunidade.motivo_perda`), campo de
    contexto humano, distinto de `motivo_perda_ref` (a FK pro catalogo)."""
    if somente_se_vazio and (oportunidade.motivo_perda or '').strip():
        return {'aplicado': False, 'motivo_skip': 'ja_tinha', 'detalhe': 'Detalhe de perda ja preenchido.'}
    texto = '' if valor is None else str(valor)
    oportunidade.motivo_perda = texto
    oportunidade.save(update_fields=['motivo_perda'])
    return {'aplicado': True, 'motivo_skip': None, 'detalhe': 'Detalhe de perda gravado.'}


def _marcador(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True):
    """Grava `valor` em `oportunidade.dados_custom[chave]`. Sem `valor` (vazio),
    grava o timestamp atual (ISO 8601), o marcador de "processado em" mais
    usado pelas varreduras (freio `sem_marcador`) pra nao reprocessar o mesmo
    registro."""
    chave_limpa = (chave or '').strip()
    if not chave_limpa:
        return {'aplicado': False, 'motivo_skip': 'sem_chave', 'detalhe': 'Chave nao especificada.'}
    if somente_se_vazio and chave_limpa in (oportunidade.dados_custom or {}):
        return {
            'aplicado': False, 'motivo_skip': 'ja_tinha',
            'detalhe': f'Chave "{chave_limpa}" ja marcada.',
        }
    valor_gravado = valor if (valor is not None and valor != '') else timezone.now().isoformat()
    oportunidade.dados_custom = {**(oportunidade.dados_custom or {}), chave_limpa: valor_gravado}
    oportunidade.save(update_fields=['dados_custom'])
    return {'aplicado': True, 'motivo_skip': None, 'detalhe': f'{chave_limpa} = {valor_gravado}'}


def _valor_estimado(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True):
    """Override manual do valor estimado (`oportunidade.valor_estimado_manual`,
    escrito via a property `valor_estimado`). A fonte primaria real do valor
    exibido e a soma dos itens da oportunidade; isto e so o override quando
    ela ainda nao tem itens vinculados."""
    if somente_se_vazio and oportunidade.valor_estimado_manual:
        return {'aplicado': False, 'motivo_skip': 'ja_tinha', 'detalhe': 'Ja tem valor estimado.'}
    try:
        decimal_valor = Decimal(str(valor).strip().replace(',', '.'))
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        return {
            'aplicado': False, 'motivo_skip': 'valor_invalido',
            'detalhe': f'Valor "{valor}" nao e um numero valido.',
        }
    oportunidade.valor_estimado = decimal_valor  # setter -> valor_estimado_manual
    oportunidade.save(update_fields=['valor_estimado_manual'])
    return {'aplicado': True, 'motivo_skip': None, 'detalhe': f'Valor estimado definido: {decimal_valor}.'}


def _viabilidade_lead(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True):
    """Escreve o status de viabilidade do LEAD da oportunidade em
    `lead.dados_custom.viabilidade.status`, preservando o resto do dict.

    Existe pra fechar o ciclo aberto pela regra de viabilidade: a regra 22/26
    cria a tarefa "Validar cobertura" quando o status e fora_cobertura ou
    pendente_revisao, mas concluir a tarefa nao mexe no status, entao a regra
    (que dispara a cada movimento de estagio) recria a tarefa pra sempre.
    Marcando cobertura_ok na conclusao, a condicao da regra para de bater.

    `somente_se_vazio` aqui NAO se aplica (o objetivo e justamente sobrescrever
    o status antigo), mas o valor precisa ser um status conhecido pra nao
    poluir o dado com texto livre vindo de um fluxo mal configurado.
    """
    STATUS_VALIDOS = {'cobertura_ok', 'fora_cobertura', 'pendente_revisao', 'nao_consultado'}
    novo = (valor or '').strip()
    if novo not in STATUS_VALIDOS:
        return {
            'aplicado': False, 'motivo_skip': 'status_invalido',
            'detalhe': f'"{novo}" nao e um status de viabilidade valido ({", ".join(sorted(STATUS_VALIDOS))}).',
        }

    lead = getattr(oportunidade, 'lead', None)
    if lead is None:
        return {'aplicado': False, 'motivo_skip': 'sem_lead', 'detalhe': 'Oportunidade sem lead.'}

    dados = dict(lead.dados_custom or {})
    via = dict(dados.get('viabilidade') or {})
    if via.get('status') == novo:
        return {
            'aplicado': False, 'motivo_skip': 'ja_estava',
            'detalhe': f'Viabilidade do lead ja estava "{novo}".',
        }

    anterior = via.get('status')
    via['status'] = novo
    # Rastro da validacao humana, sem apagar o motivo original do HubSoft.
    via['origem_status'] = 'validacao_humana'
    via['validado_em'] = timezone.now().isoformat()
    if anterior:
        via['status_anterior'] = anterior
    dados['viabilidade'] = via
    lead.dados_custom = dados
    lead.save(update_fields=['dados_custom'])
    return {
        'aplicado': True, 'motivo_skip': None,
        'detalhe': f'Viabilidade do lead {anterior or "—"} -> {novo} (validacao humana).',
    }


PROPRIEDADES = {
    'motivo_perda': {'label': 'Motivo de perda (catalogo)', 'usa_chave': False, 'handler': _motivo_perda},
    'detalhe_perda': {'label': 'Detalhe da perda (texto livre)', 'usa_chave': False, 'handler': _detalhe_perda},
    'marcador': {'label': 'Marcador (dados_custom)', 'usa_chave': True, 'handler': _marcador},
    'valor_estimado': {'label': 'Valor estimado (R$)', 'usa_chave': False, 'handler': _valor_estimado},
    'viabilidade_lead': {'label': 'Status de viabilidade (lead)', 'usa_chave': False, 'handler': _viabilidade_lead},
}


def opcoes_propriedades(tenant=None):
    """Opcoes pro dropdown do campo `propriedade` do no `definir_propriedade_oportunidade`.

    `tenant` nao filtra (o catalogo de propriedades e global, nao por tenant).
    O parametro so existe pra seguir a assinatura padrao das fontes de opcoes
    (`opcoes.py:opcoes_de`, que sempre chama `fn(tenant)`).
    """
    return [{'value': k, 'label': v['label']} for k, v in PROPRIEDADES.items()]
