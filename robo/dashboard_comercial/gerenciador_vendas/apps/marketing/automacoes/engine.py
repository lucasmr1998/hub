"""
Engine de automações — dual-mode.

Modo legacy (modo_fluxo=False): evento → condições AND → ações sequenciais
Modo fluxo (modo_fluxo=True): evento → BFS no grafo de nodos → branching, delays, ações

Responsável por:
1. Receber eventos (via signals ou chamada direta)
2. Buscar regras ativas para o evento
3. Verificar controles (rate limit, cooldown)
4. Avaliar condições / traversar grafo
5. Executar ações
6. Registrar logs
"""
import json
import logging
from datetime import timedelta

import requests
from django.contrib.auth.models import User
from django.utils import timezone

from apps.sistema.middleware import get_current_tenant

logger = logging.getLogger(__name__)


# ============================================================================
# PONTO DE ENTRADA
# ============================================================================

def disparar_evento(evento, contexto=None, tenant=None):
    """Ponto de entrada principal. Chamado pelos signals ou manualmente."""
    from .models import RegraAutomacao

    if contexto is None:
        contexto = {}
    if tenant is None:
        tenant = get_current_tenant()
    if tenant is None:
        logger.warning(f'Automações: evento {evento} sem tenant, ignorando.')
        return

    regras = RegraAutomacao.all_tenants.filter(
        tenant=tenant, evento=evento, ativa=True,
    ).prefetch_related('condicoes', 'acoes', 'nodos', 'conexoes')

    for regra in regras:
        try:
            # Extrair lead do contexto para controles e logs
            lead = contexto.get('lead')

            # Verificar controles (rate limit, cooldown)
            if lead and hasattr(lead, 'pk') and not _verificar_controles(regra, lead):
                logger.debug(f'Automações: regra {regra.pk} bloqueada por controle para lead {lead.pk}')
                continue

            if regra.modo_fluxo:
                _processar_fluxo(regra, contexto, lead)
            else:
                _processar_regra_legacy(regra, contexto, lead)
        except Exception as e:
            logger.error(f'Automações: erro ao processar regra {regra.pk} ({regra.nome}): {e}')
            _registrar_log(regra, None, 'erro', contexto, str(e), lead=lead)
            regra.total_execucoes += 1
            regra.total_erro += 1
            regra.save(update_fields=['total_execucoes', 'total_erro'])


# ============================================================================
# CONTROLES DE EXECUÇÃO
# ============================================================================

def _verificar_controles(regra, lead):
    """Verifica rate limits e cooldown antes de processar."""
    from .models import ControleExecucao

    if regra.max_execucoes_por_lead == 0 and regra.cooldown_horas == 0:
        return True

    controle, created = ControleExecucao.all_tenants.get_or_create(
        tenant=regra.tenant, lead=lead, regra=regra,
        defaults={'primeira_execucao_periodo': timezone.now()},
    )

    agora = timezone.now()

    # Reset período se expirou
    if controle.primeira_execucao_periodo:
        periodo_delta = timedelta(hours=regra.periodo_limite_horas)
        if agora - controle.primeira_execucao_periodo > periodo_delta:
            controle.total_execucoes_periodo = 0
            controle.primeira_execucao_periodo = agora

    # Verificar max execuções no período
    if regra.max_execucoes_por_lead > 0:
        if controle.total_execucoes_periodo >= regra.max_execucoes_por_lead:
            return False

    # Verificar cooldown
    if regra.cooldown_horas > 0 and controle.ultima_execucao:
        cooldown_delta = timedelta(hours=regra.cooldown_horas)
        if agora - controle.ultima_execucao < cooldown_delta:
            return False

    # Atualizar contadores
    controle.total_execucoes_periodo += 1
    controle.ultima_execucao = agora
    controle.save()
    return True


# ============================================================================
# MODO LEGACY (linear)
# ============================================================================

