"""Ações de negócio (hooks) disparadas após uma validação bem-sucedida.

Porta fiel dos hooks que o engine.validar_por_regra dispara, mas chamando
os SERVIÇOS diretamente (robovendas / _alvo). Assim o /conv/turno executa
as mesmas ações do determinístico SEM passar pelo validar_por_regra — o
ponto de acoplamento que forçava editar o núcleo a cada ajuste do conv.

Cada hook é tolerante a falha (try/except) — uma ação que falha nunca
derruba o turno; o atendente humano resolve.
"""
from __future__ import annotations

import logging
from datetime import datetime

from src.integracoes.robovendas import robovendas
from src.regras import alvo as _alvo

logger = logging.getLogger(__name__)


def _patch_status(cellphone: str, status: str) -> None:
    """Espelha o status no cache em memória (coerência das leituras)."""
    try:
        _alvo._ctx_patch_lead_cache(cellphone, {'status_api': status})  # noqa: SLF001
    except Exception:
        pass


def disparar_hooks(
    qid: str,
    regra: dict,
    *,
    lead_id: int | None,
    cellphone: str,
    resultado,          # validacao.Resultado
    analise: dict,
    em_new_service: bool,
) -> dict:
    """Dispara as ações de negócio do passo. Retorna info p/ o orquestrador."""
    info: dict = {}
    if not lead_id:
        return info

    extra = getattr(resultado, 'extra', {}) or {}
    negou = extra.get('confirmacao') is False   # confirmação respondida "não"

    # ── Passos com tratamento PRÓPRIO (não aplicam status/tags genéricos) ─
    especial = qid in ('menu_cliente_existente', 'escolha_data',
                       'pergunta_finalizar', 'retomar_ou_recomecar')

    # ── 0) retomar_ou_recomecar → limpa campos se "começar de novo" ───
    if qid == 'retomar_ou_recomecar':
        if extra.get('opcao') == 'recomecar':
            try:
                from src.conversacional.retomada import CAMPOS_RECOMECAR
                _alvo.atualizar_alvo(lead_id, dict(CAMPOS_RECOMECAR), telefone=cellphone)
                _alvo._ctx_patch_lead_cache(cellphone, dict(CAMPOS_RECOMECAR))  # noqa: SLF001
                info['recomecou'] = True
                logger.info('Cliente optou por RECOMEÇAR — campos limpos (lead=%s)', lead_id)
            except Exception as e:
                logger.warning('Falha limpar campos no recomeçar lead=%s: %s', lead_id, e)
        return info

    # ── 1) CPF → consulta Hubsoft (Django seta status se for cliente) ──
    if qid == 'coleta_cpf':
        try:
            res = robovendas.verificar_cliente_por_cpf(lead_id)
            info['hubsoft'] = res
            if res and res.get('eh_cliente'):
                # Django já setou status_api='cliente_ativo' — espelha no cache
                _patch_status(cellphone, 'cliente_ativo')
                logger.info('CPF é cliente Hubsoft (lead=%s)', lead_id)
        except Exception as e:
            logger.warning('Hubsoft check falhou lead=%s: %s', lead_id, e)

    # ── 2) Menu cliente existente → roteia opção ──────────────────────
    if qid == 'menu_cliente_existente':
        opcao = extra.get('opcao')
        if opcao == 'novo_servico':
            try:
                nsid = _alvo.iniciar_fluxo_new_service(lead_id, telefone=cellphone)
                info['new_service_id'] = nsid
                logger.info('NewService iniciado lead=%s ns=%s', lead_id, nsid)
            except Exception as e:
                logger.warning('Falha iniciar NewService lead=%s: %s', lead_id, e)
        elif opcao == 'upgrade_plano':
            try:
                aid = _alvo.iniciar_fluxo_upgrade(lead_id, telefone=cellphone)
                if aid:
                    info['upgrade_atendimento_id'] = aid
                    logger.info('Fluxo upgrade iniciado lead=%s aid=%s', lead_id, aid)
                else:
                    logger.warning('Falha iniciar Upgrade lead=%s — transbordando', lead_id)
                    info['transbordo_menu'] = True
            except Exception as e:
                logger.warning('Falha iniciar upgrade lead=%s: %s', lead_id, e)
                info['transbordo_menu'] = True
        elif opcao == 'finalizar':
            try:
                robovendas.atualizar_status(lead_id, 'atendimento_concluido')
                _patch_status(cellphone, 'atendimento_concluido')
                info['finalizou'] = True
            except Exception as e:
                logger.warning('Falha finalizar atendimento lead=%s: %s', lead_id, e)
        else:
            # upgrade / acompanhar / atendimento → transbordo humano
            info['transbordo_menu'] = True

    # ── 3) escolha_data → mapeia opção→data, salva e agenda/encerra ───
    if qid == 'escolha_data':
        opcao = extra.get('opcao') or analise.get('opcao_numerica')
        info['agendamento'] = _agendar(lead_id, cellphone, opcao, em_new_service)

    # ── 4) status / tags genéricos (demais passos) ────────────────────
    if not especial and not negou:
        status = (regra.get('status_api_apos_sucesso') or '').strip()
        if status and not em_new_service:
            try:
                robovendas.atualizar_status(lead_id, status)
                _patch_status(cellphone, status)
            except Exception as e:
                logger.warning('Falha status=%s lead=%s: %s', status, lead_id, e)

    if not especial and not negou:
        add = regra.get('tags_adicionar') or []
        rem = regra.get('tags_remover') or []
        if add or rem:
            try:
                robovendas.atualizar_tags(lead_id, tags_add=add, tags_remove=rem)
            except Exception as e:
                logger.warning('Falha tags lead=%s: %s', lead_id, e)

    return info


def _agendar(lead_id: int, cellphone: str, opcao, em_new_service: bool) -> dict | None:
    """Mapeia a opção (1/2/3) pra data real, salva e dispara agendamento.

    Em fluxo de Novo Serviço, encerra o NewService em vez de abrir OS Hubsoft.
    """
    if not opcao:
        return None
    try:
        hoje = datetime.now().strftime('%d/%m/%Y')
        datas = robovendas.consultar_datas_disponiveis(hoje)
        idx = int(str(opcao).strip()) - 1
        if not (0 <= idx < len(datas)):
            logger.warning('Opção %s fora do range de datas (lead=%s)', opcao, lead_id)
            return {'status': 'opcao_fora_range'}
        data_str = datas[idx]
        try:
            dt = datetime.strptime(data_str, '%d/%m/%Y')
        except ValueError:
            dt = datetime.strptime(data_str, '%Y-%m-%d')
        data_iso = dt.strftime('%Y-%m-%d')
        _alvo.atualizar_alvo(lead_id, {'data_instalacao': data_iso}, telefone=cellphone)

        nsid = _alvo.descobrir_new_service_id(lead_id, cellphone)
        if nsid:
            _alvo.encerrar_fluxo_new_service(
                lead_id, nsid, telefone=cellphone,
                observacoes=f'Cliente concluiu coleta — data {data_str}',
            )
            _patch_status(cellphone, 'cliente_ativo')
            logger.info('NewService %s finalizado (lead=%s)', nsid, lead_id)
            return {'status': 'new_service_finalizado', 'data': data_str}
        resultado = robovendas.agendar_instalacao_ia(lead_id)
        logger.info('Agendamento IA lead=%s → %s', lead_id,
                    (resultado or {}).get('status'))
        return resultado
    except Exception as e:
        logger.exception('Falha agendar instalação lead=%s: %s', lead_id, e)
        return None
