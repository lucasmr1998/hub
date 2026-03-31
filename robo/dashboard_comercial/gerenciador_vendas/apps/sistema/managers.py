from django.db import models


class TenantQuerySet(models.QuerySet):
    """QuerySet com helpers de tenant."""

    def for_tenant(self, tenant):
        """Filtro explícito por tenant (para quando auto-filtro está desligado)."""
        if tenant:
            return self.filter(tenant=tenant)
        return self


class TenantManager(models.Manager):
    """
    Manager que filtra automaticamente pelo tenant do request atual.

    Usa thread-local storage definido pelo TenantMiddleware.
    Fora de um request (management commands, tasks), retorna tudo.

    Uso nas views:
        leads = LeadProspecto.objects.all()  # já filtrado por tenant

    Escape hatch (admin, superuser, commands):
        leads = LeadProspecto.all_tenants.all()  # sem filtro
    """

    def get_queryset(self):
        from apps.sistema.middleware import get_current_tenant

        qs = TenantQuerySet(self.model, using=self._db)
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs
