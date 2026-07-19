"""Orquestrador da camada conversacional — usa os MÓDULOS PRÓPRIOS.

A partir da Fase 5, o /conv/turno NÃO chama mais validar_por_regra (o
bundle opaco validar+persistir+hooks que era o ponto de acoplamento com o
núcleo). Cada turno é montado com peças próprias:

  - memoria        → sabe QUAL pergunta o cliente está respondendo
  - extrator (IA)  → entende a mensagem (multi-campo, confirmação, dúvida)
  - planos         → resolve o plano por preço/velocidade ("99 reais")
  - validacao      → valida o passo reusando só os validadores PUROS
  - acoes          → dispara os hooks de negócio via serviços diretos
  - respostas      → mensagem específica por tipo de erro + escalonamento
  - motor          → decide o próximo passo da coleta (sequência própria)

Persistência via _alvo (serviço, roteia lead/NewService). A mensagem da
PRÓXIMA pergunta é montada pelo roteador determinístico
(onboarding.decidir_proximo_passo, read-only) — ele já gera as confirmações
dinâmicas (plano/endereço/resumo), o menu e os estados de finalizar/
transbordo, que não são "lógica de validação" e seria perigoso duplicar.

Resultado: bugs de validação/resposta/plano do conv se corrigem AQUI,
nunca mais editando engine.py / onboarding.py.

Tudo tolerante a falha: se um passo de IA falhar, cai no texto determinístico.
"""
from __future__ import annotations

import logging

from src.regras import regras_client
from src.integracoes import robovendas
from src import onboarding
from src.regras import alvo as _alvo

from src.conversacional.extrator import analisar_mensagem
from src.conversacional.faq import responder_e_emendar
from src.conversacional.humanizador import humanizar_pergunta
from src.conversacional import motor, validacao, respostas, planos, retomada
from src.conversacional.memoria import memoria

logger = logging.getLogger(__name__)

# Status em que o cliente está em COLETA de venda (lead novo). Só nesses o
# desvio de retomar/recomeçar faz sentido — cliente existente (cliente_ativo,
# menu, etc) é tratado pelo roteador determinístico.
_STATUS_COLETA = {'', 'lead_novo', 'em_andamento', 'processamento_manual', 'em_coleta'}


def _em_new_service(dados: dict) -> bool:
    return (dados.get('_alvo') == 'new_service'
            or (dados.get('status_api') or '') == 'em_fluxo_new_service')


def _primeiro_nome(dados: dict) -> str:
    nome = (dados.get('nome_razaosocial') or '').strip()
    if motor.nome_eh_generico(nome):
        return ''
    return nome.split(' ')[0] if nome else ''


def _resolver_qid_atual(
    telefone: str, question_id: str, dados: dict, em_ns: bool,
) -> str:
    """Decide com certeza qual pergunta o cliente está respondendo.

    Prioridade:
      1. question_id confiável vindo do Matrix
      2. última pergunta que NÓS fizemos (memória) — captura perguntas
         especiais (menu, finalizar) que não são campos da sequência
      3. inferência pelo próximo campo pendente (motor)
    """
    qid = (question_id or '').strip()
    if qid:
        return qid
    qid = memoria.ultima_pergunta(telefone)
    if qid:
        return qid
    return motor.proxima_pergunta_id(dados, em_ns)


def _carregar_dados(cellphone: str, lead_id: int | None) -> tuple[int | None, dict]:
    if not lead_id and cellphone:
        try:
            lead_id = robovendas.buscar_lead_por_telefone(cellphone)
        except Exception as e:
            logger.warning('Falha buscar lead por telefone %s: %s', cellphone, e)
    dados: dict = {}
    if lead_id:
        dados = _alvo.consultar_dados_alvo(lead_id, cellphone) or {}
    return lead_id, dados


def _tratar_correcao(cellphone, mensagem, campo, lead_id, dados, debug):
    """Cliente quer mudar um dado já informado.

    LIMPA o campo (pra o roteador re-perguntar) e devolve uma confirmação
    curta. No próximo turno de ROTEAR, o decidir_proximo_passo acha o campo
    vazio e pergunta de novo; a resposta seguinte sobrescreve.
    """
    from src.conversacional.fluxo import mapa_qid_para_campo
    campo_para_qid = {c: q for q, c in mapa_qid_para_campo().items()}
    qid = campo_para_qid.get(campo)
    if not qid:
        return None
    if lead_id:
        try:
            _alvo.atualizar_alvo(lead_id, {campo: ''}, telefone=cellphone)
            _alvo._ctx_patch_lead_cache(cellphone, {campo: ''})  # noqa: SLF001
            dados[campo] = ''
        except Exception as e:
            logger.warning('Falha limpar campo %s p/ correção: %s', campo, e)
    debug['passos'].append({'correcao': campo, 'qid_destino': qid})
    nome = _primeiro_nome(dados)
    base = 'Claro, sem problema! Vamos corrigir esse dado.'
    msg = humanizar_pergunta(base, primeiro_nome=nome,
                             contexto='cliente pediu pra corrigir um dado') or base
    return _montar_retorno(
        cellphone, mensagem, qid, msg, [],
        proxima_qid=qid, transbordo=False,
        valido=True, motivo='', analise={'intencao': 'corrigir'}, debug=debug,
    )


