import logging
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='leads.LeadProspecto')
def criar_oportunidade_automatica(sender, instance, created, **kwargs):
    """
    Cria OportunidadeVenda automaticamente quando um lead é qualificado.
    Critérios: score_qualificacao >= config.score_minimo OU status_api == 'sucesso'.
    """
    from apps.comercial.crm.models import OportunidadeVenda, ConfiguracaoCRM

    # Evitar loop de signals
    if getattr(instance, '_skip_crm_signal', False):
        return

    # Verificar se já existe oportunidade para este lead (all_tenants para funcionar em signals)
    if OportunidadeVenda.all_tenants.filter(lead=instance).exists():
        return

    try:
        config = ConfiguracaoCRM.all_tenants.filter(pk=1).first()
        if not config:
            return
    except Exception:
        return

    if not config.criar_oportunidade_automatico:
        return

    if not config.estagio_inicial_padrao:
        return

    # Critérios de qualificação
    score = getattr(instance, 'score_qualificacao', 0) or 0
    status_api = getattr(instance, 'status_api', '') or ''

    qualificado = (
        score >= config.score_minimo_auto_criacao
        or status_api == 'sucesso'
    )

    if not qualificado:
        return

    try:
        OportunidadeVenda.objects.create(
            lead=instance,
            pipeline=getattr(config, 'pipeline_padrao', None),
            estagio=config.estagio_inicial_padrao,
            valor_estimado=getattr(instance, 'valor', None),
            origem_crm='automatico',
            probabilidade=config.estagio_inicial_padrao.probabilidade_padrao,
        )
        logger.info(f"[CRM] OportunidadeVenda criada para LeadProspecto id={instance.pk}")
    except Exception as e:
        logger.error(f"[CRM] Erro ao criar OportunidadeVenda para lead {instance.pk}: {e}")


@receiver(post_save, sender='leads.HistoricoContato')
def verificar_conversao_historico(sender, instance, created, **kwargs):
    """
    Quando HistoricoContato.converteu_venda=True, move a oportunidade do lead
    para o estágio de 'ganho' automaticamente.
    """
    from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio, HistoricoPipelineEstagio

    if not created:
        return

    if not getattr(instance, 'converteu_venda', False):
        return

    lead = getattr(instance, 'lead', None)
    if not lead:
        return

    try:
        oportunidade = OportunidadeVenda.objects.select_related('estagio').get(lead=lead, ativo=True)
    except OportunidadeVenda.DoesNotExist:
        return

    # Já está em estágio de ganho
    if oportunidade.estagio.is_final_ganho:
        return

    estagio_ganho = PipelineEstagio.objects.filter(is_final_ganho=True, ativo=True).first()
    if not estagio_ganho:
        return

    try:
        estagio_anterior = oportunidade.estagio
        horas_no_estagio = (
            (timezone.now() - oportunidade.data_entrada_estagio).total_seconds() / 3600
        )

        HistoricoPipelineEstagio.objects.create(
            oportunidade=oportunidade,
            estagio_anterior=estagio_anterior,
            estagio_novo=estagio_ganho,
            motivo='Conversão automática via IVR/atendimento',
            tempo_no_estagio_horas=round(horas_no_estagio, 2),
        )

        oportunidade.estagio = estagio_ganho
        oportunidade.data_entrada_estagio = timezone.now()
        oportunidade.data_fechamento_real = timezone.now()
        campos = ['estagio', 'data_entrada_estagio', 'data_fechamento_real', 'data_atualizacao']
        if instance.valor_venda:
            oportunidade.valor_estimado = Decimal(str(instance.valor_venda))
            campos.append('valor_estimado')
        oportunidade.save(update_fields=campos)

        logger.info(f"[CRM] Oportunidade {oportunidade.pk} movida para '{estagio_ganho.nome}' por conversão IVR")
    except Exception as e:
        logger.error(f"[CRM] Erro ao mover oportunidade por conversão IVR: {e}")
