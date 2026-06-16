"""
Service unificado de consulta de viabilidade tecnica por endereco.

Endpoint primario: HubSoft `consultar_viabilidade_endereco`
(`POST /api/v1/integracao/mapeamento/viabilidade/consultar`). Esse retorna
`viabilidade.atende = true/false` baseado em mapeamento real de cobertura
de rede.

Estrategia:
  1) Auto-preencher campos faltantes via ViaCEP quando o operador so digitou CEP.
  2) Se endereco continua incompleto: retorna 'endereco_incompleto'.
  3) Chama HubSoft `consultar_viabilidade_endereco` se tenant tem hubsoft ativa.
  4) Fallback: CidadeViabilidade local (mesma logica do endpoint /n8n/matrix/viabilidade/).
  5) Sem nenhuma fonte/dado: 'nao_consultado'.

Status possiveis no resultado:
  - 'cobertura_ok'        — atende (HubSoft) ou cidade cadastrada (local)
  - 'fora_cobertura'      — nao atende (HubSoft) ou cidade nao cadastrada
  - 'endereco_incompleto' — falta dado pra chamar HubSoft (e nao tem CidadeViabilidade)
  - 'nao_consultado'      — tenant nao tem fonte de viabilidade
  - 'erro'                — falha imprevista
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone as dt_timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ResultadoViabilidade:
    status: str              # cobertura_ok | fora_cobertura | endereco_incompleto | nao_consultado | erro
    cep_consultado: str
    cidade: str = ''
    uf: str = ''
    fonte: str = ''          # 'hubsoft' | 'cidade_viabilidade' | ''
    detalhes: Optional[dict] = None
    consultado_em: str = ''
    # Campos auto-preenchidos via ViaCEP — pra UI saber o que foi inferido
    auto_preenchido: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ----- helpers -----

def _normalizar_cep(cep: str) -> str:
    so_digitos = re.sub(r'\D', '', str(cep or ''))
    return so_digitos if len(so_digitos) == 8 else ''


def _agora_iso() -> str:
    return datetime.now(dt_timezone.utc).isoformat()


def _buscar_viacep(cep_digits: str) -> dict:
    """Retorna dict com logradouro/bairro/cidade/uf. Vazio se falhar."""
    try:
        resp = requests.get(f'https://viacep.com.br/ws/{cep_digits}/json/', timeout=5)
        if resp.status_code != 200:
            return {}
        dados = resp.json() or {}
        if dados.get('erro'):
            return {}
        return {
            'logradouro': (dados.get('logradouro') or '').strip(),
            'bairro': (dados.get('bairro') or '').strip(),
            'cidade': (dados.get('localidade') or '').strip(),
            'uf': (dados.get('uf') or '').strip().upper(),
        }
    except Exception as exc:
        logger.warning('ViaCEP falhou cep=%s: %s', cep_digits, exc)
        return {}


# ----- API publica -----

def consultar_viabilidade(
    tenant,
    cep: str,
    *,
    logradouro: str = '',
    numero: str = '',
    bairro: str = '',
    cidade: str = '',
    uf: str = '',
    auto_completar_via_cep: bool = True,
) -> ResultadoViabilidade:
    """
    Consulta viabilidade do endereco pro tenant. NUNCA levanta excecao.

    - tenant: instancia Tenant
    - cep, logradouro, numero, bairro, cidade, uf: campos do endereco
    - auto_completar_via_cep: se True, busca campos faltantes no ViaCEP

    Ordem:
      1. HubSoft `consultar_viabilidade_endereco`
      2. CidadeViabilidade local + ViaCEP
      3. nao_consultado
    """
    cep_digits = _normalizar_cep(cep)
    if not cep_digits:
        return ResultadoViabilidade(
            status='erro', cep_consultado='', fonte='',
            detalhes={'erro': 'cep_invalido'},
            consultado_em=_agora_iso(),
        )

    cep_fmt = f'{cep_digits[:5]}-{cep_digits[5:]}'
    auto = {}

    # Auto-preenche via ViaCEP os campos vazios
    if auto_completar_via_cep:
        faltam_geo = not (cidade and uf and (logradouro or bairro))
        if faltam_geo:
            via = _buscar_viacep(cep_digits)
            if via:
                if not logradouro and via.get('logradouro'):
                    logradouro = via['logradouro']
                    auto['logradouro'] = logradouro
                if not bairro and via.get('bairro'):
                    bairro = via['bairro']
                    auto['bairro'] = bairro
                if not cidade and via.get('cidade'):
                    cidade = via['cidade']
                    auto['cidade'] = cidade
                if not uf and via.get('uf'):
                    uf = via['uf']
                    auto['uf'] = uf

    # 1) HubSoft
    res_hub = _tentar_hubsoft(
        tenant, cep_fmt,
        logradouro=logradouro, numero=numero, bairro=bairro, cidade=cidade, uf=uf,
    )
    if res_hub is not None:
        res_hub.auto_preenchido = auto
        return res_hub

    # 2) CidadeViabilidade local
    res_local = _tentar_cidade_viabilidade(tenant, cep_fmt, cidade, uf)
    if res_local is not None:
        res_local.auto_preenchido = auto
        return res_local

    # 3) Sem fonte
    return ResultadoViabilidade(
        status='nao_consultado', cep_consultado=cep_fmt,
        cidade=cidade, uf=uf,
        auto_preenchido=auto, consultado_em=_agora_iso(),
    )


def _tentar_hubsoft(
    tenant, cep_fmt,
    *, logradouro, numero, bairro, cidade, uf,
) -> Optional[ResultadoViabilidade]:
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

    # HubSoft precisa de cidade+UF no minimo. Se nao temos isso (mesmo apos
    # ViaCEP), nao tem como chamar.
    if not (cidade and uf):
        return ResultadoViabilidade(
            status='endereco_incompleto', cep_consultado=cep_fmt,
            cidade=cidade, uf=uf, fonte='hubsoft',
            detalhes={'erro': 'falta cidade/uf (ViaCEP nao retornou)'},
            consultado_em=_agora_iso(),
        )

    service = HubsoftService(integracao)
    try:
        resultado_api = service.consultar_viabilidade_endereco(
            endereco=logradouro or '',
            numero=str(numero or 'S/N'),
            bairro=bairro or '',
            cidade=cidade,
            estado=uf,
        )
    except HubsoftServiceError as exc:
        logger.warning('viabilidade hubsoft erro cep=%s tenant=%s: %s', cep_fmt, tenant.slug, exc)
        return ResultadoViabilidade(
            status='erro', cep_consultado=cep_fmt,
            cidade=cidade, uf=uf, fonte='hubsoft',
            detalhes={'erro': str(exc)[:200]},
            consultado_em=_agora_iso(),
        )
    except Exception as exc:
        logger.exception('viabilidade hubsoft inesperado cep=%s', cep_fmt)
        return ResultadoViabilidade(
            status='erro', cep_consultado=cep_fmt,
            cidade=cidade, uf=uf, fonte='hubsoft',
            detalhes={'erro': f'{type(exc).__name__}: {exc}'[:200]},
            consultado_em=_agora_iso(),
        )

    # API retorna `resultado_api['viabilidade']` com 'atende' bool
    via = resultado_api.get('viabilidade') if isinstance(resultado_api, dict) else None
    if not isinstance(via, dict):
        # Algumas versoes podem retornar direto sem nesting
        via = resultado_api if isinstance(resultado_api, dict) else {}

    atende = bool(via.get('atende'))
    detalhes = {
        'tipo_atendimento': via.get('tipo_atendimento'),
        'planos': len(via.get('planos_disponiveis') or []),
        'motivo': via.get('motivo') or via.get('obs'),
    }
    detalhes = {k: v for k, v in detalhes.items() if v is not None}

    return ResultadoViabilidade(
        status='cobertura_ok' if atende else 'fora_cobertura',
        cep_consultado=cep_fmt,
        cidade=cidade, uf=uf, fonte='hubsoft',
        detalhes=detalhes,
        consultado_em=_agora_iso(),
    )


def _tentar_cidade_viabilidade(
    tenant, cep_fmt: str, cidade: str, uf: str,
) -> Optional[ResultadoViabilidade]:
    """Fallback baseado na tabela CidadeViabilidade. None se tenant nao tem
    nenhuma cidade cadastrada."""
    try:
        from apps.comercial.viabilidade.models import CidadeViabilidade
    except Exception:
        return None

    qs_base = CidadeViabilidade.all_tenants.filter(tenant=tenant, ativo=True)
    if not qs_base.exists():
        return None

    # CEP direto
    direto = qs_base.filter(cep=cep_fmt).first()
    if direto:
        return ResultadoViabilidade(
            status='cobertura_ok', cep_consultado=cep_fmt,
            cidade=direto.cidade, uf=direto.estado,
            fonte='cidade_viabilidade',
            detalhes={'match': 'cep_direto'},
            consultado_em=_agora_iso(),
        )

    if cidade and uf:
        cruz = qs_base.filter(cidade__iexact=cidade, estado=uf).exists()
        return ResultadoViabilidade(
            status='cobertura_ok' if cruz else 'fora_cobertura',
            cep_consultado=cep_fmt,
            cidade=cidade, uf=uf,
            fonte='cidade_viabilidade',
            detalhes={'match': 'cidade' if cruz else 'cidade_nao_cadastrada'},
            consultado_em=_agora_iso(),
        )

    return ResultadoViabilidade(
        status='endereco_incompleto', cep_consultado=cep_fmt,
        cidade=cidade, uf=uf, fonte='cidade_viabilidade',
        detalhes={'erro': 'sem cidade/uf'},
        consultado_em=_agora_iso(),
    )
