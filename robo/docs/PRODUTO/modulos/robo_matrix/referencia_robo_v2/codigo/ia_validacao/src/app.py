"""API IA Validação — entrada HTTP.

Endpoints principais (v2):
- POST /validar         → validador v2 (recebe {question, answer, cellphone, lead_id, question_id?})
- POST /admin/invalidar-cache/  → recebe callback do Django ao editar regra
- GET  /regras          → lista regras carregadas em cache (debug)

Endpoints legados (mantidos pra retrocompat):
- POST /validar/etapa   → modelo antigo com etapa explícita
- POST /validar/matrix  → modelo antigo compat N8N
- POST /conversar       → modelo dinâmico (API controla fluxo)
- GET  /contexto/{telefone} (debug)
- DELETE /contexto/{telefone} (reset)
"""
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import config
from src.contexto.conversa import gerenciador
from src.contexto.fluxo import listar_fluxos, carregar_fluxo
from src.conversa import conversar
from src.ia.validador import validar as validar_legado
from src.onboarding import decidir_proximo_passo, decidir_recontato
from src.regras import regras_client, validar_por_regra

logging.basicConfig(level=config.LOG_LEVEL,
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


app = FastAPI(
    title='Megalink IA Validação',
    description='Validador dinâmico baseado em regras (RegraValidacao no Django) + ações em background',
    version='2.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# ── Camada conversacional (ISOLADA) — rotas sob /conv ─────────────────
# Não afeta /validar nem /proximo-passo. Falha no import não derruba o app.
try:
    from src.conversacional.rotas import router as conv_router
    app.include_router(conv_router)
except Exception as _e:  # pragma: no cover
    logger.warning('Camada conversacional não carregada: %s', _e)


# ─────────────────────────────────────────────────────────────────────
# SCHEMAS — V2 (novo)
# ─────────────────────────────────────────────────────────────────────

class ValidarV2Request(BaseModel):
    """Schema v2 — usado pelo flow.json novo."""
    question: str = Field(..., description='Texto da pergunta feita ao cliente')
    answer: str = Field(..., description='Resposta do cliente (texto ou URL de imagem)')
    cellphone: str = Field(..., description='Telefone do contato')
    lead_id: Optional[int] = Field(default=None, description='ID do lead no Django (se já existe)')
    question_id: Optional[str] = Field(default='', description='Identificador da regra (opcional). Se vier, lookup direto.')


class ProximoPassoRequest(BaseModel):
    """Decisor de roteamento inicial — chamado uma vez quando cliente entra no fluxo."""
    cellphone: str = Field(..., description='Telefone do contato')
    lead_id: Optional[int] = Field(default=None, description='ID do lead (opcional; busca pelo telefone se ausente)')
    ultima_mensagem: Optional[str] = Field(default='', description='Última mensagem do cliente (ajuda detectar intent)')


class ProximoPassoResponse(BaseModel):
    lead_id: Optional[int]
    status_lead: str
    proximo_passo: str
    proxima_pergunta_id: str
    deve_perguntar: bool
    deve_transbordar: bool
    motivo: str
    mensagem_inicial: str         # com \n (use em msg pro cliente — fica bonita no WhatsApp)
    mensagem_inicial_safe: str    # sem \n (use em body de outras APIs — evita JSON quebrado)
    intent_detectado: str
    dados_ja_coletados: dict
    # URA estruturada (aditivo): null quando a pergunta é aberta; quando é URA de
    # opções → {tipo, titulo, pergunta, opcoes:[{numero,texto}], total_opcoes,
    # respostas_validas}. Título = id da pergunta (ex.: tipo_imovel).
    ura: Optional[dict] = None


class RecontatoRequest(BaseModel):
    """Chamado pelo Matrix quando o cliente NÃO respondeu (tempo de espera)."""
    cellphone: str = Field(..., description='Telefone do contato')
    lead_id: Optional[int] = Field(default=None, description='ID do lead (opcional)')
    pergunta_id: Optional[str] = Field(default='', description='Identificador da pergunta que ficou pendente (opcional)')
    ultima_mensagem: Optional[str] = Field(default='', description='Última mensagem enviada ao cliente (opcional)')


class RecontatoResponse(BaseModel):
    acao: str                     # 'recontatar' | 'encerrar'
    tentativa: int                # nº do silêncio consecutivo (1, 2, 3...)
    max_tentativas: int
    mensagem: str                 # texto de reengajamento (com \n)
    mensagem_safe: str            # sem \n — use em body JSON de outra API
    reperguntar: bool             # dica: na última tentativa pode emendar a pergunta
    pergunta_id: str              # a pergunta pendente (devolvida p/ conveniência)
    deve_transbordar: bool


class AcaoExecutada(BaseModel):
    tipo: str
    ok: bool
    detalhes: Optional[str] = None


class ValidarV2Response(BaseModel):
    valido: bool
    extracted_data: dict = {}
    message: str = ''
    motivo_invalido: str = ''
    intent: str = ''
    transbordo: bool = False
    fim_fluxo: bool = False
    actions_executed: list = []
    regra_aplicada: str = ''
    tentativas: int = 0
    usou_ia: bool = False
    confianca: float = 0.0
    # Campos LEGADOS retornados também (compat com flow Matrix antigo)
    answerIsCorrect: str = 'true'
    resposta_correta: str = 'true'
    resposta_sem_erro_api: str = 'true'
    errorMessage: str = ''
    retorno_erro_api: str = ''
    isAClient: str = 'false'
    hasCancelledService: str = 'false'
    cancelado: str = 'false'
    needsReception: str = 'false'
    time_instalacao: str = ''
    viabilidade_cep: str = 'false'
    givesServiceToCity: str = 'true'
    api_cep: str = ''
    ret_cep: str = ''
    ret_estado: str = ''
    ret_cidade: str = ''
    ret_bairro: str = ''
    ret_rua: str = ''


# ─────────────────────────────────────────────────────────────────────
# SCHEMAS — LEGADO (compatibilidade)
# ─────────────────────────────────────────────────────────────────────

class ValidarLegadoRequest(BaseModel):
    telefone: str
    etapa: str
    resposta: str
    fluxo: str = 'vendas_megalink'
    pergunta: Optional[str] = ''
    contexto: Optional[dict] = None


class ValidarMatrixRequest(BaseModel):
    """Compatível com api_16 DynamicValidator antigo (sem question_id)."""
    question: str
    answer: str
    telefone: str
    cellphone: Optional[str] = None  # alias


class ConversarRequest(BaseModel):
    telefone: str
    mensagem: str
    fluxo: str = 'vendas_megalink'
    url_imagem: Optional[str] = ''


# ─────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@app.get('/')
def health():
    erros = config.validar()
    return {
        'status': 'ok' if not erros else 'config_pendente',
        'versao': '2.0.0',
        'persona': config.PERSONA_NOME,
        'modelo_ia': config.OPENAI_MODEL,
        'erros_config': erros,
        'regras_stats': regras_client.stats(),
        'fluxos_yaml_legados': listar_fluxos(),
    }


# ───────────── VALIDADOR V2 (PRINCIPAL) ─────────────────────────────

def _log_interacao_async(endpoint: str, req_dict: dict, resp_dict: dict,
                          duracao_ms: int) -> None:
    """Dispara log pro Django em background."""
    try:
        from src.integracoes import log_interacao as _li
        from src.integracoes.robovendas import robovendas as _rv
        _li.registrar_log(
            base_url=_rv.base_url,
            endpoint=endpoint,
            cellphone=str(req_dict.get('cellphone') or ''),
            lead_id=req_dict.get('lead_id'),
            question_id=str(req_dict.get('question_id') or req_dict.get('question') or ''),
            answer=str(req_dict.get('answer') or ''),
            mensagem_resposta=str(resp_dict.get('mensagem_resposta')
                                  or resp_dict.get('message')
                                  or resp_dict.get('mensagem_inicial') or ''),
            payload_in=req_dict, payload_out=resp_dict,
            duracao_ms=duracao_ms,
            valido=resp_dict.get('valido') if isinstance(resp_dict.get('valido'), bool) else None,
            transbordou=bool(resp_dict.get('transbordo')
                              or resp_dict.get('deve_transbordar') in (True, 'true')),
            motivo=str(resp_dict.get('motivo')
                       or resp_dict.get('motivo_invalido') or ''),
        )
    except Exception as e:
        logger.debug('Falha logar interação: %s', e)


_KW_VOLTAR_MENU = ('menu', 'voltar', 'cancelar', 'desistir', 'sair',
                   'recomeçar', 'recomecar', 'voltar ao menu', 'voltar menu')


def _eh_voltar_menu_engine(texto: str) -> bool:
    """True se a resposta é um pedido exato de voltar ao menu/desistir do fluxo."""
    s = (texto or '').lower().strip().rstrip('!.?')
    return s in _KW_VOLTAR_MENU


def _resposta_voltar_menu() -> dict:
    """Resposta do /validar que ACEITA a keyword 'voltar ao menu' (valido=true)
    — o /proximo-passo seguinte detecta a keyword, abandona o fluxo e mostra o
    menu. Compat com o flow Matrix (answerIsCorrect=true)."""
    return {
        'valido': True, 'extracted_data': {}, 'message': '',
        'motivo_invalido': '', 'intent': 'voltar_menu',
        'transbordo': False, 'fim_fluxo': False,
        'actions_executed': ['voltar_menu'], 'regra_aplicada': 'voltar_menu',
        'tentativas': 0, 'usou_ia': False, 'confianca': 0.9,
        'answerIsCorrect': 'true', 'resposta_correta': 'true',
        'resposta_sem_erro_api': 'true', 'errorMessage': '',
        'retorno_erro_api': '', 'isAClient': 'false',
        'hasCancelledService': 'false', 'cancelado': 'false',
        'needsReception': 'false', 'time_instalacao': '',
        'viabilidade_cep': 'false', 'givesServiceToCity': 'true',
        'api_cep': '', 'ret_cep': '', 'ret_estado': '',
        'ret_cidade': '', 'ret_bairro': '', 'ret_rua': '',
    }


def _validar_turno_upgrade(req) -> dict:
    """Submete a resposta do cliente à pergunta atual do fluxo de upgrade
    (Django /api/upgrade-conversa/turno/ em modo 'responder') e devolve o
    contrato que o flow Matrix espera. A PRÓXIMA pergunta vem na próxima
    chamada de /proximo-passo (status_api='em_fluxo_upgrade')."""
    from src.integracoes import robovendas

    resp = robovendas.turno_upgrade(req.lead_id, req.answer or '')
    valido = bool(resp.get('valido')) if resp else False
    erro = (resp or {}).get('erro') or ''
    # mensagem_pos: mensagem de sucesso quando a confirmação leva ao
    # encerramento — exibida como feedback antes do Matrix fechar.
    mensagem_pos = (resp or {}).get('mensagem_pos') or ''
    if valido:
        message = mensagem_pos
    else:
        message = erro or 'Não entendi sua escolha. Pode repetir?'
    return {
        'valido': valido,
        'extracted_data': {'valor': (req.answer or '').strip()},
        'message': message,
        'motivo_invalido': '' if valido else (erro or 'resposta não reconhecida'),
        'intent': '',
        'transbordo': False,
        'fim_fluxo': False,
        'actions_executed': ['upgrade_turno_responder'],
        'regra_aplicada': 'upgrade_turno',
        'tentativas': 0,
        'usou_ia': False,
        'confianca': 0.9 if valido else 0.2,
        # Compat — flow Matrix
        'answerIsCorrect': 'true' if valido else 'false',
        'resposta_correta': 'true' if valido else 'false',
        'resposta_sem_erro_api': 'true',
        'errorMessage': '' if valido else message,
        'retorno_erro_api': '',
        'isAClient': 'false',
        'hasCancelledService': 'false',
        'cancelado': 'false',
        'needsReception': 'false',
        'time_instalacao': '',
        'viabilidade_cep': 'false',
        'givesServiceToCity': 'true',
        'api_cep': '',
        'ret_cep': '',
        'ret_estado': '',
        'ret_cidade': '',
        'ret_bairro': '',
        'ret_rua': '',
    }


@app.post('/validar', response_model=ValidarV2Response)
def endpoint_validar_v2(req: ValidarV2Request):
    """Endpoint principal v2 — recebe {question, answer, cellphone, lead_id, question_id?}.

    Fluxo:
    1. Se question_id veio, lookup direto na RegraValidacao
    2. Senão, infere pela pergunta (com cache + fallback IA)
    3. Aplica extractor da regra (cpf, cep, imagem, opcao, ...)
    4. Executa ações em background (atualizar lead, status, tags, histórico)
    5. Retorna JSON estruturado pro Matrix
    """
    import time as _t
    _ini = _t.time()
    try:
        # 0a) "VOLTAR AO MENU" dentro de um fluxo (upgrade/novo serviço):
        # aceita a resposta (valido=true) pro flow Matrix/simulador seguir pro
        # /proximo-passo, que detecta a keyword e abandona o fluxo (mostra o
        # menu). Sem isso, o /validar do fluxo rejeitaria 'menu' e repetiria a
        # pergunta. Funciona IGUAL no Matrix porque está no engine compartilhado.
        if _eh_voltar_menu_engine(req.answer):
            _em_upgrade = (req.question_id or '').startswith('upgrade_')
            _status = ''
            try:
                from src.regras.alvo import consultar_lead_cached
                _status = (consultar_lead_cached(req.lead_id, req.cellphone) or {}
                           ).get('status_api') or ''
            except Exception:
                _status = ''
            if _em_upgrade or _status in ('em_fluxo_upgrade', 'em_fluxo_new_service'):
                resultado = _resposta_voltar_menu()
                _log_interacao_async('validar', req.dict(), resultado,
                                     int((_t.time() - _ini) * 1000))
                return resultado

        # 0b) Fluxo de UPGRADE — pergunta conduzida pelo /proximo-passo.
        # Submete a resposta direto no atendimento Django (turno responder).
        if (req.question_id or '').startswith('upgrade_'):
            resultado = _validar_turno_upgrade(req)
            _log_interacao_async('validar', req.dict(), resultado,
                                 int((_t.time() - _ini) * 1000))
            return resultado

        # 1) Identifica a regra
        regra = None
        if req.question_id:
            regra = regras_client.obter_por_id(req.question_id)
            if not regra:
                logger.warning(f'question_id "{req.question_id}" não encontrado — fallback por pergunta')

        if not regra:
            regra = regras_client.inferir_por_pergunta(req.question)

        if not regra:
            # Nenhuma regra encontrada — aceita "livre" mas retorna campos
            # legados preenchidos pra não travar o flow Matrix.
            logger.warning(f'Nenhuma regra aplicável pra pergunta: {req.question[:80]!r}')
            return {
                'valido': True,
                'extracted_data': {'valor': req.answer.strip()},
                'message': 'Anotei!',
                'motivo_invalido': '',
                'intent': '',
                'transbordo': False,
                'fim_fluxo': False,
                'actions_executed': [],
                'regra_aplicada': '_sem_regra',
                'tentativas': 0,
                'usou_ia': False,
                'confianca': 0.3,
                # Compat — flow Matrix antigo precisa desses
                'answerIsCorrect': 'true',
                'resposta_correta': 'true',
                'resposta_sem_erro_api': 'true',
                'errorMessage': '',
                'retorno_erro_api': '',
                'isAClient': 'false',
                'hasCancelledService': 'false',
                'cancelado': 'false',
                'needsReception': 'false',
                'time_instalacao': '',
                'viabilidade_cep': 'false',
                'givesServiceToCity': 'true',
                'api_cep': '',
                'ret_cep': '',
                'ret_estado': '',
                'ret_cidade': '',
                'ret_bairro': '',
                'ret_rua': '',
            }

        # 2) Aplica regra
        resultado = validar_por_regra(
            regra=regra,
            question=req.question,
            answer=req.answer,
            cellphone=req.cellphone,
            lead_id=req.lead_id,
        )
        _log_interacao_async('validar', req.dict(),
                              resultado if isinstance(resultado, dict) else {},
                              int((_t.time() - _ini) * 1000))
        return resultado

    except Exception as e:
        logger.exception(f'Erro em /validar v2: {e}')
        raise HTTPException(500, detail=str(e))


@app.post('/proximo-passo', response_model=ProximoPassoResponse)
def endpoint_proximo_passo(req: ProximoPassoRequest):
    """Decisor de roteamento inicial.

    Quando o cliente entra no fluxo Matrix, o flow chama este endpoint UMA VEZ
    passando {cellphone, lead_id, ultima_mensagem}. A API consulta o Django,
    olha o status_api do lead + campos preenchidos, e responde:
    - se é cliente novo → começa fluxo de vendas
    - se já tem dados parciais → retoma de onde parou
    - se já é cliente / cancelado → transbordo
    - se já está em outras etapas → atalho pro nó certo

    O Matrix usa o `proximo_passo` (identifier do nó) num red type=2
    pra fazer o jump dinâmico.
    """
    import time as _t
    _ini = _t.time()
    try:
        resultado = decidir_proximo_passo(
            telefone=req.cellphone,
            lead_id=req.lead_id,
            ultima_mensagem=req.ultima_mensagem or '',
        )
        _log_interacao_async('proximo-passo',
                              req.dict(),
                              resultado if isinstance(resultado, dict) else {},
                              int((_t.time() - _ini) * 1000))
        return resultado
    except Exception as e:
        logger.exception(f'Erro em /proximo-passo: {e}')
        raise HTTPException(500, detail=str(e))


@app.post('/recontato', response_model=RecontatoResponse)
def endpoint_recontato(req: RecontatoRequest):
    """Recontato por TEMPO DE ESPERA (cliente não respondeu à pergunta).

    O Matrix chama este endpoint no ramo "tempo de espera" do nó de pergunta.
    A API escala uma mensagem de reengajamento DIFERENTE a cada silêncio
    consecutivo (fisga o cliente, sem repetir a pergunta) e, após o máximo de
    tentativas, responde `acao='encerrar'`. O contador zera sozinho quando o
    cliente volta a responder (no /validar).

    Uso no Matrix (ramo "tempo de espera"):
      - acao == 'recontatar' → envie `mensagem` e volte a AGUARDAR a resposta.
          • se o cliente responder → re-pergunte a pendente (chame /proximo-passo
            ou volte ao nó da pergunta).
          • se estourar o tempo de novo → chame /recontato outra vez.
      - acao == 'encerrar' → siga para o nó de encerramento/pausa.
    """
    import time as _t
    _ini = _t.time()
    try:
        resultado = decidir_recontato(
            telefone=req.cellphone,
            lead_id=req.lead_id,
            pergunta_id=req.pergunta_id or '',
            ultima_mensagem=req.ultima_mensagem or '',
        )
        _log_interacao_async('recontato', req.dict(),
                             resultado if isinstance(resultado, dict) else {},
                             int((_t.time() - _ini) * 1000))
        return resultado
    except Exception as e:
        logger.exception(f'Erro em /recontato: {e}')
        raise HTTPException(500, detail=str(e))


@app.post('/admin/invalidar-cache/')
def endpoint_invalidar_cache():
    """Callback chamado pelo Django quando uma regra OU mensagem é editada."""
    regras_client.invalidar_cache()
    try:
        from src.regras.mensagens_client import mensagens_client
        mensagens_client.invalidar_cache()
    except Exception:
        pass
    return {'ok': True}


@app.get('/regras')
def endpoint_listar_regras():
    """Debug — lista o que está em cache."""
    regras_client._recarregar_se_necessario()
    return {
        'stats': regras_client.stats(),
        'regras': [
            {'question_id': qid, 'extractor': r.get('extractor_tipo'),
             'campo': r.get('campo_lead_atualizar'), 'pergunta': r.get('pergunta_padrao', '')[:60]}
            for qid, r in regras_client._cache_regras.items()
        ],
    }


# ───────────── ENDPOINTS LEGADOS ────────────────────────────────────

@app.post('/validar/etapa')
def endpoint_validar_etapa(req: ValidarLegadoRequest):
    """Legado: validação por etapa do fluxo YAML. Mantido pra retrocompat."""
    try:
        return validar_legado(
            telefone=req.telefone,
            etapa_id=req.etapa,
            resposta_cliente=req.resposta,
            fluxo_nome=req.fluxo,
            pergunta_extra=req.pergunta or '',
            contexto_extra=req.contexto,
        )
    except Exception as e:
        logger.exception(f'Erro em /validar/etapa: {e}')
        raise HTTPException(500, detail=str(e))


@app.post('/validar/matrix')
def endpoint_validar_matrix(req: ValidarMatrixRequest):
    """Legado N8N: {question, answer, telefone}. Mapeia pro validador v2."""
    cellphone = req.cellphone or req.telefone
    return endpoint_validar_v2(ValidarV2Request(
        question=req.question, answer=req.answer,
        cellphone=cellphone, lead_id=None, question_id='',
    ))


# ───────────── VALIDAÇÃO DE IMAGEM (uso direto pelo site /cadastro/) ─────

class ValidarImagemRequest(BaseModel):
    url: str = Field(..., description='URL pública da imagem (http/https)')
    descricao: str = Field(..., description='selfie_com_doc | frente_doc | verso_doc')


class ValidarImagemResponse(BaseModel):
    aprovado: bool
    motivo_codigo: str
    motivo_humano: str
    msg_refoto: str = ''   # Mensagem amigável pra exibir quando rejeitado


@app.post('/validar-imagem', response_model=ValidarImagemResponse)
def endpoint_validar_imagem(req: ValidarImagemRequest):
    """Valida uma única imagem isoladamente via OpenAI Vision.

    Usado pelo formulário do site /cadastro/ pra dar feedback imediato
    no upload (cliente sabe em ~3s se a foto serve).

    Reaproveita exatamente a mesma função usada pelo WhatsApp.
    """
    import time as _t
    from src.integracoes import openai_imagens
    _ini = _t.time()
    try:
        resultado = openai_imagens.validar_imagem(
            url=req.url,
            descricao=req.descricao,
        )
        resp_dict = {
            'aprovado': resultado.aprovado,
            'motivo_codigo': resultado.motivo_codigo,
            'motivo_humano': resultado.motivo_humano,
            'msg_refoto': resultado.msg_refoto,
        }
        _log_interacao_async('validar-imagem', req.dict(), resp_dict,
                              int((_t.time() - _ini) * 1000))
        return ValidarImagemResponse(**resp_dict)
    except Exception as e:
        logger.exception(f'Erro em /validar-imagem: {e}')
        raise HTTPException(500, detail=str(e))


@app.post('/conversar')
def endpoint_conversar(req: ConversarRequest):
    """Legado modelo dinâmico — API controla fluxo (deprecated)."""
    try:
        return conversar(
            telefone=req.telefone,
            mensagem=req.mensagem,
            fluxo_nome=req.fluxo,
            url_imagem=req.url_imagem or '',
        )
    except Exception as e:
        logger.exception(f'Erro em /conversar: {e}')
        raise HTTPException(500, detail=str(e))


# ───────────── DEBUG / CONTEXTO ─────────────────────────────────────

@app.get('/contexto/{telefone}')
def endpoint_contexto(telefone: str):
    ctx = gerenciador.obter(telefone)
    return {
        'telefone': telefone,
        'etapa_atual': ctx.get('etapa_atual', ''),
        'dados_extraidos': ctx.get('dados_extraidos', {}),
        'historico_count': len(ctx.get('historico', [])),
        'tentativas': dict(ctx.get('tentativas', {})),
        'lead_id': ctx.get('lead_id'),
    }


@app.delete('/contexto/{telefone}')
def endpoint_reset_contexto(telefone: str):
    if telefone in gerenciador._dados:
        del gerenciador._dados[telefone]
    return {'ok': True}


@app.get('/fluxos')
def endpoint_listar_fluxos():
    return {'fluxos': listar_fluxos()}


@app.get('/fluxos/{nome}')
def endpoint_obter_fluxo(nome: str):
    f = carregar_fluxo(nome)
    if not f:
        raise HTTPException(404, 'Fluxo não encontrado')
    return f
