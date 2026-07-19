"""Núcleo da captação de leads do Wifeed — reutilizado pelo poller (management
command) e pelo botão "Salvar seleção" da página de fontes.

Fontes ativas (WifeedFonte.ativo=True):
  - LOCAL    → GET /report/record?local=<id>   (cadastros do formulário)
  - CAMPANHA → GET /report/access?campaign=<id> (acessos; traz CPF)
Dedupe por id_origem (id da pessoa no Wifeed) dentro do ciclo e no banco.
"""
import datetime
import logging
import re

from django.conf import settings
from django.db import connection, connections
from django.utils import timezone

logger = logging.getLogger(__name__)

ADVISORY_LOCK = 947_312_042
_RE_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_RE_BR = re.compile(r'^(\d{2})/(\d{2})/(\d{4})$')


def _digits(v):
    return re.sub(r'\D', '', str(v or ''))


def _nascimento(v):
    """Normaliza nascimento p/ 'YYYY-MM-DD' (aceita ISO ou DD/MM/YYYY)."""
    s = (v or '').strip()
    if _RE_ISO.match(s):
        return s
    m = _RE_BR.match(s)
    if m:
        return f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    return ''


def fontes_ativas():
    """(locais_ids, campanhas_ids) ativas no painel + WIFEED_LOCAIS (legado)."""
    from crm.services.wifeed_fontes import ids_ativos
    locais = set(ids_ativos('local')) | set(getattr(settings, 'WIFEED_LOCAIS', []) or [])
    campanhas = set(ids_ativos('campanha'))
    return sorted(locais), sorted(campanhas)


def _de_record(rec, local):
    return {
        'id_origem': str(rec.get('id') or '').strip(),
        'nome': (rec.get('name') or '').strip(),
        'telefone': _digits(rec.get('phoneNumber')),
        'email': (rec.get('email') or '').strip(),
        'data_nascimento': _nascimento(rec.get('birthDate')),
        'cpf_cnpj': '',
        'id_origem_servico': (str(local) if local is not None else ''),
    }


def _de_access(row, campanha):
    extra = row.get('clientExtraFields') or {}
    cpf = _digits(extra.get('CPF') or extra.get('cpf'))
    return {
        'id_origem': str(row.get('clientId') or '').strip(),
        'nome': (row.get('clientName') or '').strip(),
        'telefone': _digits(row.get('clientPhoneNumber')),
        'email': (row.get('clientEmail') or '').strip(),
        'data_nascimento': _nascimento(row.get('clientBirthdate')),
        'cpf_cnpj': cpf,
        'id_origem_servico': f'camp:{campanha}',
    }


def _processar(d, seen, dry_run, total, emit):
    from vendas_web.models import LeadProspecto

    rec_id, nome, telefone = d['id_origem'], d['nome'], d['telefone']
    if not rec_id or not nome or not telefone:
        total['ignorados'] += 1
        return
    if rec_id in seen:
        total['dedupe'] += 1
        return
    seen.add(rec_id)
    if LeadProspecto.objects.filter(canal_entrada='wifeed', id_origem=rec_id).exists():
        total['dedupe'] += 1
        return

    data = {k: v for k, v in d.items() if v}
    data['nome_razaosocial'] = nome
    data.pop('nome', None)

    if dry_run:
        total['criados'] += 1
        emit(f'(dry) criaria lead: {nome} / {telefone} (id {rec_id}'
             f'{", CPF" if d["cpf_cnpj"] else ""})')
        return
    try:
        from crm.views import criar_lead_wifeed
        lead, op = criar_lead_wifeed(data)
        total['criados'] += 1
        emit(f'lead {lead.id} criado ({nome}) op={op.id if op else "?"}')
    except Exception as e:  # noqa: BLE001
        total['erros'] += 1
        emit(f'ERRO ao criar lead (id {rec_id}): {e}')


def sincronizar_leads(dias=0, dry_run=False, todos_locais=False, emit=None):
    """Um ciclo de captação. Retorna dict com contagens (+ 'erro' se abortou).

    `dias`: além de hoje, quantos dias para trás varrer.
    `emit`: callback(str) para log/progresso (default: logger.info).
    """
    emit = emit or (lambda m: logger.info('[wifeed] %s', m))
    total = {'criados': 0, 'dedupe': 0, 'ignorados': 0, 'erros': 0}

    locais, campanhas = fontes_ativas()
    if not locais and not campanhas and not todos_locais:
        return {**total, 'erro': 'nenhuma fonte ativa'}

    with connection.cursor() as cur:
        cur.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK])
        if not cur.fetchone()[0]:
            return {**total, 'erro': 'sincronização já em andamento'}
    try:
        from crm.services.wifeed_client import WifeedClient, WifeedError
        client = WifeedClient()
        hoje = timezone.localdate()
        datas = [hoje - datetime.timedelta(days=d) for d in range(dias + 1)]
        alvos_local = locais if locais else ([None] if todos_locais else [])
        seen = set()
        for data in datas:
            dstr = data.strftime('%Y-%m-%d')
            for local in alvos_local:
                try:
                    for rec in client.iter_records(dstr, local=local):
                        _processar(_de_record(rec, local), seen, dry_run, total, emit)
                except WifeedError as e:
                    total['erros'] += 1
                    emit(f'{dstr} local={local}: {e}')
            for camp in campanhas:
                try:
                    for row in client.iter_access(dstr, campaign=camp):
                        _processar(_de_access(row, camp), seen, dry_run, total, emit)
                except WifeedError as e:
                    total['erros'] += 1
                    emit(f'{dstr} campanha={camp}: {e}')
        return total
    finally:
        with connection.cursor() as cur:
            cur.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK])


def sincronizar_em_background(dias=0):
    """Dispara um ciclo em thread separada (para chamadas web). Fecha conexões
    ao final para não vazar. Protegido pelo advisory lock."""
    import threading

    def _run():
        try:
            res = sincronizar_leads(dias=dias)
            logger.info('[wifeed] sync (save) resultado: %s', res)
        except Exception:  # noqa: BLE001
            logger.exception('[wifeed] sync (save) falhou')
        finally:
            connections.close_all()

    threading.Thread(target=_run, daemon=True).start()
