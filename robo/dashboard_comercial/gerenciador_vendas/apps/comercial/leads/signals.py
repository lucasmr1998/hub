"""
Signals de leads migrados de vendas_web/signals.py.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.comercial.leads.models import LeadProspecto, Prospecto


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
