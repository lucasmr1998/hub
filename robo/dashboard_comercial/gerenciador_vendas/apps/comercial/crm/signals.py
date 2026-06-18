import logging
from decimal import Decimal

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='leads.LeadProspecto')
def criar_oportunidade_automatica(sender, instance, created, **kwargs):
    """
    Cria OportunidadeVenda automaticamente assim que um lead nasce.

    - Lead novo qualificado (score >= minimo OU status_api='sucesso'):
        OportunidadeVenda(is_rascunho=False) — aparece no funil normal,
        recebe distribuicao automatica.
    - Lead novo NAO qualificado:
        OportunidadeVenda(is_rascunho=True) — escondida do funil padrao,
        nao recebe distribuicao. Serve pra motor de automacao do CRM poder
        disparar regras (ex: sincronizar_prospecto_hubsoft) desde a chegada
        do lead. Quando qualifica, signal `qualificar_oportunidade_rascunho`
        marca is_rascunho=False e ela vira oportunidade normal.
    """
    from apps.comercial.crm.models import OportunidadeVenda, ConfiguracaoCRM

    # Evitar loop de signals
    if getattr(instance, '_skip_crm_signal', False):
        return

    # Verificar se já existe oportunidade para este lead
    if OportunidadeVenda.all_tenants.filter(lead=instance).exists():
        return

    try:
        config = ConfiguracaoCRM.all_tenants.filter(tenant=instance.tenant).first()
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

    try:
        oportunidade = OportunidadeVenda.objects.create(
            lead=instance,
            pipeline=getattr(config, 'pipeline_padrao', None),
            estagio=config.estagio_inicial_padrao,
            valor_estimado=getattr(instance, 'valor', None),
            origem_crm='automatico',
            probabilidade=config.estagio_inicial_padrao.probabilidade_padrao,
            is_rascunho=not qualificado,
        )
        logger.info(
            f"[CRM] OportunidadeVenda criada para LeadProspecto id={instance.pk} "
            f"is_rascunho={oportunidade.is_rascunho}"
        )

        # Distribuicao automatica so pra oportunidade ja qualificada — rascunho
        # nao deve poluir round-robin de vendedores
        if qualificado:
            from apps.comercial.crm.distribution import distribuir_oportunidade
            distribuir_oportunidade(oportunidade)

    except Exception as e:
        logger.error(f"[CRM] Erro ao criar OportunidadeVenda para lead {instance.pk}: {e}")


@receiver(post_save, sender='leads.LeadProspecto')
def qualificar_oportunidade_rascunho(sender, instance, created, **kwargs):
    """
    Promove oportunidade is_rascunho=True -> False quando o lead qualifica.
    Disparada por mudanca de score/status_api.
    """
    if getattr(instance, '_skip_crm_signal', False):
        return
    if created:
        return  # tratado pelo criar_oportunidade_automatica

    from apps.comercial.crm.models import OportunidadeVenda, ConfiguracaoCRM

    config = ConfiguracaoCRM.all_tenants.filter(tenant=instance.tenant).first()
    if not config:
        return

    score = getattr(instance, 'score_qualificacao', 0) or 0
    status_api = getattr(instance, 'status_api', '') or ''
    qualificado = (
        score >= config.score_minimo_auto_criacao
        or status_api == 'sucesso'
    )
    if not qualificado:
        return

    op = OportunidadeVenda.all_tenants.filter(lead=instance, is_rascunho=True).first()
    if not op:
        return

    op.is_rascunho = False
    op.save(update_fields=['is_rascunho'])
    logger.info(f"[CRM] Oportunidade {op.pk} promovida de rascunho para qualificada (lead {instance.pk})")

    # Agora distribui (nao distribuimos quando ainda era rascunho)
    if not op.responsavel:
        try:
            from apps.comercial.crm.distribution import distribuir_oportunidade
            distribuir_oportunidade(op)
        except Exception as e:
            logger.error(f"[CRM] Falha ao distribuir oportunidade {op.pk} apos qualificacao: {e}")


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
            tenant=oportunidade.tenant,
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


