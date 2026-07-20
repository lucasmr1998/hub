"""
Consultas nomeadas sobre colaborador.

Existem por um motivo concreto: se cada Tool do modulo (Feedback, Recrutamento,
Treinamento) escrever seu proprio `filter(situacao=...)`, o vocabulario racha de
novo, que e exatamente o defeito D2 que a reconstrucao veio corrigir. Uma vira
"em_experiencia", outra inclui "em_admissao" no mesmo conceito, e o relatorio de
duas telas passa a discordar.

Entao a regra e: `filter(situacao=...)` so dentro de `apps/people/`. Fora daqui,
use estas funcoes. Ha varredura de codigo garantindo isso em
tests/test_people_contrato.py.
"""
from django.db.models import Count

from apps.people import estados
from apps.people.models import Colaborador


def _base(tenant=None, unidade=None):
    """Queryset base. Sem tenant explicito, confia no TenantManager."""
    if tenant is not None:
        qs = Colaborador.all_tenants.filter(tenant=tenant)
    else:
        qs = Colaborador.objects.all()
    if unidade is not None:
        qs = qs.filter(unidade=unidade)
    return qs


def colaboradores_ativos(tenant=None, unidade=None):
    """Quem esta no quadro. Desligado e freelancer ficam de fora."""
    return _base(tenant, unidade).filter(situacao__in=estados.SITUACOES_ATIVAS)


def em_experiencia(tenant=None, unidade=None):
    """Inclui quem teve a experiencia prorrogada: prorrogacao nao e estado."""
    return _base(tenant, unidade).filter(situacao=estados.SITUACAO_EM_EXPERIENCIA)


def em_admissao(tenant=None, unidade=None):
    return _base(tenant, unidade).filter(situacao=estados.SITUACAO_EM_ADMISSAO)


def efetivados(tenant=None, unidade=None):
    return _base(tenant, unidade).filter(situacao=estados.SITUACAO_EFETIVADO)


def desligados(tenant=None, unidade=None):
    return _base(tenant, unidade).filter(situacao=estados.SITUACAO_DESLIGADO)


def elegiveis_freelancer(tenant=None, unidade=None):
    """Ex colaboradores que podem voltar. Alimenta o banco de freelancers."""
    return desligados(tenant, unidade).filter(elegivel_recontratacao=True)


def pendentes_revisao(tenant=None, unidade=None):
    """
    Fila de trabalho do RH: cadastro sem CPF, com CPF invalido, ou com suspeita
    de duplicata que ninguem resolveu.
    """
    return _base(tenant, unidade).filter(pendente_revisao=True)


def contagem_por_situacao(tenant=None, unidade=None):
    """
    Dict situacao para total, com zero nas situacoes vazias.

    Uma query so. O board precisa do contador em todas as colunas, e fazer isso
    com um count por coluna e o N mais facil de introduzir sem perceber.
    """
    bruto = dict(
        _base(tenant, unidade)
        .values_list('situacao')
        .annotate(total=Count('id'))
    )
    return {situacao: bruto.get(situacao, 0) for situacao in estados.VALORES_SITUACAO}