def _processar_regra_legacy(regra, contexto, lead=None):
    """Modo legacy: condições AND → ações sequenciais."""
    for condicao in regra.condicoes.all():
        if not condicao.avaliar(contexto):
            return

    for acao in regra.acoes.all():
        try:
            if acao.delay_ativo and acao.delay_valor > 0:
                _agendar_acao_legacy(regra, acao, contexto, lead)
            else:
                _executar_acao_legacy(regra, acao, contexto, lead)
        except Exception as e:
            logger.error(f'Automações: erro na ação {acao.pk} ({acao.tipo}): {e}')
            _registrar_log(regra, acao, 'erro', contexto, str(e), lead=lead)
            regra.total_execucoes += 1
            regra.total_erro += 1
            regra.save(update_fields=['total_execucoes', 'total_erro'])


def _executar_acao_legacy(regra, acao, contexto, lead=None):
    """Executa uma ação do modo legacy."""
    executor = _get_executor(acao.tipo)
    if not executor:
        raise ValueError(f'Tipo de ação não implementado: {acao.tipo}')

    resultado = executor(regra, acao, contexto)
    _registrar_log(regra, acao, 'sucesso', contexto, resultado or 'OK', lead=lead)
    regra.total_execucoes += 1
    regra.total_sucesso += 1
    regra.save(update_fields=['total_execucoes', 'total_sucesso'])


def _agendar_acao_legacy(regra, acao, contexto, lead=None):
    """Agenda ação com delay para execução futura."""
    from .models import ExecucaoPendente

    data_agendada = timezone.now() + acao.delay_timedelta
    ExecucaoPendente.all_tenants.create(
        tenant=regra.tenant, regra=regra, acao=acao, lead=lead,
        contexto_json=_serializar_contexto(contexto),
        data_agendada=data_agendada,
    )
    _registrar_log(regra, acao, 'agendado', contexto,
                   f'Agendado para {data_agendada:%d/%m/%Y %H:%M}',
                   lead=lead, data_agendada=data_agendada)


# ============================================================================
# MODO FLUXO (grafo visual)
# ============================================================================

def _processar_fluxo(regra, contexto, lead=None):
    """Modo fluxo: BFS no grafo de nodos."""
    trigger = regra.nodos.filter(tipo='trigger').first()
    if not trigger:
        return

    _executar_nodo_e_seguir(regra, trigger, contexto, lead)


def _executar_nodo_e_seguir(regra, nodo, contexto, lead):
    """Executa um nodo e segue conexões de saída recursivamente."""

    if nodo.tipo == 'trigger':
        # Trigger: registrar e passar para o próximo
        _registrar_log(regra, None, 'sucesso', contexto,
                       f'Gatilho: {nodo.subtipo}', lead=lead, nodo=nodo)
        for conexao in nodo.saidas.filter(tipo_saida='default'):
            _executar_nodo_e_seguir(regra, conexao.nodo_destino, contexto, lead)

    elif nodo.tipo == 'condition':
        # Avaliar condição e seguir branch true ou false
        resultado = _avaliar_condicao_nodo(nodo, contexto)
        branch = 'true' if resultado else 'false'
        _registrar_log(regra, None, 'sucesso', contexto,
                       f'Condição: {nodo.subtipo} → {branch}',
                       lead=lead, nodo=nodo)
        for conexao in nodo.saidas.filter(tipo_saida=branch):
            _executar_nodo_e_seguir(regra, conexao.nodo_destino, contexto, lead)

    elif nodo.tipo == 'delay':
        # Criar execução pendente e parar (retoma via cron)
        from .models import ExecucaoPendente
        config = nodo.configuracao
        delay = _calcular_delay_nodo(config)
        data_agendada = timezone.now() + delay

        ExecucaoPendente.all_tenants.create(
            tenant=regra.tenant, regra=regra, nodo=nodo, lead=lead,
            contexto_json=_serializar_contexto(contexto),
            data_agendada=data_agendada,
        )
        _registrar_log(regra, None, 'agendado', contexto,
                       f'Delay: {config.get("valor", 0)} {config.get("unidade", "minutos")}',
                       lead=lead, nodo=nodo, data_agendada=data_agendada)

    elif nodo.tipo == 'action':
        # Executar ação e seguir conexões
        try:
            _executar_acao_nodo(regra, nodo, contexto, lead)
        except Exception as e:
            logger.error(f'Automações: erro no nodo {nodo.pk} ({nodo.subtipo}): {e}')
            _registrar_log(regra, None, 'erro', contexto, str(e), lead=lead, nodo=nodo)
            regra.total_execucoes += 1
            regra.total_erro += 1
            regra.save(update_fields=['total_execucoes', 'total_erro'])
            return  # Não seguir em caso de erro

        for conexao in nodo.saidas.filter(tipo_saida='default'):
            _executar_nodo_e_seguir(regra, conexao.nodo_destino, contexto, lead)


