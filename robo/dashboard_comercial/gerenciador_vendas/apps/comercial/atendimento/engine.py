"""
Engine de fluxos visuais de atendimento (node-based).

Diferenca fundamental das automacoes: atendimento e CONVERSACIONAL.
A execucao PAUSA em nos 'questao' esperando resposta do lead via N8N/WhatsApp.

Retorno padrao:
{
    'tipo': 'questao' | 'finalizado' | 'delay' | 'erro',
    'questao': { ... },       # se tipo == 'questao'
    'resultado': { ... },     # se tipo == 'finalizado'
    'mensagem': '...',
}
"""
import logging
from datetime import timedelta

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============================================================================
# DESPACHO POR CANAL
# ============================================================================

def buscar_fluxo_por_canal(canal, tenant=None):
    """Busca o fluxo ativo para um canal especifico.
    Prioridade: fluxo do canal exato > fluxo 'qualquer' > None
    """
    from .models import FluxoAtendimento

    qs = FluxoAtendimento.objects.filter(ativo=True, status='ativo')
    if tenant:
        qs = qs.filter(tenant=tenant)

    # Primeiro tenta fluxo especifico do canal
    fluxo = qs.filter(canal=canal).first()
    if fluxo:
        return fluxo

    # Fallback para 'qualquer'
    fluxo = qs.filter(canal='qualquer').first()
    return fluxo


def iniciar_por_canal(lead, canal, tenant=None):
    """Inicia um atendimento automaticamente baseado no canal do lead.
    Retorna (atendimento, resultado) ou (None, erro).
    """
    from .models import FluxoAtendimento, AtendimentoFluxo

    if tenant is None and hasattr(lead, 'tenant'):
        tenant = lead.tenant

    fluxo = buscar_fluxo_por_canal(canal, tenant)
    if not fluxo:
        return None, {'tipo': 'erro', 'mensagem': f'Nenhum fluxo ativo para o canal {canal}'}

    if not fluxo.pode_ser_usado():
        return None, {'tipo': 'erro', 'mensagem': f'Fluxo "{fluxo.nome}" nao pode ser usado'}

    # Verificar se ja tem atendimento ativo para este lead neste fluxo
    ativo = AtendimentoFluxo.objects.filter(
        lead=lead, fluxo=fluxo,
        status__in=['iniciado', 'em_andamento', 'pausado']
    ).first()
    if ativo:
        return ativo, {'tipo': 'em_andamento', 'mensagem': 'Atendimento ja em andamento', 'atendimento_id': ativo.id}

    # Criar atendimento
    total_q = fluxo.nodos.filter(tipo='questao').count() if fluxo.modo_fluxo else fluxo.get_total_questoes()
    atendimento = AtendimentoFluxo.objects.create(
        tenant=tenant,
        lead=lead,
        fluxo=fluxo,
        total_questoes=total_q,
        max_tentativas=fluxo.max_tentativas,
    )

    if fluxo.modo_fluxo:
        resultado = iniciar_fluxo_visual(atendimento)
    else:
        primeira = fluxo.get_questao_por_indice(1)
        resultado = {
            'tipo': 'questao',
            'questao': {
                'indice': 1,
                'titulo': primeira.titulo if primeira else '',
            },
        }

    return atendimento, resultado


# ============================================================================
# PONTO DE ENTRADA
# ============================================================================

def iniciar_fluxo_visual(atendimento):
    """Inicia um fluxo visual: encontra o nodo 'entrada' e percorre ate a primeira questao."""
    fluxo = atendimento.fluxo
    nodo_entrada = fluxo.nodos.filter(tipo='entrada').first()

    if not nodo_entrada:
        return {'tipo': 'erro', 'mensagem': 'Fluxo sem nodo de entrada'}

    contexto = _construir_contexto(atendimento)
    return _percorrer_a_partir_de(atendimento, nodo_entrada, contexto)


