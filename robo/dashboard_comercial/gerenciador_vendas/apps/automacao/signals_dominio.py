"""Signals de domínio que disparam eventos pra engine de automação nova.

Relocados de `apps.marketing.automacoes.signals` (motor antigo aposentado). Cada signal
captura um evento do sistema, monta o contexto e chama o hub neutro (`hub.disparar_evento`).
Registrados no `apps.py::ready()` da engine nova.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .hub import disparar_evento

logger = logging.getLogger(__name__)


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
