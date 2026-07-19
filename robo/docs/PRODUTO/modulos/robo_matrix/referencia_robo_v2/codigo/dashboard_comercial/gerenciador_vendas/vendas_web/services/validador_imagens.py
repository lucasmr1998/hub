"""Validador de imagens de documentação via OpenAI Vision (gpt-4o-mini).

Recebe uma ImagemLeadProspecto pendente e:
1. Detecta duplicatas no mesmo lead (mesma imagem em slots diferentes)
2. Envia a URL pra OpenAI Vision com prompt estruturado
3. Aplica a decisão (aprovado/rejeitado) e grava motivo

Padrões aprendidos a partir das rejeições históricas:
- 'foto repetida' / 'duplicada' → mesma imagem em múltiplos slots
- 'foto não correspondente' → enviou conta de luz, doc só, etc
- 'foto ilegível' → documento borrado / escuro demais
- 'self sem o documento' → selfie sem RG visível
- 'não é a self com a documentação' → mandou só doc no slot de selfie
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI

logger = logging.getLogger(__name__)


def _carregar_openai_key() -> str:
    """Lê OPENAI_API_KEY do env ou de ia_validacao/.env."""
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if key:
        return key
    env_path = Path(__file__).resolve().parents[4] / 'ia_validacao' / '.env'
    if env_path.exists():
        for linha in env_path.read_text().splitlines():
            if linha.startswith('OPENAI_API_KEY='):
                return linha.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


# Mapeia o "descricao" do banco pro tipo esperado pelo prompt
DESC_PARA_TIPO = {
    # WhatsApp / fluxo dinâmico
    'selfie_com_doc':    'selfie_com_doc',
    'frente_doc':        'frente_doc',
    'verso_doc':         'verso_doc',
    # Site / dashboard
    'Selfie com documento': 'selfie_com_doc',
    'Frente do documento':  'frente_doc',
    'Verso do documento':   'verso_doc',
}


PROMPT_SISTEMA = (
    "Você é um validador automatizado de documentos brasileiros pra abertura "
    "de cadastro de internet. Sua resposta deve ser SEMPRE um JSON válido, "
    "sem texto adicional, sem markdown.\n\n"
    "Tipos esperados:\n"
    "- selfie_com_doc: rosto da pessoa + documento (RG/CNH) visíveis na mesma foto\n"
    "- frente_doc: frente da carteira de identidade (RG) ou CNH — com foto e nome\n"
    "- verso_doc: verso do RG (com CPF, assinatura, digital) ou verso da CNH\n\n"
    "Regras de aprovação (TODAS devem ser verdadeiras):\n"
    "1. tipo_detectado == tipo_esperado\n"
    "2. documento_legivel == true (texto visível e foto nítida)\n"
    "3. eh_documento_brasileiro_real == true (não é conta de luz, panfleto, foto de tela)\n\n"
    "Se for selfie_com_doc, exija rosto da pessoa E documento visíveis simultaneamente.\n"
    "Se for frente/verso, NÃO deve aparecer rosto da pessoa em primeiro plano (só a foto pequena no doc)."
)


def _prompt_usuario(tipo_esperado: str) -> str:
    return (
        f'Tipo esperado: "{tipo_esperado}"\n\n'
        'Analise a imagem e responda em JSON com as chaves:\n'
        '{\n'
        '  "tipo_detectado": "selfie_com_doc" | "frente_doc" | "verso_doc" | "outro",\n'
        '  "eh_documento_brasileiro_real": true|false,\n'
        '  "documento_legivel": true|false,\n'
        '  "qualidade": "boa" | "media" | "ruim",\n'
        '  "aprovado": true|false,\n'
        '  "motivo": "explicação curta em português (máx 120 chars)"\n'
        '}'
    )


@dataclass
class ResultadoValidacao:
    aprovado: bool
    motivo: str
    raw: dict[str, Any]
    custo_estimado: float = 0.0  # USD


class ValidadorImagens:
    MODELO = 'gpt-4o-mini'
    TIMEOUT_HTTP = 25

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or _carregar_openai_key()
        if not self.api_key:
            raise RuntimeError(
                'OPENAI_API_KEY não encontrado (nem em env, nem em ia_validacao/.env)'
            )
        self.client = OpenAI(api_key=self.api_key)

    # ─────────────────────────────────────────────────────────────────
    # API principal
    # ─────────────────────────────────────────────────────────────────
    def validar(self, imagem) -> ResultadoValidacao:
        """Valida uma ImagemLeadProspecto. Retorna ResultadoValidacao.

        Antes de chamar a OpenAI, checa se a imagem é duplicata de outra
        do mesmo lead (mesmo hash em descricao diferente = foto repetida).
        """
        tipo_esperado = DESC_PARA_TIPO.get(imagem.descricao.strip(), '')
        if not tipo_esperado:
            return ResultadoValidacao(
                aprovado=False,
                motivo=f'Descrição desconhecida: {imagem.descricao!r}',
                raw={'erro': 'descricao_invalida'},
            )

        # 1) Detecta duplicata via hash
        dup = self._detectar_duplicata(imagem)
        if dup:
            return ResultadoValidacao(
                aprovado=False,
                motivo=f'Foto repetida — mesmo arquivo da imagem #{dup.id} ({dup.descricao})',
                raw={'duplicata_id': dup.id},
            )

        # 2) Valida via OpenAI Vision
        try:
            return self._validar_openai(imagem.link_url, tipo_esperado)
        except Exception as e:
            logger.exception('Erro na validação OpenAI da imagem #%s', imagem.id)
            return ResultadoValidacao(
                aprovado=False,
                motivo=f'Erro ao consultar IA: {e!s}'[:120],
                raw={'erro': str(e)},
            )

    # ─────────────────────────────────────────────────────────────────
    # Detecção de duplicatas (foto repetida)
    # ─────────────────────────────────────────────────────────────────
    def _hash_imagem(self, url: str) -> str | None:
        try:
            r = requests.get(url, timeout=self.TIMEOUT_HTTP)
            r.raise_for_status()
            return hashlib.sha256(r.content).hexdigest()
        except Exception as e:
            logger.warning('Falhou hash da imagem %s: %s', url, e)
            return None

    def _detectar_duplicata(self, imagem):
        """Procura outra imagem do MESMO lead com hash idêntico mas descrição diferente."""
        from vendas_web.models import ImagemLeadProspecto

        h_atual = self._hash_imagem(imagem.link_url)
        if not h_atual:
            return None

        outras = (
            ImagemLeadProspecto.objects
            .filter(lead_id=imagem.lead_id)
            .exclude(pk=imagem.pk)
        )
        for outra in outras:
            h_outra = self._hash_imagem(outra.link_url)
            if h_outra and h_outra == h_atual and outra.descricao != imagem.descricao:
                return outra
        return None

    # ─────────────────────────────────────────────────────────────────
    # Chamada OpenAI
    # ─────────────────────────────────────────────────────────────────
    def _validar_openai(self, url: str, tipo_esperado: str) -> ResultadoValidacao:
        resp = self.client.chat.completions.create(
            model=self.MODELO,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': PROMPT_SISTEMA},
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': _prompt_usuario(tipo_esperado)},
                        {'type': 'image_url', 'image_url': {'url': url}},
                    ],
                },
            ],
            max_tokens=300,
            temperature=0.1,
        )

        conteudo = resp.choices[0].message.content or '{}'
        try:
            dados = json.loads(conteudo)
        except json.JSONDecodeError:
            dados = {'erro': 'json_invalido', 'raw': conteudo[:200]}

        aprovado = bool(dados.get('aprovado'))
        motivo = (dados.get('motivo') or '').strip()[:240]
        if not motivo:
            motivo = 'Aprovado pela IA' if aprovado else 'Rejeitado pela IA'

        # Custo aproximado (gpt-4o-mini): ~$0.00015 input + ~$0.0006 output por 1k tokens
        # + ~$0.000425 por imagem (low detail). Estimativa simples:
        usage = getattr(resp, 'usage', None)
        if usage:
            custo = (
                (usage.prompt_tokens / 1_000_000) * 0.15
                + (usage.completion_tokens / 1_000_000) * 0.60
            )
        else:
            custo = 0.0

        return ResultadoValidacao(
            aprovado=aprovado, motivo=motivo, raw=dados, custo_estimado=custo,
        )
