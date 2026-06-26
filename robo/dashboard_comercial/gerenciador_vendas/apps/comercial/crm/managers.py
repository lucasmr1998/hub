"""Managers customizados pra OportunidadeVenda.

Pra B (valor_estimado como property dinamica), todos filtros/aggregates SQL
precisam usar `.com_valor_estimado()` em vez do antigo campo `valor_estimado`
direto. Esse helper anota `valor_estimado_anotado` com a soma dos itens
(fallback no `valor_estimado_manual`).
"""
from django.db import models
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
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