def _validar_passo(
    regra: dict, qid: str, mensagem: str, analise: dict,
) -> validacao.Resultado:
    """Valida o passo atual. Para escolha_plano, tenta resolver por preço."""
    if qid == 'escolha_plano':
        # 1) opção numérica direta (1/2) cai na validação normal de opção
        # 2) senão, tenta resolver o plano citado por preço/velocidade
        if not analise.get('opcao_numerica'):
            plano = planos.resolver_plano(mensagem)
            if plano:
                campo = regra.get('campo_lead_atualizar') or 'id_plano_rp'
                return validacao.Resultado(
                    True,
                    campos={campo: plano['id_plano_rp'],
                            'valor': plano['valor']},
                    extra={'plano': plano},
                )
    return validacao.validar(regra, mensagem, analise)


def processar_turno(
    cellphone: str,
    lead_id: int | None,
    mensagem: str,
    question_id: str = '',
    modo: str = 'validar',
) -> dict:
    """Processa um turno. DOIS modos, casando com o flow do Matrix:

    - 'rotear'  (api_proximo_passo): decide a PRÓXIMA pergunta/menu/transbordo.
      NÃO valida. Devolve a pergunta em `message`/`mensagem`.
    - 'validar' (api_validar): valida a RESPOSTA do cliente contra a pergunta
      atual. NÃO avança a pergunta (o rotear faz isso). Devolve resposta_correta
      + confirmação (sucesso) ou retorno_erro_api.
    """
    debug: dict = {'passos': [], 'modo': modo}
    lead_id, dados = _carregar_dados(cellphone, lead_id)
    em_ns = _em_new_service(dados)
    if modo == 'rotear':
        return _rotear(cellphone, lead_id, mensagem, dados, em_ns, debug)
    return _validar(cellphone, lead_id, mensagem, question_id, dados, em_ns, debug)


def _rotear(cellphone, lead_id, mensagem, dados, em_ns, debug):
    """Modo ROTEAR — decide o próximo passo. NÃO valida nada."""
    # Retomar/recomeçar: cliente voltou com progresso, na coleta de venda.
    status_atual = (dados.get('status_api') or '').strip()
    if (status_atual in _STATUS_COLETA and memoria.sessao_nova(cellphone)
            and not em_ns and retomada.tem_progresso(dados)):
        msg = retomada.montar_resumo(dados)
        return _montar_retorno(
            cellphone, mensagem, '', msg, [],
            proxima_qid='retomar_ou_recomecar', transbordo=False,
            valido=True, motivo='', analise={}, debug=debug,
        )

    proximo = onboarding.decidir_proximo_passo(
        telefone=cellphone, lead_id=lead_id, ultima_mensagem=mensagem,
    )
    proxima_qid = proximo.get('proxima_pergunta_id', '')
    transbordo = bool(proximo.get('deve_transbordar'))
    msg_base = (proximo.get('mensagem_inicial') or '').strip()
    proximo_passo = (proximo.get('proximo_passo') or '').strip()
    status_lead = (proximo.get('status_lead') or '').strip()
    encerrar = proximo_passo == 'red_encerrar'

    nome = _primeiro_nome(dados)
    if transbordo or encerrar:
        mensagem_final = msg_base or 'Um momento, vou te transferir pra um atendente.'
    else:
        mensagem_final = humanizar_pergunta(msg_base, primeiro_nome=nome) or msg_base

    return _montar_retorno(
        cellphone, mensagem, proxima_qid, mensagem_final, [],
        proxima_qid=proxima_qid, transbordo=transbordo, valido=True,
        motivo='', analise={}, debug=debug, proximo_passo=proximo_passo,
        status_lead=status_lead, encerrar=encerrar,
        is_cliente=(status_lead == 'cliente_ativo'),
    )


