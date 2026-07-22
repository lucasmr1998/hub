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

import logging
from dataclasses import dataclass
from typing import Optional

from apps.comercial.leads.models import LeadProspecto
from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

logger = logging.getLogger(__name__)


# Placeholders padrao usados quando o lead nao tem dado real ainda.
# CEP precisa ser real pra HubSoft resolver cidade — pode ser sobrescrito
# por tenant via IntegracaoAPI.configuracoes_extras.cep_default.
PLACEHOLDER_CEP_FALLBACK = '13730000'  # Mococa-SP centro (default Nuvyon)
PLACEHOLDER_TEXTO = 'A confirmar'
PLACEHOLDER_NUMERO = 'S/N'
OBSERVACAO_RASCUNHO = 'RASCUNHO - dados pendentes via Hubtrix'


@dataclass
class ResultadoSincProspecto:
    ok: bool
    acao: str                    # 'criado' / 'atualizado' / 'ja_cliente' / 'pulado' / 'erro'
    motivo: Optional[str]        # mensagem em caso de erro/pular
    id_prospecto: Optional[str]  # preenchido em sucesso


def _so_digitos(valor) -> str:
    return ''.join(ch for ch in str(valor or '') if ch.isdigit())


def _marcar_convertido(lead: LeadProspecto) -> None:
    """Fecha o ciclo do lead: ele virou cliente, nao ha mais o que sincronizar."""
    LeadProspecto.all_tenants.filter(pk=lead.pk).update(
        status_api='convertido_cliente',
        motivo_rejeicao=None,
    )


def _reconhecer_cliente_existente(lead: LeadProspecto, service) -> Optional[ResultadoSincProspecto]:
    """O prospecto ja virou cliente no HubSoft? Entao espelha e encerra.

    Devolve um `ResultadoSincProspecto` quando reconheceu (o chamador deve parar
    ali) ou `None` quando nao e cliente / nao deu pra afirmar (segue o fluxo
    normal de edicao).

    Por que existe: o pre-flight exige 8 campos antes de editar o prospecto, mas
    prospecto convertido nao pode mais ser editado — o HubSoft recusa. Sem esta
    checagem o lead ficava travado por dado que ninguem mais precisa, mesmo com o
    cliente ja existindo do outro lado.

    Duas salvaguardas, porque marcar alguem como cliente por engano e pior do que
    deixar travado:

    1. So age com resposta REAL da API. Erro de consulta devolve None em vez de
       adivinhar — melhor seguir o fluxo normal e falhar visivelmente.
    2. Confere que o CPF devolvido bate com o perguntado. O `clientes[0]` da API
       e pego sem validacao; hoje o HubSoft se comporta como busca exata, mas
       depender disso vincularia a pessoa errada no dia em que mudar.
    """
    cpf = _so_digitos(lead.cpf_cnpj)
    if not cpf:
        return None

    from apps.integracoes.models import ClienteHubsoft

    # Ja espelhado: nem precisa perguntar de novo.
    if ClienteHubsoft.all_tenants.filter(tenant=lead.tenant, lead=lead).exists():
        _marcar_convertido(lead)
        return ResultadoSincProspecto(
            ok=True, acao='ja_cliente',
            motivo='cliente ja espelhado',
            id_prospecto=(lead.id_hubsoft or '').strip() or None,
        )

    try:
        resposta = service.consultar_cliente(lead.cpf_cnpj, lead=lead)
    except HubsoftServiceError as exc:
        # Nao da pra afirmar nada: segue o fluxo normal.
        logger.info(
            '[rascunho] consulta de cliente falhou pro lead %s, seguindo fluxo normal: %s',
            lead.pk, str(exc)[:160],
        )
        return None

    clientes = resposta.get('clientes') or []
    if not clientes:
        return None

    dados = clientes[0]
    if _so_digitos(dados.get('cpf_cnpj')) != cpf:
        logger.warning(
            '[rascunho] HubSoft devolveu CPF diferente do consultado no lead %s '
            '(pedido=%s devolvido=%s); NAO vinculando',
            lead.pk, cpf, _so_digitos(dados.get('cpf_cnpj')),
        )
        return None

    cliente = service._sincronizar_dados_cliente(dados, lead)
    _marcar_convertido(lead)
    logger.info(
        '[rascunho] lead %s reconhecido como cliente HubSoft %s; espelhado e marcado convertido',
        lead.pk, getattr(cliente, 'id_cliente', None),
    )
    return ResultadoSincProspecto(
        ok=True, acao='ja_cliente', motivo=None,
        id_prospecto=(lead.id_hubsoft or '').strip() or None,
    )


