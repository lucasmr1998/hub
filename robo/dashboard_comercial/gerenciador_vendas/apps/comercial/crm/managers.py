"""Managers customizados pra OportunidadeVenda.

Pra B (valor_estimado como property dinamica), todos filtros/aggregates SQL
precisam usar `.com_valor_estimado()` em vez do antigo campo `valor_estimado`
direto. Esse helper anota `valor_estimado_anotado` com a soma dos itens
(fallback no `valor_estimado_manual`).
"""
from django.db import models
from django.db.models import (
    Case, Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When,
)
from django.db.models.functions import Coalesce

from apps.sistema.managers import TenantManager, TenantQuerySet


_DEC12 = DecimalField(max_digits=12, decimal_places=2)


class OportunidadeQuerySet(TenantQuerySet):
    """QuerySet com helpers de calculo do valor estimado.

    Use `.com_valor_estimado()` antes de qualquer filter/order/aggregate que
    dependa do valor estimado:

        OportunidadeVenda.objects.com_valor_estimado().filter(
            valor_estimado_anotado__gte=100
        )

        OportunidadeVenda.objects.com_valor_estimado().aggregate(
            total=Sum('valor_estimado_anotado')
        )
    """

    def com_valor_estimado(self):
        return self.annotate(
            _soma_itens=Coalesce(
                Sum(
                    F('itens__quantidade') * F('itens__valor_unitario')
                    - F('itens__desconto'),
                    output_field=_DEC12,
                ),
                Value(0, output_field=_DEC12),
                output_field=_DEC12,
            ),
            valor_estimado_anotado=Case(
                When(_soma_itens__gt=0, then=F('_soma_itens')),
                default=Coalesce(
                    F('valor_estimado_manual'),
                    Value(0, output_field=_DEC12),
                    output_field=_DEC12,
                ),
                output_field=_DEC12,
            ),
        )

    def totais_por_estagio(self):
        """{estagio_id: (total, total_valor)} calculado no banco, sobre o filtro inteiro.

        Existe pra que o cabecalho da coluna do kanban NAO dependa da lista
        carregada: com paginacao por coluna, `len(ops)` viraria o tamanho da
        pagina e a tela mentiria (foi exatamente o bug do contador da aba de
        tarefas concluidas, e no board e pior: o vendedor decide o dia olhando
        esse numero).

        Nao da pra usar `Sum('valor_estimado_anotado')`: o ORM proibe somar um
        aggregate de outro aggregate. Entao a soma dos itens entra como subquery
        escalar, o que de quebra tira o JOIN (e o risco de Count inflado).
        Equivalencia conferida contra os valores reais de prod nos dois tenants.
        """
        from apps.comercial.crm.models import ItemOportunidade

        zero = Value(0, output_field=_DEC12)
        soma_itens = Subquery(
            ItemOportunidade.objects.filter(oportunidade_id=OuterRef('pk'))
            .values('oportunidade_id')
            .annotate(s=Sum(
                F('quantidade') * F('valor_unitario') - F('desconto'),
                output_field=_DEC12,
            ))
            .values('s')[:1],
            output_field=_DEC12,
        )
        # all_tenants aqui NAO abre escopo: os ids vem do proprio self, que ja
        # carrega o filtro de tenant. Usar .objects aplicaria o tenant de novo e
        # brigaria com o escopo do self quando ele vier de all_tenants.
        linhas = (
            self.model.all_tenants.filter(id__in=Subquery(self.values('id')))
            .annotate(_si=Coalesce(soma_itens, zero, output_field=_DEC12))
            .annotate(_v=Case(
                When(_si__gt=0, then=F('_si')),
                default=Coalesce(F('valor_estimado_manual'), zero, output_field=_DEC12),
                output_field=_DEC12,
            ))
            .values('estagio_id')
            .annotate(total=Count('id'), total_valor=Sum('_v'))
        )
        return {
            l['estagio_id']: (l['total'], float(l['total_valor'] or 0))
            for l in linhas
        }


class OportunidadeManager(TenantManager):
    """Manager filtrado por tenant + helpers de valor_estimado."""

    def get_queryset(self):
        from apps.sistema.middleware import get_current_tenant

        qs = OportunidadeQuerySet(self.model, using=self._db)
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs

    def com_valor_estimado(self):
        return self.get_queryset().com_valor_estimado()


class OportunidadeAllTenantsManager(models.Manager):
    """Manager sem filtro de tenant (admin/commands), com helpers de valor_estimado."""

    def get_queryset(self):
        return OportunidadeQuerySet(self.model, using=self._db)

    def com_valor_estimado(self):
        return self.get_queryset().com_valor_estimado()
