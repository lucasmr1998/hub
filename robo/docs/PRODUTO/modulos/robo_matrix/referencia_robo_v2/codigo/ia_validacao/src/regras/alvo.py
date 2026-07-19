"""Dispatcher do alvo de escrita: LeadProspecto vs NewService.

Quando o cliente Hubsoft está no fluxo de "Contratar novo serviço", a IA
coleta os mesmos dados (endereço, plano, docs, agendamento) — mas eles
não devem sobrescrever o `LeadProspecto` original. Vão pra um `NewService`
em coleta.

Este módulo centraliza a decisão de ALVO. O engine + onboarding chamam
estas funções em vez de `robovendas.atualizar_lead` / `consultar_lead_completo`
diretamente — assim o fluxo é o mesmo, mas grava no lugar certo.
"""
from __future__ import annotations

import logging
from typing import Any

from src.contexto.conversa import gerenciador as ctx_gerenciador
from src.integracoes import robovendas
from src.integracoes import log_interacao as _log_ia

logger = logging.getLogger(__name__)


def _log_ns(evento: str, *, lead_id: int | None = None, telefone: str = '',
            new_service_id: int | None = None, valido: bool | None = None,
            payload_in: dict | None = None, payload_out: dict | None = None,
            mensagem: str = '') -> None:
    """Helper local pra logar eventos do fluxo Novo Serviço.

    Cada chamada cria um registro em LogInteracaoIA com endpoint='new_service'.
    Motivo carrega o nome do evento (iniciado/atualizado/cancelado/finalizado/etc).
    `payload_out` recebe um snapshot do estado do NS quando relevante.
    """
    try:
        from src.config import config as _cfg
        base_url = getattr(_cfg, 'ROBOVENDAS_API_URL', '') or ''
    except Exception:
        base_url = ''
    _log_ia.registrar_log(
        base_url,
        endpoint='new_service',
        cellphone=telefone or '',
        lead_id=lead_id,
        question_id=(new_service_id and f'ns:{new_service_id}') or '',
        answer='',
        mensagem_resposta=mensagem or '',
        payload_in=payload_in or {},
        payload_out=payload_out or {},
        valido=valido,
        motivo=f'ns:{evento}',
    )


# Campos do NewService que correspondem ao mesmo nome no LeadProspecto.
# A coleta reusa os mesmos question_ids/regras, então as chaves batem.
CAMPOS_NEW_SERVICE = {
    'tipo_imovel', 'tipo_residencia',
    'cep', 'rua', 'numero_residencia', 'bairro', 'cidade', 'estado',
    'endereco_confirmado', 'ponto_referencia',
    'id_plano_rp', 'plano_confirmado', 'id_dia_vencimento', 'valor',
    'dados_confirmados', 'tipo_ajuste',
    'doc_selfie_recebida', 'doc_frente_recebida', 'doc_verso_recebida',
    'turno_instalacao', 'data_instalacao',
}


def _ctx_new_service_id(telefone: str) -> int | None:
    if not telefone:
        return None
    ctx = ctx_gerenciador.obter(telefone)
    return ctx.get('dados_extraidos', {}).get('new_service_id_em_coleta')


def _ctx_definir_new_service_id(telefone: str, new_service_id: int | None) -> None:
    if not telefone:
        return
    ctx_gerenciador.salvar_dado(telefone, 'new_service_id_em_coleta', new_service_id)


def _ctx_obter_ns_cache(telefone: str) -> dict | None:
    """Cache em memória do NewService — evita GETs repetidos (nginx 503)."""
    if not telefone:
        return None
    ctx = ctx_gerenciador.obter(telefone)
    return ctx.get('dados_extraidos', {}).get('new_service_cache')


def _ctx_atualizar_ns_cache(telefone: str, ns: dict | None) -> None:
    if not telefone:
        return
    ctx_gerenciador.salvar_dado(telefone, 'new_service_cache', dict(ns) if ns else None)


def _ctx_patch_ns_cache(telefone: str, campos: dict) -> None:
    """Aplica updates no cache (espelha o write no Django)."""
    if not telefone:
        return
    ctx = ctx_gerenciador.obter(telefone)
    cache = ctx.get('dados_extraidos', {}).get('new_service_cache')
    if isinstance(cache, dict):
        cache.update(campos)
        ctx_gerenciador.salvar_dado(telefone, 'new_service_cache', cache)


