"""Validador de imagens de documentação via OpenAI Vision (gpt-4o-mini).

Usado INLINE pelo `engine.py` no momento em que o cliente envia uma imagem
de documentação. Se a IA aprovar → fluxo segue. Se rejeitar → bot pede de
novo explicando o motivo.

Padrões aprendidos das rejeições históricas (~40 casos no dashboard):
- 'foto repetida'             → mesma imagem em slots diferentes
- 'foto não correspondente'   → conta de luz, doc só, foto qualquer
- 'foto ilegível'             → documento borrado/escuro demais
- 'self sem o documento'      → selfie sozinha (sem RG visível)
- 'não é a self com a doc'    → só doc no slot de selfie
"""
from __future__ import annotations

import base64
import ipaddress
import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import OpenAI

logger = logging.getLogger(__name__)


# Mapeia descricao → tipo esperado pelo prompt da IA
DESC_PARA_TIPO = {
    'selfie_com_doc':       'selfie_com_doc',
    'frente_doc':           'frente_doc',
    'verso_doc':            'verso_doc',
    'Selfie com documento': 'selfie_com_doc',
    'Frente do documento':  'frente_doc',
    'Verso do documento':   'verso_doc',
}


# Mensagens de pedido de refoto — específicas por tipo de erro
MSGS_REFOTO = {
    'tipo_errado_selfie':       'Hmm, a imagem que você enviou não parece ser uma *selfie segurando o documento*. Por favor, envie uma foto sua *segurando o RG ou CNH ao lado do rosto*.',
    'tipo_errado_frente':       'A foto enviada não parece ser a *frente do documento*. Por favor, envie a foto da *frente do seu RG ou CNH* (com sua foto e nome visíveis).',
    'tipo_errado_verso':        'A foto enviada não parece ser o *verso do documento*. Por favor, envie a foto do *verso do seu RG ou CNH* (com CPF, assinatura ou digital).',
    'ilegivel':                 'A foto está pouco nítida — não consegui ler os dados. Pode tirar outra em um *local com boa iluminação* e *sem tremer*?',
    'nao_eh_documento':         'A foto enviada não parece ser um documento brasileiro válido (RG ou CNH). Pode tentar de novo?',
    'self_sem_doc':             'Não vi o documento na foto. Lembre-se: você precisa estar *segurando o RG ou CNH ao lado do rosto* na mesma imagem.',
    'self_sem_rosto':           'Não vi seu rosto na foto. Tire uma *selfie* segurando o documento ao lado do rosto.',
    'erro_generico':            'Não consegui validar essa imagem. Pode tentar tirar outra foto?',
}


