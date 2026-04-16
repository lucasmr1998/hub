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


def iniciar_por_canal(lead, canal, tenant=None, fluxo_forcado=None):
    """Inicia um atendimento automaticamente baseado no canal do lead.
    Se fluxo_forcado for passado (vinculado ao CanalInbox), usa esse.
    Retorna (atendimento, resultado) ou (None, erro).
    """
    from .models import FluxoAtendimento, AtendimentoFluxo

    if tenant is None and hasattr(lead, 'tenant'):
        tenant = lead.tenant

    fluxo = fluxo_forcado or buscar_fluxo_por_canal(canal, tenant)
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
    total_q = fluxo.nodos.filter(tipo='questao').count()
    atendimento = AtendimentoFluxo.objects.create(
        tenant=tenant,
        lead=lead,
        fluxo=fluxo,
        total_questoes=total_q,
        max_tentativas=fluxo.max_tentativas,
    )

    resultado = iniciar_fluxo_visual(atendimento)
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
        # Se tem fallback (false branch) conectado, enviar para la (ex: Agente IA)
        tem_fallback = nodo_atual.saidas.filter(tipo_saida='false').exists()
        if tem_fallback:
            _registrar_log(atendimento, nodo_atual, 'fallback',
                           f'Validacao falhou, redirecionando para fallback: {msg_erro}')
            # Salvar a mensagem para o agente poder usar
            dados = atendimento.dados_respostas or {}
            dados['_ultima_mensagem'] = resposta
            atendimento.dados_respostas = dados
            atendimento.save(update_fields=['dados_respostas'])
            # Base de conhecimento no fallback de validacao
            if atendimento.fluxo.base_conhecimento_ativa:
                contexto_kb = _consultar_base_para_fallback(resposta, atendimento)
                if contexto_kb:
                    contexto['_base_conhecimento'] = contexto_kb
            return _seguir_conexoes(atendimento, nodo_atual, contexto, branch_forcado='false')
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

    # Salvar resposta no campo do lead (se configurado)
    salvar_em = config.get('salvar_em', '')
    if salvar_em and atendimento.lead:
        _salvar_no_lead(atendimento.lead, salvar_em, resposta)

    # Adicionar resposta ao contexto
    contexto[f'resposta_nodo_{nodo_atual.id}'] = resposta
    contexto['ultima_resposta'] = resposta

    # Salvar ultima mensagem para nos IA downstream
    dados['_ultima_mensagem'] = resposta
    atendimento.dados_respostas = dados
    atendimento.save(update_fields=['dados_respostas', 'questoes_respondidas'])

    # IA integrada na questao: classificar e/ou extrair
    ia_acao = config.get('ia_acao', 'validar')
    tem_ia = config.get('integracao_ia_id') and ia_acao != 'validar'
    ia_sucesso = True
    if tem_ia:
        ia_sucesso = _processar_ia_questao(atendimento, nodo_atual, config, resposta, contexto)

    # Seguir conexoes: questoes em modo visual sempre usam true/false
    if tem_ia:
        if ia_sucesso:
            branch = 'true'
        else:
            branch = 'false'
            # Base de conhecimento: injetar artigos no contexto do fallback
            if atendimento.fluxo.base_conhecimento_ativa:
                contexto_kb = _consultar_base_para_fallback(resposta, atendimento)
                if contexto_kb:
                    contexto['_base_conhecimento'] = contexto_kb
    else:
        branch = 'true'
    return _seguir_conexoes(atendimento, nodo_atual, contexto, branch_forcado=branch)


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

    # Verificar se o nodo sinalizou um branch especifico (ex: extrator IA)
    branch = getattr(atendimento, '_branch_saida', None)
    if branch:
        atendimento._branch_saida = None
        return _seguir_conexoes(atendimento, nodo, contexto, branch_forcado=branch)

    # Nodo foi executado (entrada, acao, condicao), seguir conexoes
    return _seguir_conexoes(atendimento, nodo, contexto)


def _seguir_conexoes(atendimento, nodo, contexto, branch_forcado=None):
    """Segue as conexoes de saida de um nodo."""
    # Branch forcado (ex: extrator IA com true/false)
    if branch_forcado:
        conexoes = nodo.saidas.filter(tipo_saida=branch_forcado).select_related('nodo_destino')
        if not conexoes.exists():
            # Fallback para default se nao tem a saida especifica
            conexoes = nodo.saidas.filter(tipo_saida='default').select_related('nodo_destino')
    elif nodo.tipo == 'condicao':
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
        config = nodo.configuracao
        titulo = config.get('titulo', 'Responda:')
        espera = config.get('espera_resposta', True)

        # Skip: se configurado para pular e o campo ja tem valor no lead
        salvar_em = config.get('salvar_em', '')
        if salvar_em and espera and config.get('pular_se_preenchido') and atendimento.lead:
            valor_existente = getattr(atendimento.lead, salvar_em, None)
            if valor_existente and str(valor_existente).strip():
                _registrar_log(atendimento, nodo, 'sucesso',
                               f'Pulou questao: {salvar_em} ja preenchido ({valor_existente})')
                # Salvar no contexto como se tivesse respondido
                dados = atendimento.dados_respostas or {}
                dados[str(nodo.id)] = {
                    'resposta': str(valor_existente),
                    'data_resposta': timezone.now().isoformat(),
                    'valida': True,
                    'pulada': True,
                }
                dados['_ultima_mensagem'] = str(valor_existente)
                atendimento.dados_respostas = dados
                atendimento.save(update_fields=['dados_respostas'])
                contexto[f'resposta_nodo_{nodo.id}'] = str(valor_existente)
                contexto['ultima_resposta'] = str(valor_existente)
                # Processar IA se configurado
                ia_acao = config.get('ia_acao', 'validar')
                if config.get('integracao_ia_id') and ia_acao != 'validar':
                    ia_sucesso = _processar_ia_questao(atendimento, nodo, config, str(valor_existente), contexto)
                    atendimento._branch_saida = 'true' if ia_sucesso else 'false'
                else:
                    atendimento._branch_saida = 'true'
                return None  # segue para proximo no

        if espera:
            # PAUSA: retorna dados da questao para o lead responder
            atendimento.nodo_atual = nodo
            atendimento.save(update_fields=['nodo_atual', 'dados_respostas', 'questoes_respondidas'])
            _registrar_log(atendimento, nodo, 'aguardando', f'Pergunta: {titulo}')
            # Incluir mensagens pendentes de nodos anteriores (espera_resposta=False)
            pendentes = getattr(atendimento, '_mensagens_pendentes', [])
            mensagem_final = titulo
            if pendentes:
                mensagem_final = '\n\n'.join(pendentes) + '\n\n' + titulo
                atendimento._mensagens_pendentes = []
            return {
                'tipo': 'questao',
                'questao': _montar_dados_questao(nodo),
                'mensagem': mensagem_final,
            }
        else:
            # NAO ESPERA: envia mensagem e continua o fluxo
            _registrar_log(atendimento, nodo, 'sucesso', f'Mensagem enviada: {titulo}')

            # Se tem IA classificadora/extratora, processar com _ultima_mensagem
            ia_acao = config.get('ia_acao', 'validar')
            if config.get('integracao_ia_id') and ia_acao != 'validar':
                ultima = _get_ultima_mensagem(atendimento)
                if ultima:
                    ia_sucesso = _processar_ia_questao(atendimento, nodo, config, ultima, contexto)
                    atendimento._branch_saida = 'true' if ia_sucesso else 'false'
            else:
                # Questoes sem IA em modo visual usam branch 'true'
                atendimento._branch_saida = 'true'

            # Acumular mensagens pendentes (nao pausa, mas precisa enviar)
            if titulo:
                if not hasattr(atendimento, '_mensagens_pendentes'):
                    atendimento._mensagens_pendentes = []
                atendimento._mensagens_pendentes.append(titulo)
                atendimento._mensagem_pendente = {
                    'tipo': 'mensagem',
                    'questao': _montar_dados_questao(nodo),
                    'mensagem': titulo,
                }
            return None  # Continua percorrendo

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
        atendimento.motivo_finalizacao = 'completado'
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

    elif nodo.tipo == 'transferir_humano':
        return _executar_transferir_humano(atendimento, nodo, contexto)

    # Nos IA que NAO pausam (passam direto)
    elif nodo.tipo == 'ia_classificador':
        return _executar_ia_classificador(atendimento, nodo, contexto)

    elif nodo.tipo == 'ia_extrator':
        return _executar_ia_extrator(atendimento, nodo, contexto)

    # Nos IA que PAUSAM (esperam resposta do usuario)
    elif nodo.tipo == 'ia_respondedor':
        return _executar_ia_respondedor(atendimento, nodo, contexto)

    elif nodo.tipo == 'ia_agente':
        return _executar_ia_agente_inicial(atendimento, nodo, contexto)

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

    if subtipo == 'criar_oportunidade':
        _acao_criar_oportunidade(config, contexto, atendimento)
    elif subtipo == 'webhook':
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


