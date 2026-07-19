"""Endpoint `/conversar` — modelo dinâmico com tipo_acao.

Recebe {telefone, mensagem, [url_imagem]} e retorna:
  - mensagem_bot: texto pra Matrix enviar
  - tipo_acao: o que o Matrix deve fazer a seguir
      "responder"          → exibe mensagem, volta pro sol_loop (caminho default)
      "pedir_imagem"       → exibe mensagem, espera upload de imagem
      "aguarda_hubsoft"    → API entra em polling, Matrix mostra "aguarde..."
      "agendar"            → dispara sub-fluxo de agendamento (URAs Matrix)
      "transbordo"         → exibe msg + ser_humano
      "fim"                → exibe msg + fin
  - proxima_etapa, fim_fluxo, transbordo_humano, dados_extraidos, etc.
"""
from __future__ import annotations

import logging
import time

from src.contexto.conversa import gerenciador
from src.contexto.fluxo import carregar_fluxo, obter_etapa
from src.ia.validador import validar, _disparar_sync
from src.integracoes import robovendas
from src.integracoes.robovendas import PLANOS

logger = logging.getLogger(__name__)


ETAPAS_FIM = {'fim', 'encerramento'}
ETAPAS_TRANSBORDO = {'transbordo_humano'}

# Mapeamento tipo_yaml → tipo_acao Matrix
TIPO_YAML_PARA_ACAO = {
    'pergunta': 'responder',
    'confirmacao': 'responder',
    'coleta_imagem': 'pedir_imagem',
    'aguarda_hubsoft': 'aguarda_hubsoft',
    'escolha_data': 'responder',  # opções já vêm na pergunta
    'agendamento_final': 'fim',
    'fim': 'fim',
    'transbordo': 'transbordo',
}


def _substituir_placeholders(texto: str, telefone: str, contexto_dados: dict) -> str:
    """Substitui {placeholders} na pergunta com dados do contexto.

    Suporta: {nome}, {cpf}, {telefone}, {cidade}, {bairro}, {rua}, {cep},
    {numero_residencia}, {data_nascimento}, {plano_titulo}, {valor_plano},
    {dia_vencimento}, {data_1}, {data_2}, {data_3}.
    """
    if '{' not in texto:
        return texto

    dados = dict(contexto_dados)
    dados.setdefault('telefone', telefone)

    # Aliases — ViaCEP retorna "logradouro", YAML usa "rua"
    if dados.get('logradouro') and not dados.get('rua'):
        dados['rua'] = dados['logradouro']
    if dados.get('localidade') and not dados.get('cidade'):
        dados['cidade'] = dados['localidade']

    # Enriquece com derivados de plano_velocidade
    plano_v = dados.get('plano_velocidade')
    if plano_v:
        chave = str(plano_v).strip().lower().replace(' ', '').replace('mb', '').replace('mega', '')
        plano = PLANOS.get(chave)
        if plano:
            dados.setdefault('plano_titulo', plano['titulo'])
            dados.setdefault('valor_plano', f"{plano['valor']:.2f}".replace('.', ','))

    # Datas de instalação (vêm do polling de agenda — fallback genérico)
    dados.setdefault('data_1', '—')
    dados.setdefault('data_2', '—')
    dados.setdefault('data_3', '—')

    # Defaults pra placeholders ausentes (não quebra a renderização)
    import re
    for placeholder in re.findall(r'\{([a-z_0-9]+)\}', texto):
        dados.setdefault(placeholder, '—')

    try:
        return texto.format(**dados)
    except (KeyError, IndexError):
        return texto  # fallback se sobrar algo


def _proxima_pergunta(fluxo_nome: str, etapa_id: str, telefone: str = '', contexto_dados: dict | None = None) -> str:
    if not etapa_id or etapa_id in ETAPAS_FIM or etapa_id in ETAPAS_TRANSBORDO:
        return ''
    etapa = obter_etapa(fluxo_nome, etapa_id) or {}
    pergunta = etapa.get('pergunta', '')
    if telefone and contexto_dados is not None:
        pergunta = _substituir_placeholders(pergunta, telefone, contexto_dados)
    return pergunta


def _tipo_acao(fluxo_nome: str, etapa_id: str) -> str:
    """Determina o tipo_acao baseado no `tipo` da etapa-alvo no YAML."""
    if not etapa_id:
        return 'fim'
    if etapa_id in ETAPAS_FIM:
        return 'fim'
    if etapa_id in ETAPAS_TRANSBORDO:
        return 'transbordo'
    etapa = obter_etapa(fluxo_nome, etapa_id) or {}
    return TIPO_YAML_PARA_ACAO.get(etapa.get('tipo', 'pergunta'), 'responder')


