"""Views da API readonly de regras — a API IA (FastAPI) consulta daqui."""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from datetime import timedelta

from .models import RegraValidacao, LogInteracaoIA, MensagemRobo

logger = logging.getLogger(__name__)


@require_http_methods(['GET'])
def listar_regras(request):
    """Retorna todas as regras ativas. Usado pela API IA pra carregar/refresh cache."""
    qs = RegraValidacao.objects.filter(ativo=True).order_by('ordem', 'question_id')
    return JsonResponse({
        'regras': [r.to_dict() for r in qs],
        'total': qs.count(),
    })


@require_http_methods(['GET'])
def listar_mensagens(request):
    """Retorna as mensagens do robô ativas (chave→texto). O engine carrega e
    cacheia, aplicando override quando o texto não está vazio."""
    qs = MensagemRobo.objects.filter(ativo=True)
    return JsonResponse({
        'mensagens': [m.to_dict() for m in qs],
        'total': qs.count(),
    })


@require_http_methods(['GET'])
def obter_regra(request, question_id: str):
    """Retorna uma regra específica por question_id."""
    try:
        regra = RegraValidacao.objects.get(question_id=question_id, ativo=True)
        return JsonResponse(regra.to_dict())
    except RegraValidacao.DoesNotExist:
        return JsonResponse({'error': 'Regra não encontrada'}, status=404)


@csrf_exempt
@require_http_methods(['POST'])
def invalidar_cache(request):
    """Endpoint chamado pelo Django (via signal) pra avisar a API IA externa
    que uma regra foi editada e o cache deve ser invalidado.

    A API IA (FastAPI) implementa um endpoint POST /admin/invalidar-cache/
    que recebe esse callback.
    """
    # Aqui apenas confirma que recebeu — o signal vai disparar HTTP pra IA externa.
    return JsonResponse({'ok': True})


# ───────────────────────────────────────────────────────────────────
# PÁGINA EXPLICATIVA — Dashboard do IA Validador
# ───────────────────────────────────────────────────────────────────

# Categorias de regras pra agrupar visualmente na página
CATEGORIAS_REGRAS = [
    ('Dados pessoais',      ['coleta_cpf', 'coleta_nome', 'coleta_rg',
                              'coleta_data_nascimento', 'coleta_email']),
    ('Tipo de imóvel',      ['tipo_imovel', 'coleta_tipo_residencia']),
    ('Endereço',            ['coleta_cep', 'confirmacao_endereco',
                              'coleta_cidade', 'coleta_bairro', 'coleta_rua',
                              'coleta_numero', 'coleta_ponto_referencia']),
    ('Plano e pagamento',   ['escolha_plano', 'confirmacao_plano',
                              'dia_vencimento']),
    ('Confirmação geral',   ['confirmacao_dados', 'o_que_ajustar']),
    ('Documentação',        ['documentacao_selfie', 'documentacao_frente_doc',
                              'documentacao_verso_doc']),
    ('Agendamento',         ['escolha_turno', 'escolha_data',
                              'confirmacao_agendamento']),
    ('Cliente existente',   ['menu_cliente_existente', 'pergunta_finalizar']),
]

# STATUS_ROTAS espelho (mantido em sync com ia_validacao/src/onboarding.py)
STATUS_ROTAS_DOC = [
    ('lead_novo',              'Inicia fluxo de venda',           'Coleta CPF'),
    ('cliente_ativo',          'Cliente Hubsoft detectado',       'Menu de 4 opções'),
    ('instalacao_agendada',    'Cliente já agendou instalação',   'Menu de 4 opções'),
    ('aguardando_assinatura',  'Cadastrado, aguarda assinatura',  'Transbordo'),
    ('aguardando_finalizacao', 'Já viu OS / agendamento ok',      'Pergunta finalizar/voltar'),
    ('atendimento_concluido',  'Cliente encerrou conversa',       'Mensagem de despedida'),
    ('transbordo_atendente',   'Cliente pediu humano (menu 1/2/4)','Transbordo'),
    ('cancelado',              'Cliente cancelado historicamente', 'Transbordo retenção'),
]