def _acao_criar_oportunidade(config, contexto, atendimento):
    """Cria oportunidade no CRM para o lead, se ainda nao existir."""
    try:
        from apps.comercial.crm.models import OportunidadeVenda, Pipeline, PipelineEstagio
        from django.contrib.auth.models import User

        lead = atendimento.lead
        if not lead:
            return

        # Se ja existe oportunidade, atualizar dados_custom e nao duplicar
        oport_existente = OportunidadeVenda.objects.filter(lead=lead).first()
        if oport_existente:
            variaveis = (atendimento.dados_respostas or {}).get('variaveis', {})
            custom = oport_existente.dados_custom or {}
            atualizado = False
            for var_nome, var_valor in variaveis.items():
                if var_nome.startswith('oport_dados_custom_') and var_valor:
                    campo = var_nome.replace('oport_dados_custom_', '')
                    custom[campo] = var_valor
                    atualizado = True
                elif var_nome in ('curso_interesse', 'forma_ingresso', 'status_matricula') and var_valor:
                    custom[var_nome] = var_valor
                    atualizado = True
            if atualizado:
                oport_existente.dados_custom = custom
                oport_existente.save(update_fields=['dados_custom'])
            logger.info(f'Oportunidade ja existe para lead {lead.id}, dados_custom atualizados.')
            return

        tenant = atendimento.fluxo.tenant

        # Buscar pipeline (config ou padrao do tenant)
        pipeline = None
        pipeline_id = config.get('pipeline_id')
        if pipeline_id:
            pipeline = Pipeline.objects.filter(id=pipeline_id).first()
        if not pipeline:
            pipeline = Pipeline.objects.filter(tenant=tenant, padrao=True).first()
        if not pipeline:
            pipeline = Pipeline.objects.filter(tenant=tenant).first()

        # Buscar estagio inicial (config ou primeiro do pipeline)
        estagio = None
        estagio_slug = config.get('estagio', '')
        if estagio_slug and pipeline:
            estagio = PipelineEstagio.objects.filter(pipeline=pipeline, slug=estagio_slug).first()
        if not estagio and pipeline:
            estagio = PipelineEstagio.objects.filter(pipeline=pipeline).order_by('ordem').first()
        if not estagio:
            estagio = PipelineEstagio.objects.filter(tenant=tenant).order_by('ordem').first()

        if not estagio:
            logger.error('Criar oportunidade: nenhum estagio encontrado')
            return

        # Responsavel
        responsavel = None
        resp_id = config.get('responsavel_id')
        if resp_id:
            responsavel = User.objects.filter(id=resp_id).first()

        titulo = _substituir_variaveis(
            config.get('titulo', '{{lead_nome}}'),
            contexto
        )

        # Preencher dados_custom com variaveis do fluxo
        dados_custom = {}
        variaveis = (atendimento.dados_respostas or {}).get('variaveis', {})
        for var_nome, var_valor in variaveis.items():
            # Variáveis com prefixo oport_dados_custom_ vão para dados_custom
            if var_nome.startswith('oport_dados_custom_') and var_valor:
                campo = var_nome.replace('oport_dados_custom_', '')
                dados_custom[campo] = var_valor
            # Variáveis explícitas como curso_interesse, forma_ingresso
            elif var_nome in ('curso_interesse', 'forma_ingresso', 'status_matricula') and var_valor:
                dados_custom[var_nome] = var_valor

        oportunidade = OportunidadeVenda.objects.create(
            tenant=tenant,
            lead=lead,
            pipeline=pipeline,
            estagio=estagio,
            responsavel=responsavel,
            titulo=titulo,
            valor_estimado=lead.valor,
            origem_crm='automatico',
            dados_custom=dados_custom,
        )

        # Distribuir automaticamente se não tem responsável
        if not responsavel:
            from apps.comercial.crm.distribution import distribuir_oportunidade
            distribuir_oportunidade(oportunidade)

    except Exception as e:
        logger.error(f'Criar oportunidade erro: {e}')
        raise


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
        from django.contrib.auth.models import User
        titulo = _substituir_variaveis(config.get('titulo', 'Tarefa do fluxo'), contexto)
        # Buscar responsavel: config > primeiro user staff do tenant
        responsavel = None
        resp_id = config.get('responsavel_id')
        if resp_id:
            responsavel = User.objects.filter(id=resp_id).first()
        if not responsavel:
            responsavel = User.objects.filter(is_staff=True, is_active=True).first()
        TarefaCRM.objects.create(
            tenant=atendimento.fluxo.tenant,
            titulo=titulo,
            tipo=config.get('tipo_tarefa', 'ligacao'),
            prioridade=config.get('prioridade', 'media'),
            lead=atendimento.lead,
            responsavel=responsavel,
        )
    except Exception as e:
        logger.error(f'Criar tarefa erro: {e}')
        raise


