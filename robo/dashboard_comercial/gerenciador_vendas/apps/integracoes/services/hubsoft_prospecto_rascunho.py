"""
Helper de SINCRONIZACAO de prospecto HubSoft (rascunho cedo + update tardio).

Diferente de `hubsoft_prospecto.py::criar_prospecto_para_lead`:
- Nao bloqueia se faltar CPF/score/docs (pre-flight reduzido)
- Decide automaticamente: cria rascunho se `id_hubsoft` vazio, atualiza se preenchido
- Usado pela acao de automacao `sincronizar_prospecto_hubsoft`

Filosofia "rascunho + update":
- Lead chega no Hubtrix com nome + telefone reais → cria prospecto rascunho no
  HubSoft com placeholders nos demais campos (cep=0, endereco="A confirmar", etc.)
- Quando lead atinge status 'pendente' (dados reais coletados), atualiza o
  mesmo prospecto via PUT /prospecto/{id} com os dados reais.

NAO mexe nos crons antigos (`processar_pendentes`, `criar_prospectos_crm`) — eles
continuam ativos. Este helper roda EM PARALELO via automacao.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from apps.comercial.leads.models import LeadProspecto
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError


# Placeholders padrao usados quando o lead nao tem dado real ainda
PLACEHOLDER_CEP = '00000000'
PLACEHOLDER_TEXTO = 'A confirmar'
PLACEHOLDER_NUMERO = 'S/N'
OBSERVACAO_RASCUNHO = 'RASCUNHO - dados pendentes via Hubtrix'


@dataclass
class ResultadoSincProspecto:
    ok: bool
    acao: str                    # 'criado' / 'atualizado' / 'pulado' / 'erro'
    motivo: Optional[str]        # mensagem em caso de erro/pular
    id_prospecto: Optional[str]  # preenchido em sucesso


def _preencher_placeholders_para_rascunho(lead: LeadProspecto) -> dict:
    """Mantém nome+telefone reais; preenche placeholders nos vazios pra
    passar validacao do create do HubSoft.

    Retorna dict {campo: valor_placeholder} que vai SOBRESCREVER campos vazios
    do lead apenas no momento da chamada — NAO persiste no lead.
    """
    overrides = {}
    if not (lead.cep or '').strip():
        overrides['cep'] = PLACEHOLDER_CEP
    if not (lead.rua or lead.endereco or '').strip():
        overrides['endereco'] = PLACEHOLDER_TEXTO
    if not (lead.bairro or '').strip():
        overrides['bairro'] = PLACEHOLDER_TEXTO
    if not (lead.numero_residencia or '').strip():
        overrides['numero'] = PLACEHOLDER_NUMERO
    if not (lead.observacoes or '').strip():
        overrides['observacao'] = OBSERVACAO_RASCUNHO
    return overrides


def sincronizar_prospecto_hubsoft(
    lead: LeadProspecto,
    integracao: Optional[IntegracaoAPI] = None,
) -> ResultadoSincProspecto:
    """Cria rascunho OU atualiza prospecto existente — decide pelo `lead.id_hubsoft`.

    Side effects: atualiza `LeadProspecto.id_hubsoft`, `status_api` e
    `motivo_rejeicao` conforme resultado.

    NUNCA levanta excecao — sempre retorna ResultadoSincProspecto. Caller (o
    engine de automacao) usa o resultado pra logar e prosseguir sem travar o
    fluxo do lead.
    """
    # Pre-flight minimo
    if not (lead.nome_razaosocial or '').strip():
        return ResultadoSincProspecto(
            ok=False, acao='pulado',
            motivo='nome_razaosocial vazio', id_prospecto=None,
        )
    if not (lead.telefone or '').strip():
        return ResultadoSincProspecto(
            ok=False, acao='pulado',
            motivo='telefone vazio', id_prospecto=None,
        )

    # Resolve integracao
    if integracao is None:
        integracao = IntegracaoAPI.all_tenants.filter(
            tenant=lead.tenant, tipo='hubsoft', ativa=True,
        ).first()
        if integracao is None:
            return ResultadoSincProspecto(
                ok=False, acao='pulado',
                motivo='IntegracaoAPI HubSoft ativa nao encontrada',
                id_prospecto=None,
            )

    service = HubsoftService(integracao)

    # ---- DECISAO: cria vs atualiza
    id_hubsoft_atual = (lead.id_hubsoft or '').strip()

    if not id_hubsoft_atual:
        # CRIA rascunho com placeholders
        overrides = _preencher_placeholders_para_rascunho(lead)
        # Aplica overrides em campos vazios via attribute set TEMPORARIO
        snapshot = {}
        try:
            for campo, valor in overrides.items():
                if campo == 'cep':
                    snapshot['cep'] = lead.cep
                    lead.cep = valor
                elif campo == 'endereco':
                    snapshot['rua'] = lead.rua
                    snapshot['endereco_attr'] = lead.endereco
                    lead.rua = valor
                elif campo == 'bairro':
                    snapshot['bairro'] = lead.bairro
                    lead.bairro = valor
                elif campo == 'numero':
                    snapshot['numero_residencia'] = lead.numero_residencia
                    lead.numero_residencia = valor
                elif campo == 'observacao':
                    snapshot['observacoes'] = lead.observacoes
                    lead.observacoes = valor

            try:
                resposta = service.cadastrar_prospecto(lead)
            except HubsoftServiceError as exc:
                LeadProspecto.all_tenants.filter(pk=lead.pk).update(
                    motivo_rejeicao=f'rascunho falhou: {exc}'[:500],
                )
                return ResultadoSincProspecto(
                    ok=False, acao='erro',
                    motivo=str(exc), id_prospecto=None,
                )

            id_prospecto = (resposta.get('prospecto') or {}).get('id_prospecto')
            update_fields = {'status_api': 'rascunho_hubsoft', 'motivo_rejeicao': None}
            if id_prospecto:
                update_fields['id_hubsoft'] = str(id_prospecto)
            LeadProspecto.all_tenants.filter(pk=lead.pk).update(**update_fields)

            return ResultadoSincProspecto(
                ok=True, acao='criado', motivo=None,
                id_prospecto=str(id_prospecto) if id_prospecto else None,
            )
        finally:
            # Restaura campos do lead em memoria (nao foram persistidos)
            for attr, valor in snapshot.items():
                setattr(lead, attr.replace('_attr', ''), valor)

    # ATUALIZA prospecto existente com dados reais
    try:
        resposta = service.editar_prospecto(lead, id_hubsoft_atual)
    except HubsoftServiceError as exc:
        LeadProspecto.all_tenants.filter(pk=lead.pk).update(
            motivo_rejeicao=f'editar falhou: {exc}'[:500],
        )
        return ResultadoSincProspecto(
            ok=False, acao='erro',
            motivo=str(exc), id_prospecto=id_hubsoft_atual,
        )

    LeadProspecto.all_tenants.filter(pk=lead.pk).update(
        status_api='processado',
        motivo_rejeicao=None,
    )
    return ResultadoSincProspecto(
        ok=True, acao='atualizado', motivo=None,
        id_prospecto=id_hubsoft_atual,
    )
