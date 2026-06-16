"""
Service unificado de consulta de viabilidade tecnica por CEP.

Estrategia em camadas (cai pra proxima se a anterior nao se aplica):
  1) **HubSoft API** — se o tenant tem IntegracaoAPI tipo='hubsoft' ativa,
     usa o endpoint /prospecto/create?cep=<cep> (listar_planos_por_cep).
     Se retorna planos: cobertura_ok. Vazio: fora_cobertura.
  2) **CidadeViabilidade local** — match direto por CEP, depois cidade/UF
     via ViaCEP (logica originalmente embutida no engine de atendimento).
  3) Sem nenhuma fonte: status='nao_consultado' (sem erro).

Centralizado pra ser chamado de:
  - CRM (api_editar_oportunidade — inline trigger no edit do CEP)
  - Engine de atendimento (_acao_check_viabilidade)
  - Outras integracoes futuras
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone as dt_timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ResultadoViabilidade:
    status: str              # 'cobertura_ok' | 'fora_cobertura' | 'nao_consultado' | 'erro'
    cep_consultado: str
    cidade: str = ''
    uf: str = ''
    fonte: str = ''          # 'hubsoft' | 'cidade_viabilidade' | ''
    detalhes: Optional[dict] = None
    consultado_em: str = ''

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _normalizar_cep(cep: str) -> str:
    """Retorna CEP com apenas digitos. Vazio se invalido."""
    so_digitos = re.sub(r'\D', '', str(cep or ''))
    return so_digitos if len(so_digitos) == 8 else ''


def _agora_iso() -> str:
    return datetime.now(dt_timezone.utc).isoformat()


def consultar_viabilidade(tenant, cep: str) -> ResultadoViabilidade:
    """
    Consulta viabilidade do CEP pro tenant. NUNCA levanta excecao — sempre
    retorna ResultadoViabilidade.

    - tenant: instancia Tenant
    - cep: string com ou sem formatacao

    Ordem de tentativa:
      1. HubSoft (se tenant tem IntegracaoAPI hubsoft ativa)
      2. CidadeViabilidade local + ViaCEP
      3. nao_consultado
    """
    cep_digits = _normalizar_cep(cep)
    if not cep_digits:
        return ResultadoViabilidade(
            status='erro', cep_consultado='', cidade='', uf='',
            fonte='', detalhes={'erro': 'cep_invalido'},
            consultado_em=_agora_iso(),
        )

    cep_fmt = f'{cep_digits[:5]}-{cep_digits[5:]}'

    # 1) HubSoft API
    res_hub = _tentar_hubsoft(tenant, cep_digits, cep_fmt)
    if res_hub is not None:
        return res_hub

    # 2) CidadeViabilidade local + ViaCEP
    res_local = _tentar_cidade_viabilidade(tenant, cep_digits, cep_fmt)
    if res_local is not None:
        return res_local

    # 3) Sem fonte configurada
    return ResultadoViabilidade(
        status='nao_consultado', cep_consultado=cep_fmt,
        consultado_em=_agora_iso(),
    )


def _tentar_hubsoft(tenant, cep_digits: str, cep_fmt: str) -> Optional[ResultadoViabilidade]:
    """Retorna None se tenant nao tem integracao hubsoft ativa."""
    try:
        from apps.integracoes.models import IntegracaoAPI
        from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    except Exception:
        return None

    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=tenant, tipo='hubsoft', ativa=True,
    ).first()
    if not integracao:
        return None

    try:
        service = HubsoftService(integracao)
        servicos = service.listar_planos_por_cep(cep_digits) or []
    except HubsoftServiceError as exc:
        msg = str(exc).lower()
        # HubSoft retorna erro generico pra CEP sem cobertura.
        # Tratamos qualquer erro de regra de negocio como fora_cobertura.
        if any(kw in msg for kw in ('cep', 'cidade', 'unidade', 'sem plano', 'sem servico')):
            return ResultadoViabilidade(
                status='fora_cobertura', cep_consultado=cep_fmt,
                fonte='hubsoft', detalhes={'mensagem': str(exc)[:200]},
                consultado_em=_agora_iso(),
            )
        logger.warning('viabilidade hubsoft falhou cep=%s tenant=%s: %s', cep_fmt, tenant.slug, exc)
        return ResultadoViabilidade(
            status='erro', cep_consultado=cep_fmt,
            fonte='hubsoft', detalhes={'erro': str(exc)[:200]},
            consultado_em=_agora_iso(),
        )
    except Exception as exc:
        logger.exception('viabilidade hubsoft inesperado cep=%s tenant=%s', cep_fmt, tenant.slug)
        return ResultadoViabilidade(
            status='erro', cep_consultado=cep_fmt,
            fonte='hubsoft', detalhes={'erro': f'{type(exc).__name__}: {exc}'[:200]},
            consultado_em=_agora_iso(),
        )

    if servicos:
        # HubSoft pode nao retornar cidade/uf direto — pega do primeiro servico
        # ou deixa vazio. Cliente da UI vai mostrar baseado em outros campos.
        return ResultadoViabilidade(
            status='cobertura_ok', cep_consultado=cep_fmt,
            fonte='hubsoft',
            detalhes={'planos': len(servicos)},
            consultado_em=_agora_iso(),
        )
    return ResultadoViabilidade(
        status='fora_cobertura', cep_consultado=cep_fmt,
        fonte='hubsoft', detalhes={'planos': 0},
        consultado_em=_agora_iso(),
    )


def _tentar_cidade_viabilidade(tenant, cep_digits: str, cep_fmt: str) -> Optional[ResultadoViabilidade]:
    """Fallback baseado na tabela CidadeViabilidade. Retorna None se tenant
    nao tem nenhuma cidade cadastrada."""
    try:
        from apps.comercial.viabilidade.models import CidadeViabilidade
    except Exception:
        return None

    qs_base = CidadeViabilidade.all_tenants.filter(tenant=tenant, ativo=True)
    if not qs_base.exists():
        return None

    # Match direto por CEP
    direto = qs_base.filter(cep=cep_fmt).first()
    if direto:
        return ResultadoViabilidade(
            status='cobertura_ok', cep_consultado=cep_fmt,
            cidade=direto.cidade, uf=direto.estado,
            fonte='cidade_viabilidade',
            detalhes={'match': 'cep_direto'},
            consultado_em=_agora_iso(),
        )

    # ViaCEP -> cidade/UF -> cruza com CidadeViabilidade
    cidade_via = ''
    uf_via = ''
    try:
        resp = requests.get(f'https://viacep.com.br/ws/{cep_digits}/json/', timeout=5)
        dados = resp.json() if resp.status_code == 200 else {}
        if not dados.get('erro'):
            cidade_via = (dados.get('localidade') or '').strip()
            uf_via = (dados.get('uf') or '').strip()
    except Exception as exc:
        logger.warning('viabilidade ViaCEP falhou cep=%s: %s', cep_digits, exc)

    if not cidade_via or not uf_via:
        return ResultadoViabilidade(
            status='fora_cobertura', cep_consultado=cep_fmt,
            fonte='cidade_viabilidade',
            detalhes={'match': 'viacep_indisponivel'},
            consultado_em=_agora_iso(),
        )

    if qs_base.filter(cidade__iexact=cidade_via, estado=uf_via).exists():
        return ResultadoViabilidade(
            status='cobertura_ok', cep_consultado=cep_fmt,
            cidade=cidade_via, uf=uf_via,
            fonte='cidade_viabilidade',
            detalhes={'match': 'cidade'},
            consultado_em=_agora_iso(),
        )
    return ResultadoViabilidade(
        status='fora_cobertura', cep_consultado=cep_fmt,
        cidade=cidade_via, uf=uf_via,
        fonte='cidade_viabilidade',
        detalhes={'match': 'cidade_nao_cadastrada'},
        consultado_em=_agora_iso(),
    )