def _acao_mover_estagio(config, contexto, atendimento):
    """Move oportunidade de estagio no CRM."""
    try:
        from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio
        estagio_slug = config.get('estagio', '')
        if not estagio_slug or not atendimento.lead:
            return
        estagio = PipelineEstagio.objects.filter(slug=estagio_slug).first()
        if estagio:
            OportunidadeVenda.objects.filter(
                lead=atendimento.lead
            ).update(estagio=estagio)
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
    import re

    espera = config.get('espera_resposta', True)
    resp_str = str(resposta).strip()
    msg_erro = config.get('mensagem_erro', '')

    # Se nao espera resposta, sempre valida
    if not espera:
        return True, None

    # Resposta vazia
    if not resp_str:
        return False, msg_erro or 'Resposta obrigatoria'

    # Validacao por opcoes
    opcoes = config.get('opcoes_resposta', [])
    if opcoes and resp_str not in [str(o) for o in opcoes]:
        try:
            idx = int(resposta)
            if 0 <= idx < len(opcoes):
                return True, None
        except (ValueError, TypeError):
            pass
        return False, msg_erro or 'Opcao invalida'

    # Validacao por tipo
    validacao = config.get('validacao', 'texto')
    if validacao == 'email' and '@' not in resp_str:
        return False, msg_erro or 'Informe um e-mail valido'
    elif validacao == 'telefone' and len(re.sub(r'\D', '', resp_str)) < 10:
        return False, msg_erro or 'Informe um telefone valido'
    elif validacao == 'cpf_cnpj' and len(re.sub(r'\D', '', resp_str)) not in (11, 14):
        return False, msg_erro or 'Informe um CPF ou CNPJ valido'
    elif validacao == 'cep' and len(re.sub(r'\D', '', resp_str)) != 8:
        return False, msg_erro or 'Informe um CEP valido'
    elif validacao == 'numero':
        try:
            float(resp_str.replace(',', '.'))
        except ValueError:
            return False, msg_erro or 'Informe um numero valido'

    # Validacao por regex
    regex = config.get('regex', '')
    if regex:
        try:
            if not re.match(regex, resp_str):
                return False, msg_erro or 'Formato invalido'
        except re.error:
            logger.warning(f'Regex invalido na config: {regex}')

    # Validacao por integracao IA
    integracao_ia_id = config.get('integracao_ia_id', '')
    if integracao_ia_id:
        try:
            resultado_ia = _validar_com_ia(integracao_ia_id, resp_str, config)
            if resultado_ia and not resultado_ia.get('valido', True):
                return False, resultado_ia.get('mensagem', msg_erro or 'Resposta invalida segundo a IA')
        except Exception as e:
            logger.error(f'Validacao IA erro: {e}')

    # Validacao por webhook
    webhook_url = config.get('webhook_validacao', '')
    if webhook_url:
        try:
            prompt = config.get('prompt_validacao', '')
            res = requests.post(webhook_url, json={
                'resposta': resp_str,
                'prompt': prompt,
                'config': {k: v for k, v in config.items() if k not in ('webhook_validacao',)},
            }, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if not data.get('valido', True):
                    return False, data.get('mensagem', msg_erro or 'Resposta invalida')
        except Exception as e:
            logger.error(f'Webhook validacao erro: {e}')

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

    # Contexto do assistente CRM (sem lead, com usuario)
    dados_resp = atendimento.dados_respostas or {}
    if dados_resp.get('_assistente_usuario_id'):
        contexto['assistente_modo'] = True
        contexto['assistente_usuario_id'] = dados_resp['_assistente_usuario_id']
        contexto['assistente_tenant_id'] = dados_resp.get('_assistente_tenant_id')
        contexto['assistente_telefone'] = dados_resp.get('_telefone', '')

    # Respostas anteriores
    dados = atendimento.dados_respostas or {}
    for nodo_key, resp_data in dados.items():
        if nodo_key == 'variaveis':
            continue  # variaveis IA tratadas separadamente
        if isinstance(resp_data, dict):
            contexto[f'resposta_nodo_{nodo_key}'] = resp_data.get('resposta', '')

    # Variaveis IA (classificador, extrator, etc.)
    variaveis = dados.get('variaveis', {})
    contexto['var'] = variaveis
    for var_nome, var_valor in variaveis.items():
        contexto[var_nome] = var_valor

    return contexto


def _validar_com_ia(integracao_id, resposta, config):
    """Valida resposta usando uma integracao de IA configurada."""
    from apps.integracoes.models import IntegracaoAPI

    integracao = IntegracaoAPI.objects.filter(id=integracao_id, ativa=True).first()
    if not integracao:
        logger.warning(f'Integracao IA {integracao_id} nao encontrada ou inativa')
        return None

    prompt = config.get('prompt_validacao', '')
    titulo = config.get('titulo', '')
    mensagem = f"Pergunta: {titulo}\nResposta do usuario: {resposta}\n\n{prompt}\n\nResponda em JSON: {{\"valido\": true/false, \"mensagem\": \"explicacao\"}}"

    tipo = integracao.tipo
    base_url = integracao.base_url
    extras = integracao.configuracoes_extras or {}
    api_key = integracao.api_key or extras.get('api_key', '') or integracao.access_token or integracao.client_secret or ''
    modelo = extras.get('modelo', '')

    headers = {'Content-Type': 'application/json'}
    payload = {}

    if tipo == 'openai':
        headers['Authorization'] = f'Bearer {api_key}'
        url = base_url or 'https://api.openai.com/v1/chat/completions'
        payload = {
            'model': modelo or 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': mensagem}],
            'response_format': {'type': 'json_object'},
            'max_tokens': 200,
        }
    elif tipo == 'anthropic':
        headers['x-api-key'] = api_key
        headers['anthropic-version'] = '2023-06-01'
        url = base_url or 'https://api.anthropic.com/v1/messages'
        payload = {
            'model': modelo or 'claude-haiku-4-5-20251001',
            'max_tokens': 200,
            'messages': [{'role': 'user', 'content': mensagem}],
        }
    elif tipo == 'groq':
        headers['Authorization'] = f'Bearer {api_key}'
        url = base_url or 'https://api.groq.com/openai/v1/chat/completions'
        payload = {
            'model': modelo or 'llama-3.1-8b-instant',
            'messages': [{'role': 'user', 'content': mensagem}],
            'max_tokens': 200,
        }
    elif tipo == 'google_ai':
        url = (base_url or f'https://generativelanguage.googleapis.com/v1beta/models/{modelo or "gemini-2.0-flash"}:generateContent') + f'?key={api_key}'
        payload = {
            'contents': [{'parts': [{'text': mensagem}]}],
        }
        headers.pop('Authorization', None)
    else:
        # Tipo generico: POST com payload padrao
        headers['Authorization'] = f'Bearer {api_key}'
        url = base_url
        payload = {'prompt': mensagem}

    try:
        import json as json_mod
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code != 200:
            logger.error(f'IA {tipo} retornou {res.status_code}: {res.text[:200]}')
            return None

        data = res.json()

        # Extrair texto da resposta conforme o provider
        texto = ''
        if tipo in ('openai', 'groq'):
            texto = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        elif tipo == 'anthropic':
            texto = data.get('content', [{}])[0].get('text', '')
        elif tipo == 'google_ai':
            texto = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        else:
            texto = data.get('content', data.get('text', data.get('result', str(data))))

        # Tentar parsear JSON da resposta
        try:
            # Limpar markdown se vier ```json ... ```
            texto_limpo = texto.strip()
            if texto_limpo.startswith('```'):
                texto_limpo = texto_limpo.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            resultado = json_mod.loads(texto_limpo)
            return resultado
        except (json_mod.JSONDecodeError, IndexError):
            # Se nao e JSON, interpretar como texto
            lower = texto.lower()
            valido = 'valido' in lower or 'true' in lower or 'sim' in lower
            return {'valido': valido, 'mensagem': texto[:200]}

    except Exception as e:
        logger.error(f'Erro chamando IA {tipo}: {e}')
        return None


def _salvar_no_lead(lead, campo, valor):
    """Salva a resposta em um campo do lead."""
    campos_permitidos = {
        'nome_razaosocial', 'email', 'telefone', 'cpf_cnpj', 'rg',
        'cidade', 'estado', 'cep', 'rua', 'numero_residencia',
        'bairro', 'ponto_referencia', 'empresa', 'observacoes',
        'data_nascimento',
    }
    if campo not in campos_permitidos:
        return
    try:
        setattr(lead, campo, valor)
        lead.save(update_fields=[campo])
    except Exception as e:
        logger.error(f'Erro ao salvar no lead campo {campo}: {e}')


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


# ============================================================================
# NOS IA — CLASSIFICADOR, EXTRATOR, RESPONDEDOR, AGENTE
# ============================================================================

def _processar_ia_questao(atendimento, nodo, config, resposta, contexto):
    """Processa IA integrada na questao: classificar e/ou extrair.
    Retorna True se processou com sucesso, False se falhou (fallback).
    Para classificar_extrair: extrai primeiro. Se extraiu dados, classificacao e positiva."""
    ia_acao = config.get('ia_acao', 'validar')
    integracao = _obter_integracao_ia(config, atendimento.fluxo.tenant)
    if not integracao:
        return False

    modelo = config.get('ia_modelo', '')
    prompt_base = config.get('prompt_validacao', '')
    sucesso_classificacao = True
    sucesso_extracao = True

    # Para classificar_extrair: extrair PRIMEIRO, classificar baseado no resultado
    # Para classificar sozinho: classificar normalmente
    if ia_acao == 'classificar':
        categorias = config.get('ia_categorias', [])
        var_saida = config.get('ia_variavel_saida', 'classificacao')

        system = f"""{prompt_base}

Categorias disponiveis: {', '.join(categorias)}

Responda APENAS com o nome exato de uma das categorias acima. Nenhum texto adicional."""

        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': resposta},
        ]
        resultado = _chamar_llm_simples(integracao, modelo, messages)
        if resultado:
            categoria = resultado.strip().lower().replace('"', '').replace("'", '')
            for c in categorias:
                if c.lower() == categoria or c.lower() in categoria:
                    categoria = c
                    break
            else:
                if categorias:
                    categoria = categorias[0]
            _salvar_variavel(atendimento, var_saida, categoria)
            contexto['var'] = (atendimento.dados_respostas or {}).get('variaveis', {})
            contexto[var_saida] = categoria
            _registrar_log(atendimento, nodo, 'sucesso',
                           f'IA classificou como: {categoria}',
                           dados={'variavel': var_saida, 'valor': categoria})
        else:
            sucesso_classificacao = False

    # Extrair
    if ia_acao in ('extrair', 'classificar_extrair'):
        campos = config.get('ia_campos_extrair', [])
        if campos:
            campos_para_llm = []
            for c in campos:
                nome_base = c['nome'].split('.')[-1] if '.' in c['nome'] else c['nome']
                campos_para_llm.append(f'- {nome_base}: {c.get("descricao", "")}')
            campos_desc = '\n'.join(campos_para_llm)

            system = f"""Extraia os seguintes dados da mensagem do usuario:

{campos_desc}

{prompt_base}

Responda APENAS em JSON. Se nao encontrar, use string vazia."""

            messages = [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': resposta},
            ]
            resultado = _chamar_llm_simples(integracao, modelo, messages)
            if resultado:
                import json as json_mod
                try:
                    texto_limpo = resultado.strip()
                    if texto_limpo.startswith('```'):
                        texto_limpo = texto_limpo.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                    dados_extraidos = json_mod.loads(texto_limpo)
                except (json_mod.JSONDecodeError, IndexError):
                    dados_extraidos = {}

                # Salvar variaveis e no lead/oportunidade
                campos_lead = []
                campos_oport = {}
                for campo in campos:
                    nome = campo['nome']
                    nome_base = nome.split('.')[-1] if '.' in nome else nome
                    valor = dados_extraidos.get(nome_base, '') or dados_extraidos.get(nome, '')
                    if not valor:
                        continue
                    var_nome = nome.replace('.', '_')
                    _salvar_variavel(atendimento, var_nome, valor)
                    contexto[var_nome] = valor

                    if config.get('ia_salvar_no_lead'):
                        if nome.startswith('oport.dados_custom.'):
                            campo_custom = nome.replace('oport.dados_custom.', '')
                            campos_oport[f'dados_custom.{campo_custom}'] = valor
                        elif nome.startswith('oport.'):
                            campo_oport = nome.replace('oport.', '')
                            campos_oport[campo_oport] = valor
                        elif atendimento.lead and hasattr(atendimento.lead, nome):
                            setattr(atendimento.lead, nome, valor)
                            campos_lead.append(nome)

                if campos_lead and atendimento.lead:
                    atendimento.lead.save(update_fields=campos_lead)

                if campos_oport and atendimento.lead:
                    from apps.comercial.crm.models import OportunidadeVenda
                    oport = OportunidadeVenda.objects.filter(lead=atendimento.lead).order_by('-data_criacao').first()
                    if oport:
                        oport_fields = []
                        for cn, cv in campos_oport.items():
                            if cn.startswith('dados_custom.'):
                                custom_key = cn.replace('dados_custom.', '')
                                custom = oport.dados_custom or {}
                                custom[custom_key] = cv
                                oport.dados_custom = custom
                                if 'dados_custom' not in oport_fields:
                                    oport_fields.append('dados_custom')
                            elif hasattr(oport, cn):
                                setattr(oport, cn, cv)
                                oport_fields.append(cn)
                        if oport_fields:
                            oport.save(update_fields=oport_fields)

                campos_com_valor = {k: v for k, v in dados_extraidos.items() if v and str(v).strip()}
                if campos_com_valor:
                    _registrar_log(atendimento, nodo, 'sucesso',
                                   f'IA extraiu: {dados_extraidos}',
                                   dados={'campos': dados_extraidos})
                else:
                    sucesso_extracao = False
                    _registrar_log(atendimento, nodo, 'erro',
                                   f'IA nao extraiu dados: {dados_extraidos}',
                                   dados={'campos': dados_extraidos})
            else:
                sucesso_extracao = False

    # Para classificar_extrair: usar uma unica chamada que classifica E extrai juntas
    if ia_acao == 'classificar_extrair':
        categorias = config.get('ia_categorias', [])
        var_saida = config.get('ia_variavel_saida', 'classificacao')

        # Chamar IA para classificar baseado no prompt completo (mais preciso que separar)
        system_class = f"""{prompt_base}

Categorias disponiveis: {', '.join(categorias)}

IMPORTANTE: Considere os dados extraidos acima. Se a extracao encontrou um valor valido, classifique como {categorias[0] if categorias else 'sucesso'}.
Se nao encontrou ou o valor nao e valido conforme as regras, classifique como {categorias[1] if len(categorias) > 1 else 'falha'}.

Responda APENAS com o nome exato de uma das categorias."""

        messages_class = [
            {'role': 'system', 'content': system_class},
            {'role': 'user', 'content': resposta},
        ]
        resultado_class = _chamar_llm_simples(integracao, modelo, messages_class)
        if resultado_class:
            categoria = resultado_class.strip().lower().replace('"', '').replace("'", '')
            for c in categorias:
                if c.lower() == categoria or c.lower() in categoria:
                    categoria = c
                    break
            else:
                categoria = categorias[1] if len(categorias) > 1 else categorias[0]
        elif sucesso_extracao:
            categoria = categorias[0] if categorias else 'sucesso'
        else:
            categoria = categorias[1] if len(categorias) > 1 else (categorias[0] if categorias else 'falha')
        _salvar_variavel(atendimento, var_saida, categoria)
        contexto[var_saida] = categoria
        sucesso_classificacao = sucesso_extracao
        _registrar_log(atendimento, nodo, 'sucesso',
                       f'IA classificou (via extracao): {categoria}',
                       dados={'variavel': var_saida, 'valor': categoria})

    # Atualizar contexto com variaveis
    contexto['var'] = (atendimento.dados_respostas or {}).get('variaveis', {})

    return sucesso_classificacao and sucesso_extracao