PROMPT_SISTEMA = (
    "Você é um validador automatizado de fotos de documentos brasileiros (RG ou CNH).\n"
    "Sua tarefa é AVALIAR APENAS O TIPO DA FOTO e a QUALIDADE — você NÃO valida "
    "identidade, NÃO confere se os dados do documento batem com algum cadastro.\n"
    "Responda SEMPRE com JSON puro, sem markdown.\n\n"
    "═══ TIPOS DE FOTO ═══\n\n"
    "▸ selfie_com_doc — Foto em que aparecem SIMULTANEAMENTE:\n"
    "   • o rosto da pessoa em primeiro plano (uma selfie real, não foto de foto)\n"
    "   • um RG ou CNH segurado pela própria pessoa ao lado do rosto\n"
    "   • REJEITAR se faltar rosto OU faltar documento\n\n"
    "▸ frente_doc — Foto em que aparece APENAS a frente do documento:\n"
    "   ═══ DISCRIMINADOR CHAVE: a FRENTE SEMPRE tem a FOTO BIOMÉTRICA do titular ═══\n"
    "   (foto oficial impressa de rosto + IMPRESSÃO DIGITAL nos RGs antigos).\n"
    "   Sem foto biométrica visível, NÃO é frente — é verso.\n\n"
    "   FRENTE do RG ANTIGO (modelo verde brasileiro):\n"
    "     - FOTO BIOMÉTRICA do titular + IMPRESSÃO DIGITAL\n"
    "     - 'REPÚBLICA FEDERATIVA DO BRASIL' no topo\n"
    "     - Brasão do Brasil ao centro\n"
    "     - Assinatura DO TITULAR (não do diretor)\n"
    "   FRENTE do RG NOVO (CIN, polímero PVC):\n"
    "     - FOTO BIOMÉTRICA + nome + número de identificação único + CPF + data nascimento\n"
    "   FRENTE da CNH:\n"
    "     - FOTO BIOMÉTRICA + nome + CPF + filiação + nº registro\n\n"
    "   • É NORMAL e ESPERADO que não tenha rosto da pessoa em primeiro plano\n"
    "   • NUNCA exija rosto da pessoa real — só o documento basta\n"
    "   • REJEITAR só se: não for documento brasileiro válido, estiver ilegível,\n"
    "     ou for o lado SEM foto biométrica (esse é o verso)\n\n"
    "▸ verso_doc — Foto em que aparece APENAS o verso do documento:\n"
    "   ═══ DISCRIMINADOR CHAVE: o VERSO NUNCA tem foto biométrica nem digital ═══\n"
    "   Tem texto/dados pessoais + assinatura do DIRETOR/EXPEDIDOR + texto legal.\n\n"
    "   VERSO do RG ANTIGO (modelo verde brasileiro) — o lado MAIS COMUM enviado:\n"
    "     - REGISTRO GERAL (número do RG, ex: 8401126)\n"
    "     - NOME completo + FILIAÇÃO (pais) + NATURALIDADE\n"
    "     - DOC ORIGEM (Cert. Nascimento, livro/folha)\n"
    "     - CPF + DATA EXPEDIÇÃO + DATA NASCIMENTO\n"
    "     - ASSINATURA do DIRETOR/PERITO CRIMINAL (ex: 'Juarez Gonçalves de Carvalho')\n"
    "     - Topo: 'VÁLIDA EM TODO O TERRITÓRIO NACIONAL'\n"
    "     - Rodapé: 'LEI Nº 7.116 DE 29/08/83'\n"
    "     - SEM FOTO BIOMÉTRICA, SEM DIGITAL\n"
    "   VERSO do RG NOVO (CIN):\n"
    "     - Filiação + órgão expedidor + local + data emissão\n"
    "     - Assinatura do EXPEDIDOR + QR code + nº registro (ex: A100357304S1)\n"
    "     - 'VÁLIDA EM TODO O TERRITÓRIO NACIONAL' + 'LEI Nº 7.116 DE 29/08/83'\n"
    "   VERSO da CNH:\n"
    "     - Observações, código de segurança, eventualmente categorias\n\n"
    "   ATENÇÃO IMPORTANTE: o VERSO do RG antigo brasileiro TEM nome, filiação,\n"
    "   data de nascimento e CPF. Esses dados NÃO indicam que é frente. O que\n"
    "   indica frente é a FOTO BIOMÉTRICA do titular. Se NÃO há foto biométrica,\n"
    "   é VERSO.\n"
    "   • É NORMAL não ter rosto da pessoa\n"
    "   • É VÁLIDO mesmo se a assinatura for do diretor/expedidor\n"
    "   • REJEITAR só se: não for documento brasileiro válido, estiver ilegível,\n"
    "     ou tiver foto biométrica visível (esse é a frente)\n\n"
    "═══ REGRAS DE APROVAÇÃO ═══\n\n"
    "Aprove (aprovado=true) SOMENTE quando TODAS forem true:\n"
    "1. tipo_detectado == tipo_esperado\n"
    "2. documento_legivel == true (dados visíveis e nítidos)\n"
    "3. eh_documento_brasileiro_real == true (não é conta de luz, panfleto, etc)\n\n"
    "═══ CÓDIGOS DE MOTIVO ═══\n\n"
    "Use UM dos códigos abaixo em motivo_codigo:\n"
    "• 'ok'               → aprovado\n"
    "• 'tipo_errado'      → enviou tipo diferente do solicitado (ex: pediu frente, mandou verso)\n"
    "• 'ilegivel'         → muito borrado/escuro/recortado\n"
    "• 'nao_eh_documento' → não é RG nem CNH brasileira (conta de luz, doc estrangeiro, etc)\n"
    "• 'self_sem_doc'     → SÓ aplicável a selfie_com_doc — falta o documento na foto\n"
    "• 'self_sem_rosto'   → SÓ aplicável a selfie_com_doc — falta o rosto na foto\n"
    "• 'outro'            → outros casos\n\n"
    "ATENÇÃO: NÃO use os códigos 'self_*' quando tipo_esperado for frente_doc ou verso_doc."
)