# ── Cache do LEAD (mesma motivação: nginx rate-limit no GET) ──────────
def _ctx_obter_lead_cache(telefone: str) -> dict | None:
    if not telefone:
        return None
    ctx = ctx_gerenciador.obter(telefone)
    return ctx.get('dados_extraidos', {}).get('lead_cache')


def _ctx_atualizar_lead_cache(telefone: str, lead: dict | None) -> None:
    if not telefone:
        return
    ctx_gerenciador.salvar_dado(telefone, 'lead_cache', dict(lead) if lead else None)


def _ctx_patch_lead_cache(telefone: str, campos: dict) -> None:
    if not telefone:
        return
    ctx = ctx_gerenciador.obter(telefone)
    cache = ctx.get('dados_extraidos', {}).get('lead_cache')
    if isinstance(cache, dict):
        cache.update(campos)
        ctx_gerenciador.salvar_dado(telefone, 'lead_cache', cache)


def consultar_lead_cached(lead_id: int | None, telefone: str = '') -> dict | None:
    """Wrapper cacheado pro robovendas.consultar_lead_completo.

    Evita bater no Django (e levar 503 do nginx) em cada /proximo-passo.
    Cache vive por sessão (em memória do FastAPI). Writes em campos do lead
    via `atualizar_alvo` atualizam o cache, mantendo consistência.
    """
    cached = _ctx_obter_lead_cache(telefone)
    if cached:
        return cached
    lead = robovendas.consultar_lead_completo(lead_id=lead_id, telefone=telefone)
    if lead:
        _ctx_atualizar_lead_cache(telefone, lead)
    return lead


def descobrir_new_service_id(lead_id: int, telefone: str = '') -> int | None:
    """Retorna o id do NewService em coleta do lead.

    Cache: lê do contexto primeiro; se vazio, consulta o Django.
    Quando consulta, popula o cache completo (evita GET futuro).
    """
    nsid = _ctx_new_service_id(telefone)
    if nsid:
        return nsid
    if not lead_id:
        return None
    ns = robovendas.obter_new_service_em_coleta(lead_id)
    if ns:
        nsid = ns.get('id')
        if nsid:
            _ctx_definir_new_service_id(telefone, nsid)
            _ctx_atualizar_ns_cache(telefone, ns)
        return nsid
    return None


# ──────────────────────────────────────────────────────────────────────
#  API pública — usada por engine + onboarding
# ──────────────────────────────────────────────────────────────────────
def iniciar_fluxo_new_service(lead_id: int, telefone: str = '') -> int | None:
    """Cria um NewService NOVO em coleta + marca o lead + reseta cache.

    Marca lead.status_api='em_fluxo_new_service' pra que o onboarding
    saiba que o cliente está no fluxo de contratação de novo serviço.
    Inicializa o cache com o NS recém-criado (todos campos vazios).
    """
    nsid = robovendas.criar_new_service(lead_id)
    if not nsid:
        _log_ns('iniciar_falhou', lead_id=lead_id, telefone=telefone, valido=False,
                mensagem='Falha ao criar NewService no Django')
        return None
    _ctx_definir_new_service_id(telefone, nsid)
    # Inicializa cache com NS vazio (o endpoint criar retornou dict completo,
    # mas como não temos aqui, busca uma vez OU inicializa do zero).
    _ctx_atualizar_ns_cache(telefone, {
        'id': nsid, 'status': 'em_coleta',
        'tipo_imovel': '', 'tipo_residencia': '',
        'cep': '', 'rua': '', 'numero_residencia': '',
        'bairro': '', 'cidade': '', 'estado': '',
        'endereco_confirmado': None, 'ponto_referencia': '',
        'id_plano_rp': None, 'plano_confirmado': None,
        'id_dia_vencimento': None, 'valor': None,
        'dados_confirmados': None, 'tipo_ajuste': '',
        'doc_selfie_recebida': None, 'doc_frente_recebida': None, 'doc_verso_recebida': None,
        'turno_instalacao': '', 'data_instalacao': None,
    })
    try:
        robovendas.atualizar_status(lead_id, 'em_fluxo_new_service')
        _ctx_patch_lead_cache(telefone, {'status_api': 'em_fluxo_new_service'})
    except Exception as e:
        logger.warning('Falha marcar lead %s em_fluxo_new_service: %s', lead_id, e)
    _log_ns('iniciado', lead_id=lead_id, telefone=telefone,
            new_service_id=nsid, valido=True,
            payload_out={'new_service_id': nsid, 'status_api': 'em_fluxo_new_service'},
            mensagem='NewService criado e lead marcado em_fluxo_new_service')
    return nsid