def _chamar_llm_simples(integracao, modelo, messages):
    """Chama LLM e retorna o texto da resposta. Reutiliza padrao de _validar_com_ia."""
    tipo = integracao.tipo
    base_url = integracao.base_url
    extras = integracao.configuracoes_extras or {}
    api_key = integracao.api_key or extras.get('api_key', '') or integracao.access_token or integracao.client_secret or ''
    modelo = modelo or extras.get('modelo', '')

    headers = {'Content-Type': 'application/json'}
    payload = {}

    if tipo in ('openai', 'groq'):
        headers['Authorization'] = f'Bearer {api_key}'
        url = base_url or ('https://api.openai.com/v1/chat/completions' if tipo == 'openai' else 'https://api.groq.com/openai/v1/chat/completions')
        payload = {
            'model': modelo or ('gpt-4o-mini' if tipo == 'openai' else 'llama-3.1-8b-instant'),
            'messages': messages,
            'max_tokens': 1000,
        }
    elif tipo == 'anthropic':
        headers['x-api-key'] = api_key
        headers['anthropic-version'] = '2023-06-01'
        url = base_url or 'https://api.anthropic.com/v1/messages'
        # Anthropic: system separado dos messages
        system_msg = ''
        chat_messages = []
        for m in messages:
            if m['role'] == 'system':
                system_msg += m['content'] + '\n'
            else:
                chat_messages.append(m)
        payload = {
            'model': modelo or 'claude-haiku-4-5-20251001',
            'max_tokens': 1000,
            'messages': chat_messages,
        }
        if system_msg:
            payload['system'] = system_msg.strip()
    elif tipo == 'google_ai':
        url = (base_url or f'https://generativelanguage.googleapis.com/v1beta/models/{modelo or "gemini-2.0-flash"}:generateContent') + f'?key={api_key}'
        # Converter messages para formato Google
        contents = []
        for m in messages:
            role = 'model' if m['role'] == 'assistant' else 'user'
            if m['role'] == 'system':
                contents.append({'role': 'user', 'parts': [{'text': f'[System]: {m["content"]}'}]})
            else:
                contents.append({'role': role, 'parts': [{'text': m['content']}]})
        payload = {'contents': contents}
        headers.pop('Authorization', None)
    else:
        headers['Authorization'] = f'Bearer {api_key}'
        url = base_url
        payload = {'prompt': messages[-1].get('content', '')}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code != 200:
            logger.error(f'LLM {tipo} retornou {res.status_code}: {res.text[:200]}')
            return None

        data = res.json()

        if tipo in ('openai', 'groq'):
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
        elif tipo == 'anthropic':
            return data.get('content', [{}])[0].get('text', '')
        elif tipo == 'google_ai':
            return data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        else:
            return data.get('content', data.get('text', str(data)))
    except Exception as e:
        logger.error(f'Erro ao chamar LLM {tipo}: {e}')
        return None


def _obter_integracao_ia(config, tenant):
    """Busca a integracao IA configurada no nodo, filtrando por tenant.
    Se nao achar no tenant do fluxo, tenta sem filtro (para assistente cross-tenant)."""
    from apps.integracoes.models import IntegracaoAPI
    integracao_id = config.get('integracao_ia_id')
    if not integracao_id:
        return None
    integracao = IntegracaoAPI.all_tenants.filter(
        id=integracao_id, tenant=tenant, ativa=True
    ).first()
    if not integracao:
        # Fallback: buscar sem filtro de tenant (assistente cross-tenant)
        integracao = IntegracaoAPI.all_tenants.filter(
            id=integracao_id, ativa=True
        ).first()
    return integracao


def _salvar_variavel(atendimento, nome, valor):
    """Salva uma variavel IA no dados_respostas do atendimento."""
    dados = atendimento.dados_respostas or {}
    if 'variaveis' not in dados:
        dados['variaveis'] = {}
    dados['variaveis'][nome] = valor
    atendimento.dados_respostas = dados
    atendimento.save(update_fields=['dados_respostas'])


def _get_ultima_mensagem(atendimento):
    """Pega a ultima mensagem do contato na conversa do atendimento."""
    # Prioridade 1: dados_respostas._ultima_mensagem (setado pelo handler anterior)
    atendimento.refresh_from_db(fields=['dados_respostas'])
    dados = atendimento.dados_respostas or {}
    ultima = dados.get('_ultima_mensagem', '')
    if ultima:
        return ultima

    # Prioridade 2: buscar no Inbox via conversa_id salva (assistente sem lead)
    try:
        from apps.inbox.models import Mensagem, Conversa
        conversa_id = dados.get('_conversa_id')
        if conversa_id:
            msg = Mensagem.all_tenants.filter(
                conversa_id=conversa_id, remetente_tipo='contato'
            ).order_by('-data_envio').first()
            if msg:
                return msg.conteudo

        # Prioridade 3: buscar via lead (fluxos tradicionais)
        if atendimento.lead:
            conversa = atendimento.lead.conversas.filter(
                status__in=['aberta', 'pendente']
            ).order_by('-ultima_mensagem_em').first()
            if conversa:
                msg = Mensagem.objects.filter(
                    conversa=conversa, remetente_tipo='contato'
                ).order_by('-data_envio').first()
                if msg:
                    return msg.conteudo
    except Exception:
        pass
    return ''


# ── TRANSFERIR PARA HUMANO ──

def _executar_transferir_humano(atendimento, nodo, contexto):
    """Transfere a conversa para fila humana e finaliza o fluxo do bot."""
    config = nodo.configuracao
    fila_id = config.get('fila_id')
    mensagem = config.get('mensagem', 'Transferindo para um atendente. Aguarde um momento.')

    # Buscar conversa aberta do lead
    conversa = None
    if atendimento.lead:
        from apps.inbox.models import Conversa
        conversa = Conversa.objects.filter(
            lead=atendimento.lead,
            status__in=['aberta', 'pendente'],
        ).order_by('-ultima_mensagem_em').first()

    if conversa:
        conversa.modo_atendimento = 'humano'
        update_fields = ['modo_atendimento']
        if fila_id:
            from apps.inbox.models import FilaInbox
            fila = FilaInbox.objects.filter(pk=fila_id).select_related('equipe').first()
            if fila:
                conversa.fila = fila
                conversa.equipe = fila.equipe
                update_fields.extend(['fila', 'equipe'])
        conversa.save(update_fields=update_fields)

        # Distribuir para agente da fila
        from apps.inbox.distribution import distribuir_conversa
        distribuir_conversa(conversa, atendimento.fluxo.tenant)

    # Finalizar o atendimento do bot
    atendimento.status = 'transferido'
    atendimento.motivo_finalizacao = 'transferido'
    atendimento.nodo_atual = None
    atendimento.save(update_fields=['status', 'motivo_finalizacao', 'nodo_atual'])

    _registrar_log(atendimento, nodo, 'sucesso',
                   f'Transferido para humano. Fila: {fila_id or "padrao"}',
                   dados={'fila_id': fila_id, 'conversa_id': conversa.pk if conversa else None})

    return {
        'tipo': 'transferido',
        'mensagem': mensagem,
    }


