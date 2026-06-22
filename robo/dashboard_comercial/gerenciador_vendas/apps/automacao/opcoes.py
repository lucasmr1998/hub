"""Fontes de opções dinâmicas pros campos do editor (dropdowns por tenant).

Cada fonte é uma função `(tenant) -> [{'value','label'}]`. O editor pede via
`/automacao/api/opcoes/<fonte>/` e o campo vira **dropdown** em vez de texto livre.
Tudo **read-only** e **tenant-scoped**. Adicionar uma fonte = uma função + entrada
em `FONTES`. Pros campos usarem, declarar `'fonte': '<nome>'` no `campos_config`
(ou no subcampo do evento).
"""


def _segmentos(tenant):
    from apps.comercial.crm.models import SegmentoCRM
    return [{'value': s.nome, 'label': s.nome}
            for s in SegmentoCRM.all_tenants.filter(tenant=tenant).order_by('nome')]


def _pipelines(tenant):
    from apps.comercial.crm.models import Pipeline
    return [{'value': p.slug, 'label': p.nome + (' (padrão)' if p.padrao else '')}
            for p in Pipeline.all_tenants.filter(tenant=tenant, ativo=True).order_by('-padrao', 'nome')]


def _estagios(tenant):
    from apps.comercial.crm.models import PipelineEstagio
    return [{'value': e.slug, 'label': f'{e.pipeline.nome} › {e.nome}'}
            for e in (PipelineEstagio.all_tenants.filter(tenant=tenant)
                      .select_related('pipeline').order_by('pipeline__nome', 'ordem'))]


def _responsaveis(tenant):
    from apps.sistema.models import PerfilUsuario
    out = []
    for p in (PerfilUsuario.objects.filter(tenant=tenant, user__is_staff=True, user__is_active=True)
              .select_related('user')):
        out.append({'value': p.user.username, 'label': p.user.get_full_name() or p.user.username})
    return out


FONTES = {
    'segmentos': _segmentos,
    'pipelines': _pipelines,
    'estagios': _estagios,
    'responsaveis': _responsaveis,
}


def opcoes_de(fonte, tenant):
    """Devolve as opções de uma fonte pro tenant (lista de {value, label}); [] se
    fonte desconhecida, sem tenant, ou erro (nunca levanta)."""
    fn = FONTES.get(fonte)
    if fn is None or tenant is None:
        return []
    try:
        return fn(tenant)
    except Exception:
        return []
