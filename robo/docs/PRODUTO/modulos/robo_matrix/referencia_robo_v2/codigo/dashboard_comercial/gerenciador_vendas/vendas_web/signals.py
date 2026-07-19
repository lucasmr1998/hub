import logging
import threading

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db.models.signals import post_migrate

from .models import (
    LeadProspecto, Prospecto, StatusConfiguravel, ImagemLeadProspecto,
    AtendimentoFluxo, HistoricoStatusLead,
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=LeadProspecto)
def registrar_mudanca_status_api(sender, instance: LeadProspecto, **kwargs):
    """Grava em HistoricoStatusLead sempre que `status_api` muda via `.save()`.

    Não cobre `.update()` em massa (não dispara signals do Django) — os
    poucos pontos que usam isso (ex: integracoes/signals.py) registram o
    histórico manualmente. Instância nova (sem pk) não tem "anterior" pra
    comparar, então não gera entrada (o status inicial fica implícito na
    criação do lead).
    """
    if not instance.pk:
        return
    try:
        anterior = LeadProspecto.objects.only('status_api').get(pk=instance.pk).status_api
    except LeadProspecto.DoesNotExist:
        return
    if anterior == instance.status_api:
        return
    try:
        HistoricoStatusLead.objects.create(
            lead_id=instance.pk,
            status_anterior=anterior,
            status_novo=instance.status_api,
            origem='sistema',
        )
    except Exception:
        logger.exception(
            'Falha ao registrar histórico de status_api do lead %s (%s → %s)',
            instance.pk, anterior, instance.status_api,
        )


# ════════════════════════════════════════════════════════════════════
#  NEW SERVICE → marca p/ sync (worker periódico processa)
# ════════════════════════════════════════════════════════════════════
# Receiver é conectado em vendas_web/apps.py:ready() (não com decorator
# @receiver), porque NewService está definido APÓS o import de signals
# dentro de models.py, causando circular import se importássemos aqui.
#
# Histórico: anteriormente usávamos threading.Timer(120s) aqui pra abrir
# Atendimento+OS no Matrix logo após finalização. Não era confiável:
# gunicorn recicla workers a cada max_requests=1000, matando threads
# daemon que estavam aguardando o Timer disparar.
# Agora o signal só LOGA a finalização — quem processa é o worker
# periódico (`processar_newservice_finalizados`), que respeita a janela
# de 2 min após `finalizado_em` (tempo do webdriver criar o serviço).


def disparar_sync_matrix_ao_finalizar(sender, instance, created, **kwargs):
    """Log do disparo de finalização — worker periódico processa em até 1 min.

    Sem trabalho em thread daemon: gunicorn pode reciclar o worker antes
    do delay terminar. Quem garante o sync é o systemd timer rodando
    `processar_newservice_finalizados` a cada minuto, filtrando por
    `finalizado_em <= now - 2min` (janela do webdriver).
    """
    if instance.status != 'finalizado':
        return
    if instance.matrix_sync_status != 'pendente':
        return
    logger.info(
        'NewService %s marcado como finalizado — worker periódico '
        'processará em ~1-3 min (janela de 2 min para webdriver criar serviço).',
        instance.pk,
    )


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

    # "Todas válidas" precisa significar o CONJUNTO COMPLETO do fluxo
    # (selfie+frente+verso) — no meio da coleta só a selfie existe e o
    # anexo parcial travava as fotos seguintes (caso real: lead 243).
    from .services.contrato_service import docs_do_fluxo_completos
    if not docs_do_fluxo_completos(lead):
        return

    # Marca as flags de documentação no lead AQUI (e não só no caminho
    # 'aprovado_ia'): a IA do engine grava as imagens já como
    # 'documentos_validos', pulando o receiver de promoção — sem isso o lead
    # ficava com documentacao_completa/validada=False para sempre (e o funil
    # do Analytics subcontava "Docs validados").
    from django.utils import timezone as _tz
    type(lead).objects.filter(pk=lead.pk, documentacao_validada=False).update(
        documentacao_completa=True, documentacao_validada=True,
        data_documentacao_completa=_tz.now(),
        data_documentacao_validada=_tz.now())
    lead.refresh_from_db()

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


# ════════════════════════════════════════════════════════════════════
#  IA VALIDA SEM CONFERÊNCIA HUMANA → auto-promove aprovado_ia p/ válido
#  (dispara o aceite do contrato acima). Humanos só AUDITAM depois.
# ════════════════════════════════════════════════════════════════════
@receiver(post_save, sender=ImagemLeadProspecto)
def auto_validar_documentos_pela_ia(sender, instance: ImagemLeadProspecto, **kwargs):
    """Quando a IA aprova um documento (status_validacao='aprovado_ia'), promove
    automaticamente para 'documentos_validos' — o que dispara o aceite do contrato
    no signal acima. Os humanos passam a só AUDITAR (e podem reverter depois).

    Não auto-valida se a IA tiver REPROVADO alguma imagem do lead (vai p/ auditoria).
    """
    if instance.status_validacao != ImagemLeadProspecto.STATUS_APROVADO_IA:
        return
    lead = instance.lead
    if not lead:
        return
    if lead.imagens.filter(
            status_validacao=ImagemLeadProspecto.STATUS_REJEITADO).exists():
        return
    # promove esta imagem (o save dispara o signal do contrato quando todas válidas)
    instance.status_validacao = ImagemLeadProspecto.STATUS_VALIDO
    instance.save(update_fields=['status_validacao'])
    # marca a documentação como validada quando todas as imagens estiverem válidas
    if all(s == ImagemLeadProspecto.STATUS_VALIDO
           for s in lead.imagens.values_list('status_validacao', flat=True)):
        from django.utils import timezone
        type(lead).objects.filter(pk=lead.pk, documentacao_validada=False).update(
            documentacao_validada=True, data_documentacao_validada=timezone.now())


# ════════════════════════════════════════════════════════════════════
#  ATENDIMENTO DE UPGRADE → cria UpgradePlano(status='finalizado')
#  quando o fluxo é completado. Polling externo dispara o webdriver.
# ════════════════════════════════════════════════════════════════════
@receiver(post_save, sender=AtendimentoFluxo)
def criar_upgrade_quando_atendimento_completa(sender, instance: AtendimentoFluxo,
                                              created, **kwargs):
    if instance.status != 'completado':
        return
    # Só age em fluxos do tipo upgrade — evita overhead pros outros tipos
    try:
        if instance.fluxo.tipo_fluxo != 'upgrade':
            return
    except Exception:
        return
    try:
        from .services.upgrade_plano_service import criar_upgrade_plano_do_atendimento
        criar_upgrade_plano_do_atendimento(instance)
    except Exception:
        logger.exception(
            "criar_upgrade_quando_atendimento_completa: falha ao criar "
            "UpgradePlano para atendimento %s", instance.pk,
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