# ── CLASSIFICADOR IA ──

def _executar_ia_classificador(atendimento, nodo, contexto):
    """Classifica a mensagem do usuario em uma categoria. NAO pausa."""
    config = nodo.configuracao
    integracao = _obter_integracao_ia(config, atendimento.fluxo.tenant)
    if not integracao:
        _registrar_log(atendimento, nodo, 'erro', 'Integracao IA nao configurada')
        return None  # passa direto

    categorias = config.get('categorias', [])
    prompt = config.get('prompt', '')
    mensagem_usuario = _get_ultima_mensagem(atendimento)

    system_content = f"""{prompt}

Categorias disponiveis: {', '.join(categorias)}

Responda APENAS com o nome exato de uma das categorias acima. Nenhum texto adicional."""

    messages = [
        {'role': 'system', 'content': system_content},
        {'role': 'user', 'content': mensagem_usuario or '(sem mensagem)'},
    ]

    resultado = _chamar_llm_simples(integracao, config.get('modelo', ''), messages)
    if not resultado:
        _registrar_log(atendimento, nodo, 'erro', 'LLM nao retornou resposta')
        return None

    # Limpar e validar categoria
    categoria = resultado.strip().lower().replace('"', '').replace("'", '')
    categorias_lower = [c.lower() for c in categorias]
    if categoria not in categorias_lower and categorias:
        # Tentar match parcial
        for c in categorias_lower:
            if c in categoria:
                categoria = c
                break
        else:
            categoria = categorias[0] if categorias else categoria

    # Recuperar o nome original da categoria (preservar case)
    for c_original in categorias:
        if c_original.lower() == categoria:
            categoria = c_original
            break

    var_saida = config.get('variavel_saida', 'classificacao')
    _salvar_variavel(atendimento, var_saida, categoria)

    _registrar_log(atendimento, nodo, 'sucesso',
                   f'Classificado como: {categoria}',
                   dados={'variavel': var_saida, 'valor': categoria, 'mensagem': mensagem_usuario})

    # Atualizar contexto para nos seguintes
    contexto['var'] = (atendimento.dados_respostas or {}).get('variaveis', {})
    contexto[var_saida] = categoria

    return None  # passa direto para o proximo no


# ── EXTRATOR IA ──

def _executar_ia_extrator(atendimento, nodo, contexto):
    """Extrai dados estruturados da mensagem. NAO pausa.
    Se extraiu pelo menos 1 campo: saida 'true'. Se nao extraiu nada: saida 'false' (fallback)."""
    config = nodo.configuracao
    integracao = _obter_integracao_ia(config, atendimento.fluxo.tenant)
    if not integracao:
        _registrar_log(atendimento, nodo, 'erro', 'Integracao IA nao configurada')
        atendimento._branch_saida = 'false'
        return None

    campos = config.get('campos_extrair', [])
    prompt_extra = config.get('prompt', '')
    mensagem_usuario = _get_ultima_mensagem(atendimento)

    # Usar nome base (sem prefixo oport.) para a LLM
    campos_para_llm = []
    for c in campos:
        nome_base = c['nome'].split('.')[-1] if '.' in c['nome'] else c['nome']
        campos_para_llm.append(f'- {nome_base}: {c.get("descricao", "")} (tipo: {c.get("tipo", "string")})')
    campos_desc = '\n'.join(campos_para_llm)

    system_content = f"""Extraia os seguintes dados da mensagem do usuario:

{campos_desc}

{prompt_extra}

Responda APENAS em JSON com os campos encontrados. Se um campo nao for encontrado, use string vazia.
Exemplo: {{"nome": "Joao Silva", "curso": "Direito"}}"""

    messages = [
        {'role': 'system', 'content': system_content},
        {'role': 'user', 'content': mensagem_usuario or '(sem mensagem)'},
    ]

    resultado = _chamar_llm_simples(integracao, config.get('modelo', ''), messages)
    if not resultado:
        _registrar_log(atendimento, nodo, 'erro', 'LLM nao retornou resposta')
        atendimento._branch_saida = 'false'
        return None

    # Parsear JSON
    import json as json_mod
    try:
        texto_limpo = resultado.strip()
        if texto_limpo.startswith('```'):
            texto_limpo = texto_limpo.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        dados_extraidos = json_mod.loads(texto_limpo)
    except (json_mod.JSONDecodeError, IndexError):
        _registrar_log(atendimento, nodo, 'erro', f'Resposta IA nao e JSON: {resultado[:100]}')
        atendimento._branch_saida = 'false'
        return None

    # Salvar variaveis e dados no lead/oportunidade
    campos_lead_atualizar = []
    campos_oport_atualizar = {}
    for campo in campos:
        nome = campo['nome']
        # A LLM recebe o nome sem prefixo, buscar pelo nome base
        nome_base = nome.split('.')[-1] if '.' in nome else nome
        valor = dados_extraidos.get(nome_base, '') or dados_extraidos.get(nome, '')
        if not valor:
            continue

        # Salvar como variavel do fluxo (sempre)
        var_nome = nome.replace('.', '_')
        _salvar_variavel(atendimento, var_nome, valor)
        contexto[var_nome] = valor

        if config.get('salvar_no_lead'):
            if nome.startswith('oport.dados_custom.'):
                # Campo custom da oportunidade
                campo_custom = nome.replace('oport.dados_custom.', '')
                campos_oport_atualizar[f'dados_custom.{campo_custom}'] = valor
            elif nome.startswith('oport.'):
                # Campo direto da oportunidade
                campo_oport = nome.replace('oport.', '')
                campos_oport_atualizar[campo_oport] = valor
            elif atendimento.lead and hasattr(atendimento.lead, nome):
                # Campo do lead
                setattr(atendimento.lead, nome, valor)
                campos_lead_atualizar.append(nome)

    # Persistir lead
    if campos_lead_atualizar and atendimento.lead:
        atendimento.lead.save(update_fields=campos_lead_atualizar)

    # Persistir oportunidade
    if campos_oport_atualizar and atendimento.lead:
        from apps.comercial.crm.models import OportunidadeVenda
        oport = OportunidadeVenda.objects.filter(lead=atendimento.lead).order_by('-data_criacao').first()
        if oport:
            oport_fields = []
            for campo_nome, campo_valor in campos_oport_atualizar.items():
                if campo_nome.startswith('dados_custom.'):
                    custom_key = campo_nome.replace('dados_custom.', '')
                    custom = oport.dados_custom or {}
                    custom[custom_key] = campo_valor
                    oport.dados_custom = custom
                    if 'dados_custom' not in oport_fields:
                        oport_fields.append('dados_custom')
                elif hasattr(oport, campo_nome):
                    setattr(oport, campo_nome, campo_valor)
                    oport_fields.append(campo_nome)
            if oport_fields:
                oport.save(update_fields=oport_fields)

    # Verificar se extraiu pelo menos 1 campo com valor
    campos_com_valor = {k: v for k, v in dados_extraidos.items() if v and str(v).strip()}
    extraiu = len(campos_com_valor) > 0

    _registrar_log(atendimento, nodo, 'sucesso' if extraiu else 'erro',
                   f'Extraido: {dados_extraidos}' if extraiu else f'Nao extraiu dados: {dados_extraidos}',
                   dados={'campos': dados_extraidos, 'extraiu': extraiu})

    # Sinalizar branch: true se extraiu, false se nao (fallback)
    atendimento._branch_saida = 'true' if extraiu else 'false'
    return None  # passa direto


# ── RESPONDEDOR IA ──

