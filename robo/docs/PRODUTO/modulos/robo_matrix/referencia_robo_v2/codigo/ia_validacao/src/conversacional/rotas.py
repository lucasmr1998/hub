"""Rotas da camada conversacional (APIRouter isolado).

Montadas sob o prefixo /conv. NÃO afetam /ia/validar nem /ia/proximo-passo.
O flow Matrix novo (opt-in) chama estas rotas; o flow atual segue intacto.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/conv', tags=['conversacional'])


class TurnoRequest(BaseModel):
    """Schema tolerante: aceita os vários formatos que o Matrix pode mandar.

    - lead_id: aceita int, string numérica, string vazia ou ausente → None
    - mensagem do cliente: aceita 'mensagem', 'ultima_mensagem' ou 'answer'
    - etapa atual: aceita 'question_id' ou 'question'
    """
    cellphone: str = Field('', description='Telefone do cliente')
    lead_id: int | None = Field(None, description='ID do lead (se já existe)')
    mensagem: str = ''
    ultima_mensagem: str = ''
    answer: str = ''
    question_id: str = ''
    question: str = ''

    @field_validator('lead_id', mode='before')
    @classmethod
    def _parse_lead_id(cls, v):
        # Matrix às vezes manda "" ou "null" — tratamos como ausente.
        if v in (None, '', 'null', 'None', 'undefined'):
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @property
    def texto_cliente(self) -> str:
        return (self.mensagem or self.ultima_mensagem or self.answer or '').strip()

    @property
    def qid(self) -> str:
        return (self.question_id or self.question or '').strip()

    @property
    def modo(self) -> str:
        """Distingue as DUAS chamadas do flow do Matrix pela forma do body:

        - api_proximo_passo manda só {ultima_mensagem} → modo 'rotear'
          (decide a próxima pergunta, NÃO valida).
        - api_validar manda {answer, question_id} → modo 'validar'
          (valida a resposta do cliente).
        """
        tem_resposta = bool((self.answer or '').strip()
                            or (self.question_id or '').strip()
                            or (self.question or '').strip())
        return 'validar' if tem_resposta else 'rotear'


class TurnoResponse(BaseModel):
    valido: bool
    mensagem: str
    campos_salvos: list[str]
    proxima_pergunta_id: str
    transbordo: bool
    tem_pergunta_cliente: bool
    usou_ia: bool
    # campos legados pro Matrix (compat com o estilo dos outros endpoints)
    needsReception: str
    mensagem_resposta: str
    # ── Contrato esperado pelo flow não-determinístico do Matrix ──────
    # O `store` de cada nó mapeia a resposta POR NOME de campo. Estes são
    # os nomes que o flow lê (ver fluxos/flow_matrix_conversacional.json):
    resposta_correta: str        # "true"/"false" → branch principal (valido)
    message: str                 # mensagem de SUCESSO (→ {#mensagem_resposta})
    retorno_erro_api: str        # mensagem de ERRO (→ {#retorno_erro_api})
    isAClient: str               # "true"/"false" (cliente Hubsoft)
    deve_transbordar: str        # "true"/"false"
    encerrar: str                # "true"/"false" (finalizar atendimento)
    status_lead: str
    proximo_passo: str


def _mapear_resposta(r: dict) -> dict:
    """Traduz a saída do orquestrador pros nomes que o flow do Matrix espera.

    Regra (mutuamente exclusivos): em sucesso vai `message`; em erro vai
    `retorno_erro_api`. O flow ramifica por `resposta_correta`/`needsReception`.
    """
    transbordo = bool(r.get('transbordo'))
    valido = bool(r.get('valido'))
    msg = r.get('mensagem') or ''

    if transbordo or valido:
        resposta_correta = 'true'
        message = msg
        retorno_erro = ''
    else:
        resposta_correta = 'false'
        message = ''
        retorno_erro = msg

    flag = lambda b: 'true' if b else 'false'  # noqa: E731
    return {
        # compat / debug
        'valido': valido,
        'mensagem': msg,
        'campos_salvos': r.get('campos_salvos') or [],
        'proxima_pergunta_id': r.get('proxima_pergunta_id') or '',
        'transbordo': transbordo,
        'tem_pergunta_cliente': bool(r.get('tem_pergunta_cliente')),
        'usou_ia': bool(r.get('usou_ia')),
        'mensagem_resposta': msg,
        # contrato do flow
        'needsReception': flag(transbordo),
        'deve_transbordar': flag(transbordo),
        'resposta_correta': resposta_correta,
        'message': message,
        'retorno_erro_api': retorno_erro,
        'isAClient': flag(r.get('is_cliente')),
        'encerrar': flag(r.get('encerrar')),
        'status_lead': r.get('status_lead') or '',
        'proximo_passo': r.get('proximo_passo') or '',
    }


@router.post('/turno', response_model=TurnoResponse)
def endpoint_turno(req: TurnoRequest):
    """Processa um turno conversacional (humanizar + extrair + FAQ).

    Reusa o núcleo determinístico pra validar/salvar/rotear. Em qualquer
    falha de IA, cai no comportamento determinístico.
    """
    import time as _t
    from src.conversacional.orquestrador import processar_turno
    _ini = _t.time()
    try:
        r = processar_turno(
            cellphone=req.cellphone,
            lead_id=req.lead_id,
            mensagem=req.texto_cliente,
            question_id=req.qid,
            modo=req.modo,
        )
        # ── Registra o log de comunicação (visibilidade do agente) ────
        try:
            from src.integracoes import log_interacao as _li
            from src.integracoes.robovendas import robovendas as _rv
            analise = r.get('analise') or {}
            _li.registrar_log(
                base_url=_rv.base_url,
                endpoint='conv-turno',
                cellphone=req.cellphone,
                lead_id=req.lead_id,
                question_id=r.get('qid_atual', ''),
                answer=req.texto_cliente,
                mensagem_resposta=r.get('mensagem', ''),
                payload_in={
                    'mensagem_cliente': req.texto_cliente,
                    'qid_atual': r.get('qid_atual', ''),
                    'ia_extraiu': {
                        'campos': analise.get('campos'),
                        'opcao_numerica': analise.get('opcao_numerica'),
                        'confirmacao': analise.get('confirmacao'),
                        'tem_pergunta': analise.get('tem_pergunta'),
                        'pergunta_texto': analise.get('pergunta_texto'),
                        'intencao': analise.get('intencao'),
                    },
                },
                payload_out={
                    'campos_salvos': r.get('campos_salvos'),
                    'proxima_pergunta_id': r.get('proxima_pergunta_id'),
                    'transbordo': r.get('transbordo'),
                    'mensagem': r.get('mensagem', '')[:500],
                },
                duracao_ms=int((_t.time() - _ini) * 1000),
                valido=r.get('valido'),
                transbordou=bool(r.get('transbordo')),
                motivo=r.get('motivo_invalido', ''),
            )
        except Exception as _le:
            logger.debug('Falha logar conv-turno: %s', _le)
        return _mapear_resposta(r)
    except Exception as e:
        logger.exception('Erro em /conv/turno: %s', e)
        raise HTTPException(500, detail=str(e))


@router.get('/health')
def health():
    """Status da camada conversacional + modelo em uso."""
    from src.conversacional.config import conv_config
    return {
        'status': 'ok',
        'modelo_conversa': conv_config.MODELO_CONVERSA,
        'modelo_rapido': conv_config.MODELO_RAPIDO,
        'passo1_humanizar': conv_config.PASSO1_HUMANIZAR,
        'passo2_extracao': conv_config.PASSO2_EXTRACAO,
        'passo3_faq': conv_config.PASSO3_FAQ,
    }