def _validar_upgrade(cellphone, lead_id, mensagem, debug):
    """Fluxo de UPGRADE: a pergunta é dinâmica (servida pelo Django), então a
    resposta é submetida ao turno_upgrade em vez de validar_por_regra."""
    from src.integracoes.robovendas import robovendas
    resp = robovendas.turno_upgrade(lead_id, mensagem or '')
    valido = bool((resp or {}).get('valido'))
    erro = (resp or {}).get('erro') or ''
    msg = ((resp or {}).get('mensagem_pos') or '') if valido \
        else (erro or 'Não entendi sua escolha. Pode repetir?')
    return _montar_retorno(
        cellphone, mensagem, 'upgrade_turno', msg, [],
        proxima_qid='upgrade_turno', transbordo=False, valido=valido,
        motivo='' if valido else (erro or 'resposta não reconhecida'),
        analise={}, debug=debug,
    )


def _validar(cellphone, lead_id, mensagem, question_id, dados, em_ns, debug):
    """Modo VALIDAR — valida a resposta atual. NÃO avança a pergunta."""
    # Fluxo de upgrade conduzido pelo Django (pergunta dinâmica) → delega.
    status_api = (dados.get('status_api') or '').strip()
    if lead_id and (status_api == 'em_fluxo_upgrade'
                    or (question_id or '').startswith('upgrade_')):
        return _validar_upgrade(cellphone, lead_id, mensagem, debug)
    qid_atual = _resolver_qid_atual(cellphone, question_id, dados, em_ns)
    regra_atual = regras_client.obter_por_id(qid_atual) if qid_atual else None
    pergunta_txt = (regra_atual or {}).get('pergunta_padrao', '')
    campo_atual = (regra_atual or {}).get('campo_lead_atualizar', '')

    analise = analisar_mensagem(
        mensagem, campo_atual=campo_atual, pergunta_atual=pergunta_txt,
    )
    debug['passos'].append({'qid_atual': qid_atual, 'analise': analise})

    intencao = analise.get('intencao') or 'outro'
    parece_resposta = bool(
        analise.get('opcao_numerica') or analise.get('confirmacao')
        or analise.get('campos') or intencao in ('responder', 'ambos')
    )
    nome = _primeiro_nome(dados)

    # ── Conversa livre: corrigir ou perguntar ────────────────────────
    if not parece_resposta and lead_id:
        alvo_corrigir = analise.get('campo_corrigir')
        if alvo_corrigir:
            resp = _tratar_correcao(cellphone, mensagem, alvo_corrigir,
                                    lead_id, dados, debug)
            if resp is not None:
                return resp
        if (intencao == 'perguntar' or analise.get('tem_pergunta')) and regra_atual:
            duvida = analise.get('pergunta_texto') or mensagem
            resp_faq = responder_e_emendar(duvida, pergunta_txt, primeiro_nome=nome)
            msg = resp_faq or 'Pode me enviar essa informação, por favor?'
            return _montar_retorno(
                cellphone, mensagem, qid_atual, msg, [],
                proxima_qid=qid_atual, transbordo=False, valido=True,
                motivo='', analise=analise, debug=debug, tem_pergunta=True,
            )

    # Saudação ou sem pergunta atual → nada a validar (sucesso silencioso;
    # quem mostra a pergunta é o ROTEAR).
    if intencao == 'saudacao' or not (qid_atual and regra_atual):
        return _montar_retorno(
            cellphone, mensagem, qid_atual, '', [],
            proxima_qid=qid_atual, transbordo=False, valido=True,
            motivo='', analise=analise, debug=debug,
        )

    # ── Valida + persiste ────────────────────────────────────────────
    resultado = _validar_passo(regra_atual, qid_atual, mensagem, analise)
    if resultado.valido:
        memoria.resetar_tentativa(cellphone, qid_atual)
        campos_salvos: list[str] = []
        if resultado.campos and lead_id:
            try:
                _alvo.atualizar_alvo(lead_id, resultado.campos, telefone=cellphone)
                _alvo._ctx_patch_lead_cache(cellphone, resultado.campos)  # noqa: SLF001
                dados.update(resultado.campos)
                campos_salvos = list(resultado.campos.keys())
            except Exception as e:
                logger.warning('Falha persistir %s: %s', resultado.campos, e)
        try:
            acoes_disparar(
                qid_atual, regra_atual, lead_id=lead_id, cellphone=cellphone,
                resultado=resultado, analise=analise, em_new_service=em_ns,
            )
        except Exception as e:
            logger.warning('Falha hooks %s: %s', qid_atual, e)
        # Sucesso → confirmação (msg_sucesso). A próxima pergunta vem do ROTEAR.
        extracted = next((str(v) for v in (resultado.campos or {}).values()), '')
        msg_ok = respostas.mensagem_sucesso(regra_atual, extracted=extracted)
        return _montar_retorno(
            cellphone, mensagem, qid_atual, msg_ok, campos_salvos,
            proxima_qid=qid_atual, transbordo=False, valido=True,
            motivo='', analise=analise, debug=debug,
        )

    # ── Inválido ─────────────────────────────────────────────────────
    # Se o cliente fez uma pergunta junto, responde em vez de só errar.
    if analise.get('tem_pergunta') and analise.get('pergunta_texto'):
        resp_faq = responder_e_emendar(
            analise['pergunta_texto'], pergunta_txt, primeiro_nome=nome)
        if resp_faq:
            return _montar_retorno(
                cellphone, mensagem, qid_atual, resp_faq, [],
                proxima_qid=qid_atual, transbordo=False, valido=True,
                motivo='', analise=analise, debug=debug, tem_pergunta=True,
            )
    tentativa = memoria.incrementar_tentativa(cellphone, qid_atual)
    if respostas.deve_transbordar(regra_atual, tentativa):
        return _montar_retorno(
            cellphone, mensagem, qid_atual,
            respostas.mensagem_max_tentativas(regra_atual), [],
            proxima_qid=qid_atual, transbordo=True, valido=False,
            motivo=resultado.motivo, analise=analise, debug=debug,
        )
    erro_msg = respostas.mensagem_erro(regra_atual, resultado.motivo, tentativa=tentativa)
    return _montar_retorno(
        cellphone, mensagem, qid_atual, erro_msg, [],
        proxima_qid=qid_atual, transbordo=False, valido=False,
        motivo=resultado.motivo, analise=analise, debug=debug,
    )


