"""Signals de domínio que disparam eventos pra engine de automação nova.

Relocados de `apps.marketing.automacoes.signals` (motor antigo aposentado). Cada signal
captura um evento do sistema, monta o contexto e chama o hub neutro (`hub.disparar_evento`).
Registrados no `apps.py::ready()` da engine nova.
"""
import logging

from django.conf import settings
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver

from .hub import disparar_evento

logger = logging.getLogger(__name__)


# ============================================================================
# EVENTOS FINOS DA MIGRAÇÃO DO FUNIL (v2)
# Emitem no MOMENTO real de negócio (não no pulso genérico). Detecção de mudança
# via pre_save (dispara só na transição, sem ruído). Gated por wiring/shadow →
# zero overhead quando ambos off. Blindado: emissão nunca quebra o save. Os
# fluxos agem na OPORTUNIDADE, então todo contexto resolve a op a partir do lead.
# ============================================================================

def _emissao_ativa():
    """Só emite (e paga o custo do pre_save) quando o wiring OU o shadow estão on."""
    return (getattr(settings, 'AUTOMACAO_WIRING_ATIVO', False)
            or getattr(settings, 'AUTOMACAO_SHADOW_ATIVO', False))


def _op_do_lead(lead):
    """Oportunidade (ativa, mais recente) do lead — os fluxos do funil agem nela."""
    if lead is None or not getattr(lead, 'pk', None):
        return None
    try:
        from apps.comercial.crm.models import OportunidadeVenda
        return (OportunidadeVenda.all_tenants.filter(lead=lead)
                .select_related('estagio', 'pipeline', 'lead')
                .order_by('-ativo', '-data_criacao').first())
    except Exception:  # noqa: BLE001
        return None


def _ctx(op=None, lead=None, **extra):
    """Contexto do evento: resolve op↔lead e monta os escalares base + extras."""
    if op is None and lead is not None:
        op = _op_do_lead(lead)
    if lead is None and op is not None:
        lead = getattr(op, 'lead', None)
    base = {
        'oportunidade': op, 'lead': lead,
        'lead_nome': getattr(lead, 'nome_razaosocial', '') if lead else '',
        'telefone': getattr(lead, 'telefone', '') if lead else '',
    }
    base.update(extra)
    return base


@receiver(post_save, sender='leads.LeadProspecto')
def on_lead_criado(sender, instance, created, **kwargs):
    """Dispara 'lead_criado' quando um novo lead é salvo."""
    if not created:
        return
    if getattr(instance, '_skip_automacao', False):
        return
    disparar_evento('lead_criado', {
        'lead': instance,
        'lead_nome': instance.nome_razaosocial,
        'lead_telefone': instance.telefone,
        'lead_email': instance.email or '',
        'lead_origem': instance.origem or '',
        'lead_score': instance.score_qualificacao,
        'lead_valor': str(instance.valor) if instance.valor else '0',
        'telefone': instance.telefone,
        'nome': instance.nome_razaosocial,
    }, tenant=instance.tenant)


@receiver(post_save, sender='leads.LeadProspecto')
def on_lead_status_pendente(sender, instance, created, **kwargs):
    """Dispara 'lead_status_pendente' quando lead atinge status_api 'pendente'."""
    if getattr(instance, '_skip_automacao', False):
        return
    if getattr(instance, 'status_api', None) != 'pendente':
        return
    disparar_evento('lead_status_pendente', {
        'lead': instance,
        'lead_nome': instance.nome_razaosocial,
        'lead_telefone': instance.telefone,
        'lead_id_hubsoft': instance.id_hubsoft or '',
        'telefone': instance.telefone,
        'nome': instance.nome_razaosocial,
    }, tenant=instance.tenant)


@receiver(post_save, sender='leads.LeadProspecto')
def on_lead_qualificado(sender, instance, created, **kwargs):
    """Dispara 'lead_qualificado' quando score muda para >= 7."""
    if created:
        return
    if getattr(instance, '_skip_automacao', False):
        return
    if not instance.score_qualificacao or instance.score_qualificacao < 7:
        return
    disparar_evento('lead_qualificado', {
        'lead': instance,
        'lead_nome': instance.nome_razaosocial,
        'lead_score': instance.score_qualificacao,
        'telefone': instance.telefone,
        'nome': instance.nome_razaosocial,
    }, tenant=instance.tenant)