def _executar_ia_respondedor(atendimento, nodo, contexto):
    """Gera resposta conversacional com IA. PAUSA apos enviar."""
    config = nodo.configuracao
    integracao = _obter_integracao_ia(config, atendimento.fluxo.tenant)
    if not integracao:
        _registrar_log(atendimento, nodo, 'erro', 'Integracao IA nao configurada')
        return {'tipo': 'ia_respondedor', 'mensagem': config.get('mensagem_timeout', 'Erro ao processar.')}

    # Montar system prompt com variaveis substituidas
    system_prompt = config.get('system_prompt', '')
    system_prompt = _substituir_variaveis(system_prompt, contexto)

    # Adicionar dados do lead ao system prompt
    if atendimento.lead:
        lead = atendimento.lead
        system_prompt += f"\n\nDados do lead: Nome: {lead.nome_razaosocial}, Telefone: {lead.telefone}, Email: {lead.email or 'N/A'}, Cidade: {lead.cidade or 'N/A'}"

    # Injetar artigos da base de conhecimento (se disponivel no contexto)
    kb_contexto = contexto.get('_base_conhecimento')
    if kb_contexto:
        system_prompt += f"\n\nINFORMACOES DA BASE DE CONHECIMENTO (use para responder a duvida do candidato):\n{kb_contexto}"

    messages = [{'role': 'system', 'content': system_prompt}]

    # Historico se habilitado
    dados = atendimento.dados_respostas or {}
    historico = dados.get(f'ia_historico_{nodo.id}', [])
    mensagem_usuario = None
    if config.get('incluir_historico', True) and historico:
        max_hist = config.get('max_historico', 10)
        messages.extend(historico[-max_hist:])
        # Mensagem do usuario (so se ja tem historico, ou seja, multi-turno)
        mensagem_usuario = _get_ultima_mensagem(atendimento)
        if mensagem_usuario:
            messages.append({'role': 'user', 'content': mensagem_usuario})
    else:
        # Primeira execucao: enviar instrucao para iniciar a conversa
        messages.append({'role': 'user', 'content': 'Apresente as informacoes conforme instruido.'})

    resultado = _chamar_llm_simples(integracao, config.get('modelo', ''), messages)
    if not resultado:
        resultado = config.get('mensagem_timeout', 'Desculpe, nao consegui processar.')

    # Salvar historico
    dados = atendimento.dados_respostas or {}
    historico_key = f'ia_historico_{nodo.id}'
    historico = dados.get(historico_key, [])
    if mensagem_usuario:
        historico.append({'role': 'user', 'content': mensagem_usuario})
    historico.append({'role': 'assistant', 'content': resultado})
    dados[historico_key] = historico
    atendimento.dados_respostas = dados

    # PAUSA: setar nodo_atual
    atendimento.nodo_atual = nodo
    atendimento.save(update_fields=['dados_respostas', 'nodo_atual'])

    _registrar_log(atendimento, nodo, 'aguardando',
                   f'IA respondeu: {resultado[:100]}')

    return {
        'tipo': 'ia_respondedor',
        'mensagem': resultado,
    }


def processar_resposta_ia_respondedor(atendimento, resposta):
    """Processa resposta do usuario para um no ia_respondedor.
    Re-responde com IA (multi-turno) e segue o fluxo, passando a resposta para os proximos nos."""
    nodo = atendimento.nodo_atual
    config = nodo.configuracao

    # Salvar mensagem no historico
    dados = atendimento.dados_respostas or {}
    historico_key = f'ia_historico_{nodo.id}'
    historico = dados.get(historico_key, [])
    historico.append({'role': 'user', 'content': resposta})

    # Re-responder com IA (multi-turno conversacional)
    integracao = _obter_integracao_ia(config, atendimento.fluxo.tenant)
    if integracao:
        system_prompt = config.get('system_prompt', '')
        contexto = _construir_contexto(atendimento)
        system_prompt = _substituir_variaveis(system_prompt, contexto)
        if atendimento.lead:
            lead = atendimento.lead
            system_prompt += f"\n\nDados do lead: Nome: {lead.nome_razaosocial}, Telefone: {lead.telefone}, Email: {lead.email or 'N/A'}"

        messages = [{'role': 'system', 'content': system_prompt}]
        for m in historico:
            if isinstance(m, dict) and 'role' in m and 'content' in m:
                messages.append({'role': m['role'], 'content': m['content']})

        resposta_ia = _chamar_llm_simples(integracao, config.get('modelo', ''), messages)
        if resposta_ia:
            historico.append({'role': 'assistant', 'content': resposta_ia})

    dados[historico_key] = historico
    dados['_ultima_mensagem'] = resposta
    atendimento.dados_respostas = dados
    atendimento.nodo_atual = None
    atendimento.save(update_fields=['dados_respostas', 'nodo_atual'])

    # Seguir para o proximo no (passa a resposta do usuario para classificadores etc)
    contexto = _construir_contexto(atendimento)
    resultado = _seguir_conexoes(atendimento, nodo, contexto)

    # Se a IA respondeu, incluir a resposta antes do resultado do proximo no
    if integracao and resposta_ia:
        if resultado and resultado.get('mensagem'):
            resultado['mensagem'] = f"{resposta_ia}\n\n{resultado['mensagem']}"
        elif resultado:
            resultado['mensagem'] = resposta_ia

    return resultado


# ── AGENTE IA (multi-turno com tools) ──

def _executar_ia_agente_inicial(atendimento, nodo, contexto):
    """Inicia o agente IA. Envia primeira mensagem e PAUSA."""
    config = nodo.configuracao
    integracao = _obter_integracao_ia(config, atendimento.fluxo.tenant)
    if not integracao:
        _registrar_log(atendimento, nodo, 'erro', 'Integracao IA nao configurada')
        return {'tipo': 'ia_agente', 'mensagem': config.get('mensagem_timeout', 'Erro ao processar.')}

    # Detectar se chegou via fallback de uma questao
    nodo_retorno = None
    if atendimento.nodo_atual and atendimento.nodo_atual.tipo == 'questao' and atendimento.nodo_atual.pk != nodo.pk:
        nodo_retorno = atendimento.nodo_atual

    system_prompt = config.get('system_prompt', '')
    system_prompt = _substituir_variaveis(system_prompt, contexto)
    if atendimento.lead:
        lead = atendimento.lead
        system_prompt += f"\n\nDados do lead: Nome: {lead.nome_razaosocial}, Telefone: {lead.telefone}, Email: {lead.email or 'N/A'}, Cidade: {lead.cidade or 'N/A'}"
    elif contexto.get('assistente_modo'):
        # Assistente CRM: injetar dados do usuario vendedor
        _dados = atendimento.dados_respostas or {}
        usuario = getattr(atendimento, '_assistente_usuario', None)
        if not usuario and _dados.get('_assistente_usuario_id'):
            from django.contrib.auth.models import User
            usuario = User.objects.filter(pk=_dados['_assistente_usuario_id']).first()
        if usuario:
            nome = usuario.get_full_name() or usuario.username
            system_prompt += f"\n\nVoce esta atendendo o vendedor: {nome}"

    # Se veio de fallback, instruir o agente a retomar a pergunta naturalmente
    if nodo_retorno:
        titulo_questao = nodo_retorno.configuracao.get('titulo', '')
        if titulo_questao:
            system_prompt += (
                f"\n\nIMPORTANTE: O candidato estava respondendo a seguinte pergunta: \"{titulo_questao}\"\n"
                "Ele enviou uma mensagem que nao responde diretamente a essa pergunta. "
                "Responda a duvida dele de forma breve e educada, e no final retome a pergunta de forma natural e conversacional. "
                "NAO repita a pergunta exatamente como esta, reformule de forma resumida e amigavel."
            )

    # Injetar artigos da base de conhecimento (se disponivel)
    kb_contexto = contexto.get('_base_conhecimento')
    if kb_contexto:
        system_prompt += f"\n\nINFORMACOES DA BASE DE CONHECIMENTO (use para responder a duvida):\n{kb_contexto}"

    mensagem_usuario = _get_ultima_mensagem(atendimento)

    messages = [{'role': 'system', 'content': system_prompt}]
    if mensagem_usuario:
        messages.append({'role': 'user', 'content': mensagem_usuario})

    # Chamar LLM com tools
    resultado = _chamar_llm_com_tools(
        integracao, config.get('modelo', ''), messages,
        config, atendimento, contexto
    )

    # Salvar historico
    dados = atendimento.dados_respostas or {}
    historico_key = f'ia_agente_{nodo.id}'
    historico = {'messages': [], 'turnos': 0}
    if mensagem_usuario:
        historico['messages'].append({'role': 'user', 'content': mensagem_usuario})
    historico['messages'].append({'role': 'assistant', 'content': resultado})
    historico['turnos'] = 1
    dados[historico_key] = historico
    dados['_ultima_mensagem'] = mensagem_usuario or ''

    # Verificar saida imediata (one-shot: agente classifica e sai na primeira mensagem)
    import json as json_mod
    try:
        if '{' in resultado and 'sair' in resultado.lower():
            texto_limpo = resultado.strip()
            if texto_limpo.startswith('```'):
                texto_limpo = texto_limpo.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            parsed = json_mod.loads(texto_limpo)
            if parsed.get('sair'):
                motivo = parsed.get('motivo', '')
                _salvar_variavel(atendimento, 'motivo_saida', motivo)
                atendimento.dados_respostas = dados
                atendimento.nodo_atual = None
                atendimento.save(update_fields=['dados_respostas', 'nodo_atual'])
                _registrar_log(atendimento, nodo, 'sucesso', f'Agente IA (one-shot): {motivo}')
                contexto = _construir_contexto(atendimento)
                return _seguir_conexoes(atendimento, nodo, contexto)
    except (json_mod.JSONDecodeError, AttributeError):
        pass

    # Se veio de fallback de questao, retornar para a questao apos responder
    if nodo_retorno:
        atendimento.nodo_atual = nodo_retorno
        atendimento.dados_respostas = dados
        atendimento.save(update_fields=['dados_respostas', 'nodo_atual'])
        _registrar_log(atendimento, nodo, 'sucesso',
                       f'Agente IA (fallback): {resultado[:100]}. Retornando para questao {nodo_retorno.pk}')
        return {'tipo': 'ia_agente', 'mensagem': resultado}

    # PAUSA normal (agente conversacional standalone)
    atendimento.nodo_atual = nodo
    atendimento.dados_respostas = dados
    atendimento.save(update_fields=['dados_respostas', 'nodo_atual'])

    _registrar_log(atendimento, nodo, 'aguardando', f'Agente IA iniciou: {resultado[:100]}')

    return {'tipo': 'ia_agente', 'mensagem': resultado}


