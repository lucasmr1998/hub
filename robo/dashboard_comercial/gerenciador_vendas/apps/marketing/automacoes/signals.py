"""
Signals que conectam eventos do sistema à engine de automações.

Cada signal captura um evento, monta o contexto e chama disparar_evento().
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='leads.LeadProspecto')
def on_lead_criado(sender, instance, created, **kwargs):
    """Dispara evento 'lead_criado' quando um novo lead é salvo."""
    if not created:
        return
    if getattr(instance, '_skip_automacao', False):
        return

    from .engine import disparar_evento
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
def on_lead_qualificado(sender, instance, created, **kwargs):
    """Dispara evento 'lead_qualificado' quando score muda para >= 7."""
    if created:
        return
    if getattr(instance, '_skip_automacao', False):
        return
    if not instance.score_qualificacao or instance.score_qualificacao < 7:
        return

    from .engine import disparar_evento
    disparar_evento('lead_qualificado', {
        'lead': instance,
        'lead_nome': instance.nome_razaosocial,
        'lead_score': instance.score_qualificacao,
        'telefone': instance.telefone,
        'nome': instance.nome_razaosocial,
    }, tenant=instance.tenant)


@receiver(post_save, sender='crm.OportunidadeVenda')
def on_oportunidade_movida(sender, instance, created, **kwargs):
    """Dispara evento 'oportunidade_movida' quando o estágio muda."""
    if created:
        return
    if getattr(instance, '_skip_automacao', False):
        return

    from .engine import disparar_evento
    disparar_evento('oportunidade_movida', {
        'oportunidade': instance,
        'oportunidade_titulo': instance.titulo,
        'estagio': instance.estagio.nome if instance.estagio else '',
        'pipeline': instance.pipeline.nome if instance.pipeline else '',
        'lead': instance.lead,
        'responsavel': instance.responsavel,
        'nome': instance.titulo,
    }, tenant=instance.tenant)


@receiver(post_save, sender='leads.ImagemLeadProspecto')
def on_docs_validados(sender, instance, created, **kwargs):
    """Dispara evento 'docs_validados' quando todos os docs são aprovados."""
    if getattr(instance, '_skip_automacao', False):
        return
    if instance.status != 'validado':
        return

    lead = instance.lead
    # Verificar se TODOS os docs do lead estão validados
    total_docs = lead.imagens.count()
    docs_validados = lead.imagens.filter(status='validado').count()
    if total_docs == 0 or docs_validados < total_docs:
        return

    from .engine import disparar_evento
    disparar_evento('docs_validados', {
        'lead': lead,
        'lead_nome': lead.nome_razaosocial,
        'telefone': lead.telefone,
        'nome': lead.nome_razaosocial,
    }, tenant=lead.tenant)


@receiver(post_save, sender='indicacoes.Indicacao')
def on_indicacao_convertida(sender, instance, created, **kwargs):
    """Dispara evento 'indicacao_convertida' quando status muda para 'convertido'."""
    if getattr(instance, '_skip_automacao', False):
        return
    if instance.status != 'convertido':
        return

    from .engine import disparar_evento
    disparar_evento('indicacao_convertida', {
        'indicacao': instance,
        'nome_indicado': instance.nome_indicado,
        'telefone_indicado': instance.telefone_indicado,
        'membro_indicador': instance.membro_indicador.nome if instance.membro_indicador else '',
    }, tenant=instance.tenant)
