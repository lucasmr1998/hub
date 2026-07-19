"""Lógica central de validação dinâmica.

Estratégia:
1. Se a etapa tem extractor local (cpf, cep, etc), tenta extrair sem chamar IA.
2. Se o extractor falhar OU a etapa exige análise semântica, chama OpenAI.
3. Retorna resposta estruturada padronizada.
"""
import logging
import threading
from typing import Any

from src.config import config
from src.contexto.conversa import gerenciador
from src.contexto.fluxo import obter_etapa
from src.extractors import (
    extrair_cpf, validar_cpf,
    extrair_cep, validar_cep, consultar_cep_viacep,
    extrair_nome,
    extrair_telefone,
    extrair_data_nascimento,
)
from src.acoes import executar_acoes
from src.ia.openai_client import client as openai_client
from src.ia.prompts import PERSONA_SYSTEM, prompt_validar_etapa
from src.integracoes import robovendas

logger = logging.getLogger(__name__)


def _validar_local(extractor: str, resposta: str) -> dict | None:
    """Tenta validar localmente. Retorna dict no formato padrão ou None se inconclusivo."""
    if extractor == 'cpf':
        cpf = extrair_cpf(resposta)
        if cpf:
            if validar_cpf(cpf):
                return {
                    'valido': True,
                    'dados_extraidos': {'cpf': cpf},
                    'motivo_invalido': '',
                    'confianca': 1.0,
                    'usou_ia': False,
                }
            return {
                'valido': False,
                'dados_extraidos': {},
                'motivo_invalido': 'cpf_invalido',
                'confianca': 1.0,
                'usou_ia': False,
            }
        # Sem dígitos identificáveis — deixa IA decidir (cliente pode ter dito "nao tenho", "depois", etc)
        return None

    if extractor == 'cep':
        cep = extrair_cep(resposta)
        if cep:
            via = consultar_cep_viacep(cep)
            if via:
                return {
                    'valido': True,
                    'dados_extraidos': {
                        'cep': cep,
                        'logradouro': via.get('logradouro', ''),
                        'bairro': via.get('bairro', ''),
                        'cidade': via.get('localidade', ''),
                        'estado': via.get('uf', ''),
                    },
                    'motivo_invalido': '',
                    'confianca': 1.0,
                    'usou_ia': False,
                }
            return {
                'valido': False, 'dados_extraidos': {},
                'motivo_invalido': 'cep_nao_existe',
                'confianca': 1.0, 'usou_ia': False,
            }
        return None

    if extractor == 'nome':
        r = extrair_nome(resposta)
        # Nomes podem ter formas ambíguas — só aceita local se claramente válido
        if r['valido']:
            return {
                'valido': True,
                'dados_extraidos': {'nome': r['nome']},
                'motivo_invalido': '',
                'confianca': 0.9,
                'usou_ia': False,
            }
        # Se inválido, deixa IA tentar entender (cliente pode ter respondido "joao silva ribeiro")
        return None

    if extractor == 'telefone':
        tel = extrair_telefone(resposta)
        if tel:
            return {
                'valido': True,
                'dados_extraidos': {'telefone': tel},
                'motivo_invalido': '',
                'confianca': 1.0,
                'usou_ia': False,
            }
        return {
            'valido': False, 'dados_extraidos': {},
            'motivo_invalido': 'telefone_invalido',
            'confianca': 1.0, 'usou_ia': False,
        }

    if extractor == 'data_nascimento':
        r = extrair_data_nascimento(resposta)
        if r['valido']:
            return {
                'valido': True,
                'dados_extraidos': {
                    'data_nascimento': r['data'],
                    'idade': r['idade'],
                },
                'motivo_invalido': '',
                'confianca': 1.0, 'usou_ia': False,
            }
        if r['motivo'] == 'menor_de_idade':
            return {
                'valido': False, 'dados_extraidos': {'idade': r['idade']},
                'motivo_invalido': 'menor_de_idade',
                'confianca': 1.0, 'usou_ia': False,
            }
        return None

    return None


def _validar_via_ia(
    etapa_id: str,
    pergunta: str,
    resposta: str,
    contexto: dict,
    historico: list,
    instrucoes_etapa: str = '',
) -> dict:
    """Chama OpenAI para validar de forma semântica."""
    user = prompt_validar_etapa(
        etapa_id=etapa_id,
        pergunta=pergunta,
        resposta=resposta,
        contexto=contexto,
        historico=historico,
        instrucoes_etapa=instrucoes_etapa,
    )
    try:
        result = openai_client.chat_json(
            system=PERSONA_SYSTEM,
            user=user,
            temperatura=0.4,
            max_tokens=400,
        )
        return {
            'valido': bool(result.get('valido')),
            'dados_extraidos': result.get('dados_extraidos', {}),
            'mensagem_bot': result.get('mensagem_bot', ''),
            'motivo_invalido': result.get('motivo_invalido', ''),
            'confianca': float(result.get('confianca', 0.5)),
            'intencao_detectada': result.get('intencao_detectada', ''),
            'usou_ia': True,
        }
    except Exception as e:
        logger.exception(f"Erro ao chamar IA: {e}")
        return {
            'valido': False,
            'dados_extraidos': {},
            'mensagem_bot': 'Desculpe, tive um problema. Pode repetir, por favor?',
            'motivo_invalido': 'erro_ia',
            'confianca': 0.0,
            'usou_ia': True,
        }