def conversar(
    telefone: str,
    mensagem: str,
    fluxo_nome: str = 'vendas_megalink',
    url_imagem: str = '',
) -> dict:
    """Endpoint dinâmico — uma chamada por turno do cliente.

    Args:
        telefone: identificador da conversa
        mensagem: texto digitado pelo cliente (ou URL se foi imagem)
        fluxo_nome: qual YAML usar
        url_imagem: se a "mensagem" foi um upload de imagem, a URL dela
    """
    conversa_ctx = gerenciador.obter(telefone)
    etapa_atual = conversa_ctx.get('etapa_atual', '')

    # Primeiro turno — começa pela 1ª etapa do fluxo
    if not etapa_atual:
        fluxo = carregar_fluxo(fluxo_nome) or {}
        etapas = fluxo.get('etapas', [])
        if etapas:
            etapa_atual = etapas[0]['id']

    etapa_def = obter_etapa(fluxo_nome, etapa_atual) or {}

    # ── Trata coleta de imagem como caso especial ────────────────────
    # Se a etapa atual é tipo coleta_imagem e o cliente mandou uma imagem,
    # registra a imagem direto no Django e avança a etapa SEM chamar IA.
    if etapa_def.get('tipo') == 'coleta_imagem' and url_imagem:
        descricao = etapa_def.get('descricao_imagem', 'documento')
        proxima_etapa = etapa_def.get('proxima', '')

        # registra a imagem em background
        _disparar_sync(
            telefone,
            dados_extraidos={},
            etapa_id=etapa_atual,
            acoes=[{'tipo': 'registrar_imagem', 'descricao': descricao}],
            url_imagem=url_imagem,
        )

        gerenciador.adicionar_msg(telefone, 'cliente', f'[imagem: {descricao}]')
        gerenciador.definir_etapa(telefone, proxima_etapa)

        msg_bot = f"Recebi! ##2705##"
        pergunta_proxima = _proxima_pergunta(fluxo_nome, proxima_etapa, telefone, conversa_ctx.get('dados_extraidos', {}))
        if pergunta_proxima:
            msg_bot = f"{msg_bot} {pergunta_proxima}"

        return {
            'mensagem_bot': msg_bot,
            'proxima_etapa': proxima_etapa,
            'etapa_anterior': etapa_atual,
            'tipo_acao': _tipo_acao(fluxo_nome, proxima_etapa),
            'fim_fluxo': proxima_etapa in ETAPAS_FIM,
            'transbordo_humano': proxima_etapa in ETAPAS_TRANSBORDO,
            'intencao': '',
            'dados_extraidos': {},
            'tentativas': 0,
            'usou_ia': False,
        }

    # ── Trata aguarda_hubsoft (polling) como caso especial ───────────
    if etapa_def.get('tipo') == 'aguarda_hubsoft':
        lead_id = conversa_ctx.get('lead_id')
        if lead_id:
            status = robovendas.hubsoft_status(lead_id) or {}
            eh_cliente = status.get('eh_cliente_hubsoft') is True
            doc_validada = (status.get('lead') or {}).get('documentacao_validada') is True
            if eh_cliente and doc_validada:
                proxima_etapa = etapa_def.get('proxima', '')
                gerenciador.definir_etapa(telefone, proxima_etapa)
                pergunta = _proxima_pergunta(fluxo_nome, proxima_etapa, telefone, conversa_ctx.get('dados_extraidos', {}))
                return {
                    'mensagem_bot': f'Documentação validada! ##2705## {pergunta}',
                    'proxima_etapa': proxima_etapa,
                    'etapa_anterior': etapa_atual,
                    'tipo_acao': _tipo_acao(fluxo_nome, proxima_etapa),
                    'fim_fluxo': False,
                    'transbordo_humano': False,
                    'intencao': '',
                    'dados_extraidos': {},
                    'tentativas': 0,
                    'usou_ia': False,
                }
        # ainda aguardando
        return {
            'mensagem_bot': etapa_def.get('pergunta') or 'Aguarde, estou validando sua documentação...',
            'proxima_etapa': etapa_atual,
            'etapa_anterior': etapa_atual,
            'tipo_acao': 'aguarda_hubsoft',
            'fim_fluxo': False,
            'transbordo_humano': False,
            'intencao': '',
            'dados_extraidos': {},
            'tentativas': 0,
            'usou_ia': False,
        }

    # ── Caminho normal: valida a resposta via IA / extractor ─────────
    resultado = validar(
        telefone=telefone,
        etapa_id=etapa_atual,
        resposta_cliente=mensagem,
        fluxo_nome=fluxo_nome,
    )

    proxima_etapa = resultado.get('proxima_etapa', '')
    mensagem_bot = resultado.get('mensagem_bot', '')

    fim_fluxo = proxima_etapa in ETAPAS_FIM or not proxima_etapa
    transbordo = proxima_etapa in ETAPAS_TRANSBORDO

    # Se houve avanço — anexa a pergunta da próxima etapa
    if resultado.get('valido') and proxima_etapa and proxima_etapa != etapa_atual:
        pergunta_proxima = _proxima_pergunta(fluxo_nome, proxima_etapa, telefone, conversa_ctx.get('dados_extraidos', {}))
        if pergunta_proxima:
            mensagem_bot = f"{mensagem_bot.strip()} {pergunta_proxima}".strip()
        gerenciador.definir_etapa(telefone, proxima_etapa)

    return {
        'mensagem_bot': mensagem_bot,
        'proxima_etapa': proxima_etapa,
        'etapa_anterior': etapa_atual,
        'tipo_acao': _tipo_acao(fluxo_nome, proxima_etapa),
        'fim_fluxo': fim_fluxo,
        'transbordo_humano': transbordo,
        'intencao': resultado.get('intencao_detectada', ''),
        'dados_extraidos': resultado.get('dados_extraidos', {}),
        'tentativas': resultado.get('tentativas', 0),
        'usou_ia': resultado.get('usou_ia', False),
    }
