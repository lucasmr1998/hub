"""
Engine do Assistente CRM.
Recebe mensagem do usuario, chama LLM com tools, executa acoes, retorna resposta.
"""
import json
import logging
import requests

from django.utils import timezone

from .tools import TOOLS_ASSISTENTE
from .models import ConversaAssistente, MensagemAssistente

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Voce e o assistente Hubtrix, um assistente de CRM via WhatsApp.
Voce ajuda vendedores a gerenciar suas oportunidades, leads, tarefas e notas direto pelo WhatsApp.

Regras:
- Seja conciso e direto. Respostas curtas, sem enrolacao.
- Use as tools disponiveis para executar acoes no CRM.
- Se o vendedor pedir algo ambiguo, pergunte para confirmar.
- Sempre confirme a acao executada.
- Se nao encontrar o que o vendedor pediu, informe e sugira alternativas.
- Formate listas de forma legivel para WhatsApp (sem markdown pesado).
- Use emojis com moderacao para facilitar a leitura.
- Quando o vendedor pedir algo que voce NAO consegue fazer (algo fora das suas tools), responda de forma amigavel e profissional. Diga que essa funcionalidade ainda nao esta disponivel, sugira usar o comando "ver comandos" para ver o que esta disponivel, e diga algo como "Vou passar pro nosso time de produto dar uma olhada nisso! Quem sabe na proxima atualizacao a gente ja tem." Seja descontraido mas profissional, sem ser ironico.