def encerrar_fluxo_new_service(lead_id: int, new_service_id: int,
                               telefone: str = '', observacoes: str = '') -> bool:
    """Finaliza o NewService e restaura status_api do lead pra 'cliente_ativo'."""
    # Snapshot do NS antes do encerramento (pra ter registro do estado final)
    snap = _ctx_obter_ns_cache(telefone) or {}
    ok = robovendas.finalizar_new_service(new_service_id, observacoes=observacoes)
    _ctx_definir_new_service_id(telefone, None)
    _ctx_atualizar_ns_cache(telefone, None)
    try:
        robovendas.atualizar_status(lead_id, 'cliente_ativo')
        _ctx_patch_lead_cache(telefone, {'status_api': 'cliente_ativo'})
    except Exception as e:
        logger.warning('Falha restaurar status do lead %s: %s', lead_id, e)
    _log_ns(
        'finalizado' if ok else 'finalizar_falhou',
        lead_id=lead_id, telefone=telefone, new_service_id=new_service_id,
        valido=ok,
        payload_in={'observacoes': observacoes},
        payload_out={'snapshot': snap, 'status_api_restaurado': 'cliente_ativo'},
        mensagem=observacoes or 'NewService finalizado',
    )
    return ok


# ──────────────────────────────────────────────────────────────────────
#  FLUXO UPGRADE DE PLANO (cliente Hubsoft escolheu "2)" no menu)
#  O atendimento vive no Django (FluxoAtendimento tipo='upgrade'); aqui só
#  guardamos o atendimento_id em contexto e marcamos o status do lead.
# ──────────────────────────────────────────────────────────────────────
def _ctx_upgrade_atendimento_id(telefone: str) -> int | None:
    if not telefone:
        return None
    ctx = ctx_gerenciador.obter(telefone)
    return ctx.get('dados_extraidos', {}).get('upgrade_atendimento_id')


def _ctx_definir_upgrade_atendimento_id(telefone: str, atendimento_id: int | None) -> None:
    if not telefone:
        return
    ctx_gerenciador.salvar_dado(telefone, 'upgrade_atendimento_id', atendimento_id)


def iniciar_fluxo_upgrade(lead_id: int, telefone: str = '') -> int | None:
    """Cria o atendimento de upgrade no Django + marca o lead
    status_api='em_fluxo_upgrade'. Devolve o atendimento_id (ou None)."""
    resp = robovendas.turno_upgrade(lead_id, '')
    aid = (resp or {}).get('atendimento_id')
    if not aid:
        _log_ns('upgrade_iniciar_falhou', lead_id=lead_id, telefone=telefone,
                valido=False, mensagem='Falha ao criar atendimento de upgrade no Django')
        return None
    _ctx_definir_upgrade_atendimento_id(telefone, aid)
    try:
        robovendas.atualizar_status(lead_id, 'em_fluxo_upgrade')
        _ctx_patch_lead_cache(telefone, {'status_api': 'em_fluxo_upgrade'})
    except Exception as e:
        logger.warning('Falha marcar lead %s em_fluxo_upgrade: %s', lead_id, e)
    _log_ns('upgrade_iniciado', lead_id=lead_id, telefone=telefone, valido=True,
            payload_out={'atendimento_id': aid, 'status_api': 'em_fluxo_upgrade'},
            mensagem='Atendimento de upgrade criado e lead marcado em_fluxo_upgrade')
    return aid


def encerrar_fluxo_upgrade(lead_id: int, telefone: str = '',
                           upgrade_id: int | None = None,
                           status_final: str = 'cliente_ativo') -> None:
    """Limpa o contexto do upgrade e define o status_api final do lead.

    status_final:
      - 'atendimento_concluido' → upgrade concluído com sucesso: encerra o
        atendimento (a conversa fecha no nó red_encerrar).
      - 'cliente_ativo'         → abandono/transbordo: volta pro menu.
    """
    _ctx_definir_upgrade_atendimento_id(telefone, None)
    try:
        robovendas.atualizar_status(lead_id, status_final)
        _ctx_patch_lead_cache(telefone, {'status_api': status_final})
    except Exception as e:
        logger.warning('Falha definir status do lead %s: %s', lead_id, e)
    _log_ns('upgrade_finalizado', lead_id=lead_id, telefone=telefone, valido=True,
            payload_out={'upgrade_id': upgrade_id, 'status_api_final': status_final},
            mensagem='Fluxo de upgrade encerrado')