@receiver(post_save, sender='crm.OportunidadeVenda')
def on_oportunidade_criada(sender, instance, created, **kwargs):
    """Dispara 'oportunidade_criada' quando op eh criada (manual ou auto).

    Permite que automacoes visuais no /automacao/editor/ escutem o evento
    e reajam (criar rascunho HubSoft, distribuir, etc) sem precisar
    hardcodar a logica."""
    if not created:
        return
    if getattr(instance, '_skip_automacao', False):
        return
    disparar_evento('oportunidade_criada', {
        'oportunidade': instance,
        'oportunidade_titulo': instance.titulo or '',
        'estagio': instance.estagio.slug if instance.estagio else '',
        'estagio_nome': instance.estagio.nome if instance.estagio else '',
        'pipeline': instance.pipeline.slug if instance.pipeline else '',
        'pipeline_nome': instance.pipeline.nome if instance.pipeline else '',
        'origem_crm': instance.origem_crm or '',
        'lead': instance.lead,
        'lead_nome': instance.lead.nome_razaosocial if instance.lead else '',
        'lead_id_hubsoft': (instance.lead.id_hubsoft if instance.lead else '') or '',
        'telefone': instance.lead.telefone if instance.lead else '',
        'nome': instance.titulo or '',
    }, tenant=instance.tenant)


@receiver(post_save, sender='crm.OportunidadeVenda')
def on_oportunidade_movida(sender, instance, created, **kwargs):
    """Dispara 'oportunidade_movida' quando o estágio muda (update)."""
    if created:
        return
    if getattr(instance, '_skip_automacao', False):
        return
    disparar_evento('oportunidade_movida', {
        'oportunidade': instance,
        'oportunidade_titulo': instance.titulo,
        'estagio': instance.estagio.slug if instance.estagio else '',
        'estagio_nome': instance.estagio.nome if instance.estagio else '',
        'pipeline': instance.pipeline.slug if instance.pipeline else '',
        'pipeline_nome': instance.pipeline.nome if instance.pipeline else '',
        'lead': instance.lead,
        'lead_nome': instance.lead.nome_razaosocial if instance.lead else '',
        'responsavel': instance.responsavel.get_full_name() if instance.responsavel else '',
        'telefone': instance.lead.telefone if instance.lead else '',
        'nome': instance.titulo,
    }, tenant=instance.tenant)


@receiver(post_save, sender='leads.ImagemLeadProspecto')
def on_docs_validados(sender, instance, created, **kwargs):
    """Dispara 'docs_validados' quando todos os docs do lead são aprovados."""
    from apps.comercial.leads.models import ImagemLeadProspecto

    if getattr(instance, '_skip_automacao', False):
        return
    if instance.status_validacao != ImagemLeadProspecto.STATUS_VALIDO:
        return

    lead = instance.lead
    todas = list(
        ImagemLeadProspecto.all_tenants
        .filter(lead_id=lead.pk)
        .values_list('status_validacao', flat=True)
    )
    if not todas or not all(s == ImagemLeadProspecto.STATUS_VALIDO for s in todas):
        return
    disparar_evento('docs_validados', {
        'lead': lead,
        'lead_nome': lead.nome_razaosocial,
        'telefone': lead.telefone,
        'nome': lead.nome_razaosocial,
    }, tenant=lead.tenant)


@receiver(post_save, sender='indicacoes.Indicacao')
def on_indicacao_convertida(sender, instance, created, **kwargs):
    """Dispara 'indicacao_convertida' quando status muda para 'convertido'."""
    if getattr(instance, '_skip_automacao', False):
        return
    if instance.status != 'convertido':
        return
    disparar_evento('indicacao_convertida', {
        'indicacao': instance,
        'nome_indicado': instance.nome_indicado,
        'telefone_indicado': instance.telefone_indicado,
        'membro_indicador': instance.membro_indicador.nome if instance.membro_indicador else '',
    }, tenant=instance.tenant)


