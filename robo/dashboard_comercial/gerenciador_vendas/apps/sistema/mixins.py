from django.db import models
from apps.sistema.managers import TenantManager


class TenantMixin(models.Model):
    """
    Mixin base para todos os models que pertencem a um tenant.

    Adiciona:
      - FK tenant (nullable para migração incremental)
      - objects: TenantManager (auto-filtra pelo tenant do request)
      - all_tenants: Manager padrão (sem filtro, para admin e commands)

    Uso:
        class MeuModel(TenantMixin):
            nome = models.CharField(max_length=100)

        # Na view (auto-filtrado):
        MeuModel.objects.all()

        # No admin ou command (sem filtro):
        MeuModel.all_tenants.all()
    """
    tenant = models.ForeignKey(
        'sistema.Tenant',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s',
        verbose_name="Tenant",
        null=True,
        blank=True,
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Auto-preenche tenant se não definido e há um tenant no request."""
        if not self.tenant_id:
            from apps.sistema.middleware import get_current_tenant
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
        super().save(*args, **kwargs)
