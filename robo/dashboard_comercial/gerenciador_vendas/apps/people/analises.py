"""
Metricas do departamento pessoal.

Tudo aqui sai do `HistoricoSituacao`, que existe desde o passo 4 justamente
porque foi desenhado como fonte primaria de telemetria e nao como log
decorativo. Nenhuma metrica precisou de instrumentacao nova.

A escolha que mais importa: EFETIVACAO E POR COORTE. "Dos que entraram neste
periodo, quantos ja foram efetivados" responde a pergunta do RH. Dividir
efetivados do mes por cadastrados do mes compara gente diferente e produz
numero que sobe quando a operacao piora.
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.people import estados
from apps.people.models import Colaborador, HistoricoSituacao


# Quantos dias sem avancar ate o cadastro contar como parado. O produto de
# origem usa 3 e chama de "acao necessaria".
DIAS_PARA_PARADO = 3

# Situacoes em que ficar parado e problema. Efetivado nao entra: ficar efetivado
# e o objetivo, nao uma fila.
SITUACOES_EM_ANDAMENTO = (
    estados.SITUACAO_CADASTRO,
    estados.SITUACAO_EM_ADMISSAO,
    estados.SITUACAO_EM_EXPERIENCIA,
)


def _intervalo(dias):
    fim = timezone.now()
    return fim - timedelta(days=dias), fim


def resumo(tenant, dias=30, unidade=None):
    """Os cinco numeros do topo, com comparacao contra o periodo anterior."""
    inicio, fim = _intervalo(dias)
    inicio_anterior = inicio - timedelta(days=dias)

    base = Colaborador.all_tenants.filter(tenant=tenant)
    if unidade is not None:
        base = base.filter(unidade=unidade)

    coorte = base.filter(criado_em__gte=inicio, criado_em__lt=fim)
    coorte_anterior = base.filter(criado_em__gte=inicio_anterior, criado_em__lt=inicio)

    cadastros = coorte.count()
    cadastros_antes = coorte_anterior.count()

    # Efetivados DESTA coorte: quem entrou no periodo e ja chegou em efetivado,
    # independente de quando chegou. E o que responde "o funil esta andando?".
    efetivados_coorte = coorte.filter(
        historico_situacao__para=estados.SITUACAO_EFETIVADO).distinct().count()

    desligamentos = HistoricoSituacao.all_tenants.filter(
        tenant=tenant, para=estados.SITUACAO_DESLIGADO,
        criado_em__gte=inicio, criado_em__lt=fim,
    )
    desligamentos_antes = HistoricoSituacao.all_tenants.filter(
        tenant=tenant, para=estados.SITUACAO_DESLIGADO,
        criado_em__gte=inicio_anterior, criado_em__lt=inicio,
    )
    if unidade is not None:
        desligamentos = desligamentos.filter(colaborador__unidade=unidade)
        desligamentos_antes = desligamentos_antes.filter(colaborador__unidade=unidade)

    return {
        'cadastros': cadastros,
        'cadastros_variacao': _variacao(cadastros, cadastros_antes),
        'taxa_efetivacao': round(100 * efetivados_coorte / cadastros, 1) if cadastros else 0.0,
        'efetivados_coorte': efetivados_coorte,
        'parados': len(parados(tenant, unidade=unidade)),
        'desligamentos': desligamentos.count(),
        'desligamentos_variacao': _variacao(desligamentos.count(), desligamentos_antes.count()),
        'dias': dias,
    }


def _variacao(atual, anterior):
    """Percentual contra o periodo anterior. None quando nao ha base."""
    if not anterior:
        return None
    return round(100 * (atual - anterior) / anterior, 1)


def parados(tenant, unidade=None, dias=DIAS_PARA_PARADO):
    """
    Colaboradores sem avancar ha mais de N dias.

    E a metrica operacional do modulo: nao interessa quantos entraram, interessa
    quantos travaram. "Parado" e medido pela ultima transicao, nao pela data de
    cadastro, senao quem avancou ontem depois de duas semanas apareceria como
    parado.
    """
    limite = timezone.now() - timedelta(days=dias)

    base = (Colaborador.all_tenants
            .filter(tenant=tenant, situacao__in=SITUACOES_EM_ANDAMENTO)
            .select_related('unidade'))
    if unidade is not None:
        base = base.filter(unidade=unidade)

    travados = []
    for colaborador in base:
        ultima = (colaborador.historico_situacao
                  .order_by('-criado_em')
                  .values_list('criado_em', flat=True)
                  .first())
        referencia = ultima or colaborador.criado_em
        if referencia < limite:
            travados.append({
                'colaborador': colaborador,
                'desde': referencia,
                'dias': (timezone.now() - referencia).days,
            })

    travados.sort(key=lambda t: t['dias'], reverse=True)
    return travados


def por_unidade(tenant, dias=30):
    """
    Cartao por loja, com o status operacional.

    O produto de origem chama de "lojas por prioridade" e mostra o texto da acao
    junto do numero. Numero sem interpretacao vira dashboard que ninguem olha.
    """
    inicio, fim = _intervalo(dias)
    travados_por_unidade = {}
    for item in parados(tenant):
        chave = item['colaborador'].unidade_id
        travados_por_unidade[chave] = travados_por_unidade.get(chave, 0) + 1

    from apps.people.models import Unidade

    linhas = []
    for unidade in Unidade.all_tenants.filter(tenant=tenant, ativo=True):
        cadastros = Colaborador.all_tenants.filter(
            tenant=tenant, unidade=unidade,
            criado_em__gte=inicio, criado_em__lt=fim).count()
        efetivados = Colaborador.all_tenants.filter(
            tenant=tenant, unidade=unidade,
            situacao=estados.SITUACAO_EFETIVADO).count()
        travados = travados_por_unidade.get(unidade.pk, 0)

        if travados >= 3:
            status, variante = f'{travados} parados, acao necessaria', 'danger'
        elif travados:
            status, variante = f'{travados} parado{"s" if travados > 1 else ""}, monitorar', 'warning'
        else:
            status, variante = 'Admissao saudavel, sem pendencias', 'success'

        linhas.append({
            'unidade': unidade,
            'cadastros': cadastros,
            'efetivados': efetivados,
            'parados': travados,
            'status': status,
            'variante': variante,
        })

    # Quem precisa de acao primeiro.
    linhas.sort(key=lambda l: l['parados'], reverse=True)
    return linhas


def funil(tenant, dias=30, unidade=None):
    """
    Quantos estao em cada fase do ciclo agora.

    E foto, nao fluxo: responde "onde a fila esta" e nao "quantos passaram".
    """
    base = Colaborador.all_tenants.filter(tenant=tenant)
    if unidade is not None:
        base = base.filter(unidade=unidade)

    contagem = dict(
        base.values_list('situacao').annotate(total=Count('id')))

    etapas = [
        estados.SITUACAO_CADASTRO,
        estados.SITUACAO_EM_ADMISSAO,
        estados.SITUACAO_EM_EXPERIENCIA,
        estados.SITUACAO_EFETIVADO,
    ]
    maximo = max([contagem.get(e, 0) for e in etapas] + [1])

    return [
        {
            'situacao': etapa,
            'rotulo': estados.rotulo(etapa),
            'total': contagem.get(etapa, 0),
            'percentual': round(100 * contagem.get(etapa, 0) / maximo, 1),
        }
        for etapa in etapas
    ]


def evolucao_mensal(tenant, meses=6, unidade=None):
    """Cadastros e desligamentos por mes, pro grafico de tendencia."""
    from django.db.models.functions import TruncMonth

    inicio = timezone.now() - timedelta(days=meses * 31)

    cadastros = Colaborador.all_tenants.filter(tenant=tenant, criado_em__gte=inicio)
    desligamentos = HistoricoSituacao.all_tenants.filter(
        tenant=tenant, para=estados.SITUACAO_DESLIGADO, criado_em__gte=inicio)
    if unidade is not None:
        cadastros = cadastros.filter(unidade=unidade)
        desligamentos = desligamentos.filter(colaborador__unidade=unidade)

    def por_mes(queryset):
        return {
            linha['mes'].date(): linha['total']
            for linha in queryset.annotate(mes=TruncMonth('criado_em'))
                                 .values('mes').annotate(total=Count('id'))
        }

    mapa_cadastros = por_mes(cadastros)
    mapa_desligamentos = por_mes(desligamentos)

    meses_ordenados = sorted(set(mapa_cadastros) | set(mapa_desligamentos))
    return [
        {
            'mes': mes,
            'cadastros': mapa_cadastros.get(mes, 0),
            'desligamentos': mapa_desligamentos.get(mes, 0),
            'saldo': mapa_cadastros.get(mes, 0) - mapa_desligamentos.get(mes, 0),
        }
        for mes in meses_ordenados
    ]