# Shadow v2: o hook não é mais aqui (observador do motor_disparado, removido). Agora
# é no `hub.disparar_evento`, que chama `shadow.avaliar_evento_shadow` por evento fino.

# ---- LeadProspecto: campos-chave, status_api e viabilidade (detecção de mudança) ----
_LEAD_CAMPOS_GATILHO = ('id_plano_rp', 'id_dia_vencimento', 'id_hubsoft', 'cep',
                        'numero_residencia', 'cpf_cnpj', 'data_nascimento', 'email')


@receiver(pre_save, sender='leads.LeadProspecto')
def _stash_lead(sender, instance, **kwargs):
    if not _emissao_ativa() or not instance.pk:
        instance._old_lead = {}
        return
    try:
        instance._old_lead = (sender.all_tenants.filter(pk=instance.pk)
                              .values('status_api', 'dados_custom', *_LEAD_CAMPOS_GATILHO).first()) or {}
    except Exception:  # noqa: BLE001
        instance._old_lead = {}


@receiver(post_save, sender='leads.LeadProspecto')
def on_lead_eventos_finos(sender, instance, created, **kwargs):
    if not _emissao_ativa() or getattr(instance, '_skip_automacao', False):
        return
    try:
        old = getattr(instance, '_old_lead', {}) or {}
        tenant = instance.tenant
        # status_api mudou
        novo_status = instance.status_api or ''
        if novo_status and novo_status != (old.get('status_api') or ''):
            disparar_evento('lead_status_mudou', _ctx(lead=instance, status_api=novo_status), tenant=tenant)
        # campos-chave que ganharam valor
        for campo in _LEAD_CAMPOS_GATILHO:
            novo = getattr(instance, campo, None)
            if novo and str(novo) != str(old.get(campo) or ''):
                disparar_evento('lead_campo_mudou',
                                _ctx(lead=instance, campo=campo, valor=str(novo)), tenant=tenant)
        # viabilidade consultada
        via_novo = ((instance.dados_custom or {}).get('viabilidade') or {}).get('status')
        via_antigo = ((old.get('dados_custom') or {}).get('viabilidade') or {}).get('status')
        if via_novo and via_novo not in ('', 'nao_consultado') and via_novo != via_antigo:
            disparar_evento('viabilidade_consultada',
                            _ctx(lead=instance, viabilidade_status=via_novo), tenant=tenant)
    except Exception:  # noqa: BLE001
        logger.exception('eventos finos: on_lead falhou')


# ---- HistoricoContato criado ----
@receiver(post_save, sender='leads.HistoricoContato')
def on_historico_contato(sender, instance, created, **kwargs):
    if not _emissao_ativa() or not created:
        return
    try:
        lead = getattr(instance, 'lead', None)
        if lead is None:
            return
        disparar_evento('historico_contato',
                        _ctx(lead=lead, status=instance.status or ''),
                        tenant=getattr(lead, 'tenant', None))
    except Exception:  # noqa: BLE001
        logger.exception('eventos finos: on_historico falhou')


# ---- ImagemLeadProspecto: mudança de status_validacao ----
@receiver(pre_save, sender='leads.ImagemLeadProspecto')
def _stash_imagem(sender, instance, **kwargs):
    if not _emissao_ativa() or not instance.pk:
        instance._old_img_status = None
        return
    try:
        instance._old_img_status = (sender.all_tenants.filter(pk=instance.pk)
                                    .values_list('status_validacao', flat=True).first())
    except Exception:  # noqa: BLE001
        instance._old_img_status = None


@receiver(post_save, sender='leads.ImagemLeadProspecto')
def on_documento_status_mudou(sender, instance, created, **kwargs):
    if not _emissao_ativa():
        return
    try:
        novo = instance.status_validacao
        antigo = None if created else getattr(instance, '_old_img_status', None)
        if novo and novo != antigo:
            disparar_evento('documento_status_mudou',
                            _ctx(lead=getattr(instance, 'lead', None), status=novo),
                            tenant=getattr(instance, 'tenant', None))
    except Exception:  # noqa: BLE001
        logger.exception('eventos finos: on_documento falhou')