def alvo_de_escrita(lead_id: int, telefone: str = '') -> tuple[str, int]:
    """Retorna ('lead'|'new_service', id_alvo)."""
    nsid = descobrir_new_service_id(lead_id, telefone)
    if nsid:
        return ('new_service', nsid)
    return ('lead', lead_id)


def atualizar_alvo(lead_id: int, campos: dict[str, Any], telefone: str = '') -> bool:
    """Despacha o update pro alvo correto + espelha no cache em memória."""
    if not campos:
        return True

    tipo, alvo_id = alvo_de_escrita(lead_id, telefone)
    if tipo == 'lead':
        ok = robovendas.atualizar_lead(lead_id, campos)
        if ok:
            # Espelha no cache em memória — senão o /proximo-passo seguinte lê
            # o lead velho (sem o campo recém-salvo) e RE-PERGUNTA o mesmo
            # campo (ex.: pede o CPF de novo após "CPF validado!").
            _ctx_patch_lead_cache(telefone, campos)
        return ok

    campos_ns = {k: v for k, v in campos.items() if k in CAMPOS_NEW_SERVICE}
    campos_lead = {k: v for k, v in campos.items() if k not in CAMPOS_NEW_SERVICE}

    ok_ns = True
    if campos_ns:
        ok_ns = robovendas.atualizar_new_service(alvo_id, campos_ns)
        if ok_ns:
            # Espelha no cache pra próximas leituras não baterem no nginx
            _ctx_patch_ns_cache(telefone, campos_ns)
    ok_lead = True
    if campos_lead:
        ok_lead = robovendas.atualizar_lead(lead_id, campos_lead)
        if ok_lead:
            _ctx_patch_lead_cache(telefone, campos_lead)

    _log_ns(
        'atualizado' if (ok_ns and ok_lead) else 'atualizar_falhou',
        lead_id=lead_id, telefone=telefone, new_service_id=alvo_id,
        valido=(ok_ns and ok_lead),
        payload_in={'campos_ns': campos_ns, 'campos_lead': campos_lead},
        payload_out={'ok_ns': ok_ns, 'ok_lead': ok_lead},
        mensagem=', '.join(campos_ns.keys()) or 'sem campos NS',
    )
    return ok_ns and ok_lead


def registrar_imagem_alvo(lead_id: int, link_url: str, descricao: str,
                           status_validacao: str = '',
                           observacao_validacao: str = '',
                           telefone: str = '') -> bool:
    """Despacha registro de imagem pro NewService (se em coleta) ou pro Lead."""
    tipo, alvo_id = alvo_de_escrita(lead_id, telefone)
    if tipo == 'new_service':
        ok = robovendas.registrar_imagem_new_service(
            alvo_id, link_url, descricao,
            status_validacao=status_validacao,
            observacao_validacao=observacao_validacao,
        )
        _log_ns(
            'imagem_registrada' if ok else 'imagem_falhou',
            lead_id=lead_id, telefone=telefone, new_service_id=alvo_id,
            valido=ok,
            payload_in={'link_url': link_url, 'descricao': descricao,
                        'status_validacao': status_validacao},
            payload_out={'ok': ok},
            mensagem=f'{descricao}: {link_url[:80]}',
        )
        return ok
    return robovendas.registrar_imagem(
        lead_id, link_url, descricao,
        status_validacao=status_validacao,
        observacao=observacao_validacao,
    )


def consultar_dados_alvo(lead_id: int, telefone: str = '') -> dict[str, Any] | None:
    """Retorna lead + NewService espelhado.

    OTIMIZAÇÃO crítica: NewService vem do CACHE em memória (cada write
    espelha lá). Evita 3-4 GETs por /proximo-passo que disparavam 503 do
    nginx. Cache só é populado uma vez por sessão (no inicio do fluxo).
    """
    tipo, alvo_id = alvo_de_escrita(lead_id, telefone)
    lead = consultar_lead_cached(lead_id, telefone) or {}
    if tipo == 'lead':
        return lead

    # Lê NS do cache (não bate no Django se o cache existir)
    ns = _ctx_obter_ns_cache(telefone)
    if ns is None:
        # Cache vazio (worker reiniciou ou sessão nova) — busca uma vez
        ns = robovendas.obter_new_service(alvo_id) or {}
        if ns:
            _ctx_atualizar_ns_cache(telefone, ns)

    combinado = dict(lead)
    for k in CAMPOS_NEW_SERVICE:
        if k in ns:
            combinado[k] = ns[k]
    combinado['_alvo'] = 'new_service'
    combinado['_new_service_id'] = alvo_id
    return combinado