def _avaliar_condicao_nodo(nodo, contexto):
    """Avalia condição de um nodo condition."""
    config = nodo.configuracao
    campo = config.get('campo', '')
    operador = config.get('operador', 'igual')
    valor = config.get('valor', '')

    if not campo or not valor:
        return True  # Sem condição configurada, passa

    # Resolver valor do campo no contexto
    valor_campo = _resolver_campo_contexto(campo, contexto)
    if valor_campo is None:
        return False

    # Comparar
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
    """Resolve campo.subcampo no contexto."""
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


def _calcular_delay_nodo(config):
    """Calcula timedelta a partir da config de um nodo delay."""
    valor = int(config.get('valor', 0))
    unidade = config.get('unidade', 'minutos')
    if unidade == 'minutos':
        return timedelta(minutes=valor)
    elif unidade == 'horas':
        return timedelta(hours=valor)
    elif unidade == 'dias':
        return timedelta(days=valor)
    return timedelta(0)


class _NodoAcaoAdapter:
    """Adapta NodoFluxo para a interface que os executores esperam (como AcaoRegra)."""

    def __init__(self, nodo):
        self.pk = nodo.pk
        self.tipo = nodo.subtipo
        self.configuracao = nodo.configuracao.get('template', '')
        # Para executores que parseiam linhas da config
        if not self.configuracao and nodo.configuracao:
            linhas = []
            for k, v in nodo.configuracao.items():
                if k not in ('template',):
                    linhas.append(f'{k}: {v}')
            self.configuracao = '\n'.join(linhas)


def _executar_acao_nodo(regra, nodo, contexto, lead):
    """Executa um nodo de ação usando os executores existentes."""
    executor = _get_executor(nodo.subtipo)
    if not executor:
        raise ValueError(f'Tipo de ação não implementado: {nodo.subtipo}')

    adapter = _NodoAcaoAdapter(nodo)
    resultado = executor(regra, adapter, contexto)

    _registrar_log(regra, None, 'sucesso', contexto, resultado or 'OK', lead=lead, nodo=nodo)
    regra.total_execucoes += 1
    regra.total_sucesso += 1
    regra.save(update_fields=['total_execucoes', 'total_sucesso'])


# ============================================================================
# EXECUÇÃO DE PENDENTES (chamado pelo cron)
# ============================================================================

def executar_pendentes(tenant=None):
    """Executa ações pendentes (delays) que já passaram do horário agendado."""
    from .models import ExecucaoPendente

    agora = timezone.now()
    qs = ExecucaoPendente.all_tenants.filter(status='pendente', data_agendada__lte=agora)
    if tenant:
        qs = qs.filter(tenant=tenant)

    count = 0
    for pendente in qs.select_related('regra', 'nodo', 'acao', 'lead'):
        try:
            contexto = pendente.contexto_json
            if pendente.lead:
                contexto['lead'] = pendente.lead

            if pendente.nodo:
                # Modo fluxo: retomar a partir do nodo de delay
                for conexao in pendente.nodo.saidas.filter(tipo_saida='default'):
                    _executar_nodo_e_seguir(pendente.regra, conexao.nodo_destino, contexto, pendente.lead)
            elif pendente.acao:
                # Modo legacy: executar a ação diretamente
                _executar_acao_legacy(pendente.regra, pendente.acao, contexto, pendente.lead)

            pendente.status = 'executado'
            pendente.data_execucao = agora
            pendente.save(update_fields=['status', 'data_execucao'])
            count += 1
        except Exception as e:
            pendente.status = 'erro'
            pendente.resultado = str(e)[:500]
            pendente.save(update_fields=['status', 'resultado'])
            logger.error(f'Automações: erro ao executar pendente {pendente.pk}: {e}')

    return count