# ---- OportunidadeVenda.tags (m2m): tag adicionada ----
def _conectar_tag_evento():
    from apps.comercial.crm.models import OportunidadeVenda

    @receiver(m2m_changed, sender=OportunidadeVenda.tags.through, weak=False)
    def on_tag_adicionada(sender, instance, action, pk_set, **kwargs):
        if action != 'post_add' or not _emissao_ativa():
            return
        try:
            for tag in instance.tags.filter(pk__in=list(pk_set or [])):
                nome = getattr(tag, 'nome', None) or str(tag)
                disparar_evento('tag_adicionada', _ctx(op=instance, tag=nome),
                                tenant=getattr(instance, 'tenant', None))
        except Exception:  # noqa: BLE001
            logger.exception('eventos finos: on_tag falhou')


# ---- ServicoClienteHubsoft: mudança de status ----
def _conectar_servico_evento():
    try:
        from apps.integracoes.models import ServicoClienteHubsoft
    except Exception:  # noqa: BLE001
        return

    @receiver(pre_save, sender=ServicoClienteHubsoft, weak=False)
    def _stash_servico(sender, instance, **kwargs):
        if not _emissao_ativa() or not instance.pk:
            instance._old_servico_status = None
            return
        try:
            instance._old_servico_status = (sender.all_tenants.filter(pk=instance.pk)
                                            .values_list('status', flat=True).first())
        except Exception:  # noqa: BLE001
            instance._old_servico_status = None

    @receiver(post_save, sender=ServicoClienteHubsoft, weak=False)
    def on_servico_hubsoft_mudou(sender, instance, created, **kwargs):
        if not _emissao_ativa():
            return
        try:
            novo = instance.status
            antigo = None if created else getattr(instance, '_old_servico_status', None)
            if not novo or novo == antigo:
                return
            cliente = getattr(instance, 'cliente', None)
            lead = getattr(cliente, 'lead', None) if cliente else None
            disparar_evento('servico_hubsoft_mudou', _ctx(lead=lead, status=novo),
                            tenant=getattr(instance, 'tenant', None))
        except Exception:  # noqa: BLE001
            logger.exception('eventos finos: on_servico falhou')


# ---- Conversa: modo mudou + atribuída a vendedor ----
def _conectar_conversa_evento():
    try:
        from apps.inbox.models import Conversa
    except Exception:  # noqa: BLE001
        return

    @receiver(pre_save, sender=Conversa, weak=False)
    def _stash_conversa(sender, instance, **kwargs):
        if not _emissao_ativa() or not instance.pk:
            instance._old_conversa = {}
            return
        try:
            instance._old_conversa = (sender.all_tenants.filter(pk=instance.pk)
                                      .values('modo_atendimento', 'agente_id').first()) or {}
        except Exception:  # noqa: BLE001
            instance._old_conversa = {}

    @receiver(post_save, sender=Conversa, weak=False)
    def on_conversa_evento(sender, instance, created, **kwargs):
        if not _emissao_ativa():
            return
        try:
            old = getattr(instance, '_old_conversa', {}) or {}
            op = getattr(instance, 'oportunidade', None)
            tenant = getattr(instance, 'tenant', None)
            modo = getattr(instance, 'modo_atendimento', '') or ''
            if modo and modo != (old.get('modo_atendimento') or ''):
                disparar_evento('conversa_modo_mudou', _ctx(op=op, modo=modo), tenant=tenant)
            ag_novo = getattr(instance, 'agente_id', None)
            ag_antigo = old.get('agente_id') if not created else None
            if ag_novo and ag_novo != ag_antigo:
                disparar_evento('conversa_atribuida', _ctx(op=op, responsavel=str(ag_novo)), tenant=tenant)
        except Exception:  # noqa: BLE001
            logger.exception('eventos finos: on_conversa falhou')


# Conectar os signals de models externos (import no boot, via apps.py::ready()).
_conectar_tag_evento()
_conectar_servico_evento()
_conectar_conversa_evento()