# Hooks especiais do engine
HOOKS_ESPECIAIS = [
    {
        'evento': 'coleta_cpf válido',
        'acao': 'Backend chama API Hubsoft pra verificar se CPF já é cliente.',
        'efeito': "Se for cliente → marca status='cliente_ativo' → menu aparece na próxima rodada.",
    },
    {
        'evento': 'documentacao_* recebida (imagem)',
        'acao': 'IA Vision (gpt-4o-mini) valida frente/verso/selfie em ~3s.',
        'efeito': "Aprova → status='aprovado_ia' (aguarda valid. humana). Rejeita → pede refoto.",
    },
    {
        'evento': 'coleta_ponto_referencia',
        'acao': 'IA extrai bloco/apto/condomínio do texto livre + monta endereco completo.',
        'efeito': 'Salva ponto_referencia padronizado + campo endereco preenchido.',
    },
    {
        'evento': 'confirmacao_plano = NÃO',
        'acao': 'Engine limpa id_plano_rp + valor + plano_confirmado.',
        'efeito': 'Loop volta a perguntar escolha_plano.',
    },
    {
        'evento': 'confirmacao_dados = SIM',
        'acao': "Seta status_api='pendente' → signal Django cadastra prospecto no Hubsoft.",
        'efeito': 'Lead vira processado + id_hubsoft preenchido. Bot prossegue pros docs.',
    },
    {
        'evento': 'escolha_data válida',
        'acao': 'Engine pré-sincroniza cliente Hubsoft → consultar_agenda → abrir_atendimento → abrir_os.',
        'efeito': "Mensagem rica com data/turno/horário + status='instalacao_agendada'.",
    },
    {
        'evento': 'tipo_imovel = empresa',
        'acao': 'Engine força transbordo (bot só atende residencial).',
        'efeito': 'Cliente recebe msg sobre atendimento empresarial e é transferido.',
    },
    {
        'evento': 'menu opção 1/2/4 (novo/upgrade/atendimento)',
        'acao': "Seta status='transbordo_atendente' + needsReception=true.",
        'efeito': 'Cliente é transferido pra atendente humano.',
    },
    {
        'evento': 'menu opção 3 (acompanhar OS)',
        'acao': 'Backend sincroniza OS em tempo real + busca a mais recente.',
        'efeito': "Mostra dados da OS + pergunta 'voltar ao menu ou encerrar?'",
    },
]

# Endpoints da API IA (FastAPI)
ENDPOINTS_API_IA = [
    {
        'metodo': 'POST', 'rota': '/ia/proximo-passo',
        'cor': '#10b981',
        'descricao': 'Decisor de roteamento inicial. Chamado a cada nova mensagem do cliente.',
        'entrada': '{ cellphone, lead_id, ultima_mensagem }',
        'saida': '{ status_lead, proximo_passo, proxima_pergunta_id, deve_perguntar, deve_transbordar, mensagem_inicial }',
        'logica': 'Carrega lead → checa status_api → decide se mostra menu, retoma fluxo, transborda ou encerra.',
    },
    {
        'metodo': 'POST', 'rota': '/ia/validar',
        'cor': '#3b82f6',
        'descricao': 'Valida UMA resposta do cliente conforme a regra do question_id.',
        'entrada': '{ question, answer, cellphone, lead_id, question_id }',
        'saida': '{ valido, extracted_data, message, mensagem_resposta, needsReception, ...legados }',
        'logica': 'Aplica extractor → executa hooks especiais → dispara ações em background → retorna pro Matrix.',
    },
    {
        'metodo': 'POST', 'rota': '/ia/validar-imagem',
        'cor': '#8b5cf6',
        'descricao': 'Valida UMA imagem isoladamente via OpenAI Vision (usado pelo /cadastro/ do site).',
        'entrada': '{ url, descricao }',
        'saida': '{ aprovado, motivo_codigo, motivo_humano, msg_refoto }',
        'logica': 'Chama openai_imagens.validar_imagem — mesma função usada pelo WhatsApp.',
    },
]

# Extractores disponíveis nas regras
EXTRACTORS_DISPONIVEIS = [
    ('cpf',             'Valida CPF (regex + dígito verificador)'),
    ('cep',             'Valida CEP (regex + consulta ViaCEP + cobertura)'),
    ('nome',            'Nome completo (mínimo 2 palavras)'),
    ('telefone',        'Telefone com DDD'),
    ('data_nascimento', 'Data válida + verifica >= 18 anos'),
    ('email',           'E-mail formato válido'),
    ('numero',          'Número (residência, etc) — aceita S/N'),
    ('opcao',           'Opção numerada (1, 2, 3...) com aliases configuráveis'),
    ('confirmacao',     'Sim/Não (aceita 1/2, ok, claro, etc)'),
    ('imagem',          'URL de imagem + validação por IA Vision'),
    ('texto_livre',     'Aceita qualquer resposta não-vazia'),
    ('livre',           'Sempre aceita (mesmo vazio)'),
]