# ============================================================================
# LOG
# ============================================================================

def _registrar_log(regra, acao, status, contexto, resultado, lead=None, nodo=None, data_agendada=None):
    """Cria registro de log."""
    from .models import LogExecucao

    dados_safe = _serializar_contexto(contexto)

    LogExecucao.all_tenants.create(
        tenant=regra.tenant,
        regra=regra,
        acao=acao,
        nodo=nodo,
        lead=lead if lead and hasattr(lead, 'pk') else None,
        status=status,
        evento_dados=dados_safe,
        resultado=resultado[:500] if resultado else '',
        data_agendada=data_agendada,
    )


def _serializar_contexto(contexto):
    """Serializa contexto removendo objetos não-JSON."""
    dados = {}
    for k, v in contexto.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            dados[k] = v
        elif hasattr(v, 'pk'):
            dados[k] = f'{v.__class__.__name__}(pk={v.pk})'
        else:
            dados[k] = str(v)
    return dados


# ============================================================================
# EXECUTORES DE AÇÕES
# ============================================================================

def _get_executor(tipo):
    """Retorna a função executora para um tipo de ação."""
    return {
        'enviar_whatsapp': _acao_enviar_whatsapp,
        'enviar_email': _acao_enviar_email,
        'notificacao_sistema': _acao_notificacao_sistema,
        'criar_tarefa': _acao_criar_tarefa,
        'mover_estagio': _acao_mover_estagio,
        'atribuir_responsavel': _acao_atribuir_responsavel,
        'dar_pontos': _acao_dar_pontos,
        'webhook': _acao_webhook,
    }.get(tipo)


def _substituir_variaveis(template, contexto):
    """Substitui {{variavel}} no template pelos valores do contexto."""
    resultado = template
    for key, value in contexto.items():
        if isinstance(value, (str, int, float)):
            resultado = resultado.replace('{{' + key + '}}', str(value))
        elif hasattr(value, 'pk'):
            for attr in ['nome', 'nome_razaosocial', 'titulo', 'email', 'telefone']:
                if hasattr(value, attr):
                    resultado = resultado.replace('{{' + f'{key}_{attr}' + '}}', str(getattr(value, attr, '')))
            resultado = resultado.replace('{{' + key + '}}', str(value))
    return resultado


def _acao_enviar_whatsapp(regra, acao, contexto):
    config = acao.configuracao
    mensagem = _substituir_variaveis(config, contexto)

    telefone = contexto.get('telefone', '')
    if not telefone and hasattr(contexto.get('lead'), 'telefone'):
        telefone = contexto['lead'].telefone

    webhook_url = 'https://automation-n8n.v4riem.easypanel.host/webhook/5a88a51b-f099-4ea9-afb5-68a10254bcdd'

    try:
        resp = requests.post(webhook_url, json={
            'tipo': 'automacao', 'regra': regra.nome,
            'telefone': telefone, 'mensagem': mensagem,
        }, timeout=15)
        return f'WhatsApp enviado (status {resp.status_code})'
    except requests.RequestException as e:
        raise Exception(f'Falha ao enviar WhatsApp: {e}')