def processar_resposta_visual(atendimento, resposta):
    """Processa a resposta do lead no nodo atual e avanca no fluxo."""
    nodo_atual = atendimento.nodo_atual
    if not nodo_atual or nodo_atual.tipo != 'questao':
        return {'tipo': 'erro', 'mensagem': 'Nenhuma questao pendente'}

    contexto = _construir_contexto(atendimento)

    # Registrar log de resposta recebida
    _registrar_log(atendimento, nodo_atual, 'sucesso',
                   f'Resposta recebida: {str(resposta)[:100]}',
                   dados={'resposta': str(resposta)[:500]})

    # Validar resposta
    config = nodo_atual.configuracao
    valida, msg_erro = _validar_resposta_questao(config, resposta)

    if not valida:
        return {
            'tipo': 'questao',
            'questao': _montar_dados_questao(nodo_atual),
            'erro': msg_erro,
            'mensagem': msg_erro,
        }

    # Salvar resposta no atendimento
    nodo_key = str(nodo_atual.id)
    dados = atendimento.dados_respostas or {}
    dados[nodo_key] = {
        'resposta': resposta,
        'data_resposta': timezone.now().isoformat(),
        'valida': True,
        'nodo_tipo': nodo_atual.subtipo,
        'titulo': config.get('titulo', ''),
    }
    atendimento.dados_respostas = dados
    atendimento.questoes_respondidas += 1

    # Adicionar resposta ao contexto
    contexto[f'resposta_nodo_{nodo_atual.id}'] = resposta
    contexto['ultima_resposta'] = resposta

    # Seguir conexoes a partir do nodo questao
    return _seguir_conexoes(atendimento, nodo_atual, contexto)


def executar_pendentes_atendimento(tenant=None):
    """Executa delays pendentes (chamado por cron)."""
    from .models import ExecucaoFluxoAtendimento

    agora = timezone.now()
    qs = ExecucaoFluxoAtendimento.all_tenants.filter(
        status='pendente', data_agendada__lte=agora
    )
    if tenant:
        qs = qs.filter(tenant=tenant)

    count = 0
    for pendente in qs.select_related('atendimento', 'atendimento__fluxo', 'nodo'):
        try:
            atendimento = pendente.atendimento
            contexto = pendente.contexto_json or {}
            contexto.update(_construir_contexto(atendimento))

            # Retomar a partir das saidas do nodo de delay
            if pendente.nodo:
                _seguir_conexoes(atendimento, pendente.nodo, contexto)

            pendente.status = 'executado'
            pendente.data_execucao = agora
            pendente.save(update_fields=['status', 'data_execucao'])
            count += 1
        except Exception as e:
            pendente.status = 'erro'
            pendente.resultado = str(e)[:500]
            pendente.save(update_fields=['status', 'resultado'])
            logger.error(f'Atendimento engine: erro pendente {pendente.pk}: {e}')

    return count


# ============================================================================
# TRAVERSAL DO GRAFO
# ============================================================================

def _percorrer_a_partir_de(atendimento, nodo, contexto):
    """Percorre o grafo a partir de um nodo. Retorna quando encontra questao, delay ou fim."""
    resultado = _executar_nodo(atendimento, nodo, contexto)
    if resultado:
        return resultado

    # Nodo foi executado (entrada, acao, condicao), seguir conexoes
    return _seguir_conexoes(atendimento, nodo, contexto)


def _seguir_conexoes(atendimento, nodo, contexto):
    """Segue as conexoes de saida de um nodo."""
    # Para condicoes, o branch ja foi tratado em _executar_nodo
    if nodo.tipo == 'condicao':
        resultado_cond = _avaliar_condicao(nodo, contexto)
        branch = 'true' if resultado_cond else 'false'
        config = nodo.configuracao
        _registrar_log(atendimento, nodo, 'sucesso',
                       f'Condicao: {config.get("campo", "")} {config.get("operador", "")} {config.get("valor", "")} → {branch}',
                       dados={'branch': branch, 'resultado': resultado_cond})
        conexoes = nodo.saidas.filter(tipo_saida=branch).select_related('nodo_destino')
    else:
        conexoes = nodo.saidas.filter(tipo_saida='default').select_related('nodo_destino')

    for conexao in conexoes:
        resultado = _percorrer_a_partir_de(atendimento, conexao.nodo_destino, contexto)
        if resultado:
            return resultado

    # Sem mais conexoes, fluxo terminou sem nodo de finalizacao
    return {'tipo': 'finalizado', 'resultado': {'score': None}, 'mensagem': 'Fluxo concluido'}