O vendedor logado e: {nome_usuario}
"""

MAX_HISTORICO = 10  # mensagens no contexto (menos = mais rapido)


def processar_mensagem(usuario, tenant, mensagem_texto, integracao=None):
    """
    Processa uma mensagem do usuario e retorna a resposta do assistente.

    Args:
        usuario: User do Django
        tenant: Tenant do usuario
        mensagem_texto: texto da mensagem recebida
        integracao: IntegracaoAPI de IA (OpenAI, etc.)

    Returns:
        str: resposta do assistente
    """
    if not integracao:
        integracao = _obter_integracao_ia(tenant)
        if not integracao:
            return 'Assistente nao configurado. Peca ao admin para configurar uma integracao de IA.'

    # Obter ou criar conversa
    conversa = _obter_conversa(usuario, tenant, integracao)

    # Salvar mensagem do usuario
    MensagemAssistente.objects.create(
        tenant=tenant, conversa=conversa,
        role='user', conteudo=mensagem_texto,
    )

    # Montar historico de mensagens
    messages = _montar_historico(conversa, usuario)

    # Montar tools no formato OpenAI
    tools_openai = _montar_tools()

    # Chamar LLM com tools
    try:
        resposta = _chamar_llm(integracao, messages, tools_openai, tenant, usuario)
    except Exception as e:
        logger.error(f'[Assistente] Erro ao chamar LLM: {e}')
        resposta = 'Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente.'

    # Salvar resposta do assistente
    MensagemAssistente.objects.create(
        tenant=tenant, conversa=conversa,
        role='assistant', conteudo=resposta,
    )

    # Registrar log de auditoria
    _registrar_log(tenant, usuario, mensagem_texto, resposta)

    return resposta


def _obter_integracao_ia(tenant):
    """Busca integracao de IA ativa do tenant."""
    from apps.integracoes.models import IntegracaoAPI
    return IntegracaoAPI.all_tenants.filter(
        tenant=tenant,
        tipo__in=['openai', 'anthropic', 'groq'],
        ativa=True,
    ).first()


def _obter_conversa(usuario, tenant, integracao):
    """Obtem ou cria conversa do assistente para o usuario."""
    conversa = ConversaAssistente.objects.filter(
        usuario=usuario, ativa=True,
    ).first()

    if not conversa:
        telefone = ''
        perfil = getattr(usuario, 'perfil', None)
        if perfil:
            telefone = perfil.telefone or ''

        conversa = ConversaAssistente.objects.create(
            tenant=tenant,
            usuario=usuario,
            telefone=telefone,
            integracao=integracao,
            modelo=integracao.configuracoes_extras.get('modelo', 'gpt-4o-mini'),
        )

    return conversa


def _montar_historico(conversa, usuario):
    """Monta lista de mensagens para o contexto da LLM."""
    nome = usuario.get_full_name() or usuario.username
    system = SYSTEM_PROMPT.format(nome_usuario=nome)

    messages = [{'role': 'system', 'content': system}]

    # Ultimas N mensagens
    mensagens = conversa.mensagens.order_by('-data')[:MAX_HISTORICO]
    for m in reversed(list(mensagens)):
        if m.role in ('user', 'assistant'):
            messages.append({'role': m.role, 'content': m.conteudo})

    return messages


def _montar_tools():
    """Converte TOOLS_ASSISTENTE para formato OpenAI."""
    tools = []
    for nome, config in TOOLS_ASSISTENTE.items():
        tools.append({
            'type': 'function',
            'function': {
                'name': nome,
                'description': config['description'],
                'parameters': config['parameters'],
            },
        })
    return tools


def _chamar_llm(integracao, messages, tools, tenant, usuario):
    """Chama a LLM com tool calling e processa as respostas."""
    api_key = integracao.api_key or integracao.configuracoes_extras.get('api_key', '') or integracao.access_token or ''
    modelo = integracao.configuracoes_extras.get('modelo', 'gpt-4o-mini')
    tipo = integracao.tipo

    if tipo == 'openai':
        url = 'https://api.openai.com/v1/chat/completions'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    elif tipo == 'groq':
        url = 'https://api.groq.com/openai/v1/chat/completions'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    else:
        url = integracao.base_url
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    current_messages = list(messages)

    for iteracao in range(5):  # max 5 iteracoes de tool calling
        payload = {
            'model': modelo,
            'messages': current_messages,
            'tools': tools,
            'temperature': 0.3,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)

        if resp.status_code != 200:
            logger.error(f'[Assistente] LLM retornou {resp.status_code}: {resp.text[:200]}')
            return 'Erro ao consultar a IA. Tente novamente.'

        data = resp.json()
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})
        finish_reason = choice.get('finish_reason', '')

        # Se nao chamou tools, retornar conteudo
        if finish_reason != 'tool_calls':
            return message.get('content', '') or 'Nao consegui processar.'

        # Processar tool calls
        tool_calls = message.get('tool_calls', [])
        if not tool_calls:
            return message.get('content', '') or 'Nao consegui processar.'

        current_messages.append(message)

        for tc in tool_calls:
            func_name = tc.get('function', {}).get('name', '')
            func_args_str = tc.get('function', {}).get('arguments', '{}')
            tc_id = tc.get('id', '')

            try:
                func_args = json.loads(func_args_str)
            except json.JSONDecodeError:
                func_args = {}

            # Executar tool
            tool_config = TOOLS_ASSISTENTE.get(func_name)
            if tool_config:
                try:
                    resultado = tool_config['func'](tenant, usuario, func_args)
                    logger.info(f'[Assistente] Tool {func_name}: {resultado[:100]}')
                    _audit_tool_assistente(tenant, usuario, func_name, func_args, resultado, nivel='INFO')
                except Exception as e:
                    resultado = f'Erro ao executar {func_name}: {str(e)}'
                    logger.error(f'[Assistente] Tool {func_name} erro: {e}')
                    _audit_tool_assistente(tenant, usuario, func_name, func_args, str(e), nivel='ERROR', falhou=True)
            else:
                resultado = f'Tool {func_name} nao encontrada.'

            current_messages.append({
                'role': 'tool',
                'tool_call_id': tc_id,
                'content': resultado,
            })

    return 'Muitas iteracoes de tools. Tente simplificar o pedido.'


def _registrar_log(tenant, usuario, mensagem, resposta):
    """Registra acao no LogSistema."""
    try:
        from apps.sistema.utils import registrar_acao
        registrar_acao(
            'assistente', 'mensagem', 'assistente_crm', None,
            f'{usuario.username}: {mensagem[:100]} -> {resposta[:100]}',
        )
    except Exception:
        pass


def _audit_tool_assistente(tenant, usuario, tool_name, args, resultado, *, nivel='INFO', falhou=False):
    """
    Auditoria por tool call do assistente. Defensivo — não quebra fluxo se falhar.
    Categoria fixa 'assistente' pra agregar fácil em LogSistema.
    """
    try:
        from apps.sistema.models import LogSistema
        acao = f'tool_{tool_name}_erro' if falhou else f'tool_{tool_name}'
        LogSistema.objects.create(
            tenant=tenant,
            nivel=nivel,
            modulo=f'assistente.{acao}',
            mensagem=f'Args: {str(args)[:200]} → {"Erro" if falhou else "Resultado"}: {str(resultado)[:300]}',
            categoria='assistente',
            acao=acao,
            entidade='AssistenteTool',
            entidade_id=None,
            usuario=usuario.username if usuario else '',
        )
    except Exception as exc:
        logger.warning('Falha ao auditar tool %s do assistente: %s', tool_name, exc)