def _acao_enviar_email(regra, acao, contexto):
    """Envia e-mail via webhook N8N."""
    config = acao.configuracao
    mensagem = _substituir_variaveis(config, contexto)

    email = contexto.get('email', '')
    if not email:
        lead = contexto.get('lead')
        if lead and hasattr(lead, 'email'):
            email = lead.email or ''
    if not email:
        return 'E-mail do destinatário não encontrado'

    assunto = f'Automação: {regra.nome}'
    corpo = mensagem
    for line in mensagem.split('\n'):
        if line.lower().startswith('assunto:'):
            assunto = line.split(':', 1)[1].strip()
        elif line.lower().startswith('corpo:'):
            corpo = line.split(':', 1)[1].strip()

    webhook_url = 'https://automation-n8n.v4riem.easypanel.host/webhook/5a88a51b-f099-4ea9-afb5-68a10254bcdd'

    try:
        resp = requests.post(webhook_url, json={
            'tipo': 'email', 'regra': regra.nome,
            'email': email, 'assunto': assunto, 'mensagem': corpo,
        }, timeout=15)
        return f'E-mail enviado para {email} (status {resp.status_code})'
    except requests.RequestException as e:
        raise Exception(f'Falha ao enviar e-mail: {e}')


def _acao_atribuir_responsavel(regra, acao, contexto):
    """Atribui responsável à oportunidade (round-robin ou fixo)."""
    from apps.comercial.crm.models import OportunidadeVenda
    from apps.sistema.models import PerfilUsuario

    oportunidade = contexto.get('oportunidade')
    if not oportunidade:
        lead = contexto.get('lead')
        if lead and hasattr(lead, 'pk'):
            oportunidade = OportunidadeVenda.objects.filter(lead=lead).first()
    if not oportunidade:
        return 'Sem oportunidade para atribuir'

    config = acao.configuracao.strip().lower()

    if 'round-robin' in config or 'auto' in config:
        perfis = PerfilUsuario.objects.filter(
            tenant=regra.tenant, user__is_staff=True, user__is_active=True,
        ).select_related('user')
        if not perfis.exists():
            return 'Nenhum agente disponível para round-robin'
        from apps.comercial.crm.models import OportunidadeVenda as OV
        counts = {}
        for p in perfis:
            counts[p.user_id] = OV.objects.filter(responsavel=p.user, ativo=True).count()
        user_id = min(counts, key=counts.get)
        from django.contrib.auth.models import User
        responsavel = User.objects.get(pk=user_id)
    else:
        from django.contrib.auth.models import User
        responsavel = User.objects.filter(
            is_staff=True, username__icontains=config.split(':')[-1].strip()
        ).first()
        if not responsavel:
            return f'Responsável não encontrado: {config}'

    oportunidade.responsavel = responsavel
    oportunidade.save(update_fields=['responsavel'])
    return f'Responsável atribuído: {responsavel.get_full_name() or responsavel.username}'


def _acao_notificacao_sistema(regra, acao, contexto):
    from apps.notificacoes.models import Notificacao, TipoNotificacao, CanalNotificacao

    mensagem = _substituir_variaveis(acao.configuracao, contexto)
    tipo = TipoNotificacao.all_tenants.filter(tenant=regra.tenant, codigo='lead_novo').first()
    canal = CanalNotificacao.all_tenants.filter(tenant=regra.tenant, codigo='sistema').first()

    if tipo and canal:
        Notificacao.all_tenants.create(
            tenant=regra.tenant, tipo=tipo, canal=canal,
            titulo=f'Automação: {regra.nome}', mensagem=mensagem, status='enviada',
        )
        return 'Notificação criada'
    return 'Tipo/canal de notificação não encontrado'