def _sync_django_background(
    telefone: str,
    dados_extraidos: dict,
    etapa_id: str,
    acoes: list[dict] | None = None,
    url_imagem: str = '',
):
    """Sincroniza dados com Django + roda acoes_pos_etapa em background."""
    if not config.ROBOVENDAS_API_URL:
        return
    try:
        conversa = gerenciador.obter(telefone)
        lead_id = conversa.get('lead_id')
        if not lead_id:
            lead_id = robovendas.garantir_lead(telefone)
            if lead_id:
                conversa['lead_id'] = lead_id
        if lead_id and dados_extraidos:
            robovendas.sincronizar_dados(lead_id, dados_extraidos)
        if acoes:
            ctx = {
                'nome': conversa.get('dados_extraidos', {}).get('nome', ''),
                'url_imagem': url_imagem,
            }
            executar_acoes(telefone, lead_id, acoes, contexto=ctx)
    except Exception as e:
        logger.warning(f'_sync_django_background falhou: {e}')


def _disparar_sync(
    telefone: str,
    dados_extraidos: dict,
    etapa_id: str,
    acoes: list[dict] | None = None,
    url_imagem: str = '',
):
    """Dispara a sincronização em thread daemon — não atrasa a resposta."""
    if not dados_extraidos and not acoes:
        return
    t = threading.Thread(
        target=_sync_django_background,
        args=(telefone, dict(dados_extraidos or {}), etapa_id),
        kwargs={'acoes': list(acoes or []), 'url_imagem': url_imagem},
        daemon=True,
    )
    t.start()


def validar(
    telefone: str,
    etapa_id: str,
    resposta_cliente: str,
    fluxo_nome: str = 'vendas_megalink',
    pergunta_extra: str = '',
    contexto_extra: dict | None = None,
) -> dict:
    """Função pública: valida uma resposta dentro do contexto de uma etapa."""
    etapa = obter_etapa(fluxo_nome, etapa_id) or {}
    pergunta = etapa.get('pergunta') or pergunta_extra or ''
    extractor = etapa.get('extractor', '')
    max_tentativas = etapa.get('max_tentativas', 3)

    # Contexto + histórico
    conversa = gerenciador.obter(telefone)
    if contexto_extra:
        for k, v in contexto_extra.items():
            conversa['dados_extraidos'].setdefault(k, v)

    gerenciador.adicionar_msg(telefone, 'cliente', resposta_cliente)
    gerenciador.definir_etapa(telefone, etapa_id)

    # 1. Tentativa local
    resultado_local = _validar_local(extractor, resposta_cliente) if extractor else None

    if resultado_local and resultado_local.get('valido'):
        for k, v in resultado_local['dados_extraidos'].items():
            gerenciador.salvar_dado(telefone, k, v)
        gerenciador.resetar_tentativas(telefone, etapa_id)
        proxima = etapa.get('proxima', '')
        msg = etapa.get('on_success_msg') or f"Perfeito! "
        _disparar_sync(
            telefone,
            resultado_local['dados_extraidos'],
            etapa_id,
            acoes=etapa.get('acoes_pos_etapa', []),
        )
        return {
            **resultado_local,
            'mensagem_bot': msg,
            'proxima_etapa': proxima,
            'tentativas': 0,
        }

    # 2. Tentativa via IA (validação semântica)
    historico = conversa['historico']
    resultado_ia = _validar_via_ia(
        etapa_id=etapa_id,
        pergunta=pergunta,
        resposta=resposta_cliente,
        contexto=conversa['dados_extraidos'],
        historico=historico,
        instrucoes_etapa=etapa.get('instrucoes_ia', ''),
    )

    if resultado_ia.get('valido'):
        # Se IA validou, mesclar com extractor local
        if resultado_local is not None:
            resultado_ia['dados_extraidos'] = {**resultado_local.get('dados_extraidos', {}), **resultado_ia['dados_extraidos']}
        for k, v in resultado_ia.get('dados_extraidos', {}).items():
            gerenciador.salvar_dado(telefone, k, v)
        gerenciador.resetar_tentativas(telefone, etapa_id)
        gerenciador.adicionar_msg(telefone, 'bot', resultado_ia['mensagem_bot'])
        _disparar_sync(
            telefone,
            resultado_ia.get('dados_extraidos', {}),
            etapa_id,
            acoes=etapa.get('acoes_pos_etapa', []),
        )
        return {
            **resultado_ia,
            'proxima_etapa': etapa.get('proxima', ''),
            'tentativas': 0,
        }

    # 3. Inválido — incrementa tentativa
    tentativas = gerenciador.incrementar_tentativa(telefone, etapa_id)
    msg = resultado_ia.get('mensagem_bot') or etapa.get('on_invalid') or 'Hum, não entendi. Pode repetir?'

    if tentativas >= max_tentativas:
        msg = etapa.get('on_max_tentativas') or 'Vou transferir você para um atendente. Aguarde um momentinho!'
        gerenciador.adicionar_msg(telefone, 'bot', msg)
        return {
            **resultado_ia,
            'valido': False,
            'mensagem_bot': msg,
            'proxima_etapa': 'transbordo_humano',
            'tentativas': tentativas,
        }

    gerenciador.adicionar_msg(telefone, 'bot', msg)
    return {
        **resultado_ia,
        'mensagem_bot': msg,
        'proxima_etapa': etapa_id,  # repete a mesma etapa
        'tentativas': tentativas,
    }