def dashboard_validador(request):
    """Página explicativa do IA Validador.

    Mostra todas as regras configuradas, fluxograma, estatísticas em
    tempo real (LogInteracaoIA), hooks especiais e endpoints disponíveis.
    """
    # ── Regras agrupadas por categoria ────────────────────────────
    todas_regras = {r.question_id: r for r in RegraValidacao.objects.all().order_by('ordem')}
    categorias_render = []
    categorizadas = set()
    for nome_cat, ids in CATEGORIAS_REGRAS:
        regras_cat = []
        for qid in ids:
            r = todas_regras.get(qid)
            if r:
                regras_cat.append(r)
                categorizadas.add(qid)
        if regras_cat:
            categorias_render.append({'nome': nome_cat, 'regras': regras_cat})
    # Outras regras não categorizadas
    outras = [r for qid, r in todas_regras.items() if qid not in categorizadas]
    if outras:
        categorias_render.append({'nome': 'Outras', 'regras': outras})

    # ── Estatísticas em tempo real (LogInteracaoIA) ───────────────
    agora = timezone.now()
    desde_24h = agora - timedelta(hours=24)
    desde_7d  = agora - timedelta(days=7)

    qs = LogInteracaoIA.objects.all()
    stats_geral = {
        'total_24h':    qs.filter(timestamp__gte=desde_24h).count(),
        'total_7d':     qs.filter(timestamp__gte=desde_7d).count(),
        'total_geral':  qs.count(),
        'validar_24h':  qs.filter(timestamp__gte=desde_24h, endpoint='validar').count(),
        'proximo_24h':  qs.filter(timestamp__gte=desde_24h, endpoint='proximo-passo').count(),
        'imagem_24h':   qs.filter(timestamp__gte=desde_24h, endpoint='validar-imagem').count(),
        'transbordos_24h': qs.filter(timestamp__gte=desde_24h, transbordou=True).count(),
        'duracao_media_ms': qs.filter(
            timestamp__gte=desde_24h, duracao_ms__isnull=False
        ).aggregate(m=Avg('duracao_ms'))['m'] or 0,
    }

    # Top question_ids mais chamados (24h)
    top_questions = list(
        qs.filter(timestamp__gte=desde_24h)
          .exclude(question_id='')
          .values('question_id')
          .annotate(n=Count('id'))
          .order_by('-n')[:8]
    )

    # Últimas 10 interações (com nomes resolvidos)
    ultimas = qs.order_by('-timestamp')[:10]

    contexto = {
        'categorias': categorias_render,
        'status_rotas': STATUS_ROTAS_DOC,
        'hooks': HOOKS_ESPECIAIS,
        'endpoints': ENDPOINTS_API_IA,
        'extractors': EXTRACTORS_DISPONIVEIS,
        'stats': stats_geral,
        'top_questions': top_questions,
        'ultimas_interacoes': ultimas,
        'total_regras': len(todas_regras),
        'regras_ativas': sum(1 for r in todas_regras.values() if r.ativo),
    }
    return render(request, 'ia_validador/dashboard.html', contexto)


@csrf_exempt
@require_http_methods(['POST'])
def api_log_interacao(request):
    """Registra um log de interação com a API IA.

    POST /api/ia/log-interacao/
    Body: {
        endpoint, cellphone, lead_id, question_id, answer,
        mensagem_resposta, payload_in, payload_out,
        duracao_ms, valido, transbordou, motivo
    }

    Nenhum campo é obrigatório — apenas registramos o que vier. Erros
    não derrubam o caller (API IA não pode quebrar por causa do log).
    """
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'erro': 'json inválido'}, status=200)

    # Resolve lead pelo id (se vier)
    lead = None
    lead_id = data.get('lead_id')
    if lead_id:
        try:
            from vendas_web.models import LeadProspecto
            lead = LeadProspecto.objects.filter(pk=int(lead_id)).first()
        except Exception:
            lead = None

    try:
        log = LogInteracaoIA.objects.create(
            endpoint=(data.get('endpoint') or '')[:40],
            cellphone=(data.get('cellphone') or '')[:20],
            lead=lead,
            question_id=(data.get('question_id') or '')[:80],
            answer=(data.get('answer') or '')[:5000],
            mensagem_resposta=(data.get('mensagem_resposta') or '')[:5000],
            payload_in=data.get('payload_in') or {},
            payload_out=data.get('payload_out') or {},
            duracao_ms=data.get('duracao_ms'),
            valido=data.get('valido'),
            transbordou=bool(data.get('transbordou', False)),
            motivo=(data.get('motivo') or '')[:200],
        )
        return JsonResponse({'ok': True, 'id': log.id})
    except Exception as e:
        logger.warning('Falha gravar LogInteracaoIA: %s', e)
        return JsonResponse({'ok': False, 'erro': str(e)}, status=200)
