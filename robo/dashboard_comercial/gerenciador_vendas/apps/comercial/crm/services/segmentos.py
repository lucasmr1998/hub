"""
Service de segmentos dinâmicos.
Reutilizado por views (preview) e signals (atualização automática).
"""
import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def filtrar_leads_por_regras(regras, queryset=None):
    """Aplica regras de filtro a LeadProspecto e retorna queryset."""
    from apps.comercial.leads.models import LeadProspecto

    if queryset is None:
        queryset = LeadProspecto.objects.all()

    for r in regras:
        campo = r.get('campo', '')
        operador = r.get('operador', 'igual')
        valor = r.get('valor', '')

        if not campo or not valor:
            continue

        # Campo especial: dias desde cadastro
        if campo == 'dias_cadastro':
            try:
                dias = int(valor)
            except ValueError:
                continue
            data_limite = timezone.now() - timedelta(days=dias)
            if operador in ('maior', 'maior_igual'):
                queryset = queryset.filter(data_cadastro__lte=data_limite)
            elif operador in ('menor', 'menor_igual'):
                queryset = queryset.filter(data_cadastro__gte=data_limite)
            continue

        # Mapear campo para field do model
        field_map = {
            'origem': 'origem',
            'score_qualificacao': 'score_qualificacao',
            'cidade': 'cidade',
            'estado': 'estado',
            'bairro': 'bairro',
            'valor': 'valor',
            'status_api': 'status_api',
        }
        field = field_map.get(campo)
        if not field:
            continue

        if operador == 'igual':
            queryset = queryset.filter(**{f'{field}__iexact': valor})
        elif operador == 'diferente':
            queryset = queryset.exclude(**{f'{field}__iexact': valor})
        elif operador == 'contem':
            queryset = queryset.filter(**{f'{field}__icontains': valor})
        elif operador == 'maior':
            queryset = queryset.filter(**{f'{field}__gt': valor})
        elif operador == 'menor':
            queryset = queryset.filter(**{f'{field}__lt': valor})
        elif operador == 'maior_igual':
            queryset = queryset.filter(**{f'{field}__gte': valor})
        elif operador == 'menor_igual':
            queryset = queryset.filter(**{f'{field}__lte': valor})

    return queryset


def lead_atende_regras(lead, regras):
    """Verifica se um lead específico atende todas as regras (sem query)."""
    for r in regras:
        campo = r.get('campo', '')
        operador = r.get('operador', 'igual')
        valor = r.get('valor', '')

        if not campo or not valor:
            continue

        # Obter valor do lead
        if campo == 'dias_cadastro':
            try:
                dias = int(valor)
            except ValueError:
                continue
            dias_lead = (timezone.now() - lead.data_cadastro).days if lead.data_cadastro else 0
            valor_lead = dias_lead
            valor_cmp = dias
        else:
            field_map = {
                'origem': 'origem', 'score_qualificacao': 'score_qualificacao',
                'cidade': 'cidade', 'estado': 'estado', 'bairro': 'bairro',
                'valor': 'valor', 'status_api': 'status_api',
            }
            attr = field_map.get(campo)
            if not attr:
                continue
            valor_lead = getattr(lead, attr, None)
            valor_cmp = valor

        if valor_lead is None:
            return False

        # Comparar
        try:
            vl = float(str(valor_lead))
            vc = float(str(valor_cmp))
            is_numeric = True
        except (ValueError, TypeError):
            vl = str(valor_lead).lower()
            vc = str(valor_cmp).lower()
            is_numeric = False

        if operador == 'igual' and vl != vc:
            if is_numeric or vl != vc:
                return False
        elif operador == 'diferente' and vl == vc:
            return False
        elif operador == 'contem' and str(vc) not in str(vl):
            return False
        elif operador == 'maior' and not (vl > vc):
            return False
        elif operador == 'menor' and not (vl < vc):
            return False
        elif operador == 'maior_igual' and not (vl >= vc):
            return False
        elif operador == 'menor_igual' and not (vl <= vc):
            return False

    return True


def atualizar_membros_segmento(segmento):
    """Atualiza membros de um segmento dinâmico com base nas regras."""
    from ..models import MembroSegmento

    regras = segmento.regras_filtro.get('regras', [])
    if not regras:
        return

    leads = filtrar_leads_por_regras(regras)
    lead_ids = set(leads.values_list('pk', flat=True))

    # Remover quem não atende mais (exceto manuais)
    MembroSegmento.all_tenants.filter(
        segmento=segmento, adicionado_manualmente=False
    ).exclude(lead_id__in=lead_ids).delete()

    # Adicionar novos
    existentes = set(segmento.membros.values_list('lead_id', flat=True))
    novos = lead_ids - existentes
    for lead_id in novos:
        MembroSegmento.objects.create(
            tenant=segmento.tenant, segmento=segmento,
            lead_id=lead_id, adicionado_manualmente=False,
        )

    segmento.total_leads = segmento.membros.count()
    segmento.ultima_atualizacao_dinamica = timezone.now()
    segmento.save(update_fields=['total_leads', 'ultima_atualizacao_dinamica'])


def avaliar_lead_em_segmentos(lead):
    """Avalia um lead contra todos os segmentos dinâmicos do tenant e adiciona/remove.
    Retorna lista de segmentos aos quais o lead foi ADICIONADO (para disparo de automações).
    """
    from ..models import SegmentoCRM, MembroSegmento

    segmentos_adicionados = []

    segmentos = SegmentoCRM.all_tenants.filter(
        tenant=lead.tenant, ativo=True, tipo__in=['dinamico', 'hibrido'],
    )

    for seg in segmentos:
        regras = seg.regras_filtro.get('regras', [])
        if not regras:
            continue

        atende = lead_atende_regras(lead, regras)
        membro_existe = MembroSegmento.all_tenants.filter(
            segmento=seg, lead=lead, adicionado_manualmente=False,
        ).exists()

        if atende and not membro_existe:
            MembroSegmento.objects.create(
                tenant=lead.tenant, segmento=seg,
                lead=lead, adicionado_manualmente=False,
            )
            seg.total_leads = seg.membros.count()
            seg.save(update_fields=['total_leads'])
            segmentos_adicionados.append(seg)
            logger.info(f'Segmento: lead {lead.pk} adicionado a "{seg.nome}"')

        elif not atende and membro_existe:
            MembroSegmento.all_tenants.filter(
                segmento=seg, lead=lead, adicionado_manualmente=False,
            ).delete()
            seg.total_leads = seg.membros.count()
            seg.save(update_fields=['total_leads'])
            logger.info(f'Segmento: lead {lead.pk} removido de "{seg.nome}"')

    return segmentos_adicionados