def _executar_nodo(atendimento, nodo, contexto):
    """
    Executa um nodo. Retorna dict se deve PAUSAR (questao, delay, finalizacao).
    Retorna None se deve continuar percorrendo (entrada, acao, condicao).
    """
    if nodo.tipo == 'entrada':
        _registrar_log(atendimento, nodo, 'sucesso', 'Fluxo iniciado')
        return None  # Passa direto

    elif nodo.tipo == 'questao':
        # PAUSA: retorna dados da questao para o lead responder
        atendimento.nodo_atual = nodo
        atendimento.save(update_fields=['nodo_atual', 'dados_respostas', 'questoes_respondidas'])
        titulo = nodo.configuracao.get('titulo', 'Responda:')
        _registrar_log(atendimento, nodo, 'aguardando', f'Pergunta: {titulo}')
        return {
            'tipo': 'questao',
            'questao': _montar_dados_questao(nodo),
            'mensagem': titulo,
        }

    elif nodo.tipo == 'condicao':
        return None  # Avaliacao e log acontecem em _seguir_conexoes

    elif nodo.tipo == 'acao':
        try:
            _executar_acao(nodo, contexto, atendimento)
            _registrar_log(atendimento, nodo, 'sucesso', f'Acao executada: {nodo.subtipo}')
        except Exception as e:
            _registrar_log(atendimento, nodo, 'erro', f'Erro na acao {nodo.subtipo}: {e}')
            logger.error(f'Erro acao nodo {nodo.pk}: {e}')
        return None  # Continua

    elif nodo.tipo == 'delay':
        # PAUSA: agenda execucao futura
        from .models import ExecucaoFluxoAtendimento
        config = nodo.configuracao
        delay = _calcular_delay(config)
        data_agendada = timezone.now() + delay

        ExecucaoFluxoAtendimento.objects.create(
            tenant=atendimento.fluxo.tenant,
            atendimento=atendimento,
            nodo=nodo,
            contexto_json=_serializar_contexto(contexto),
            data_agendada=data_agendada,
        )
        atendimento.nodo_atual = nodo
        atendimento.save(update_fields=['nodo_atual'])
        _registrar_log(atendimento, nodo, 'agendado',
                       f'Delay: {config.get("valor", 0)} {config.get("unidade", "minutos")}')
        return {
            'tipo': 'delay',
            'mensagem': f'Aguardando {config.get("valor", 0)} {config.get("unidade", "minutos")}',
        }

    elif nodo.tipo == 'finalizacao':
        # PAUSA: finaliza o atendimento
        config = nodo.configuracao
        score = config.get('score', None)

        atendimento.status = 'completado'
        atendimento.data_conclusao = timezone.now()
        if atendimento.data_inicio:
            atendimento.tempo_total = int((timezone.now() - atendimento.data_inicio).total_seconds())
        if score:
            atendimento.score_qualificacao = int(score)
        atendimento.nodo_atual = None
        atendimento.save()

        # Atualizar lead se tiver score
        if score and atendimento.lead:
            atendimento.lead.score_qualificacao = int(score)
            atendimento.lead.save(update_fields=['score_qualificacao'])

        _registrar_log(atendimento, nodo, 'sucesso',
                       f'Fluxo finalizado. Score: {score or "N/A"}',
                       dados={'score': score, 'tempo_total': atendimento.tempo_total})

        return {
            'tipo': 'finalizado',
            'resultado': {
                'score': score,
                'dados_respostas': atendimento.dados_respostas,
                'tempo_total': atendimento.tempo_total,
            },
            'mensagem': config.get('mensagem_final', 'Atendimento finalizado'),
        }

    return None


# ============================================================================
# CONDICAO
# ============================================================================

def _avaliar_condicao(nodo, contexto):
    """Avalia condicao de um nodo. Mesma logica das automacoes."""
    config = nodo.configuracao
    campo = config.get('campo', '')
    operador = config.get('operador', 'igual')
    valor = config.get('valor', '')

    if not campo:
        return True

    valor_campo = _resolver_campo_contexto(campo, contexto)
    if valor_campo is None:
        return False

    try:
        vc = float(str(valor_campo))
        ve = float(str(valor))
    except (ValueError, TypeError):
        vc = str(valor_campo).lower()
        ve = str(valor).lower()

    comparadores = {
        'igual': lambda a, b: a == b,
        'diferente': lambda a, b: a != b,
        'contem': lambda a, b: str(b) in str(a),
        'maior': lambda a, b: a > b,
        'menor': lambda a, b: a < b,
        'maior_igual': lambda a, b: a >= b,
        'menor_igual': lambda a, b: a <= b,
    }
    return comparadores.get(operador, lambda a, b: False)(vc, ve)


