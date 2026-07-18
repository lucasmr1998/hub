"""Serviço de IA da engine de automação — chamada LLM tenant-aware.

Cópia canônica da chamada LLM no app novo (executor de domínio único): não
importa de `apps/comercial/atendimento/engine.py` (motor a aposentar). Multi-provider
(OpenAI / Groq / Anthropic / Google AI), resolução de credencial e modelo a partir
da `IntegracaoAPI` do tenant.

`chamar_llm` é simples (sem tools). O loop com tools (`chamar_llm_com_tools`) entra
em D3.
"""
import logging

import requests

logger = logging.getLogger(__name__)

_TIPOS_IA = ['openai', 'anthropic', 'groq', 'google_ai']


def integracao_ia_do_tenant(tenant, *, integracao_id=None):
    """Resolve a integração de IA do tenant.

    Com `integracao_id`: filtra por id + tenant (fallback cross-tenant por id, p/
    cenário do assistente). Sem id: primeira integração de IA ativa do tenant.
    """
    from apps.integracoes.models import IntegracaoAPI
    if integracao_id:
        return (
            IntegracaoAPI.all_tenants.filter(id=integracao_id, tenant=tenant, ativa=True).first()
            or IntegracaoAPI.all_tenants.filter(id=integracao_id, ativa=True).first()
        )
    return (
        IntegracaoAPI.all_tenants
        .filter(tenant=tenant, tipo__in=_TIPOS_IA, ativa=True)
        .first()
    )


def _credencial(integracao):
    extras = integracao.configuracoes_extras or {}
    return (
        integracao.api_key or extras.get('api_key', '')
        or integracao.access_token or integracao.client_secret or ''
    )