def _preencher_placeholders_para_rascunho(lead: LeadProspecto, integracao=None) -> dict:
    """Mantém nome+telefone reais; preenche placeholders nos vazios pra
    passar validacao do create do HubSoft.

    CEP precisa ser real pra HubSoft resolver cidade — e como cada
    Unidade de Negocio do HubSoft (Nuvyon, Mega/Salto, etc.) so vende seus
    planos em CEPs da cidade dela, o CEP padrao precisa bater com a empresa
    do flow que criou o lead. Resolucao em cascata:

      1. `lead.dados_custom['empresa']` + `cep_default_por_empresa[empresa]`
      2. `IntegracaoAPI.configuracoes_extras.cep_default` (legado)
      3. `PLACEHOLDER_CEP_FALLBACK` (Mococa-SP Nuvyon)

    Retorna dict {campo: valor_placeholder} que vai SOBRESCREVER campos vazios
    do lead apenas no momento da chamada — NAO persiste no lead.
    """
    extras = (integracao.configuracoes_extras or {}) if integracao else {}
    cep_default = (extras.get('cep_default') or PLACEHOLDER_CEP_FALLBACK).strip()

    # Override por empresa quando o flow Matrix marcou explicitamente
    empresa = ''
    dados_custom = getattr(lead, 'dados_custom', None) or {}
    if isinstance(dados_custom, dict):
        empresa = (dados_custom.get('empresa') or '').strip().lower()
    if empresa:
        por_empresa = extras.get('cep_default_por_empresa') or {}
        if isinstance(por_empresa, dict):
            cep_emp = (por_empresa.get(empresa) or '').strip()
            if cep_emp:
                cep_default = cep_emp

    overrides = {}
    if not (lead.cep or '').strip():
        overrides['cep'] = cep_default
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
        overrides = _preencher_placeholders_para_rascunho(lead, integracao)
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

    # ANTES do pre-flight: o prospecto ja virou cliente la?
    #
    # O pre-flight existe pra proteger a EDICAO do prospecto. Se ele ja virou
    # cliente, editar e impossivel — o HubSoft recusa com "Prospecto foi
    # convertido para o cliente. Nao e possivel alterar". Exigir os 8 campos
    # nesse ponto trava o lead por um dado que ninguem mais precisa, e foi o que
    # deixou 54 vendas de julho fora do espelho (30 delas so por falta de
    # nascimento/email/CEP, dado que o HubSoft nem devolve).
    ja_cliente = _reconhecer_cliente_existente(lead, service)
    if ja_cliente is not None:
        return ja_cliente

    # ATUALIZA prospecto existente — mas SO se lead estiver completo (mesmo
    # padrao do cron `processar_pendentes` legado: usa
    # validar_lead_pronto_para_prospect como gate). Se faltar dado, muda
    # status_api pro motivo (incompleto/cpf_invalido/etc.) e NAO chama
    # editar_prospecto — lead sai da fila ate alguem completar e setar
    # status_api='pendente' de novo.
    from apps.comercial.leads.utils import validar_lead_pronto_para_prospect
    status_pre, motivo_pre = validar_lead_pronto_para_prospect(lead, integracao)
    if status_pre != 'pendente':
        LeadProspecto.all_tenants.filter(pk=lead.pk).update(
            status_api=status_pre,
            motivo_rejeicao=(motivo_pre or '')[:500],
        )
        return ResultadoSincProspecto(
            ok=False, acao='pulado_preflight',
            motivo=f'{status_pre}: {motivo_pre}',
            id_prospecto=id_hubsoft_atual,
        )

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