def _prompt_usuario(tipo_esperado: str) -> str:
    return (
        f'Tipo esperado nesta foto: "{tipo_esperado}"\n\n'
        'IMPORTANTE: preencha o JSON na ORDEM abaixo, RACIOCINANDO ANTES de decidir o tipo.\n\n'
        '1. Primeiro veja se há FOTO BIOMÉTRICA do titular visível na foto (foto pequena\n'
        '   oficial do rosto, impressa no documento — não é o rosto da pessoa em primeiro\n'
        '   plano numa selfie).\n'
        '2. Depois veja se há IMPRESSÃO DIGITAL visível.\n'
        '3. Depois veja se há ASSINATURA DO DIRETOR/EXPEDIDOR (frase tipo "Perito Criminal",\n'
        '   "Diretor", "Juarez Gonçalves de Carvalho", "Marcelo Mascarenha").\n'
        '4. Depois veja se há textos legais ("VÁLIDA EM TODO TERRITÓRIO NACIONAL",\n'
        '   "LEI Nº 7.116 DE 29 DE AGOSTO DE 1983").\n'
        '5. SÓ ENTÃO decida tipo_detectado seguindo as regras:\n'
        '   - tem_foto_biometrica=true → frente_doc\n'
        '   - tem_foto_biometrica=false E (tem_assinatura_diretor OU tem_textos_legais\n'
        '     OU tem REGISTRO GERAL + FILIAÇÃO + NATURALIDADE + CPF juntos) → verso_doc\n'
        '   - rosto humano em primeiro plano + documento ao lado → selfie_com_doc\n\n'
        'Responda em JSON puro, sem markdown:\n'
        '{\n'
        '  "tem_foto_biometrica_visivel": true|false,\n'
        '  "tem_impressao_digital_visivel": true|false,\n'
        '  "tem_assinatura_diretor_expedidor": true|false,\n'
        '  "tem_textos_legais_brasileiros": true|false,\n'
        '  "tem_rosto_pessoa_em_primeiro_plano": true|false,\n'
        '  "tipo_detectado": "selfie_com_doc" | "frente_doc" | "verso_doc" | "outro",\n'
        '  "eh_documento_brasileiro_real": true|false,\n'
        '  "documento_legivel": true|false,\n'
        '  "qualidade": "boa" | "media" | "ruim",\n'
        '  "aprovado": true|false,\n'
        '  "motivo_codigo": "ok" | "tipo_errado" | "ilegivel" | "nao_eh_documento" '
        '| "self_sem_doc" | "self_sem_rosto" | "outro",\n'
        '  "motivo_humano": "explicação curta em português (máx 120 chars)"\n'
        '}'
    )


@dataclass
class ResultadoImagem:
    aprovado: bool
    motivo_codigo: str       # ex: 'ok', 'ilegivel', 'tipo_errado', ...
    motivo_humano: str       # texto exibido ao admin / log
    msg_refoto: str          # mensagem pedida ao cliente quando rejeitado
    raw: dict[str, Any]


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        # Tenta env primeiro, fallback no config (load_dotenv)
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


def _msg_refoto_pra(codigo: str, tipo_esperado: str) -> str:
    """Escolhe a mensagem ao cliente baseado no código de erro + tipo esperado.

    Códigos 'self_*' são reservados pra selfie_com_doc. Se a IA retornar um
    desses pra frente/verso (bug do modelo), trata como 'tipo_errado'.
    """
    if codigo.startswith('self_') and tipo_esperado != 'selfie_com_doc':
        codigo = 'tipo_errado'

    if codigo == 'tipo_errado':
        if tipo_esperado == 'selfie_com_doc':
            return MSGS_REFOTO['tipo_errado_selfie']
        if tipo_esperado == 'frente_doc':
            return MSGS_REFOTO['tipo_errado_frente']
        if tipo_esperado == 'verso_doc':
            return MSGS_REFOTO['tipo_errado_verso']
    return MSGS_REFOTO.get(codigo, MSGS_REFOTO['erro_generico'])


