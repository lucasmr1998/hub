"""Registra as ligacoes do Talk como HistoricoContato no lead.

Por que existe: o importador do Talk cria lead + oportunidade, mas NAO registra
a ligacao que originou tudo. Resultado: a chamada nao aparece na timeline da
oportunidade, o funil subconta atendimento (a 1a etapa) e o card "leads sem
contato" marca como nunca-contatado quem chegou por telefone.

Os dados vem do endpoint de rastreabilidade (listar_chamadas_por_telefone), o
mesmo que o sync_vendedores_matrix ja usa. Separado da atribuicao de proposito:
logar a ligacao vale pra TODA oportunidade, nao so as sem dono.

Idempotente por `cod_cdr` (o id unico da chamada no Talk), guardado em
dados_extras. Rodar de novo nao duplica.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.utils import timezone as dj_tz
from django.utils.dateparse import parse_datetime

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.talk import TalkService, TalkServiceError

logger = logging.getLogger(__name__)

# nom_resposta do Talk -> status do HistoricoContato
_STATUS_POR_RESPOSTA = {
    'atendida': 'ligacao_atendida',
    'ocupado': 'ocupado',
    'nao atendida': 'nao_atendeu',
    'nao atendida.': 'nao_atendeu',
    'abandonada': 'chamada_perdida',
}


@dataclass
class ResultadoLigacoes:
    leads_processados: int = 0
    ligacoes_criadas: int = 0
    ja_existiam: int = 0
    sem_chamada: int = 0
    erros: int = 0
    mensagens: list = field(default_factory=list)


def _status_da_chamada(nom_resposta: str) -> str:
    return _STATUS_POR_RESPOSTA.get((nom_resposta or '').strip().lower(), 'nao_atendeu')


def _quando(dat_ligacao: str):
    """'14/07/2026 17:42:36' -> datetime aware."""
    if not dat_ligacao:
        return None
    try:
        dt = datetime.strptime(dat_ligacao.strip(), '%d/%m/%Y %H:%M:%S')
    except (ValueError, TypeError):
        dt = parse_datetime(str(dat_ligacao))
    if dt and dj_tz.is_naive(dt):
        dt = dj_tz.make_aware(dt)
    return dt


def registrar_ligacoes_talk(tenant, dias: int = 7, limit: int = None,
                            dry_run: bool = False) -> ResultadoLigacoes:
    """Pra cada lead do Talk dos ultimos N dias, cria um HistoricoContato por
    ligacao encontrada no Talk. Idempotente por cod_cdr."""
    from apps.comercial.leads.models import LeadProspecto, HistoricoContato

    res = ResultadoLigacoes()

    integ = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='talk', ativa=True).first()
    if not integ:
        return res
    svc = TalkService(integ)

    cutoff = dj_tz.now() - timedelta(days=dias)
    leads = (LeadProspecto.all_tenants
             .filter(tenant=tenant, origem='telefone', data_cadastro__gte=cutoff)
             .exclude(telefone='')
             .order_by('-data_cadastro'))
    if limit:
        leads = leads[:limit]

    for lead in leads:
        res.leads_processados += 1
        tel = ''.join(c for c in str(lead.telefone) if c.isdigit())
        if len(tel) > 11:
            tel = tel[-11:]
        if not tel:
            continue

        # a data da ligacao e ~a da criacao do lead; olha o dia e o anterior
        base = dj_tz.localtime(lead.data_cadastro).date()
        datas = [base.isoformat(), (base - timedelta(days=1)).isoformat()]

        chamadas = []
        for dia in datas:
            try:
                chamadas += svc.listar_chamadas_por_telefone(tel, dia)
            except (TalkServiceError, Exception) as exc:  # noqa: BLE001
                res.erros += 1
                logger.warning('[registrar_ligacoes] lead=%s dia=%s erro: %s', lead.pk, dia, exc)

        if not chamadas:
            res.sem_chamada += 1
            continue

        for ch in chamadas:
            cod_cdr = str(ch.get('cod_cdr') or '').strip()
            if not cod_cdr:
                continue

            # idempotencia: essa chamada ja virou contato?
            ja = HistoricoContato.all_tenants.filter(
                tenant=tenant, lead=lead, dados_extras__cod_cdr=cod_cdr,
            ).exists()
            if ja:
                res.ja_existiam += 1
                continue

            if dry_run:
                res.ligacoes_criadas += 1
                res.mensagens.append(
                    f'[DRY] lead#{lead.pk} <- ligacao {cod_cdr} '
                    f'({ch.get("nom_resposta")}, {ch.get("nom_agente")})'
                )
                continue

            try:
                dur = int(ch.get('num_seg_bilhetado') or ch.get('num_seg_chamada') or 0)
            except (TypeError, ValueError):
                dur = 0

            HistoricoContato.all_tenants.create(
                tenant=tenant,
                lead=lead,
                telefone=lead.telefone or '',
                nome_contato=lead.nome_razaosocial or '',
                data_hora_contato=_quando(ch.get('dat_ligacao')) or lead.data_cadastro,
                status=_status_da_chamada(ch.get('nom_resposta')),
                origem_contato='telefone',
                duracao_segundos=dur,
                observacoes=f"Ligacao Talk atendida por {ch.get('nom_agente') or '—'}",
                dados_extras={
                    'origem': 'talk',
                    'cod_cdr': cod_cdr,
                    'nom_agente': ch.get('nom_agente'),
                    'nom_resposta': ch.get('nom_resposta'),
                    'gravacao_arquivo': ch.get('nom_arquivo'),  # nome do arquivo; play depende do endpoint do Talk
                },
            )
            res.ligacoes_criadas += 1

    return res
