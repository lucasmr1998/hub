"""
Importa prospects criados pelo Talk (softphone) no HubSoft pra dentro do
CRM Hubtrix como Lead + Oportunidade.

Fluxo:
1. Talk recebe ligacao → cria prospect no HubSoft com nome padrao
   "CLIENTE TALK - ADICIONAR ETIQUETA E USUARIO E NOME DO CLIENTE*"
   e telefone real.
2. Este servico consulta o HubSoft periodicamente (via cron), filtra os
   novos (por data), e cria a op correspondente no CRM Hubtrix.
3. Anti-duplicacao em cascata:
   - Se ja existe LeadProspecto com id_hubsoft == prospect['id_prospecto']  → skip
   - Se ja existe LeadProspecto com mesmo telefone → vincula id_hubsoft ao lead existente
   - Senao → cria Lead novo + Oportunidade no primeiro estagio do pipeline padrao

Uso:
    from apps.integracoes.services.importador_prospects_talk import importar_prospects_talk
    stats = importar_prospects_talk(tenant, desde=date(2026,7,3))
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List

from django.utils import timezone as dj_timezone

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

logger = logging.getLogger(__name__)

NOME_PADRAO_TALK = 'CLIENTE TALK'  # prefixo usado como termo de busca


@dataclass
class ResultadoImportacao:
    encontrados: int = 0
    ja_importados: int = 0
    vinculados_por_telefone: int = 0
    criados: int = 0
    falhas: List[dict] = field(default_factory=list)
    pulados_por_data: int = 0

    def to_dict(self):
        return {
            'encontrados': self.encontrados,
            'ja_importados': self.ja_importados,
            'vinculados_por_telefone': self.vinculados_por_telefone,
            'criados': self.criados,
            'falhas': len(self.falhas),
            'pulados_por_data': self.pulados_por_data,
        }


def _normalizar_telefone(valor):
    if not valor:
        return ''
    return re.sub(r'\D', '', str(valor))


def _prospect_created_date(prospect):
    """Extrai a data (BRT) de criacao do prospect. Aceita created_at (ISO UTC)
    ou created_at_br (dd/mm/yyyy)."""
    iso = prospect.get('created_at')
    if iso:
        try:
            # HubSoft manda formato tipo '2026-07-03T13:14:24.000000Z'
            dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
            return dj_timezone.localtime(dt).date()
        except (ValueError, TypeError):
            pass
    br = prospect.get('created_at_br') or ''
    if br:
        try:
            return datetime.strptime(br, '%d/%m/%Y').date()
        except ValueError:
            pass
    return None


def importar_prospects_talk(
    tenant,
    *,
    desde: date = None,
    limit: int = None,
    dry_run: bool = False,
) -> ResultadoImportacao:
    """
    Importa prospects Talk do HubSoft pro CRM.

    Args:
        tenant: Tenant
        desde: date filtro (default: hoje BRT)
        limit: max de prospects a processar (default: sem limite)
        dry_run: se True, nao cria nada — so lista

    Returns:
        ResultadoImportacao com estatisticas.
    """
    if desde is None:
        desde = dj_timezone.localtime().date()

    r = ResultadoImportacao()

    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=tenant, tipo='hubsoft', ativa=True,
    ).first()
    if not integracao:
        logger.warning('[TalkImporter] Sem IntegracaoAPI hubsoft ativa em %s', tenant.slug)
        return r

    svc = HubsoftService(integracao)
    try:
        resposta = svc._get(
            '/api/v1/integracao/prospecto',
            params={'busca': 'nome_razaosocial', 'termo_busca': NOME_PADRAO_TALK},
        )
    except HubsoftServiceError as exc:
        logger.warning('[TalkImporter] Falha ao consultar HubSoft %s: %s', tenant.slug, exc)
        r.falhas.append({'motivo': f'consulta_hubsoft: {exc}'})
        return r

    prospectos = (resposta or {}).get('prospectos') or []
    r.encontrados = len(prospectos)

    from apps.comercial.leads.models import LeadProspecto

    processados = 0
    for prospect in prospectos:
        if limit and processados >= limit:
            break

        data_criacao = _prospect_created_date(prospect)
        if data_criacao is None or data_criacao < desde:
            r.pulados_por_data += 1
            continue

        processados += 1
        id_prospecto = str(prospect.get('id_prospecto') or '').strip()
        telefone_raw = prospect.get('telefone') or ''
        telefone = _normalizar_telefone(telefone_raw)

        if not id_prospecto:
            r.falhas.append({'motivo': 'sem id_prospecto', 'prospect': prospect})
            continue

        # 1) Ja existe lead com esse id_hubsoft?
        existente = LeadProspecto.all_tenants.filter(
            tenant=tenant, id_hubsoft=id_prospecto,
        ).first()
        if existente:
            r.ja_importados += 1
            continue

        # 2) Ja existe lead com esse telefone? Vincula id_hubsoft
        if telefone:
            por_telefone = LeadProspecto.all_tenants.filter(
                tenant=tenant, telefone__endswith=telefone[-11:] if len(telefone) >= 11 else telefone,
            ).first()
            if por_telefone:
                if not dry_run:
                    por_telefone.id_hubsoft = id_prospecto
                    dados_custom = dict(getattr(por_telefone, 'dados_custom', None) or {})
                    dados_custom.setdefault('vinculado_talk_em', dj_timezone.now().isoformat())
                    dados_custom['talk_prospect_id'] = id_prospecto
                    por_telefone.dados_custom = dados_custom
                    por_telefone.save(update_fields=['id_hubsoft', 'dados_custom'])
                r.vinculados_por_telefone += 1
                continue

        # 3) Cria lead + oportunidade
        if dry_run:
            r.criados += 1
            continue

        try:
            _criar_lead_e_op(tenant, prospect, id_prospecto, telefone)
            r.criados += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception('[TalkImporter] Falha criando lead pra prospect %s', id_prospecto)
            r.falhas.append({
                'motivo': f'criar_lead: {type(exc).__name__}: {exc}',
                'id_prospecto': id_prospecto,
            })

    return r


def _criar_lead_e_op(tenant, prospect, id_prospecto, telefone):
    """Cria LeadProspecto + OportunidadeVenda no primeiro estagio do pipeline
    padrao. Nao atribui responsavel — deixa NULL pra distribuir_oportunidade
    (se configurado) ou pra Admin distribuir manual."""
    from apps.comercial.leads.models import LeadProspecto
    from apps.comercial.crm.models import (
        OportunidadeVenda, Pipeline, PipelineEstagio,
    )

    nome = (prospect.get('nome_razaosocial') or '').strip() or 'Aguardando (Talk)'
    lead = LeadProspecto.objects.create(
        tenant=tenant,
        nome_razaosocial=nome,
        telefone=telefone or '',
        origem='telefone',
        id_hubsoft=id_prospecto,
        dados_custom={
            'talk_prospect_id': id_prospecto,
            'talk_created_at': prospect.get('created_at'),
            'importado_do_talk': True,
        },
    )

    pipeline = Pipeline.all_tenants.filter(tenant=tenant, padrao=True).first() \
               or Pipeline.all_tenants.filter(tenant=tenant).first()
    if not pipeline:
        logger.warning('[TalkImporter] Tenant %s sem Pipeline — lead criado sem op', tenant.slug)
        return lead

    estagio = PipelineEstagio.all_tenants.filter(
        tenant=tenant, pipeline=pipeline, ativo=True,
    ).order_by('ordem').first()
    if not estagio:
        logger.warning('[TalkImporter] Pipeline %s sem estagio ativo', pipeline.pk)
        return lead

    oport = OportunidadeVenda.objects.create(
        tenant=tenant,
        pipeline=pipeline,
        lead=lead,
        estagio=estagio,
        titulo=nome,
        origem_crm='talk',
    )

    # Auto distribui se ConfiguracaoCRM tiver round_robin
    try:
        from apps.comercial.crm.distribution import distribuir_oportunidade
        distribuir_oportunidade(oport)
    except Exception:  # noqa: BLE001
        logger.debug('[TalkImporter] distribuir_oportunidade falhou (nao critico)', exc_info=True)

    return lead