def chamar_llm(integracao, messages, *, modelo=None, max_tokens=1000, timeout=30):
    """Chama o LLM e devolve o texto da resposta (ou None em erro). Sem tools.

    `messages`: lista no formato OpenAI `[{'role','content'}]`. Monta url/headers/
    payload conforme `integracao.tipo`. Síncrono.

    `timeout`: segundos do request HTTP (default 30). Quem chama no CAMINHO
    CRÍTICO de um bot conversacional deve baixar isso (ex: 8s): o Matrix corta a
    chamada em 45s, e uma resposta que chega depois disso não serve pra nada.
    """
    tipo = integracao.tipo
    base_url = integracao.base_url
    extras = integracao.configuracoes_extras or {}
    api_key = _credencial(integracao)
    modelo = modelo or extras.get('modelo', '')

    headers = {'Content-Type': 'application/json'}

    if tipo in ('openai', 'groq'):
        headers['Authorization'] = f'Bearer {api_key}'
        url = base_url or (
            'https://api.openai.com/v1/chat/completions' if tipo == 'openai'
            else 'https://api.groq.com/openai/v1/chat/completions'
        )
        payload = {
            'model': modelo or ('gpt-4o-mini' if tipo == 'openai' else 'llama-3.1-8b-instant'),
            'messages': messages,
            'max_tokens': max_tokens,
        }
    elif tipo == 'anthropic':
        headers['x-api-key'] = api_key
        headers['anthropic-version'] = '2023-06-01'
        url = base_url or 'https://api.anthropic.com/v1/messages'
        # Anthropic: system separado dos messages.
        system_msg = ''
        chat_messages = []
        for m in messages:
            if m['role'] == 'system':
                system_msg += m['content'] + '\n'
            else:
                chat_messages.append(m)
        payload = {
            'model': modelo or 'claude-haiku-4-5-20251001',
            'max_tokens': max_tokens,
            'messages': chat_messages,
        }
        if system_msg:
            payload['system'] = system_msg.strip()
    elif tipo == 'google_ai':
        url = (base_url or f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{modelo or "gemini-2.0-flash"}:generateContent') + f'?key={api_key}'
        contents = []
        for m in messages:
            if m['role'] == 'system':
                contents.append({'role': 'user', 'parts': [{'text': f'[System]: {m["content"]}'}]})
            else:
                role = 'model' if m['role'] == 'assistant' else 'user'
                contents.append({'role': role, 'parts': [{'text': m['content']}]})
        payload = {'contents': contents}
    else:
        headers['Authorization'] = f'Bearer {api_key}'
        url = base_url
        payload = {'prompt': messages[-1].get('content', '') if messages else ''}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if res.status_code != 200:
            logger.error('LLM %s retornou %s: %s', tipo, res.status_code, res.text[:200])
            return None
        data = res.json()
        if tipo in ('openai', 'groq'):
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
        if tipo == 'anthropic':
            return data.get('content', [{}])[0].get('text', '')
        if tipo == 'google_ai':
            return (data.get('candidates', [{}])[0].get('content', {})
                    .get('parts', [{}])[0].get('text', ''))
        return data.get('content', data.get('text', str(data)))
    except Exception as e:  # noqa: BLE001 — falha de rede/parse vira None (tratada pelo chamador)
        logger.error('Erro ao chamar LLM %s: %s', tipo, e)
        return None


def chamar_llm_com_tools(integracao, messages, tools_schema, despachar_tool, *, modelo=None, max_iter=5):
    """Chama o LLM com tools e roda o loop de tool-calling até a resposta final.

    - `tools_schema`: defs no formato OpenAI `[{type:'function', function:{name,description,parameters}}]`.
    - `despachar_tool(nome, args) -> str`: callback (injetado) que executa a tool e devolve o
      resultado em texto. Desacopla o loop de qualquer modelo de domínio.
    Só OpenAI/Groq fazem tool-calling; outros providers (ou sem tools) caem em `chamar_llm`.
    Devolve o texto final (ou None em falha).
    """
    import json as _json

    tipo = integracao.tipo
    if not tools_schema or tipo not in ('openai', 'groq'):
        return chamar_llm(integracao, messages, modelo=modelo)

    extras = integracao.configuracoes_extras or {}
    api_key = _credencial(integracao)
    modelo = modelo or extras.get('modelo', '')
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    url = integracao.base_url or (
        'https://api.openai.com/v1/chat/completions' if tipo == 'openai'
        else 'https://api.groq.com/openai/v1/chat/completions'
    )
    modelo_final = modelo or ('gpt-4o-mini' if tipo == 'openai' else 'llama-3.1-8b-instant')

    current = list(messages)
    ultimo_texto = None
    for _ in range(max_iter):
        payload = {'model': modelo_final, 'messages': current, 'tools': tools_schema, 'max_tokens': 1500}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=30)
        except Exception as e:  # noqa: BLE001
            logger.error('LLM tools %s erro de rede: %s', tipo, e)
            return ultimo_texto
        if res.status_code != 200:
            logger.error('LLM tools %s retornou %s: %s', tipo, res.status_code, res.text[:200])
            return ultimo_texto

        choice = (res.json().get('choices') or [{}])[0]
        message = choice.get('message', {})
        if message.get('content'):
            ultimo_texto = message['content']

        if choice.get('finish_reason') != 'tool_calls':
            return message.get('content') or ultimo_texto
        tool_calls = message.get('tool_calls') or []
        if not tool_calls:
            return message.get('content') or ultimo_texto

        current.append(message)  # assistant + tool_calls
        for tc in tool_calls:
            fn = tc.get('function', {})
            try:
                args = _json.loads(fn.get('arguments') or '{}')
            except Exception:  # noqa: BLE001
                args = {}
            try:
                resultado = despachar_tool(fn.get('name', ''), args)
            except Exception as e:  # noqa: BLE001 — tool que estoura vira resultado de erro, não derruba o loop
                resultado = f'erro ao executar {fn.get("name", "")}: {e}'
            current.append({'role': 'tool', 'tool_call_id': tc.get('id', ''), 'content': str(resultado)})

    return ultimo_texto  # estourou max_iter
