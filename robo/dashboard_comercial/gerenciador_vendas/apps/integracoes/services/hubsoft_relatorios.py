"""
Helpers de sync em lote HubSoft -> espelhos locais.

Centraliza a logica de iterar endpoints `/todos` paginados do HubSoft e fazer
UPSERT em FaturaHubsoft / OrdemServicoHubsoft / AtendimentoHubsoft / ClienteHubsoft.

Usado pelos management commands `sync_base_*_hubsoft.py` (cron diario/horario).
Mesmo padrao do `hubsoft_prospecto.py` (criado 16/06): helpers puros, retornam
dataclass com resultado, NUNCA levantam excecao (sempre retornam OK ou erro).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional

from django.utils import timezone

from apps.integracoes.models import (
    AtendimentoHubsoft,
    ClienteHubsoft,
    FaturaHubsoft,
    IntegracaoAPI,
    OrdemServicoHubsoft,
    ServicoClienteHubsoft,
)
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

logger = logging.getLogger(__name__)


@dataclass
class ResultadoSync:
    ok: bool = True
    total_paginas: int = 0
    total_registros: int = 0
    criados: int = 0
    atualizados: int = 0
    erros: int = 0
    duracao_seg: float = 0.0
    mensagens_erro: list = field(default_factory=list)

    def somar_pagina(self, criados, atualizados):
        self.criados += criados
        self.atualizados += atualizados


# ----------------------------------------------------------------------------
# Helpers de parsing seguros
# ----------------------------------------------------------------------------

def _parse_datetime(valor):
    """HubSoft usa formatos mistos: 'YYYY-MM-DD HH:MM:SS', 'DD/MM/YYYY HH:MM', ISO."""
    if not valor:
        return None
    s = str(valor).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            dt = datetime.strptime(s, fmt)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, dt_timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def _parse_date(valor):
    dt = _parse_datetime(valor)
    return dt.date() if dt else None


def _parse_decimal(valor):
    if valor in (None, ''):
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def _normalizar_status_fatura(status_raw: str, status_prefixo: str = '') -> str:
    """Mapeia status HubSoft pros choices do nosso espelho."""
    s = (status_prefixo or status_raw or '').lower()
    if 'paga' in s or 'pago' in s:
        return 'paga'
    if 'vencida' in s or 'vencido' in s:
        return 'vencida'
    if 'cancelad' in s:
        return 'cancelada'
    if 'aberta' in s or 'pendente' in s or s == '':
        return 'aberta'
    return 'outro'


# ----------------------------------------------------------------------------
# Sync de base de clientes (com servicos inline)
# ----------------------------------------------------------------------------

def sincronizar_base_clientes(
    integracao: IntegracaoAPI,
    *,
    modificados_desde: Optional[datetime] = None,
    max_paginas: Optional[int] = None,
    itens_por_pagina: int = 100,
) -> ResultadoSync:
    """
    Itera /cliente/todos paginado e UPSERT em ClienteHubsoft + ServicoClienteHubsoft.
    Reusa HubsoftService._sincronizar_dados_cliente (que ja popula servicos inline).

    - modificados_desde: filtra clientes modificados a partir desta data (delta sync).
    - max_paginas: limita pra teste/dry-run.
    """
    res = ResultadoSync()
    t0 = time.monotonic()
    svc = HubsoftService(integracao)
    pagina = 0
    data_inicio_str = modificados_desde.strftime('%Y-%m-%d') if modificados_desde else None

    while True:
        try:
            resp = svc.listar_clientes_todos(
                pagina=pagina,
                itens_por_pagina=itens_por_pagina,
                data_inicio=data_inicio_str,
            )
        except HubsoftServiceError as exc:
            res.ok = False
            res.erros += 1
            res.mensagens_erro.append(f'pagina {pagina}: {exc}'[:300])
            logger.exception('Erro sync_base_clientes pagina=%s', pagina)
            break
        except Exception as exc:
            res.ok = False
            res.erros += 1
            res.mensagens_erro.append(f'pagina {pagina}: {type(exc).__name__}: {exc}'[:300])
            logger.exception('Erro inesperado sync_base_clientes pagina=%s', pagina)
            break

        clientes = resp.get('clientes') or []
        paginacao = resp.get('paginacao') or {}
        if pagina == 0:
            res.total_registros = paginacao.get('total_registros', len(clientes))

        if not clientes:
            break

        for c in clientes:
            try:
                ja_existia = ClienteHubsoft.all_tenants.filter(
                    tenant=integracao.tenant, id_cliente=c.get('id_cliente'),
                ).exists()
                svc._sincronizar_dados_cliente(c)
                if ja_existia:
                    res.atualizados += 1
                else:
                    res.criados += 1
            except Exception as exc:
                res.erros += 1
                res.mensagens_erro.append(
                    f"cliente id={c.get('id_cliente')}: {type(exc).__name__}: {exc}"[:300]
                )
                logger.exception('Erro upsert cliente id=%s', c.get('id_cliente'))

        res.total_paginas = pagina + 1
        ultima_pagina = paginacao.get('ultima_pagina', pagina)
        if pagina >= ultima_pagina:
            break
        pagina += 1
        if max_paginas and pagina >= max_paginas:
            logger.info('max_paginas atingido (%s) — abortando sync', max_paginas)
            break

    res.duracao_seg = time.monotonic() - t0
    return res


# ----------------------------------------------------------------------------
# Sync de OS reais
# ----------------------------------------------------------------------------

def sincronizar_base_os(
    integracao: IntegracaoAPI,
    *,
    dias: int = 7,
    max_paginas: Optional[int] = None,
    itens_por_pagina: int = 100,
) -> ResultadoSync:
    """Itera /ordem_servico/todos com data_inicio = now - `dias`. UPSERT em OrdemServicoHubsoft."""
    res = ResultadoSync()
    t0 = time.monotonic()
    svc = HubsoftService(integracao)
    data_inicio = (timezone.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
    pagina = 0

    # cache pra resolver cliente_id -> ClienteHubsoft
    cache_cliente = {}

    while True:
        try:
            resp = svc.listar_os_todos(
                pagina=pagina, itens_por_pagina=itens_por_pagina, data_inicio=data_inicio,
            )
        except HubsoftServiceError as exc:
            res.ok = False
            res.erros += 1
            res.mensagens_erro.append(f'pagina {pagina}: {exc}'[:300])
            logger.exception('Erro sync_base_os pagina=%s', pagina)
            break

        ordens = resp.get('ordens_servico') or resp.get('ordem_servico') or []
        paginacao = resp.get('paginacao') or {}
        if pagina == 0:
            res.total_registros = paginacao.get('total_registros', len(ordens))

        if not ordens:
            break

        for os_data in ordens:
            try:
                id_cliente_hub = os_data.get('id_cliente') or (os_data.get('cliente') or {}).get('id_cliente')
                cliente_local = None
                if id_cliente_hub:
                    if id_cliente_hub not in cache_cliente:
                        cache_cliente[id_cliente_hub] = ClienteHubsoft.all_tenants.filter(
                            tenant=integracao.tenant, id_cliente=id_cliente_hub,
                        ).first()
                    cliente_local = cache_cliente[id_cliente_hub]

                id_cs_hub = os_data.get('id_cliente_servico')
                servico_local = None
                if id_cs_hub:
                    servico_local = ServicoClienteHubsoft.all_tenants.filter(
                        tenant=integracao.tenant, id_cliente_servico=id_cs_hub,
                    ).first()

                defaults = {
                    'cliente': cliente_local,
                    'servico': servico_local,
                    'status': (os_data.get('status') or '')[:80],
                    'status_prefixo': (os_data.get('status_prefixo') or '')[:80],
                    'tipo': (os_data.get('tipo_ordem_servico') or os_data.get('tipo') or '')[:120],
                    'tecnico_id': os_data.get('id_tecnico') or (os_data.get('tecnico') or {}).get('id_tecnico'),
                    'tecnico_nome': ((os_data.get('tecnico') or {}).get('nome') or '')[:120],
                    'data_abertura': _parse_datetime(os_data.get('data_abertura') or os_data.get('data_cadastro')),
                    'data_agendamento': _parse_datetime(os_data.get('data_agendamento') or os_data.get('data_inicio_programado')),
                    'data_conclusao': _parse_datetime(os_data.get('data_conclusao') or os_data.get('data_fechamento')),
                    'descricao': (os_data.get('descricao') or '')[:5000],
                    'motivo': (os_data.get('motivo') or '')[:255],
                    'dados_completos': os_data,
                }
                _, created = OrdemServicoHubsoft.all_tenants.update_or_create(
                    tenant=integracao.tenant,
                    id_os_hubsoft=os_data.get('id_ordem_servico') or os_data.get('id_os'),
                    defaults=defaults,
                )
                if created:
                    res.criados += 1
                else:
                    res.atualizados += 1
            except Exception as exc:
                res.erros += 1
                res.mensagens_erro.append(
                    f"OS id={os_data.get('id_ordem_servico')}: {type(exc).__name__}: {exc}"[:300]
                )
                logger.exception('Erro upsert OS id=%s', os_data.get('id_ordem_servico'))

        res.total_paginas = pagina + 1
        ultima_pagina = paginacao.get('ultima_pagina', pagina)
        if pagina >= ultima_pagina:
            break
        pagina += 1
        if max_paginas and pagina >= max_paginas:
            break

    res.duracao_seg = time.monotonic() - t0
    return res


# ----------------------------------------------------------------------------
# Sync de atendimentos
# ----------------------------------------------------------------------------

def sincronizar_base_atendimentos(
    integracao: IntegracaoAPI,
    *,
    dias: int = 30,
    max_paginas: Optional[int] = None,
    itens_por_pagina: int = 100,
) -> ResultadoSync:
    """Itera /atendimento/todos com data_inicio. UPSERT em AtendimentoHubsoft."""
    res = ResultadoSync()
    t0 = time.monotonic()
    svc = HubsoftService(integracao)
    data_inicio = (timezone.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
    pagina = 0
    cache_cliente = {}

    while True:
        try:
            resp = svc.listar_atendimentos_todos(
                pagina=pagina, itens_por_pagina=itens_por_pagina, data_inicio=data_inicio,
            )
        except HubsoftServiceError as exc:
            res.ok = False
            res.erros += 1
            res.mensagens_erro.append(f'pagina {pagina}: {exc}'[:300])
            break

        atendimentos = resp.get('atendimentos') or []
        paginacao = resp.get('paginacao') or {}
        if pagina == 0:
            res.total_registros = paginacao.get('total_registros', len(atendimentos))

        if not atendimentos:
            break

        for a in atendimentos:
            try:
                id_cliente_hub = a.get('id_cliente') or (a.get('cliente') or {}).get('id_cliente')
                cliente_local = None
                if id_cliente_hub:
                    if id_cliente_hub not in cache_cliente:
                        cache_cliente[id_cliente_hub] = ClienteHubsoft.all_tenants.filter(
                            tenant=integracao.tenant, id_cliente=id_cliente_hub,
                        ).first()
                    cliente_local = cache_cliente[id_cliente_hub]

                defaults = {
                    'cliente': cliente_local,
                    'status': (a.get('status') or '')[:80],
                    'status_prefixo': (a.get('status_prefixo') or '')[:80],
                    'tipo': (a.get('tipo_atendimento') or a.get('tipo') or '')[:120],
                    'descricao': (a.get('descricao') or '')[:5000],
                    'data_abertura': _parse_datetime(a.get('data_inicio') or a.get('data_abertura')),
                    'data_fechamento': _parse_datetime(a.get('data_fechamento') or a.get('data_fim')),
                    'dados_completos': a,
                }
                _, created = AtendimentoHubsoft.all_tenants.update_or_create(
                    tenant=integracao.tenant,
                    id_atendimento_hubsoft=a.get('id_atendimento'),
                    defaults=defaults,
                )
                if created:
                    res.criados += 1
                else:
                    res.atualizados += 1
            except Exception as exc:
                res.erros += 1
                res.mensagens_erro.append(
                    f"atendimento id={a.get('id_atendimento')}: {type(exc).__name__}: {exc}"[:300]
                )
                logger.exception('Erro upsert atendimento id=%s', a.get('id_atendimento'))

        res.total_paginas = pagina + 1
        ultima_pagina = paginacao.get('ultima_pagina', pagina)
        if pagina >= ultima_pagina:
            break
        pagina += 1
        if max_paginas and pagina >= max_paginas:
            break

    res.duracao_seg = time.monotonic() - t0
    return res


# ----------------------------------------------------------------------------
# Sync de faturas (itera clientes — HubSoft nao tem /faturas/todos)
# ----------------------------------------------------------------------------

def sincronizar_base_faturas(
    integracao: IntegracaoAPI,
    *,
    apenas_status_servico: str = 'servico_habilitado',
    max_clientes: Optional[int] = None,
    rate_limit_seg: float = 1.0,
    limit_por_cliente: int = 50,
) -> ResultadoSync:
    """
    Itera ClienteHubsoft do tenant filtrando por status do servico e chama
    listar_faturas_cliente por cliente. UPSERT em FaturaHubsoft.

    - apenas_status_servico: limita aos clientes com algum servico nesse status.
    - rate_limit_seg: pausa entre clientes pra nao estourar API.
    - limit_por_cliente: max faturas retornadas por cliente.
    """
    res = ResultadoSync()
    t0 = time.monotonic()
    svc = HubsoftService(integracao)

    # Clientes com pelo menos 1 servico ativo (pra nao chamar API pra cancelados)
    qs = ClienteHubsoft.all_tenants.filter(tenant=integracao.tenant)
    if apenas_status_servico:
        qs = qs.filter(servicos__status_prefixo=apenas_status_servico).distinct()
    if max_clientes:
        qs = qs[:max_clientes]

    res.total_registros = qs.count()

    for cliente in qs.iterator():
        try:
            faturas = svc.listar_faturas_cliente(id_cliente=cliente.id_cliente, limit=limit_por_cliente) or []
        except HubsoftServiceError as exc:
            res.erros += 1
            res.mensagens_erro.append(f'cliente {cliente.id_cliente}: {exc}'[:200])
            continue
        except Exception as exc:
            res.erros += 1
            res.mensagens_erro.append(f'cliente {cliente.id_cliente}: {type(exc).__name__}: {exc}'[:200])
            continue

        for f in faturas:
            try:
                defaults = {
                    'cliente': cliente,
                    'valor': _parse_decimal(f.get('valor')) or 0,
                    'valor_pago': _parse_decimal(f.get('valor_pago')),
                    'data_emissao': _parse_date(f.get('data_emissao') or f.get('data_geracao')),
                    'data_vencimento': _parse_date(f.get('data_vencimento')) or timezone.now().date(),
                    'data_pagamento': _parse_date(f.get('data_pagamento')),
                    'status': _normalizar_status_fatura(f.get('status'), f.get('status_prefixo', '')),
                    'forma_pagamento': (f.get('forma_pagamento') or '')[:80],
                    'linha_digitavel': (f.get('linha_digitavel') or '')[:120],
                    'descricao': (f.get('descricao') or '')[:255],
                    'dados_completos': f,
                }
                _, created = FaturaHubsoft.all_tenants.update_or_create(
                    tenant=integracao.tenant,
                    id_fatura_hubsoft=f.get('id_fatura') or f.get('id'),
                    defaults=defaults,
                )
                if created:
                    res.criados += 1
                else:
                    res.atualizados += 1
            except Exception as exc:
                res.erros += 1
                res.mensagens_erro.append(
                    f"fatura {f.get('id_fatura')}: {type(exc).__name__}: {exc}"[:300]
                )

        if rate_limit_seg > 0:
            time.sleep(rate_limit_seg)

    res.duracao_seg = time.monotonic() - t0
    return res