def processar_resposta_ia_agente(atendimento, resposta):
    """Processa resposta do usuario no agente IA multi-turno."""
    nodo = atendimento.nodo_atual
    config = nodo.configuracao

    dados = atendimento.dados_respostas or {}
    historico_key = f'ia_agente_{nodo.id}'
    historico = dados.get(historico_key, {'messages': [], 'turnos': 0})

    # Verificar max_turnos
    max_turnos = config.get('max_turnos', 10)
    if historico['turnos'] >= max_turnos:
        atendimento.nodo_atual = None
        atendimento.save(update_fields=['nodo_atual'])
        contexto = _construir_contexto(atendimento)
        _registrar_log(atendimento, nodo, 'sucesso', f'Agente IA: max_turnos atingido ({max_turnos})')
        return _seguir_conexoes(atendimento, nodo, contexto)

    integracao = _obter_integracao_ia(config, atendimento.fluxo.tenant)
    if not integracao:
        return {'tipo': 'ia_agente', 'mensagem': config.get('mensagem_timeout', 'Erro ao processar.')}

    # Reconstruir messages
    system_prompt = config.get('system_prompt', '')
    contexto = _construir_contexto(atendimento)
    system_prompt = _substituir_variaveis(system_prompt, contexto)
    if atendimento.lead:
        lead = atendimento.lead
        system_prompt += f"\n\nDados do lead: Nome: {lead.nome_razaosocial}, Telefone: {lead.telefone}, Email: {lead.email or 'N/A'}, Cidade: {lead.cidade or 'N/A'}"
    elif contexto.get('assistente_modo'):
        _dados = atendimento.dados_respostas or {}
        usuario = getattr(atendimento, '_assistente_usuario', None)
        if not usuario and _dados.get('_assistente_usuario_id'):
            from django.contrib.auth.models import User
            usuario = User.objects.filter(pk=_dados['_assistente_usuario_id']).first()
        if usuario:
            nome = usuario.get_full_name() or usuario.username
            system_prompt += f"\n\nVoce esta atendendo o vendedor: {nome}"

    messages = [{'role': 'system', 'content': system_prompt}]
    # Historico anterior (somente role + content para simplificar)
    for m in historico['messages']:
        if isinstance(m, dict) and 'role' in m and 'content' in m:
            messages.append({'role': m['role'], 'content': m['content']})
    # Nova mensagem
    messages.append({'role': 'user', 'content': resposta})

    # Chamar LLM com tools
    # Tools do config (sistema + customizadas)
    resultado = _chamar_llm_com_tools(
        integracao, config.get('modelo', ''), messages,
        config, atendimento, contexto
    )

    # Atualizar historico
    historico['messages'].append({'role': 'user', 'content': resposta})
    historico['messages'].append({'role': 'assistant', 'content': resultado})
    historico['turnos'] += 1
    dados[historico_key] = historico
    dados['_ultima_mensagem'] = resposta
    atendimento.dados_respostas = dados

    # Verificar condicao de saida (JSON {sair: true})
    import json as json_mod
    try:
        if '{' in resultado and 'sair' in resultado.lower():
            texto_limpo = resultado.strip()
            if texto_limpo.startswith('```'):
                texto_limpo = texto_limpo.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            parsed = json_mod.loads(texto_limpo)
            if parsed.get('sair'):
                motivo = parsed.get('motivo', '')
                _salvar_variavel(atendimento, 'motivo_saida', motivo)
                atendimento.nodo_atual = None
                atendimento.save(update_fields=['dados_respostas', 'nodo_atual'])
                _registrar_log(atendimento, nodo, 'sucesso', f'Agente IA finalizou: {motivo}')
                return _seguir_conexoes(atendimento, nodo, contexto)
    except (json_mod.JSONDecodeError, AttributeError):
        pass

    # PAUSA: continua esperando
    atendimento.save(update_fields=['dados_respostas'])
    _registrar_log(atendimento, nodo, 'aguardando', f'Agente IA turno {historico["turnos"]}: {resultado[:100]}')

    return {'tipo': 'ia_agente', 'mensagem': resultado}


def _consultar_base_para_fallback(mensagem, atendimento):
    """Consulta base de conhecimento para enriquecer o fallback.
    Retorna texto com artigos encontrados ou None.
    Registra PerguntaSemResposta se nao encontrou."""
    from django.db.models import Q
    from apps.suporte.models import ArtigoConhecimento, PerguntaSemResposta

    if not mensagem or len(mensagem.strip()) < 3:
        return None

    tenant = atendimento.fluxo.tenant

    # Extrair termos relevantes (limpar pontuacao)
    import re as _re
    palavras = _re.findall(r'[a-zA-ZÀ-ÿ]+', mensagem.lower())
    termos = [t for t in palavras if len(t) >= 3 and t not in _STOP_WORDS_PT]
    if not termos:
        return None

    base_qs = ArtigoConhecimento.all_tenants.filter(tenant=tenant, publicado=True)

    # Buscar por titulo/tags
    filtro = Q()
    for termo in termos[:5]:
        filtro |= Q(titulo__icontains=termo) | Q(tags__icontains=termo)
    artigos = list(base_qs.filter(filtro).distinct()[:3])

    # Fallback: buscar no conteudo
    if not artigos:
        filtro_conteudo = Q()
        for termo in termos[:3]:
            filtro_conteudo &= Q(conteudo__icontains=termo)
        artigos = list(base_qs.filter(filtro_conteudo).distinct()[:3])

    if artigos:
        resultado = '\n\n'.join(
            f'{art.titulo}: {art.conteudo[:300]}' for art in artigos
        )
        _registrar_log(atendimento, atendimento.nodo_atual, 'sucesso',
                       f'Base conhecimento: {len(artigos)} artigo(s) encontrado(s)')
        return resultado

    # Nao encontrou — registrar pergunta
    try:
        primeiro_termo = termos[0] if termos else mensagem[:30]
        existente = PerguntaSemResposta.all_tenants.filter(
            tenant=tenant, status='pendente',
            pergunta__icontains=primeiro_termo,
        ).first()
        if existente:
            existente.ocorrencias += 1
            existente.save(update_fields=['ocorrencias'])
        else:
            PerguntaSemResposta.objects.create(
                tenant=tenant, pergunta=mensagem,
                lead=atendimento.lead,
            )
        _registrar_log(atendimento, atendimento.nodo_atual, 'sucesso',
                       f'Base conhecimento: pergunta registrada "{mensagem[:50]}"')
    except Exception as e:
        logger.warning(f'Erro ao registrar pergunta sem resposta: {e}')

    return None


_STOP_WORDS_PT = {
    'a', 'o', 'e', 'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
    'um', 'uma', 'uns', 'umas', 'para', 'por', 'com', 'sem', 'que', 'se', 'como',
    'mais', 'ou', 'ao', 'aos', 'as', 'os', 'eu', 'ele', 'ela', 'nos', 'eles', 'elas',
    'meu', 'seu', 'sua', 'ter', 'ser', 'esta', 'este', 'isso', 'esse', 'essa',
    'tem', 'sao', 'foi', 'quais', 'qual', 'quando', 'onde', 'quem', 'pode',
    'ja', 'nao', 'sim', 'muito', 'bem', 'vai', 'vou', 'ta', 'to', 'me',
}


def _executar_consulta_base_conhecimento(pergunta, atendimento):
    """Busca artigos na base de conhecimento e registra perguntas sem resposta."""
    from django.db.models import Q
    from apps.suporte.models import ArtigoConhecimento, PerguntaSemResposta

    if not pergunta or len(pergunta.strip()) < 3:
        return 'Pergunta muito curta para buscar na base.'

    tenant = atendimento.tenant

    # Filtrar stop words e termos curtos
    termos = [
        t.lower() for t in pergunta.strip().split()
        if len(t) >= 3 and t.lower() not in _STOP_WORDS_PT
    ]

    if not termos:
        return 'Nenhuma informacao encontrada na base de conhecimento sobre esse assunto.'

    base_qs = ArtigoConhecimento.objects.filter(tenant=tenant, publicado=True)

    # 1) Buscar por titulo e tags (OR — qualquer termo relevante)
    filtro_titulo = Q()
    for termo in termos[:5]:
        filtro_titulo |= Q(titulo__icontains=termo) | Q(tags__icontains=termo)

    artigos = list(base_qs.filter(filtro_titulo).distinct()[:3])

    # 2) Se não encontrou em titulo/tags, buscar no conteudo (AND — todos os termos)
    if not artigos:
        filtro_conteudo = Q()
        for termo in termos[:5]:
            filtro_conteudo &= Q(conteudo__icontains=termo)
        artigos = list(base_qs.filter(filtro_conteudo).distinct()[:3])

    if artigos:
        resultado = 'Artigos encontrados na base de conhecimento:\n\n'
        for art in artigos:
            resultado += f'### {art.titulo}\n{art.conteudo[:500]}\n\n'
        return resultado

    # Nenhum artigo encontrado — registrar pergunta
    try:
        primeiro_termo = termos[0] if termos else pergunta[:30]
        existente = PerguntaSemResposta.objects.filter(
            tenant=tenant,
            status='pendente',
            pergunta__icontains=primeiro_termo,
        ).first()

        if existente:
            existente.ocorrencias += 1
            existente.save(update_fields=['ocorrencias'])
        else:
            PerguntaSemResposta.objects.create(
                tenant=tenant,
                pergunta=pergunta,
                lead=atendimento.lead,
                conversa=atendimento.conversa if hasattr(atendimento, 'conversa') else None,
            )
    except Exception as e:
        logger.warning(f'Erro ao registrar pergunta sem resposta: {e}')

    return 'Nenhuma informacao encontrada na base de conhecimento sobre esse assunto.'