def acoes_disparar(qid, regra, **kw):
    """Indireção pra facilitar mock em teste."""
    from src.conversacional import acoes
    return acoes.disparar_hooks(qid, regra, **kw)


def _persistir_extras(analise, campo_atual, lead_id, cellphone, dados, campos_salvos):
    """Valida+salva campos que o cliente adiantou fora da etapa atual."""
    from src.conversacional.fluxo import mapa_qid_para_campo
    # mapa campo→qid (inverte qid→campo das duas sequências)
    campo_para_qid = {c: q for q, c in mapa_qid_para_campo().items()}
    for campo, valor in (analise.get('campos') or {}).items():
        if campo == campo_atual or valor in (None, '', []):
            continue
        qid = campo_para_qid.get(campo)
        if not qid:
            continue
        regra_extra = regras_client.obter_por_id(qid)
        if not regra_extra:
            continue
        try:
            res = validacao.validar(regra_extra, str(valor), {})
            if res.valido and res.campos and lead_id:
                _alvo.atualizar_alvo(lead_id, res.campos, telefone=cellphone)
                _alvo._ctx_patch_lead_cache(cellphone, res.campos)  # noqa: SLF001
                dados.update(res.campos)
                campos_salvos.extend(res.campos.keys())
        except Exception as e:
            logger.warning('Falha campo extra %s=%s: %s', campo, valor, e)


def _montar_retorno(
    cellphone, mensagem_cliente, qid_atual, mensagem_final, campos_salvos,
    *, proxima_qid, transbordo, valido, motivo, analise, debug,
    tem_pergunta=False, proximo_passo='', status_lead='',
    encerrar=False, is_cliente=False,
):
    """Monta o dict de retorno + atualiza a memória da conversa."""
    # Lembra qual pergunta estamos fazendo agora (define o que o cliente
    # responde no próximo turno) + registra o turno no histórico.
    try:
        memoria.set_ultima_pergunta(cellphone, proxima_qid or '')
        memoria.registrar_turno(cellphone, mensagem_cliente, mensagem_final,
                                pergunta_id=qid_atual)
        memoria.marcar_sessao_iniciada(cellphone)
    except Exception as e:
        logger.debug('Falha atualizar memória: %s', e)

    return {
        'valido': valido,
        'mensagem': mensagem_final,
        'campos_salvos': campos_salvos,
        'proxima_pergunta_id': proxima_qid,
        'transbordo': transbordo,
        'tem_pergunta_cliente': bool(tem_pergunta),
        'motivo_invalido': motivo,
        'usou_ia': True,
        'qid_atual': qid_atual,
        'analise': analise,
        'debug': debug,
        # Campos de roteamento pro flow do Matrix (mapeados em rotas.py)
        'proximo_passo': proximo_passo,
        'status_lead': status_lead,
        'encerrar': bool(encerrar),
        'is_cliente': bool(is_cliente),
    }
