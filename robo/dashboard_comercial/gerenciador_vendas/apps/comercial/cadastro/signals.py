"""
Signal gerar_pdf_quando_documentos_validados migrado de vendas_web/signals.py.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.comercial.leads.models import ImagemLeadProspecto

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ImagemLeadProspecto)
def gerar_pdf_quando_documentos_validados(sender, instance: ImagemLeadProspecto, **kwargs):
    """
    Quando uma ImagemLeadProspecto é salva com status_validacao = documentos_validos,
    verifica se TODAS as imagens do lead estão aprovadas.
    Se sim:
    - Gera a URL do PDF da conversa (campo url_pdf_conversa no lead)
    - Busca os dados do atendimento via API externa e salva o HTML localmente
    """
    if instance.status_validacao != ImagemLeadProspecto.STATUS_VALIDO:
        return

    lead = instance.lead
    todas = list(lead.imagens.values_list('status_validacao', flat=True))

    if not todas:
        return

    todas_validas = all(s == ImagemLeadProspecto.STATUS_VALIDO for s in todas)

    if not todas_validas:
        return

    # Gera URL do PDF (comportamento já existente)
    if not lead.url_pdf_conversa:
        lead.gerar_url_pdf()

    # Gera HTML do atendimento se ainda não foi gerado
    if not lead.html_conversa_path:
        contato = lead.historico_contatos.filter(
            codigo_atendimento__isnull=False,
        ).exclude(codigo_atendimento='').order_by('-data_hora_contato').first()

        if contato and contato.codigo_atendimento:
            from apps.comercial.atendimento.services.atendimento_service import gerar_html_atendimento
            gerar_html_atendimento(lead, contato.codigo_atendimento)
            # Recarrega o lead para obter o html_conversa_path atualizado
            lead.refresh_from_db()

    # Anexa documentos ao contrato no HubSoft e marca como aceito
    if not lead.anexos_contrato_enviados:
        try:
            from apps.comercial.cadastro.services.contrato_service import anexar_documentos_e_aceitar_contrato
            anexar_documentos_e_aceitar_contrato(lead)
        except Exception as exc:
            logger.error(
                "Erro ao anexar documentos ao contrato (lead %s): %s",
                lead.pk,
                exc,
            )
