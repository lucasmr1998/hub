"""Endpoint conversacional do FLUXO DE UPGRADE — turno a turno.

Encapsula TODA a lógica do fluxo de upgrade (FluxoAtendimento
tipo_fluxo='upgrade') num único endpoint que o serviço FastAPI
`ia_validacao` consome para conduzir o cliente quando ele escolhe
"2) Fazer upgrade de plano" no menu vivo (/ia/proximo-passo + /ia/validar).

Contrato — POST /api/upgrade-conversa/turno/
  body: {"lead_id": <int>, "mensagem": <str opcional>}

  Dois modos (espelha o padrão new_service: /validar grava, /proximo-passo mostra):
    • SEM mensagem  → modo "mostrar": devolve a pergunta atual (renderizada
                      com as opções dinâmicas). Se a pergunta atual for a de
                      encerramento ('fim'), FINALIZA o atendimento aqui
                      (status='completado' → signal cria UpgradePlano).
    • COM mensagem  → modo "responder": registra a resposta na pergunta atual,
                      avança o ponteiro e devolve {valido}. NÃO finaliza —
                      o encerramento acontece no próximo "mostrar".

  resposta JSON:
    {
      atendimento_id, status, valido, finalizado, sem_opcoes,
      pergunta_id,     # 'upgrade_turno' enquanto há pergunta
      indice,          # índice da questão atual
      mensagem,        # texto pronto (título + opções numeradas)
      erro,            # msg de validação quando resposta inválida
      mensagem_final,  # texto de encerramento (quando finalizado)
      upgrade_id       # id do UpgradePlano criado (quando finalizado)
    }
"""
import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

# Aceita afirmação/negação em linguagem natural pras questões sim/não.
_AFIRMATIVAS = {'sim', 's', 'quero', 'isso', 'pode', 'claro', 'aceito',
                'confirmo', 'ok', 'okay', 'positivo', 'yes', 'y', 'bora', 'vamos'}
_NEGATIVAS = {'nao', 'não', 'n', 'negativo', 'no', 'agora nao', 'agora não'}


def _role(questao):
    vc = getattr(questao, 'variaveis_contexto', None) or {}
    return vc.get('upgrade_role') if isinstance(vc, dict) else None


def _render_opcoes(questao, contexto):
    """Lista [{valor, texto}] das opções dinâmicas (ou [] se não houver)."""
    if not getattr(questao, 'opcoes_dinamicas_fonte', None):
        return []
    try:
        ops = questao.get_opcoes_formatadas(contexto) or []
    except Exception:
        logger.exception('Falha renderizar opções dinâmicas da questão %s', questao.pk)
        return []
    return [{'valor': str(o.get('valor')), 'texto': o.get('texto', '')} for o in ops]


def _montar_mensagem(questao, opcoes):
    """Título + opções numeradas (1, 2, 3...) prontas pro WhatsApp."""
    txt = questao.titulo or ''
    if opcoes:
        linhas = [f'{i}) {op["texto"]}' for i, op in enumerate(opcoes, 1)]
        txt = f'{txt}\n\n' + '\n'.join(linhas)
    return txt


def _mapear_resposta(mensagem, questao, opcoes):
    """Converte o que o cliente digitou no VALOR esperado pela questão.

    - Opções dinâmicas: aceita índice 1-based ("1"), o valor exato, ou texto.
    - sim/não: aceita linguagem natural e índice.
    Devolve a string a submeter (se não casar, devolve a original → o
    validador rejeita e a pergunta se repete).
    """
    m = (mensagem or '').strip()
    ml = m.lower()

    if opcoes:
        if m.isdigit():
            i = int(m)
            if 1 <= i <= len(opcoes):
                return opcoes[i - 1]['valor']
        for op in opcoes:
            if str(op['valor']).lower() == ml:
                return op['valor']
        for op in opcoes:
            if ml and ml in (op['texto'] or '').lower():
                return op['valor']
        return m

    estaticas = getattr(questao, 'opcoes_resposta', None) or []
    if estaticas:
        if m.isdigit():
            i = int(m)
            if 1 <= i <= len(estaticas):
                return estaticas[i - 1]
        if ml in _AFIRMATIVAS and 'sim' in estaticas:
            return 'sim'
        if ml in _NEGATIVAS and 'nao' in estaticas:
            return 'nao'
    return m


def _resp_json(atendimento, *, valido=True, finalizado=False, sem_opcoes=False,
               pergunta_id='', indice=None, mensagem='', erro=None,
               mensagem_final='', mensagem_pos='', upgrade_id=None):
    return JsonResponse({
        'atendimento_id': atendimento.id if atendimento else None,
        'status': atendimento.status if atendimento else None,
        'valido': valido,
        'finalizado': finalizado,
        'sem_opcoes': sem_opcoes,
        'pergunta_id': pergunta_id,
        'indice': indice,
        'mensagem': mensagem,
        'erro': erro or '',
        'mensagem_final': mensagem_final,
        # Mensagem a exibir JUNTO do feedback de uma resposta válida (ex.: a
        # mensagem de sucesso quando a confirmação leva ao encerramento) —
        # garante que o cliente a veja antes do nó de encerramento do Matrix.
        'mensagem_pos': mensagem_pos,
        'upgrade_id': upgrade_id,
    })