def _resolver_campo_contexto(campo, contexto):
    """Resolve campo.subcampo no contexto (dot notation)."""
    partes = campo.split('.')
    obj = contexto
    for parte in partes:
        if isinstance(obj, dict):
            obj = obj.get(parte)
        elif hasattr(obj, parte):
            obj = getattr(obj, parte)
        else:
            flat_key = campo.replace('.', '_')
            return contexto.get(flat_key)
    return obj


# ============================================================================
# ACAO
# ============================================================================

def _executar_acao(nodo, contexto, atendimento):
    """Executa um nodo de acao."""
    subtipo = nodo.subtipo
    config = nodo.configuracao
    template = config.get('template', '')

    if subtipo == 'webhook':
        _acao_webhook(config, contexto)
    elif subtipo == 'enviar_whatsapp':
        _acao_enviar_whatsapp(config, contexto, atendimento)
    elif subtipo == 'enviar_email':
        _acao_enviar_email(config, contexto, atendimento)
    elif subtipo == 'notificacao_sistema':
        _acao_notificacao(config, contexto, atendimento)
    elif subtipo == 'criar_tarefa':
        _acao_criar_tarefa(config, contexto, atendimento)
    elif subtipo == 'mover_estagio':
        _acao_mover_estagio(config, contexto, atendimento)
    else:
        logger.warning(f'Atendimento engine: subtipo de acao desconhecido: {subtipo}')


def _acao_webhook(config, contexto):
    """Chama um webhook externo."""
    url = config.get('url', '')
    metodo = config.get('metodo', 'POST').upper()
    if not url:
        return

    payload = {}
    for k, v in contexto.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            payload[k] = v

    try:
        if metodo == 'GET':
            requests.get(url, params=payload, timeout=10)
        else:
            requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f'Webhook erro: {e}')


def _acao_enviar_whatsapp(config, contexto, atendimento):
    """Envia WhatsApp via N8N webhook."""
    import os
    webhook_url = config.get('webhook_url', os.environ.get('N8N_WEBHOOK_WHATSAPP', ''))
    template = config.get('template', '')
    if not webhook_url or not template:
        return

    mensagem = _substituir_variaveis(template, contexto)
    telefone = ''
    if atendimento.lead:
        telefone = atendimento.lead.telefone

    try:
        requests.post(webhook_url, json={
            'telefone': telefone,
            'mensagem': mensagem,
        }, timeout=10)
    except Exception as e:
        logger.error(f'WhatsApp erro: {e}')


def _acao_enviar_email(config, contexto, atendimento):
    """Envia email (placeholder)."""
    logger.info(f'Email acao: {config.get("template", "")[:100]}')


def _acao_notificacao(config, contexto, atendimento):
    """Cria notificacao no sistema."""
    try:
        from apps.notificacoes.models import Notificacao
        mensagem = _substituir_variaveis(config.get('template', ''), contexto)
        Notificacao.objects.create(
            tenant=atendimento.fluxo.tenant,
            titulo=config.get('titulo', 'Notificacao do fluxo'),
            mensagem=mensagem[:500],
            tipo='info',
        )
    except Exception as e:
        logger.error(f'Notificacao erro: {e}')


def _acao_criar_tarefa(config, contexto, atendimento):
    """Cria tarefa no CRM."""
    try:
        from apps.comercial.crm.models import TarefaCRM
        titulo = _substituir_variaveis(config.get('titulo', 'Tarefa do fluxo'), contexto)
        TarefaCRM.objects.create(
            tenant=atendimento.fluxo.tenant,
            titulo=titulo,
            tipo=config.get('tipo_tarefa', 'ligacao'),
            prioridade=config.get('prioridade', 'media'),
            lead=atendimento.lead,
        )
    except Exception as e:
        logger.error(f'Criar tarefa erro: {e}')


def _acao_mover_estagio(config, contexto, atendimento):
    """Move oportunidade de estagio no CRM."""
    try:
        from apps.comercial.crm.models import OportunidadeVenda
        estagio_slug = config.get('estagio', '')
        if not estagio_slug or not atendimento.lead:
            return
        OportunidadeVenda.objects.filter(
            lead=atendimento.lead
        ).update(estagio=estagio_slug)
    except Exception as e:
        logger.error(f'Mover estagio erro: {e}')


