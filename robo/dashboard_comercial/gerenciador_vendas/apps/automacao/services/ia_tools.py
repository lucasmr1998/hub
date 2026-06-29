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

# Classificacao das tools (tipo + categoria), pro catalogo TOOLS.md e o editor.
#   tipo: 'conhecimento' (le/consulta, read-only) | 'executavel' (faz/escreve, efeito colateral)
# Tool nova pode declarar via @_tool(..., tipo=, categoria=); senao cai aqui (indice central).
_CLASSIFICACAO = {
    'registrar_feedback':          ('executavel', 'atendimento'),
    'criar_oportunidade':          ('executavel', 'crm'),
    'consultar_base_conhecimento': ('conhecimento', 'conhecimento'),
    'marcar_cliente':              ('executavel', 'atendimento'),
    'marcar_intencao':             ('executavel', 'atendimento'),
    'marcar_intencao_energia':     ('executavel', 'atendimento'),
    'abrir_ticket':                ('executavel', 'suporte'),
    'status_pipeline':             ('conhecimento', 'dados'),
    'resumo_leads':                ('conhecimento', 'dados'),
    'vendas_periodo':              ('conhecimento', 'dados'),
    'churn_clientes':              ('conhecimento', 'dados'),
    'tickets_abertos':             ('conhecimento', 'dados'),
    'solicitar_aprovacao':         ('executavel', 'governanca'),
    'criar_projeto':               ('executavel', 'workspace'),
    'criar_tarefa_workspace':      ('executavel', 'workspace'),
    'criar_etapa':                 ('executavel', 'workspace'),
    'salvar_documento':            ('executavel', 'workspace'),
    'listar_documentos':           ('conhecimento', 'workspace'),
}


def _tool(chave, descricao, parametros, obrigatorios, tipo=None, categoria=None):
    def deco(fn):
        t, c = _CLASSIFICACAO.get(chave, ('executavel', 'geral'))
        _TOOLS[chave] = {'chave': chave, 'descricao': descricao,
                         'parametros': parametros, 'obrigatorios': obrigatorios,
                         'tipo': tipo or t, 'categoria': categoria or c, 'fn': fn}
        return fn
    return deco


def tools_disponiveis():
    """[{chave, descricao, tipo, categoria}] — subset curado pro editor."""
    return [{'chave': t['chave'], 'descricao': t['descricao'],
             'tipo': t['tipo'], 'categoria': t['categoria']} for t in _TOOLS.values()]


def catalogo_tools():
    """Metadata completa de cada tool (pro catalogo TOOLS.md). Inclui params."""
    return [{'chave': t['chave'], 'descricao': t['descricao'], 'tipo': t['tipo'],
             'categoria': t['categoria'], 'parametros': t['parametros'],
             'obrigatorios': t['obrigatorios']} for t in _TOOLS.values()]


def _prioridades():
    """Valores de prioridade vindos do modelo (fonte da verdade, nada hardcoded)."""
    from apps.suporte.models import Ticket
    return [v for v, _ in Ticket.PRIORIDADE_CHOICES]


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
    return buscar_conhecimento(contexto.tenant, args.get('pergunta', ''),
                               categorias=categorias, lead=getattr(contexto, 'lead', None))


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


@_tool(
    'abrir_ticket',
    'Abra um ticket de suporte pro time humano resolver. Use quando o cliente reportar um '
    'problema/bug, ou quando você não conseguir resolver e precisar escalar. Dê um título '
    'objetivo e uma descrição com o MÁXIMO de contexto (o que aconteceu, quando, passos pra '
    'reproduzir, o que era esperado) — quanto melhor a descrição, mais rápido o time resolve.',
    {'titulo': {'type': 'string', 'description': 'Título curto e objetivo do problema'},
     'descricao': {'type': 'string', 'description': 'Descrição detalhada: o que aconteceu, quando, '
                   'passos pra reproduzir e o que era esperado'},
     'categoria': {'type': 'string', 'description': 'Categoria do chamado (ex: Bug, Dúvida, Financeiro). Opcional.'},
     'prioridade': {'type': 'string', 'enum': _prioridades(),
                    'description': 'Prioridade do chamado. Opcional (padrão: normal).'}},
    ['titulo', 'descricao'],
)
def _abrir_ticket(contexto, args, agente=None):
    from .tickets import criar_ticket
    try:
        ticket = criar_ticket(
            contexto.tenant,
            args.get('titulo', ''),
            args.get('descricao', ''),
            categoria=(args.get('categoria') or '').strip() or None,
            prioridade=(args.get('prioridade') or 'normal'),
        )
    except Exception as e:  # noqa: BLE001
        return f'não foi possível abrir o ticket: {e}'
    cat = ticket.categoria.nome if ticket.categoria else '—'
    return f'ticket #{ticket.numero} aberto (categoria: {cat}, prioridade: {ticket.prioridade}).'


