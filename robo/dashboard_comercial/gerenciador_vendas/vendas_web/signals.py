from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models.signals import post_migrate

from .models import LeadProspecto, Prospecto, StatusConfiguravel, ImagemLeadProspecto


@receiver(post_save, sender=LeadProspecto)
def relate_prospecto_when_lead_has_hubsoft(sender, instance: LeadProspecto, created, **kwargs):
    """Quando um LeadProspecto com id_hubsoft é salvo, vincula Prospecto que
    tenha o mesmo id_prospecto_hubsoft automaticamente.
    """
    id_hub = (instance.id_hubsoft or '').strip()
    if not id_hub:
        return

    # Atualiza o Prospecto que tenha o mesmo id no Hubsoft para apontar este lead
    Prospecto.objects.filter(id_prospecto_hubsoft=id_hub).exclude(lead=instance).update(lead=instance)


@receiver(post_save, sender=Prospecto)
def relate_lead_when_prospecto_has_hubsoft(sender, instance: Prospecto, created, **kwargs):
    """Quando um Prospecto com id_prospecto_hubsoft é salvo e não tem lead,
    tenta relacionar com LeadProspecto cujo id_hubsoft seja igual.
    """
    if instance.lead_id:
        return

    id_hub = (instance.id_prospecto_hubsoft or '').strip()
    if not id_hub:
        return

    lead = LeadProspecto.objects.filter(id_hubsoft=id_hub).first()
    if lead:
        # Evita recursão de signals usando update direto no queryset
        Prospecto.objects.filter(pk=instance.pk, lead__isnull=True).update(lead=lead)


@receiver(post_save, sender=LeadProspecto)
def relate_prospecto_when_lead_has_hubsoft(sender, instance: LeadProspecto, created, **kwargs):
    """Quando um LeadProspecto com id_hubsoft é salvo (criado ou atualizado via API),
    tenta relacionar com Prospecto que tenha o mesmo id_prospecto_hubsoft e não tenha lead.
    """
    id_hub = (instance.id_hubsoft or '').strip()
    if not id_hub:
        return

    # Busca prospectos sem lead relacionado que tenham o mesmo id_hubsoft
    prospectos_sem_lead = Prospecto.objects.filter(
        id_prospecto_hubsoft=id_hub,
        lead__isnull=True
    )
    
    if prospectos_sem_lead.exists():
        # Relaciona todos os prospectos encontrados com este lead
        # Evita recursão de signals usando update direto no queryset
        prospectos_sem_lead.update(lead=instance)


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
            from .services.atendimento_service import gerar_html_atendimento
            gerar_html_atendimento(lead, contato.codigo_atendimento)
            # Recarrega o lead para obter o html_conversa_path atualizado
            lead.refresh_from_db()

    # Anexa documentos ao contrato no HubSoft e marca como aceito
    if not lead.anexos_contrato_enviados:
        try:
            from .services.contrato_service import anexar_documentos_e_aceitar_contrato
            anexar_documentos_e_aceitar_contrato(lead)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
                "Erro ao anexar documentos ao contrato (lead %s): %s",
                lead.pk,
                exc,
            )


@receiver(post_migrate)
def seed_default_status(sender, **kwargs):
    """Semeia valores padrão nos status configuráveis, se não existirem."""
    # Grupos e códigos padrão
    defaults = {
        'lead_status_api': [
            ('pendente', 'Pendente'),
            ('processado', 'Processado'),
            ('erro', 'Erro'),
            ('sucesso', 'Sucesso'),
            ('rejeitado', 'Rejeitado'),
            ('aguardando_retry', 'Aguardando Retry'),
            ('processamento_manual', 'Processamento Manual'),
        ],
        'prospecto_status': [
            ('pendente', 'Pendente'),
            ('processando', 'Processando'),
            ('processado', 'Processado'),
            ('erro', 'Erro'),
            ('finalizado', 'Finalizado'),
            ('cancelado', 'Cancelado'),
            ('aguardando_validacao', 'Aguardando Validação'),
            ('validacao_aprovada', 'Validação Aprovada'),
            ('validacao_rejeitada', 'Validação Rejeitada'),
        ],
        'historico_status': [
            ('fluxo_inicializado', 'Fluxo Inicializado'),
            ('fluxo_finalizado', 'Fluxo Finalizado'),
            ('transferido_humano', 'Transferido para Humano'),
            ('chamada_perdida', 'Chamada Perdida'),
            ('ocupado', 'Ocupado'),
            ('desligou', 'Desligou'),
            ('nao_atendeu', 'Não Atendeu'),
            ('abandonou_fluxo', 'Abandonou o Fluxo'),
            ('numero_invalido', 'Número Inválido'),
            ('erro_sistema', 'Erro do Sistema'),
            ('convertido_lead', 'Convertido em Lead'),
            ('venda_confirmada', 'Venda Confirmada'),
            ('venda_rejeitada', 'Venda Rejeitada'),
            ('venda_sem_viabilidade', 'Venda Sem Viabilidade'),
            ('cliente_desistiu', 'Cliente Desistiu'),
            ('aguardando_validacao', 'Aguardando Validação'),
            ('followup_agendado', 'Follow-up Agendado'),
            ('nao_qualificado', 'Não Qualificado'),
        ],
    }

    for grupo, pares in defaults.items():
        for ordem, (codigo, rotulo) in enumerate(pares, start=1):
            StatusConfiguravel.objects.get_or_create(
                grupo=grupo,
                codigo=codigo,
                defaults={'rotulo': rotulo, 'ativo': True, 'ordem': ordem},
            )
