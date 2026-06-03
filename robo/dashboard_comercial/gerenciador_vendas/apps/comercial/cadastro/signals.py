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

    # Anexa documentos ao contrato no HubSoft (so se a feature estiver em modo automatico)
    if not lead.anexos_contrato_enviados:
        from apps.integracoes.models import IntegracaoAPI
        integ_hs = IntegracaoAPI.objects.filter(
            tenant=lead.tenant, tipo='hubsoft', ativa=True,
        ).first()
        if not integ_hs:
            logger.debug('Sem integracao HubSoft ativa pro tenant. Lead pk=%s.', lead.pk)
            return
        if not integ_hs.sync_habilitado('anexar_documentos_contrato'):
            logger.debug(
                'Modo de anexar_documentos_contrato eh "%s" (nao automatico). Lead pk=%s ignorado.',
                integ_hs.get_modo_sync('anexar_documentos_contrato'), lead.pk,
            )
            return
        try:
            from apps.comercial.cadastro.services.contrato_service import anexar_documentos_e_aceitar_contrato
            anexar_documentos_e_aceitar_contrato(lead)
        except Exception as exc:
            logger.error(
                "Erro ao anexar documentos ao contrato (lead %s): %s",
                lead.pk,
                exc,
            )


@receiver(post_save, sender=ImagemLeadProspecto)
def enviar_venda_whatsapp_quando_documentos_validados(sender, instance: ImagemLeadProspecto, **kwargs):
    """Quando TODOS docs do lead validados, manda resumo da venda por WhatsApp.

    Tarefa Workspace #151. Por enquanto:
    - Hardcoded telefone destino = 53981521653 (Lucas, teste)
    - Aplica so pra TR Carrion (tenant slug = 'tr-carrion') — depois generaliza
    - Idempotente: se ja foi enviado uma vez (lead.dados_custom.venda_whatsapp_enviada),
      pula
    """
    if instance.status_validacao != ImagemLeadProspecto.STATUS_VALIDO:
        return

    lead = instance.lead

    # Idempotencia: nao reenvia
    if (lead.dados_custom or {}).get('venda_whatsapp_enviada'):
        return

    # Confere se TODAS imagens validas
    todas = list(lead.imagens.values_list('status_validacao', flat=True))
    if not todas or not all(s == ImagemLeadProspecto.STATUS_VALIDO for s in todas):
        return

    # Escopo: so TR Carrion por enquanto (telefone teste do Lucas)
    if getattr(lead.tenant, 'slug', '') != 'tr-carrion':
        return

    TELEFONE_DESTINO_TESTE = '53981521653'

    try:
        from apps.comercial.leads.services_whatsapp_venda import enviar_venda_whatsapp
        result = enviar_venda_whatsapp(lead, TELEFONE_DESTINO_TESTE)
        logger.info(
            '[venda_whatsapp] lead=%s ok=%s texto=%s docs_ok=%s docs_falha=%s motivo=%s',
            lead.id, result.get('ok'), result.get('texto_enviado'),
            result.get('docs_enviados'), result.get('docs_falharam'),
            result.get('motivo'),
        )
        if result.get('ok'):
            # Marca idempotencia
            dc = dict(lead.dados_custom or {})
            dc['venda_whatsapp_enviada'] = True
            from django.utils import timezone as _tz
            dc['venda_whatsapp_enviada_em'] = _tz.now().isoformat()
            lead.dados_custom = dc
            lead.save(update_fields=['dados_custom'])
    except Exception as exc:
        logger.error(
            '[venda_whatsapp] Erro ao enviar venda whatsapp (lead %s): %s',
            lead.pk, exc,
        )
