from django.db import models
from apps.sistema.mixins import TenantMixin


class ConfiguracaoNPS(TenantMixin):
    """Configuração de envio de pesquisas NPS por tenant."""
    periodicidade_dias = models.IntegerField(
        default=90, verbose_name="Periodicidade (dias)"
    )
    canal_envio = models.CharField(
        max_length=20,
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('email', 'E-mail'),
            ('ambos', 'Ambos'),
        ],
        default='whatsapp',
    )
    mensagem_template = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Configuração NPS"
        verbose_name_plural = "Configurações NPS"

    def __str__(self):
        return f"NPS Config (a cada {self.periodicidade_dias} dias)"


class PesquisaNPS(TenantMixin):
    """Registro individual de pesquisa NPS enviada/respondida."""
    cliente = models.ForeignKey(
        'integracoes.ClienteHubsoft',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    membro = models.ForeignKey(
        'clube.MembroClube',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    nota = models.IntegerField(verbose_name="Nota (0-10)")
    comentario = models.TextField(blank=True)
    categoria = models.CharField(
        max_length=20,
        choices=[
            ('promotor', 'Promotor 9-10'),
            ('neutro', 'Neutro 7-8'),
            ('detrator', 'Detrator 0-6'),
        ],
    )
    canal_resposta = models.CharField(max_length=20, default='whatsapp')
    data_envio = models.DateTimeField(null=True, blank=True)
    data_resposta = models.DateTimeField(null=True, blank=True)
    respondida = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Pesquisa NPS"
        verbose_name_plural = "Pesquisas NPS"
        ordering = ['-data_envio']

    def __str__(self):
        status = "respondida" if self.respondida else "pendente"
        return f"NPS #{self.pk} - nota {self.nota} ({status})"