def _chamar_llm_com_tools(integracao, modelo, messages, config, atendimento, contexto):
    """Chama LLM com tools customizadas. Executa tool_calls em loop. Retorna texto final."""
    import json as json_mod

    tipo = integracao.tipo
    extras = integracao.configuracoes_extras or {}
    api_key = integracao.api_key or extras.get('api_key', '') or integracao.access_token or integracao.client_secret or ''
    modelo = modelo or extras.get('modelo', '')

    # Montar tools: customizadas + sistema
    tools_openai = []
    tools_custom_map = {}  # nome -> prompt

    for tc in config.get('tools_customizadas', []):
        if not tc.get('nome'):
            continue
        tools_openai.append({
            'type': 'function',
            'function': {
                'name': tc['nome'],
                'description': tc.get('descricao', ''),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'mensagem': {'type': 'string', 'description': 'A mensagem do usuario para este especialista'},
                    },
                    'required': ['mensagem'],
                },
            },
        })
        tools_custom_map[tc['nome']] = tc.get('prompt', '')

    # Tools do sistema
    for tool_id in config.get('tools_habilitadas', []):
        if tool_id == 'atualizar_lead':
            tools_openai.append({
                'type': 'function',
                'function': {
                    'name': 'atualizar_lead',
                    'description': 'Atualiza um campo do lead/prospecto',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'campo': {'type': 'string', 'description': 'Nome do campo'},
                            'valor': {'type': 'string', 'description': 'Novo valor'},
                        },
                        'required': ['campo', 'valor'],
                    },
                },
            })
        elif tool_id == 'consultar_base_conhecimento':
            tools_openai.append({
                'type': 'function',
                'function': {
                    'name': 'consultar_base_conhecimento',
                    'description': 'Consulta a base de conhecimento da empresa para buscar informacoes sobre produtos, servicos, procedimentos e duvidas frequentes. Use sempre que o usuario fizer uma pergunta que pode ter resposta na base.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'pergunta': {'type': 'string', 'description': 'A pergunta ou tema a buscar na base de conhecimento'},
                        },
                        'required': ['pergunta'],
                    },
                },
            })
        else:
            # Tools do Assistente CRM (importadas dinamicamente)
            from apps.assistente.tools import TOOLS_ASSISTENTE
            if tool_id in TOOLS_ASSISTENTE:
                tool_def = TOOLS_ASSISTENTE[tool_id]
                tools_openai.append({
                    'type': 'function',
                    'function': {
                        'name': tool_id,
                        'description': tool_def['description'],
                        'parameters': tool_def['parameters'],
                    },
                })

    if not tools_openai:
        # Sem tools, chamada simples
        resultado = _chamar_llm_simples(integracao, modelo, messages)
        return resultado or config.get('mensagem_timeout', 'Desculpe, nao consegui processar.')

    # Chamada com tools (OpenAI/Groq format)
    if tipo not in ('openai', 'groq'):
        # Fallback para providers que nao suportam tool calling
        resultado = _chamar_llm_simples(integracao, modelo, messages)
        return resultado or config.get('mensagem_timeout', 'Desculpe, nao consegui processar.')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    url = integracao.base_url or ('https://api.openai.com/v1/chat/completions' if tipo == 'openai' else 'https://api.groq.com/openai/v1/chat/completions')

    max_iterations = 5
    current_messages = list(messages)

    for _ in range(max_iterations):
        payload = {
            'model': modelo or ('gpt-4o-mini' if tipo == 'openai' else 'llama-3.1-8b-instant'),
            'messages': current_messages,
            'tools': tools_openai,
            'max_tokens': 1500,
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=30)
            if res.status_code != 200:
                logger.error(f'LLM tool calling {tipo} retornou {res.status_code}: {res.text[:200]}')
                return config.get('mensagem_timeout', 'Desculpe, nao consegui processar.')

            data = res.json()
            choice = data.get('choices', [{}])[0]
            message = choice.get('message', {})
            finish_reason = choice.get('finish_reason', '')

            # Se retornou texto direto (sem tool call)
            if finish_reason != 'tool_calls' and message.get('content'):
                return message['content']

            # Se chamou tools
            tool_calls = message.get('tool_calls', [])
            if not tool_calls:
                return message.get('content', '') or config.get('mensagem_timeout', 'Desculpe, nao consegui processar.')

            # Adicionar mensagem do assistant com tool_calls ao historico
            current_messages.append(message)

            # Executar cada tool
            for tc in tool_calls:
                func_name = tc.get('function', {}).get('name', '')
                func_args_str = tc.get('function', {}).get('arguments', '{}')
                tc_id = tc.get('id', '')

                try:
                    func_args = json_mod.loads(func_args_str)
                except json_mod.JSONDecodeError:
                    func_args = {}

                tool_result = ''

                # Tool customizada (agente especialista)
                if func_name in tools_custom_map:
                    prompt_especialista = tools_custom_map[func_name]
                    mensagem_usuario = func_args.get('mensagem', '')

                    # Adicionar contexto do lead ao prompt
                    prompt_completo = _substituir_variaveis(prompt_especialista, contexto)
                    if atendimento.lead:
                        lead = atendimento.lead
                        prompt_completo += f"\n\nDados do lead: Nome: {lead.nome_razaosocial}, Telefone: {lead.telefone}, Email: {lead.email or 'N/A'}"

                    resp_especialista = _chamar_llm_simples(
                        integracao, modelo,
                        [
                            {'role': 'system', 'content': prompt_completo},
                            {'role': 'user', 'content': mensagem_usuario},
                        ]
                    )
                    tool_result = resp_especialista or 'Sem resposta do especialista.'
                    _registrar_log(atendimento, atendimento.nodo_atual, 'sucesso',
                                   f'Tool {func_name}: {tool_result[:100]}')

                # Tool do sistema
                elif func_name == 'atualizar_lead' and atendimento.lead:
                    campo = func_args.get('campo', '')
                    valor = func_args.get('valor', '')
                    if campo and valor and hasattr(atendimento.lead, campo):
                        setattr(atendimento.lead, campo, valor)
                        atendimento.lead.save(update_fields=[campo])
                        tool_result = f'Campo {campo} atualizado para {valor}'
                    else:
                        tool_result = f'Campo {campo} nao encontrado'

                elif func_name == 'consultar_base_conhecimento':
                    tool_result = _executar_consulta_base_conhecimento(
                        func_args.get('pergunta', ''),
                        atendimento,
                    )
                    _registrar_log(atendimento, atendimento.nodo_atual, 'sucesso',
                                   f'Tool base_conhecimento: {tool_result[:100]}')

                else:
                    # Tentar tools do Assistente CRM
                    from apps.assistente.tools import TOOLS_ASSISTENTE
                    if func_name in TOOLS_ASSISTENTE:
                        tool_func = TOOLS_ASSISTENTE[func_name]['func']
                        # Recuperar usuario e tenant do assistente (runtime ou dados_respostas)
                        _dados = atendimento.dados_respostas or {}
                        usuario = getattr(atendimento, '_assistente_usuario', None)
                        tenant = getattr(atendimento, '_assistente_tenant', None)
                        if not usuario and _dados.get('_assistente_usuario_id'):
                            from django.contrib.auth.models import User
                            usuario = User.objects.filter(pk=_dados['_assistente_usuario_id']).first()
                        if not tenant and _dados.get('_assistente_tenant_id'):
                            from apps.sistema.models import Tenant
                            tenant = Tenant.objects.filter(pk=_dados['_assistente_tenant_id']).first()
                        if not tenant:
                            tenant = atendimento.fluxo.tenant if atendimento.fluxo else atendimento.tenant
                        try:
                            tool_result = tool_func(tenant, usuario, func_args)
                            _registrar_log(atendimento, atendimento.nodo_atual, 'sucesso',
                                           f'Tool {func_name}: {tool_result[:100]}')
                        except Exception as e:
                            tool_result = f'Erro ao executar {func_name}: {str(e)}'
                            logger.error(f'Tool {func_name} erro: {e}')
                    else:
                        tool_result = f'Tool {func_name} nao encontrada'

                # Adicionar resultado da tool ao historico
                current_messages.append({
                    'role': 'tool',
                    'tool_call_id': tc_id,
                    'content': tool_result,
                })

            # Re-chamar LLM com resultados das tools (loop continua)

        except Exception as e:
            logger.error(f'Erro tool calling: {e}')
            return config.get('mensagem_timeout', 'Desculpe, nao consegui processar.')

    # Max iterations atingido
    return config.get('mensagem_timeout', 'Desculpe, nao consegui processar.')