# ============================================================================
# QUESTAO
# ============================================================================

def _montar_dados_questao(nodo):
    """Monta dict com dados da questao para retornar na API."""
    config = nodo.configuracao
    return {
        'nodo_id': nodo.id,
        'titulo': config.get('titulo', ''),
        'descricao': config.get('descricao', ''),
        'tipo_questao': nodo.subtipo or 'texto',
        'opcoes_resposta': config.get('opcoes_resposta', []),
        'obrigatoria': config.get('obrigatoria', True),
        'placeholder': config.get('placeholder', ''),
        'max_tentativas': config.get('max_tentativas', 3),
    }


def _validar_resposta_questao(config, resposta):
    """Valida resposta de uma questao. Retorna (valida, mensagem_erro)."""
    obrigatoria = config.get('obrigatoria', True)

    if obrigatoria and not str(resposta).strip():
        return False, config.get('mensagem_erro', 'Resposta obrigatoria')

    opcoes = config.get('opcoes_resposta', [])
    if opcoes and str(resposta).strip() not in [str(o) for o in opcoes]:
        # Verificar se e indice
        try:
            idx = int(resposta)
            if 0 <= idx < len(opcoes):
                return True, None
        except (ValueError, TypeError):
            pass
        return False, config.get('mensagem_erro', 'Opcao invalida')

    return True, None


# ============================================================================
# UTILS
# ============================================================================

def _construir_contexto(atendimento):
    """Constroi contexto com dados do lead e atendimento."""
    contexto = {
        'atendimento_id': atendimento.id,
        'fluxo_id': atendimento.fluxo_id,
        'fluxo_nome': atendimento.fluxo.nome,
    }

    if atendimento.lead:
        lead = atendimento.lead
        contexto.update({
            'lead': lead,
            'lead_id': lead.id,
            'lead_nome': lead.nome_razaosocial,
            'lead_telefone': lead.telefone,
            'lead_email': lead.email or '',
            'lead_cpf': lead.cpf_cnpj or '',
            'lead_cidade': lead.cidade or '',
            'lead_estado': lead.estado or '',
            'lead_score': lead.score_qualificacao,
            'lead_origem': lead.origem,
            'lead_valor': float(lead.valor) if lead.valor else 0,
        })

    # Respostas anteriores
    dados = atendimento.dados_respostas or {}
    for nodo_key, resp_data in dados.items():
        contexto[f'resposta_nodo_{nodo_key}'] = resp_data.get('resposta', '')

    return contexto


def _calcular_delay(config):
    """Calcula timedelta a partir da config de delay."""
    valor = int(config.get('valor', 0))
    unidade = config.get('unidade', 'minutos')
    if unidade == 'horas':
        return timedelta(hours=valor)
    elif unidade == 'dias':
        return timedelta(days=valor)
    return timedelta(minutes=valor)


def _substituir_variaveis(template, contexto):
    """Substitui {{variavel}} no template."""
    if not template:
        return ''
    resultado = template
    for chave, valor in contexto.items():
        if isinstance(valor, (str, int, float)):
            resultado = resultado.replace('{{' + chave + '}}', str(valor))
    return resultado


def _serializar_contexto(contexto):
    """Serializa contexto removendo objetos nao serializaveis."""
    safe = {}
    for k, v in contexto.items():
        if isinstance(v, (str, int, float, bool, type(None), list, dict)):
            safe[k] = v
    return safe


# ============================================================================
# LOG
# ============================================================================

def _registrar_log(atendimento, nodo, status, mensagem, dados=None):
    """Registra log de execucao no fluxo."""
    try:
        from .models import LogFluxoAtendimento
        LogFluxoAtendimento.objects.create(
            tenant=atendimento.fluxo.tenant,
            atendimento=atendimento,
            nodo=nodo,
            lead=atendimento.lead,
            tipo_nodo=nodo.tipo if nodo else '',
            subtipo_nodo=nodo.subtipo if nodo else '',
            status=status,
            mensagem=str(mensagem)[:500],
            dados=dados or {},
        )
    except Exception as e:
        logger.error(f'Erro ao registrar log fluxo: {e}')
