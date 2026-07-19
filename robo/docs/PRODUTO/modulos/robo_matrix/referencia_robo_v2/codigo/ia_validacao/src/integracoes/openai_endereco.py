"""Extrator estruturado de complemento de endereço via OpenAI.

Recebe a resposta livre do cliente à pergunta de ponto de referência
(que agora menciona os 3 cenários: casa térrea / apartamento / condomínio)
e devolve uma string PADRONIZADA pra salvar em `ponto_referencia`.

Exemplos de saída:
- "[CASA] perto da padaria do José"
- "[APARTAMENTO] Edif. Aurora - Bloco B - 5º andar - Apto 502. Ref: próximo ao mercado X"
- "[CONDOMÍNIO] Cond. Jardim das Flores - Quadra 3, Casa 12. Ref: portaria 2"

A string estruturada facilita pra equipe de operações localizar o cliente
durante a instalação.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


PROMPT_SISTEMA = (
    "Você extrai informações de endereço de respostas livres de clientes brasileiros.\n"
    "O cliente foi orientado a passar detalhes do tipo de imóvel (casa térrea, "
    "apartamento, condomínio fechado ou empresa) pra facilitar a instalação de internet.\n"
    "Responda SEMPRE com JSON puro, sem markdown.\n\n"
    "═══ TIPOS DE IMÓVEL ═══\n"
    "• 'casa_terrea': mora em casa térrea ou sobrado individual na rua\n"
    "• 'apartamento': mora em apartamento dentro de edifício\n"
    "• 'condominio': mora em casa dentro de condomínio fechado\n"
    "• 'empresa': escritório, loja, sala comercial, galpão (palavras-chave: empresa, "
    "comercial, sala, loja, escritório, galpão, coworking)\n"
    "• 'indefinido': cliente não disse o tipo, só mandou um ponto de referência genérico\n\n"
    "═══ CAMPOS A EXTRAIR ═══\n"
    "tipo: um dos 4 valores acima\n"
    "nome_local: nome do edifício OU nome do condomínio (vazio se não houver)\n"
    "bloco: bloco/torre/quadra (vazio se não houver)\n"
    "andar: andar do apto, ex '5', '5º', 'térreo' (vazio se não aplicável)\n"
    "unidade: número do apto OU número da casa no condomínio (vazio se não aplicável)\n"
    "referencia_externa: ponto de referência fora do imóvel ('perto de X', 'em frente a Y')\n\n"
    "Regras:\n"
    "- Se cliente disse 'apto 302 bloco B', tipo='apartamento', bloco='B', unidade='302'\n"
    "- Se disse 'condomínio Aurora casa 12', tipo='condominio', nome_local='Aurora', unidade='12'\n"
    "- Se mandou só 'perto da padaria do João', tipo='casa_terrea' (ou 'indefinido' se ambíguo)\n"
    "- NUNCA invente dados — se não souber, deixa vazio.\n"
    "- 'andar' só pra apartamento. 'bloco' pode ser bloco em apto ou quadra em condomínio."
)


PROMPT_USUARIO = (
    'Analise a resposta abaixo e retorne em JSON:\n'
    '{\n'
    '  "tipo": "casa_terrea" | "apartamento" | "condominio" | "empresa" | "indefinido",\n'
    '  "nome_local": "...",\n'
    '  "bloco": "...",\n'
    '  "andar": "...",\n'
    '  "unidade": "...",\n'
    '  "referencia_externa": "..."\n'
    '}\n\n'
    'Resposta do cliente: """{resposta}"""'
)


# Mapeia tipo extraído → label visível na string final
LABELS_TIPO = {
    'casa_terrea': 'CASA',
    'apartamento': 'APARTAMENTO',
    'condominio':  'CONDOMÍNIO',
    'empresa':     'EMPRESA',
    'indefinido':  'CASA',  # fallback prudente
}


@dataclass
class ResultadoEndereco:
    texto_estruturado: str          # string final pra salvar em ponto_referencia
    tipo: str                       # 'casa_terrea' | 'apartamento' | 'condominio' | 'indefinido'
    componentes: dict[str, str]     # dict bruto extraído
    fallback: bool                  # True se IA falhou e usamos o texto original


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get('OPENAI_API_KEY', '').strip()
        if not key:
            try:
                from src.config import config as _cfg
                key = (_cfg.OPENAI_API_KEY or '').strip()
            except Exception:
                pass
        if not key:
            raise RuntimeError('OPENAI_API_KEY não configurado')
        _client = OpenAI(api_key=key)
    return _client


def _montar_string(comp: dict[str, str], tipo: str) -> str:
    """Monta a string estruturada a partir dos componentes extraídos."""
    label = LABELS_TIPO.get(tipo, 'CASA')
    nome = (comp.get('nome_local') or '').strip()
    bloco = (comp.get('bloco') or '').strip()
    andar = (comp.get('andar') or '').strip()
    unidade = (comp.get('unidade') or '').strip()
    ref_ext = (comp.get('referencia_externa') or '').strip()

    partes: list[str] = []

    if tipo == 'apartamento':
        if nome:
            partes.append(f'Edif. {nome}' if not nome.lower().startswith(('ed.', 'edif')) else nome)
        if bloco:
            partes.append(f'Bloco {bloco}' if len(bloco) <= 3 else bloco)
        if andar:
            sufixo = '' if 'andar' in andar.lower() or 'térreo' in andar.lower() else 'º andar'
            partes.append(f'{andar}{sufixo}')
        if unidade:
            partes.append(f'Apto {unidade}' if not unidade.lower().startswith('apto') else unidade)
    elif tipo == 'condominio':
        if nome:
            partes.append(f'Cond. {nome}' if not nome.lower().startswith(('cond', 'condom')) else nome)
        if bloco:
            partes.append(f'Quadra {bloco}' if len(bloco) <= 3 else bloco)
        if unidade:
            partes.append(f'Casa {unidade}' if not unidade.lower().startswith('casa') else unidade)
    elif tipo == 'empresa':
        if nome:
            partes.append(nome)
        if bloco:
            partes.append(f'Bloco {bloco}' if len(bloco) <= 3 else bloco)
        if andar:
            sufixo = '' if 'andar' in andar.lower() else 'º andar'
            partes.append(f'{andar}{sufixo}')
        if unidade:
            partes.append(f'Sala {unidade}' if not unidade.lower().startswith(('sala', 'loja')) else unidade)

    miolo = ' - '.join(partes) if partes else ''
    saida = f'[{label}]'
    if miolo:
        saida += f' {miolo}'
    if ref_ext:
        saida += f'. Ref: {ref_ext}' if miolo else f' {ref_ext}'
    return saida.strip()


def extrair_complemento(resposta: str) -> ResultadoEndereco:
    """Extrai tipo + componentes da resposta livre do cliente.

    Em caso de erro na IA, faz fallback retornando o texto original sem
    estruturação (não bloqueia o fluxo da venda).
    """
    resp_limpa = (resposta or '').strip()
    if not resp_limpa:
        return ResultadoEndereco(
            texto_estruturado='',
            tipo='indefinido',
            componentes={},
            fallback=True,
        )

    try:
        client = _get_client()
        completion = client.chat.completions.create(
            model='gpt-4o-mini',
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': PROMPT_SISTEMA},
                {'role': 'user', 'content': PROMPT_USUARIO.replace('{resposta}', resp_limpa)},
            ],
            max_tokens=300,
            temperature=0.1,
            timeout=20,
        )
        conteudo = completion.choices[0].message.content or '{}'
        dados: dict[str, Any] = json.loads(conteudo)
    except Exception as e:
        logger.warning('Falha extração complemento via IA, usando texto original: %s', e)
        return ResultadoEndereco(
            texto_estruturado=resp_limpa,
            tipo='indefinido',
            componentes={},
            fallback=True,
        )

    tipo = (dados.get('tipo') or 'indefinido').strip()
    if tipo not in LABELS_TIPO:
        tipo = 'indefinido'

    componentes = {
        'nome_local': str(dados.get('nome_local') or ''),
        'bloco':      str(dados.get('bloco') or ''),
        'andar':      str(dados.get('andar') or ''),
        'unidade':    str(dados.get('unidade') or ''),
        'referencia_externa': str(dados.get('referencia_externa') or ''),
    }

    # Se nenhum componente estrutural foi detectado e tipo='indefinido',
    # fica só com o texto original prefixado.
    sem_estrutura = not any(componentes[k] for k in ('nome_local', 'bloco', 'andar', 'unidade'))
    if sem_estrutura and not componentes['referencia_externa']:
        texto = f'[CASA] {resp_limpa}'
    else:
        texto = _montar_string(componentes, tipo)
        # Se a IA não extraiu referência externa mas a resposta tem algo extra,
        # NÃO sobrescrevemos o texto original — confiamos no que a IA montou.

    return ResultadoEndereco(
        texto_estruturado=texto[:255],   # campo do lead é CharField(255)
        tipo=tipo,
        componentes=componentes,
        fallback=False,
    )
