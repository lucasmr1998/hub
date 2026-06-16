"""
Helper compartilhado pra criar prospecto no HubSoft a partir de um lead.

Usado por:
- `processar_pendentes` (cron padrao — lead vindo de Matrix bot, status_api='pendente')
- `criar_prospectos_crm` (cron CRM — lead "humano" travado em status_api='processamento_manual'
  que ja completou docs + score + esta no estagio "Analises - Doc & Score")

Centraliza:
- Pre-flight (validar_lead_pronto_para_prospect)
- Chamada `HubsoftService.cadastrar_prospecto`
- Atualizacao do lead (status_api, id_hubsoft, motivo_rejeicao)
- Categorizacao de erros

Nao mexe em quem chama. Cada command monta seu proprio filtro de leads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from apps.comercial.leads.models import LeadProspecto
from apps.comercial.leads.utils import validar_lead_pronto_para_prospect
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError


@dataclass
class ResultadoProspecto:
    ok: bool
    novo_status: str            # 'processado' / 'cpf_invalido' / 'vendedor_invalido' / 'regra_negocio' / 'erro' / 'pre_flight_<motivo>'
    motivo: Optional[str]       # mensagem em caso de erro/pular; None se ok
    id_prospecto: Optional[str] # preenchido em sucesso
    pulado_preflight: bool = False


def _categorizar_erro_hubsoft(mensagem: str) -> str:
    """Mapeia mensagem de erro HubSoft pra um codigo de status_api."""
    msg = (mensagem or '').lower()
    if 'cpf' in msg and ('invalido' in msg or 'inválido' in msg):
        return 'cpf_invalido'
    if 'vendedor' in msg and ('invalido' in msg or 'inválido' in msg):
        return 'vendedor_invalido'
    if any(kw in msg for kw in ('plano', 'unidade', 'cidade', 'origem')):
        return 'regra_negocio'
    return 'erro'


def criar_prospecto_para_lead(
    lead: LeadProspecto,
    integracao: Optional[IntegracaoAPI] = None,
    *,
    skip_preflight: bool = False,
) -> ResultadoProspecto:
    """
    Tenta criar prospecto no HubSoft pra um lead. Atualiza o lead com o resultado.

    - `integracao`: opcional. Se nao passar, busca IntegracaoAPI tipo='hubsoft' ativa do tenant do lead.
    - `skip_preflight`: pula `validar_lead_pronto_para_prospect`. Util pra recuperacao
      manual onde quem chama ja garantiu validacao.

    Side effects: atualiza `LeadProspecto.status_api`, `id_hubsoft`, `motivo_rejeicao`.
    Reconcilia Venda se sucesso.

    NUNCA levanta excecao — sempre retorna ResultadoProspecto.
    """
    if integracao is None:
        integracao = IntegracaoAPI.all_tenants.filter(
            tenant=lead.tenant, tipo='hubsoft', ativa=True,
        ).first()
        if integracao is None:
            return ResultadoProspecto(
                ok=False, novo_status='erro',
                motivo=f'IntegracaoAPI HubSoft ativa nao encontrada pro tenant {lead.tenant_id}',
                id_prospecto=None,
            )

    if not skip_preflight:
        status_pre, motivo_pre = validar_lead_pronto_para_prospect(lead, integracao)
        if status_pre != 'pendente':
            LeadProspecto.all_tenants.filter(pk=lead.pk).update(
                status_api=status_pre,
                motivo_rejeicao=(motivo_pre or '')[:500],
            )
            return ResultadoProspecto(
                ok=False, novo_status=status_pre, motivo=motivo_pre,
                id_prospecto=None, pulado_preflight=True,
            )

    service = HubsoftService(integracao)
    try:
        resposta = service.cadastrar_prospecto(lead)
    except HubsoftServiceError as exc:
        novo_status = _categorizar_erro_hubsoft(str(exc))
        LeadProspecto.all_tenants.filter(pk=lead.pk).update(
            status_api=novo_status,
            motivo_rejeicao=str(exc)[:500],
        )
        return ResultadoProspecto(
            ok=False, novo_status=novo_status, motivo=str(exc),
            id_prospecto=None,
        )
    except Exception as exc:
        LeadProspecto.all_tenants.filter(pk=lead.pk).update(
            status_api='erro',
            motivo_rejeicao=f'{type(exc).__name__}: {exc}'[:500],
        )
        return ResultadoProspecto(
            ok=False, novo_status='erro', motivo=str(exc),
            id_prospecto=None,
        )

    id_prospecto = resposta.get('prospecto', {}).get('id_prospecto')
    update_fields = {'status_api': 'processado', 'motivo_rejeicao': None}
    if id_prospecto:
        update_fields['id_hubsoft'] = str(id_prospecto)
    LeadProspecto.all_tenants.filter(pk=lead.pk).update(**update_fields)

    if id_prospecto:
        try:
            from apps.integracoes.signals import _reconciliar_venda_com_prospecto
            _reconciliar_venda_com_prospecto(lead.pk, lead.tenant_id)
        except Exception:
            pass  # nao bloqueia o sucesso do prospecto

    return ResultadoProspecto(
        ok=True, novo_status='processado', motivo=None,
        id_prospecto=str(id_prospecto) if id_prospecto else None,
    )