_EXT_MIME = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.webp': 'image/webp', '.gif': 'image/gif', '.bmp': 'image/bmp',
    '.heic': 'image/heic',
}


def _host_inacessivel_externamente(host: str) -> bool:
    """True se o host não é alcançável pela OpenAI (localhost/IP privado/.local).

    Nesses casos a OpenAI não consegue baixar a imagem por URL — precisamos
    enviar os bytes em base64.
    """
    if not host:
        return True
    host = host.lower()
    if host in ('localhost',) or host.endswith('.local') or host.endswith('.internal'):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        # Não é IP literal — assume hostname público (Matrix, etc.)
        return False


def _resolver_payload_imagem(url: str) -> str:
    """Resolve o valor de `image_url.url` para a chamada da OpenAI.

    - Host público → devolve a própria URL (sem custo de download/banda).
    - Host local/privado (ex.: simulador em 127.0.0.1:8200) → baixa os bytes
      localmente e devolve um data URI base64, já que a OpenAI não alcança
      endereços privados.
    """
    parsed = urlparse(url)
    if not _host_inacessivel_externamente(parsed.hostname or ''):
        return url

    resp = httpx.get(url, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    mime = resp.headers.get('content-type', '').split(';')[0].strip()
    if not mime.startswith('image/'):
        ext = os.path.splitext(parsed.path)[1].lower()
        mime = _EXT_MIME.get(ext, 'image/jpeg')
    b64 = base64.b64encode(resp.content).decode('ascii')
    logger.info('Imagem em host privado (%s) — enviando %d bytes em base64', parsed.hostname, len(resp.content))
    return f'data:{mime};base64,{b64}'


def validar_imagem(url: str, descricao: str) -> ResultadoImagem:
    """Valida uma imagem via OpenAI Vision.

    Args:
        url: URL pública da imagem (já transformada pelo engine)
        descricao: 'selfie_com_doc' | 'frente_doc' | 'verso_doc'
            (também aceita 'Selfie com documento' etc do dashboard)

    Returns:
        ResultadoImagem — caller decide o que fazer (aprovar/pedir nova foto).
    """
    tipo_esperado = DESC_PARA_TIPO.get((descricao or '').strip(), '')
    if not tipo_esperado:
        return ResultadoImagem(
            aprovado=False,
            motivo_codigo='outro',
            motivo_humano=f'Descrição desconhecida: {descricao!r}',
            msg_refoto=MSGS_REFOTO['erro_generico'],
            raw={'erro': 'descricao_invalida'},
        )

    try:
        client = _get_client()
        url_payload = _resolver_payload_imagem(url)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': PROMPT_SISTEMA},
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': _prompt_usuario(tipo_esperado)},
                        {'type': 'image_url', 'image_url': {'url': url_payload}},
                    ],
                },
            ],
            max_tokens=300,
            temperature=0.1,
            timeout=30,
        )
    except Exception as e:
        logger.exception('Erro na chamada OpenAI Vision: %s', e)
        return ResultadoImagem(
            aprovado=False,
            motivo_codigo='outro',
            motivo_humano=f'Erro IA: {e!s}'[:120],
            msg_refoto=MSGS_REFOTO['erro_generico'],
            raw={'erro_excecao': str(e)},
        )

    conteudo = resp.choices[0].message.content or '{}'
    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError:
        logger.warning('JSON inválido da OpenAI: %s', conteudo[:200])
        dados = {'erro': 'json_invalido', 'raw': conteudo[:200]}

    aprovado = bool(dados.get('aprovado'))
    motivo_codigo = (dados.get('motivo_codigo') or 'outro').strip()
    motivo_humano = (dados.get('motivo_humano') or '').strip()[:240]
    if not motivo_humano:
        motivo_humano = 'Aprovado pela IA' if aprovado else 'Rejeitado pela IA'

    msg_refoto = '' if aprovado else _msg_refoto_pra(motivo_codigo, tipo_esperado)

    return ResultadoImagem(
        aprovado=aprovado,
        motivo_codigo=motivo_codigo,
        motivo_humano=motivo_humano,
        msg_refoto=msg_refoto,
        raw=dados,
    )
