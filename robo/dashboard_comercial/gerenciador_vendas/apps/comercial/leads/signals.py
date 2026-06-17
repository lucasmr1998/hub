"""
Signals de leads migrados de vendas_web/signals.py.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.comercial.leads.models import LeadProspecto, Prospecto, HistoricoContato


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


@receiver(post_save, sender=HistoricoContato)
def marcar_lead_atendido_no_primeiro_contato(sender, instance: HistoricoContato, created, **kwargs):
    """
    Marca `LeadProspecto.atendido_em` no momento do PRIMEIRO HistoricoContato.
    Imutavel apos primeiro preenchimento (so escreve se ainda esta None).

    Usado pelo relatorio de performance das consultoras (Sprint 3.2):
    tempo medio entre cadastro do lead e primeira interacao humana = TMA.
    """
    if not created:
        return
    lead = instance.lead
    if not lead or lead.atendido_em:
        return
    # Update direto pra evitar trigger de outros signals
    data_hist = instance.data_hora_contato or timezone.now()
    LeadProspecto.all_tenants.filter(pk=lead.pk, atendido_em__isnull=True).update(
        atendido_em=data_hist,
    )
