"""
Registry de tools do agente (D3) — descritores CURADOS que delegam aos nós/serviços.

Modelo (parecer do CTO): a camada de tool é própria (chave + descrição p/ o LLM +
schema dos args) e **delega** a execução ao mesmo executor de domínio dos nós — não
é "todo nó vira tool automático". Garantias:
- **Teto de output:** o resultado devolvido ao LLM é truncado (não explode o contexto).
- **Tenant-safe:** tudo usa `contexto.tenant`.
- **Allowlist por agente:** só as tools em `Agente.tools` entram no schema.
- **Params pinados:** parâmetros sensíveis (ex: pipeline) NÃO são expostos ao LLM.
- **Idempotência:** tools de escrita delegam a nós já idempotentes (ex: criar_oportunidade).
"""

TETO_RESULTADO = 1200  # chars máx devolvidos ao LLM por tool


def _cap(texto):
    s = '' if texto is None else str(texto)
    return s if len(s) <= TETO_RESULTADO else s[:TETO_RESULTADO] + '… (truncado)'


_TOOLS = {}


def _tool(chave, descricao, parametros, obrigatorios):
    def deco(fn):
        _TOOLS[chave] = {'chave': chave, 'descricao': descricao,
                         'parametros': parametros, 'obrigatorios': obrigatorios, 'fn': fn}
        return fn
    return deco


def tools_disponiveis():
    """[(chave, descricao)] — alimenta a seção Ferramentas do editor do agente."""
    return [(t['chave'], t['descricao']) for t in _TOOLS.values()]


def schema_openai(chaves):
    """Monta o tools_schema (formato OpenAI) só das tools habilitadas e existentes."""
    schema = []
    for chave in chaves or []:
        t = _TOOLS.get(chave)
        if not t:
            continue
        schema.append({
            'type': 'function',
            'function': {
                'name': t['chave'],
                'description': t['descricao'],
                'parameters': {
                    'type': 'object',
                    'properties': t['parametros'],
                    'required': t['obrigatorios'],
                },
            },
        })
    return schema


def despachar(chave, args, contexto, agente=None):
    """Executa a tool `chave` com `args` (do LLM), tenant-safe; devolve texto (com teto).
    `agente` permite tools dependerem de config do agente (ex: RAG por categoria).
    Tool desconhecida → mensagem de erro (nunca levanta — o loop trata)."""
    t = _TOOLS.get(chave)
    if t is None:
        return f'tool desconhecida: {chave}'
    return _cap(t['fn'](contexto, args or {}, agente))


# ----------------------------------------------------------------------------
# Tools curadas
# ----------------------------------------------------------------------------

@_tool(
    'registrar_feedback',
    'Salve a avaliação do cliente (nota de 0 a 10 e comentário). Use quando o cliente '
    'avaliar o atendimento ou o serviço.',
    {'nota': {'type': 'integer', 'description': 'Nota de 0 a 10'},
     'comentario': {'type': 'string', 'description': 'Comentário do cliente (opcional)'}},
    ['nota'],
)
def _registrar_feedback(contexto, args, agente=None):
    from apps.sistema.models import LogSistema
    nota = args.get('nota')
    comentario = (args.get('comentario') or '').strip()
    lead = contexto.lead
    LogSistema.objects.create(
        tenant=contexto.tenant, modulo='automacao', categoria='crm', acao='feedback',
        entidade='lead', entidade_id=getattr(lead, 'pk', None),
        mensagem=f'Feedback do agente: nota {nota}. {comentario}'.strip(),
        dados_extras={'nota': nota, 'comentario': comentario},
    )
    return f'feedback registrado (nota {nota}).'


@_tool(
    'criar_oportunidade',
    'Crie uma oportunidade no funil para o lead atual. Use quando o cliente demonstrar '
    'interesse claro em comprar/contratar.',
    {'titulo': {'type': 'string', 'description': 'Título curto da oportunidade'},
     'valor': {'type': 'number', 'description': 'Valor estimado em reais (opcional)'}},
    ['titulo'],
)
def _criar_oportunidade(contexto, args, agente=None):
    from apps.automacao.nodes import tipo_por_slug
    no = tipo_por_slug('criar_oportunidade')
    # pipeline/estágio NÃO expostos ao LLM (pinados): o nó usa o padrão do tenant.
    config = {'titulo': str(args.get('titulo') or '').strip()}
    if args.get('valor') is not None:
        config['valor'] = args['valor']
    res = no.executar(config, {}, contexto)
    if res.branch == 'erro':
        return f'não foi possível criar a oportunidade: {res.erro}'
    return f'oportunidade criada: {(res.output or {}).get("titulo", config["titulo"])}'


@_tool(
    'consultar_base_conhecimento',
    'Consulte a base de conhecimento da empresa (produtos, serviços, procedimentos, dúvidas '
    'frequentes). Use SEMPRE que o cliente fizer uma pergunta que pode ter resposta na base.',
    {'pergunta': {'type': 'string', 'description': 'A pergunta ou tema a buscar na base'}},
    ['pergunta'],
)
def _consultar_base_conhecimento(contexto, args, agente=None):
    from .rag import buscar_conhecimento
    categorias = list(getattr(agente, 'base_categorias', None) or [])  # vazio = base inteira do tenant
    return buscar_conhecimento(contexto.tenant, args.get('pergunta', ''), categorias=categorias)


def _marcar_fato(contexto, acao, label, valor, extras=None):
    """Registra um fato booleano sobre o contato no CRM (LogSistema), tenant-safe."""
    from apps.sistema.models import LogSistema
    lead = contexto.lead
    LogSistema.objects.create(
        tenant=contexto.tenant, modulo='automacao', categoria='crm', acao=acao,
        entidade='lead', entidade_id=getattr(lead, 'pk', None),
        mensagem=f'{label}: {valor}',
        dados_extras={**(extras or {}), 'valor': valor},
    )
    return f'{label} registrado: {valor}.'


@_tool(
    'marcar_cliente',
    'Registre se o contato JÁ é cliente da Megalink. Use quando o cliente disser que é (ou não é) cliente.',
    {'e_cliente': {'type': 'boolean', 'description': 'true se já é cliente da Megalink'}},
    ['e_cliente'],
)
def _marcar_cliente(contexto, args, agente=None):
    return _marcar_fato(contexto, 'marcar_cliente', 'É cliente', bool(args.get('e_cliente')))


@_tool(
    'marcar_intencao',
    'Registre a intenção de compra do contato. Use quando ele demonstrar (ou negar) interesse em contratar.',
    {'tem_intencao': {'type': 'boolean', 'description': 'true se demonstrou intenção de compra'}},
    ['tem_intencao'],
)
def _marcar_intencao(contexto, args, agente=None):
    return _marcar_fato(contexto, 'marcar_intencao', 'Intenção de compra', bool(args.get('tem_intencao')))


@_tool(
    'marcar_intencao_energia',
    'Registre o interesse do contato no produto Mega Energia. Use só depois de o cliente aceitar ouvir sobre o Mega Energia.',
    {'tem_interesse': {'type': 'boolean', 'description': 'true se interessado no Mega Energia'}},
    ['tem_interesse'],
)
def _marcar_intencao_energia(contexto, args, agente=None):
    return _marcar_fato(contexto, 'marcar_intencao_energia', 'Interesse Mega Energia', bool(args.get('tem_interesse')))