@csrf_exempt
@require_http_methods(["POST"])
def turno_upgrade_conversa(request):
    from .models import FluxoAtendimento, AtendimentoFluxo, UpgradePlano
    from .services.upgrade_plano_service import enriquecer_contexto_upgrade

    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    lead_id = data.get('lead_id')
    mensagem = (data.get('mensagem') or '').strip()
    if not lead_id:
        return JsonResponse({'error': 'lead_id é obrigatório'}, status=400)

    fluxo = (FluxoAtendimento.objects
             .filter(tipo_fluxo='upgrade', ativo=True)
             .order_by('id').first())
    if not fluxo:
        return JsonResponse({'error': 'Fluxo de upgrade não configurado'}, status=404)

    # Atendimento ativo do lead nesse fluxo, ou cria um novo.
    atendimento = (AtendimentoFluxo.objects
                   .filter(lead_id=lead_id, fluxo=fluxo,
                           status__in=['iniciado', 'em_andamento'])
                   .order_by('-id').first())
    criado = False
    if not atendimento:
        atendimento = AtendimentoFluxo.objects.create(
            fluxo=fluxo, lead_id=lead_id, status='iniciado',
            total_questoes=fluxo.get_total_questoes() or 5,
            questao_atual=1, max_tentativas=fluxo.max_tentativas,
        )
        criado = True

    idx = atendimento.questao_atual or 1
    questao = fluxo.get_questao_por_indice(idx)
    if not questao:
        return JsonResponse({'error': 'Questão atual não encontrada'}, status=500)

    erro = None
    valido = True

    # ── MODO RESPONDER ────────────────────────────────────────────────
    # Só consome a mensagem como resposta se o atendimento já existia
    # (a pergunta atual já foi mostrada numa volta anterior).
    if mensagem and not criado:
        contexto = enriquecer_contexto_upgrade(atendimento, {})
        opcoes = _render_opcoes(questao, contexto)
        valor = _mapear_resposta(mensagem, questao, opcoes)
        sucesso, msg, acao, extras = atendimento.responder_questao_inteligente(
            indice_questao=idx, resposta=valor, contexto=contexto)
        valido = bool(sucesso)
        if sucesso:
            prox = extras.get('proxima_questao')
            if acao == 'finalizar_fluxo' or not prox:
                # Não há próxima — fica no índice atual; o "mostrar" finaliza.
                pass
            else:
                idx = prox.indice
                atendimento.questao_atual = idx
                atendimento.save(update_fields=['questao_atual'])
            questao = fluxo.get_questao_por_indice(idx)
            # Se a resposta levou à questão de encerramento ('fim'), já devolve
            # a mensagem de sucesso aqui — assim o cliente a vê como feedback da
            # confirmação, antes de o Matrix fechar o atendimento.
            mensagem_pos = questao.titulo if (questao and _role(questao) == 'fim') else ''
            # NÃO finaliza aqui — devolve só o resultado da submissão.
            return _resp_json(atendimento, valido=True, finalizado=False,
                              pergunta_id='upgrade_turno', indice=idx, mensagem='',
                              mensagem_pos=mensagem_pos)
        else:
            erro = msg  # repete a mesma pergunta com o aviso de erro

    # ── MODO MOSTRAR (e finalização) ──────────────────────────────────
    # Encerramento: questão 'fim' → finaliza o atendimento (dispara signal).
    if _role(questao) == 'fim':
        if atendimento.status in ('iniciado', 'em_andamento'):
            atendimento.status = 'completado'
            atendimento.data_conclusao = timezone.now()
            atendimento.save()  # post_save → cria UpgradePlano (se confirmado)
        upg = (UpgradePlano.objects
               .filter(lead_id=lead_id,
                       observacoes__contains=f'atendimento={atendimento.pk}')
               .order_by('-id').first())
        return _resp_json(atendimento, valido=valido, finalizado=True,
                          indice=questao.indice,
                          mensagem_final=questao.titulo or '',
                          upgrade_id=(upg.id if upg else None))

    contexto = enriquecer_contexto_upgrade(atendimento, {})
    opcoes = _render_opcoes(questao, contexto)

    # Questão de escolha dinâmica sem nenhuma opção → não dá pra seguir.
    if _role(questao) in ('servico', 'plano') and not opcoes:
        return _resp_json(atendimento, valido=False, sem_opcoes=True,
                          pergunta_id='upgrade_turno', indice=questao.indice,
                          mensagem=('Não encontrei opções disponíveis pra esse '
                                    'passo do upgrade agora.'))

    texto = _montar_mensagem(questao, opcoes)
    if erro:
        texto = f'{erro}\n\n{texto}'
    return _resp_json(atendimento, valido=valido, finalizado=False,
                      pergunta_id='upgrade_turno', indice=questao.indice,
                      mensagem=texto, erro=erro)