@receiver(post_save, sender='leads.LeadProspecto')
def avaliar_segmentos_dinamicos(sender, instance, **kwargs):
    """Avalia se o lead deve entrar/sair de segmentos dinâmicos."""
    if getattr(instance, '_skip_segmento', False):
        return
    if not instance.tenant:
        return

    try:
        from .services.segmentos import avaliar_lead_em_segmentos
        segmentos_adicionados = avaliar_lead_em_segmentos(instance)

        # Disparar automação para cada segmento em que o lead entrou
        if segmentos_adicionados:
            from apps.marketing.automacoes.engine import disparar_evento
            for seg in segmentos_adicionados:
                disparar_evento('lead_entrou_segmento', {
                    'lead': instance,
                    'lead_nome': instance.nome_razaosocial,
                    'telefone': instance.telefone,
                    'nome': instance.nome_razaosocial,
                    'segmento': seg,
                    'segmento_nome': seg.nome,
                }, tenant=instance.tenant)
    except Exception as e:
        logger.error(f"[CRM] Erro ao avaliar segmentos para lead {instance.pk}: {e}")


# ============================================================================
# AUTOMAÇÕES DO PIPELINE — disparam o engine em eventos do lead/oportunidade
# ============================================================================

def _disparar_engine(*, oportunidade=None, lead_id=None):
    """Importa e chama o engine de forma isolada pra não derrubar signals."""
    from .services.automacao_pipeline import processar_seguro
    processar_seguro(oportunidade=oportunidade, lead_id=lead_id)


@receiver(post_save, sender='leads.LeadProspecto')
def engine_apos_lead_atualizado(sender, instance, **kwargs):
    """Reavalia regras quando o lead é criado ou atualizado."""
    if getattr(instance, '_skip_rules_evaluation', False):
        return
    _disparar_engine(lead_id=instance.pk)


@receiver(post_save, sender='leads.HistoricoContato')
def engine_apos_historico(sender, instance, created, **kwargs):
    """Reavalia regras quando um histórico de contato é criado."""
    if not created:
        return
    lead_id = getattr(instance, 'lead_id', None)
    if lead_id:
        _disparar_engine(lead_id=lead_id)


@receiver(post_save, sender='leads.ImagemLeadProspecto')
def engine_apos_imagem(sender, instance, **kwargs):
    """Reavalia regras de pipeline quando uma imagem/documento muda de status."""
    lead_id = getattr(instance, 'lead_id', None)
    if lead_id:
        _disparar_engine(lead_id=lead_id)


def _conectar_signal_servico_hubsoft():
    """Conecta post_save de ServicoClienteHubsoft se o modelo existir."""
    try:
        from apps.integracoes.models import ServicoClienteHubsoft
    except Exception:
        return

    @receiver(post_save, sender=ServicoClienteHubsoft, weak=False)
    def engine_apos_servico_hubsoft(sender, instance, **kwargs):
        cliente = getattr(instance, 'cliente', None)
        if not cliente:
            return
        lead_id = getattr(cliente, 'lead_id', None)
        if lead_id:
            _disparar_engine(lead_id=lead_id)


def _conectar_signal_tags():
    """Conecta m2m_changed em OportunidadeVenda.tags pra reavaliar regras."""
    from apps.comercial.crm.models import OportunidadeVenda

    @receiver(m2m_changed, sender=OportunidadeVenda.tags.through, weak=False)
    def engine_apos_tag_changed(sender, instance, action, **kwargs):
        if action not in ('post_add', 'post_remove', 'post_clear'):
            return
        if getattr(instance, '_skip_rules_evaluation', False):
            return
        _disparar_engine(oportunidade=instance)


# Conectar signals externos ao importar o módulo
_conectar_signal_tags()
_conectar_signal_servico_hubsoft()