def _acao_criar_tarefa(regra, acao, contexto):
    from apps.comercial.crm.models import TarefaCRM
    from apps.sistema.models import PerfilUsuario

    config_lines = acao.configuracao.strip().split('\n')
    titulo = _substituir_variaveis(config_lines[0] if config_lines else f'Tarefa: {regra.nome}', contexto)
    tipo_tarefa = 'followup'
    prioridade = 'normal'
    for line in config_lines:
        if line.lower().startswith('tipo:'):
            tipo_tarefa = line.split(':', 1)[1].strip()
        elif line.lower().startswith('prioridade:'):
            prioridade = line.split(':', 1)[1].strip()
        elif line.lower().startswith('titulo:') or line.lower().startswith('título:'):
            titulo = _substituir_variaveis(line.split(':', 1)[1].strip(), contexto)

    lead = contexto.get('lead')
    oportunidade = contexto.get('oportunidade')
    responsavel = contexto.get('responsavel')
    if responsavel is None and lead and hasattr(lead, 'responsavel'):
        responsavel = getattr(lead, 'responsavel', None)
    if responsavel is None:
        perfil = PerfilUsuario.objects.filter(tenant=regra.tenant, user__is_staff=True).first()
        responsavel = perfil.user if perfil else User.objects.filter(is_superuser=True).first()
    if not responsavel:
        return 'Nenhum responsável disponível'

    tarefa = TarefaCRM.objects.create(
        tenant=regra.tenant, titulo=titulo, tipo=tipo_tarefa, prioridade=prioridade,
        status='pendente',
        lead=lead if lead and hasattr(lead, 'pk') else None,
        oportunidade=oportunidade if oportunidade and hasattr(oportunidade, 'pk') else None,
        responsavel=responsavel,
        data_vencimento=timezone.now() + timedelta(days=1),
    )
    return f'Tarefa criada (pk={tarefa.pk})'


def _acao_mover_estagio(regra, acao, contexto):
    from apps.comercial.crm.models import PipelineEstagio

    oportunidade = contexto.get('oportunidade')
    if not oportunidade:
        return 'Sem oportunidade no contexto'

    config_lines = acao.configuracao.strip().split('\n')
    estagio_slug = ''
    for line in config_lines:
        if 'estagio' in line.lower() or 'estágio' in line.lower():
            estagio_slug = line.split(':', 1)[1].strip()

    if not estagio_slug:
        return 'Estágio não especificado'

    estagio = PipelineEstagio.objects.filter(
        pipeline=oportunidade.pipeline, slug=estagio_slug,
    ).first()
    if not estagio:
        return f'Estágio "{estagio_slug}" não encontrado'

    oportunidade.estagio = estagio
    oportunidade.save(update_fields=['estagio'])
    return f'Oportunidade movida para {estagio.nome}'


def _acao_dar_pontos(regra, acao, contexto):
    from apps.cs.clube.models import MembroClube

    config_lines = acao.configuracao.strip().split('\n')
    pontos = 0
    for line in config_lines:
        if line.lower().startswith('pontos:'):
            try:
                pontos = int(line.split(':', 1)[1].strip())
            except ValueError:
                pass

    lead = contexto.get('lead')
    cpf = getattr(lead, 'cpf_cnpj', '') if lead else contexto.get('cpf', '')
    if not cpf:
        return 'CPF não encontrado'

    membro = MembroClube.objects.filter(cpf=cpf.replace('.', '').replace('-', '')[:14]).first()
    if not membro:
        return f'Membro não encontrado para CPF {cpf}'

    membro.saldo += pontos
    membro.save(update_fields=['saldo'])
    return f'{pontos} pontos adicionados a {membro.nome}'


def _acao_webhook(regra, acao, contexto):
    config_lines = acao.configuracao.strip().split('\n')
    url = ''
    metodo = 'POST'
    for line in config_lines:
        if line.lower().startswith('url:'):
            url = line.split(':', 1)[1].strip()
            if not url.startswith('http'):
                url = 'https:' + url
        elif line.lower().startswith('método:') or line.lower().startswith('metodo:'):
            metodo = line.split(':', 1)[1].strip().upper()

    if not url:
        return 'URL não especificada'

    dados = {k: v for k, v in contexto.items() if isinstance(v, (str, int, float, bool))}

    try:
        if metodo == 'GET':
            resp = requests.get(url, params=dados, timeout=15)
        else:
            resp = requests.post(url, json=dados, timeout=15)
        return f'Webhook {metodo} {url} — status {resp.status_code}'
    except requests.RequestException as e:
        raise Exception(f'Falha no webhook: {e}')