# ----------------------------------------------------------------------------
# Tools de DADOS (consulta read-only, tenant-scoped) para agentes executivos
# do workspace. Reusam os models do registry de relatorios (data_sources.py).
# Sempre filtram por contexto.tenant via all_tenants (explicito, nunca thread-local).
# ----------------------------------------------------------------------------

def _int_arg(valor, padrao):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def _reais(valor):
    return f'R$ {float(valor or 0):,.0f}'.replace(',', '.')


@_tool(
    'status_pipeline',
    'Resumo do funil comercial: quantidade de oportunidades por estagio. Use para '
    'responder sobre o pipeline ou o funil de vendas.',
    {},
    [],
)
def _status_pipeline(contexto, args, agente=None):
    from django.db.models import Count
    from apps.comercial.crm.models import OportunidadeVenda
    linhas = list(
        OportunidadeVenda.all_tenants.filter(tenant=contexto.tenant)
        .values('estagio__nome')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    if not linhas:
        return 'pipeline vazio (nenhuma oportunidade).'
    total = sum(l['n'] for l in linhas)
    partes = '; '.join(f'{(l["estagio__nome"] or "sem estagio")}: {l["n"]}' for l in linhas)
    return f'Pipeline: {total} oportunidades. Por estagio: {partes}.'


@_tool(
    'resumo_leads',
    'Resumo dos leads do funil: total, novos no periodo e principais origens. Use para '
    'responder quantos leads existem ou de onde vem os leads.',
    {'dias': {'type': 'integer', 'description': 'Janela em dias para os leads novos (padrao 30)'}},
    [],
)
def _resumo_leads(contexto, args, agente=None):
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count
    from apps.comercial.leads.models import LeadProspecto
    dias = _int_arg(args.get('dias'), 30)
    base = LeadProspecto.all_tenants.filter(tenant=contexto.tenant)
    total = base.count()
    if not total:
        return 'nenhum lead cadastrado para este tenant.'
    novos = base.filter(data_cadastro__gte=timezone.now() - timedelta(days=dias)).count()
    origens = base.values('origem').annotate(n=Count('id')).order_by('-n')[:5]
    top = '; '.join(f'{(o["origem"] or "sem origem")}: {o["n"]}' for o in origens)
    return f'Leads: {total} no total, {novos} novos nos ultimos {dias} dias. Principais origens: {top}.'


@_tool(
    'vendas_periodo',
    'Vendas registradas no periodo: quantidade e valor total. Use para responder quanto '
    'foi vendido (vendas do mes, da semana, etc).',
    {'dias': {'type': 'integer', 'description': 'Janela em dias (padrao 30)'}},
    [],
)
def _vendas_periodo(contexto, args, agente=None):
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count, Sum
    from apps.comercial.crm.models import Venda
    dias = _int_arg(args.get('dias'), 30)
    agg = (
        Venda.all_tenants
        .filter(tenant=contexto.tenant, data_venda__gte=timezone.now() - timedelta(days=dias))
        .aggregate(n=Count('id'), valor=Sum('valor'))
    )
    return f'Vendas nos ultimos {dias} dias: {agg["n"] or 0} venda(s), total {_reais(agg["valor"])}.'


@_tool(
    'churn_clientes',
    'Clientes ativos em risco de churn (churn_score alto) na base HubSoft espelhada. Use '
    'para responder sobre risco de cancelamento ou retencao.',
    {'score_minimo': {'type': 'integer',
                      'description': 'Churn score minimo para considerar em risco (0 a 100, padrao 70)'}},
    [],
)
def _churn_clientes(contexto, args, agente=None):
    from django.db.models import Avg
    from apps.integracoes.models import ClienteHubsoft
    minimo = _int_arg(args.get('score_minimo'), 70)
    base = ClienteHubsoft.all_tenants.filter(tenant=contexto.tenant, ativo=True)
    total = base.count()
    if not total:
        return 'sem clientes HubSoft espelhados para este tenant.'
    em_risco = base.filter(churn_score__gte=minimo).count()
    media = base.aggregate(m=Avg('churn_score'))['m'] or 0
    return (f'Clientes ativos: {total}. Em risco de churn (score >= {minimo}): {em_risco}. '
            f'Churn score medio: {media:.0f}.')


@_tool(
    'tickets_abertos',
    'Tickets de suporte ainda nao resolvidos, por status. Use para responder sobre a fila '
    'de suporte ou quantos chamados estao abertos.',
    {},
    [],
)
def _tickets_abertos(contexto, args, agente=None):
    from django.db.models import Count
    from apps.suporte.models import Ticket
    abertos = ['aberto', 'em_andamento', 'aguardando_cliente']
    por_status = list(
        Ticket.all_tenants.filter(tenant=contexto.tenant, status__in=abertos)
        .values('status').annotate(n=Count('id')).order_by('-n')
    )
    total = sum(s['n'] for s in por_status)
    if not total:
        return 'nenhum ticket aberto.'
    nomes = dict(Ticket.STATUS_CHOICES)
    partes = '; '.join(f'{nomes.get(s["status"], s["status"])}: {s["n"]}' for s in por_status)
    return f'Tickets abertos: {total}. Por status: {partes}.'


@_tool(
    'solicitar_aprovacao',
    'Registre uma PROPOSTA de acao para aprovacao humana, em vez de executar direto. '
    'Use quando recomendar algo que precisa do aval de uma pessoa antes (uma decisao, '
    'um gasto, uma mudanca importante). De um titulo objetivo e uma descricao com o '
    'racional e a acao que voce sugere. Prioridade: baixa, media, alta ou critica.',
    {'titulo': {'type': 'string', 'description': 'Titulo curto da proposta'},
     'descricao': {'type': 'string', 'description': 'Racional + acao sugerida, com contexto'},
     'prioridade': {'type': 'string', 'description': 'baixa | media | alta | critica (padrao media)'}},
    ['titulo', 'descricao'],
)
def _solicitar_aprovacao(contexto, args, agente=None):
    from apps.workspace.models import Proposta, PRIORIDADE_CHOICES
    validas = {v for v, _ in PRIORIDADE_CHOICES}
    prio = (args.get('prioridade') or 'media').strip().lower()
    if prio not in validas:
        prio = 'media'
    titulo = str(args.get('titulo') or '').strip()[:300]
    if not titulo:
        return 'titulo da proposta vazio.'
    p = Proposta.objects.create(
        tenant=contexto.tenant,
        agente=agente if getattr(agente, 'pk', None) else None,
        titulo=titulo,
        descricao=str(args.get('descricao') or '').strip(),
        prioridade=prio,
        status='pendente',
    )
    return f'proposta #{p.pk} registrada (prioridade {prio}), aguardando aprovacao humana.'


# ----------------------------------------------------------------------------
# Tools de acao no Workspace (o agente FAZ, nao so consulta). Tenant-safe.
# ----------------------------------------------------------------------------

def _projeto_padrao(tenant):
    """Projeto onde caem as tarefas dos agentes quando nenhum e indicado."""
    from apps.workspace.models import Projeto
    p = Projeto.all_tenants.filter(tenant=tenant, nome='Caixa dos agentes').first()
    if p is None:
        p = Projeto(tenant=tenant, nome='Caixa dos agentes',
                    objetivo='Tarefas criadas pelos agentes sem projeto definido.',
                    status='em_andamento')
        p.save()
    return p


def _slug_unico(tenant, titulo, Model):
    """Slug unico por tenant a partir do titulo (Documento exige slug unico)."""
    from django.utils.text import slugify
    base = (slugify(titulo) or 'doc')[:200]
    slug, i = base, 2
    while Model.all_tenants.filter(tenant=tenant, slug=slug).exists():
        slug = f'{base}-{i}'[:220]
        i += 1
    return slug


@_tool(
    'criar_projeto',
    'Crie um projeto no Workspace (uma frente de trabalho com objetivo). Use pra organizar '
    'um conjunto de tarefas sob uma iniciativa.',
    {'nome': {'type': 'string', 'description': 'Nome do projeto'},
     'objetivo': {'type': 'string', 'description': 'Objetivo do projeto (opcional)'}},
    ['nome'],
)
def _criar_projeto(contexto, args, agente=None):
    from apps.workspace.models import Projeto
    nome = str(args.get('nome') or '').strip()[:200]
    if not nome:
        return 'nome do projeto vazio.'
    p = Projeto(tenant=contexto.tenant, nome=nome,
                objetivo=str(args.get('objetivo') or '').strip(),
                status='em_andamento')
    p.save()
    return f'projeto #{p.pk} criado: "{nome}".'


@_tool(
    'criar_tarefa_workspace',
    'Crie uma tarefa no Workspace (backlog de projeto da empresa, NAO o funil/CRM). Use pra '
    'registrar um trabalho a fazer. Sem projeto_id, a tarefa cai na "Caixa dos agentes".',
    {'titulo': {'type': 'string', 'description': 'Titulo da tarefa'},
     'descricao': {'type': 'string', 'description': 'O que fazer (opcional)'},
     'prioridade': {'type': 'string', 'description': 'baixa | media | alta | critica (padrao media)'},
     'projeto_id': {'type': 'integer', 'description': 'ID do projeto do Workspace (opcional)'}},
    ['titulo'],
)
def _criar_tarefa_workspace(contexto, args, agente=None):
    from apps.workspace.models import Projeto, Tarefa, PRIORIDADE_CHOICES
    titulo = str(args.get('titulo') or '').strip()[:200]
    if not titulo:
        return 'titulo da tarefa vazio.'
    projeto = None
    pid = _int_arg(args.get('projeto_id'), 0)
    if pid:
        projeto = Projeto.all_tenants.filter(tenant=contexto.tenant, pk=pid).first()
    if projeto is None:
        projeto = _projeto_padrao(contexto.tenant)
    validas = {v for v, _ in PRIORIDADE_CHOICES}
    prio = (args.get('prioridade') or 'media').strip().lower()
    if prio not in validas:
        prio = 'media'
    t = Tarefa(tenant=contexto.tenant, projeto=projeto, titulo=titulo,
               descricao=str(args.get('descricao') or '').strip(),
               prioridade=prio, status='pendente',
               criado_por_agente=agente if getattr(agente, 'pk', None) else None)
    t.save()
    return f'tarefa #{t.pk} criada em "{projeto.nome}" (prioridade {prio}).'


@_tool(
    'criar_etapa',
    'Crie uma etapa (fase) dentro de um projeto do Workspace.',
    {'projeto_id': {'type': 'integer', 'description': 'ID do projeto'},
     'nome': {'type': 'string', 'description': 'Nome da etapa'}},
    ['projeto_id', 'nome'],
)
def _criar_etapa(contexto, args, agente=None):
    from apps.workspace.models import Projeto, Etapa
    pid = _int_arg(args.get('projeto_id'), 0)
    projeto = Projeto.all_tenants.filter(tenant=contexto.tenant, pk=pid).first() if pid else None
    if projeto is None:
        return 'projeto nao encontrado (passe um projeto_id valido).'
    nome = str(args.get('nome') or '').strip()[:200]
    if not nome:
        return 'nome da etapa vazio.'
    e = Etapa(tenant=contexto.tenant, projeto=projeto, nome=nome)
    e.save()
    return f'etapa #{e.pk} criada em "{projeto.nome}": {nome}.'


@_tool(
    'salvar_documento',
    'Salve um documento (markdown) no Workspace. Use pra registrar uma analise, ata, plano '
    'ou qualquer texto que deva ficar guardado e consultavel depois.',
    {'titulo': {'type': 'string', 'description': 'Titulo do documento'},
     'conteudo': {'type': 'string', 'description': 'Conteudo em markdown'},
     'categoria': {'type': 'string', 'description': 'estrategia | relatorio | decisoes | processo | outro (opcional)'}},
    ['titulo', 'conteudo'],
)
def _salvar_documento(contexto, args, agente=None):
    from apps.workspace.models import Documento, DOCUMENTO_CATEGORIA_CHOICES
    titulo = str(args.get('titulo') or '').strip()[:200]
    conteudo = str(args.get('conteudo') or '').strip()
    if not titulo or not conteudo:
        return 'titulo e conteudo sao obrigatorios.'
    cats = {v for v, _ in DOCUMENTO_CATEGORIA_CHOICES}
    categoria = (args.get('categoria') or 'outro').strip().lower()
    if categoria not in cats:
        categoria = 'outro'
    d = Documento(tenant=contexto.tenant, titulo=titulo,
                  slug=_slug_unico(contexto.tenant, titulo, Documento),
                  formato='markdown', conteudo=conteudo, categoria=categoria,
                  agente_origem=agente if getattr(agente, 'pk', None) else None)
    d.save()
    return f'documento #{d.pk} salvo: "{titulo}" (categoria {categoria}).'


@_tool(
    'listar_documentos',
    'Liste documentos do Workspace (id + titulo + categoria), opcionalmente filtrando por um '
    'termo no titulo. Use pra achar um documento antes de consultar.',
    {'busca': {'type': 'string', 'description': 'Termo pra filtrar no titulo (opcional)'}},
    [],
)
def _listar_documentos(contexto, args, agente=None):
    from apps.workspace.models import Documento
    qs = Documento.all_tenants.filter(tenant=contexto.tenant)
    termo = (args.get('busca') or '').strip()
    if termo:
        qs = qs.filter(titulo__icontains=termo)
    docs = list(qs.order_by('-atualizado_em')[:20])
    if not docs:
        return 'nenhum documento encontrado.'
    linhas = [f'#{d.pk} [{d.categoria}] {d.titulo}' for d in docs]
    return 'documentos:\n' + '\n'.join(linhas)
