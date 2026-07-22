"""Import do export de CRM do HubSoft (aba Oportunidades das inconsistencias).

Nao existe API de cards do HubSoft: o /crm/all so lista os boards, todo drill
da 404. Entao a unica fonte da matriz funil x funil e o export manual da Gabi
(um .xlsx). Este model guarda o ULTIMO envio por tenant.

Guardamos os cards ja parseados num JSONField em vez de uma tabela por linha de
proposito: sao ~1200 linhas de dado efemero (a proxima planilha substitui), que
nunca sao consultadas isoladamente, so recalculadas em bloco contra as nossas
oportunidades ao vivo. Uma tabela por card seria peso e migration sem retorno.
"""
from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


class ImportacaoCRMHubsoft(TenantMixin):
    """Ultimo export de CRM do HubSoft que alguem subiu, por tenant."""

    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='importacoes_crm_hubsoft', verbose_name="Enviado por",
    )
    enviado_em = models.DateTimeField(auto_now_add=True, verbose_name="Enviado em")
    nome_arquivo = models.CharField(max_length=255, blank=True, default='', verbose_name="Arquivo")
    total = models.PositiveIntegerField(default=0, verbose_name="Total de cards")

    # Lista de dicts, um por card, com as chaves que o parser normaliza:
    # id_prospecto, crm, crm_etapa, situacao, status_prospecto, nome_cartao,
    # nome_prospecto, cpf, telefone, tag, usuario, data_cadastro_cartao.
    cards = models.JSONField(default=list, blank=True, verbose_name="Cards parseados")

    class Meta:
        db_table = 'integracoes_importacao_crm'
        verbose_name = "Importacao CRM HubSoft"
        verbose_name_plural = "Importacoes CRM HubSoft"
        ordering = ['-enviado_em']
        indexes = [
            models.Index(fields=['tenant', '-enviado_em']),
        ]

    def __str__(self):
        return f"CRM HubSoft {self.total} cards ({self.enviado_em:%d/%m/%Y %H:%M})"
