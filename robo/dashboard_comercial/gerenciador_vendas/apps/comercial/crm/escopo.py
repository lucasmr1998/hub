"""
Escopo de visibilidade de oportunidades por usuario.

Fonte unica de verdade pra "quais responsaveis este usuario pode enxergar".
Usada no CRM (pipeline, listas, tarefas, mover) e nos relatorios
(query_builder), pra a regra viver num lugar so e nao vazar por um caminho
esquecido.

Tres niveis, dirigidos por FUNCIONALIDADE (nao por cargo), nesta ordem:
  - comercial.ver_todas_oportunidades      -> ve tudo (sem recorte)
  - comercial.ver_oportunidades_da_equipe  -> ve os times que lidera + o seu
  - nenhuma das duas                       -> ve so as suas

"Time da pessoa" = uniao de:
  - times que ela LIDERA (EquipeVendas.lider == ela). Como a FK de lider fica no
    lado do time, um gerente lidera N times.
  - o time do qual ela e MEMBRO (PerfilVendedor.equipe).
"""
from apps.sistema.decorators import user_tem_funcionalidade


def escopo_responsaveis(request):
    """
    Escopo de responsaveis visiveis pro usuario do request:
      - None       -> ve tudo (superuser ou ver_todas_oportunidades)
      - list[int]  -> ve so oportunidades desses user ids (inclui sempre ele)

    Quem tem ver_oportunidades_da_equipe mas nao lidera nem pertence a time
    algum cai no default seguro: [ele mesmo].
    """
    if user_tem_funcionalidade(request, 'comercial.ver_todas_oportunidades'):
        return None

    ids = {request.user.id}
    if user_tem_funcionalidade(request, 'comercial.ver_oportunidades_da_equipe'):
        ids |= user_ids_dos_times(request.user)
    return sorted(ids)


def times_visiveis(user):
    """IDs das equipes que o usuario enxerga: as que lidera + a que e membro.

    Filtros inerentemente por tenant: lider=user e user=user so casam com
    registros do proprio tenant do usuario (usuario pertence a um tenant so).
    """
    from apps.comercial.crm.models import EquipeVendas, PerfilVendedor
    times = set(
        EquipeVendas.objects.filter(lider=user, ativo=True)
        .values_list('id', flat=True)
    )
    equipe_id = (PerfilVendedor.objects.filter(user=user)
                 .values_list('equipe_id', flat=True).first())
    if equipe_id:
        times.add(equipe_id)
    return times


def user_ids_dos_times(user):
    """User ids dos membros ativos de todos os times visiveis ao usuario."""
    from apps.comercial.crm.models import PerfilVendedor
    times = times_visiveis(user)
    if not times:
        return set()
    return set(
        PerfilVendedor.objects.filter(equipe_id__in=times, ativo=True)
        .values_list('user_id', flat=True)
    )
