"""
Geracao de imagem por IA via Google Gemini.

Portado de megaroleta/gestao/agent_actions.py:_gerar_imagem_ia.

Configuracao:
    GOOGLE_AI_API_KEY no .env

Sem chave, levanta excecao com mensagem clara.
Modelos com fallback: gemini-3-pro-image-preview -> gemini-2.5-flash-image
"""
import logging
import os
import uuid

logger = logging.getLogger(__name__)


MODELOS_IMAGEM = ['gemini-3-pro-image-preview', 'gemini-2.5-flash-image']
MAX_IMAGENS_POR_HORA_TENANT = 20  # rate limiting basico


def gerar_imagem(prompt: str) -> bytes:
    """
    Gera imagem via Gemini. Retorna bytes da imagem (PNG).

    Levanta:
        RuntimeError se sem chave configurada
        RuntimeError se todos os modelos falharem
    """
    api_key = os.environ.get('GOOGLE_AI_API_KEY', '')
    if not api_key:
        raise RuntimeError(
            'GOOGLE_AI_API_KEY nao configurada no .env. '
            'Adicione a chave Google AI Studio (https://aistudio.google.com/apikey) pra usar geracao de imagem.'
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            'Pacote google-genai nao instalado. Rode: pip install google-genai'
        )

    client = genai.Client(api_key=api_key)

    img_bytes = None
    modelo_usado = None
    ultimo_erro = None

    for modelo in MODELOS_IMAGEM:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=['IMAGE', 'TEXT']),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    img_bytes = part.inline_data.data
                    modelo_usado = modelo
                    break
            if img_bytes:
                break
        except Exception as e:
            logger.warning(f'Modelo Gemini {modelo} falhou: {e}')
            ultimo_erro = e
            continue

    if not img_bytes:
        raise RuntimeError(f'Nenhuma imagem gerada. Ultimo erro: {ultimo_erro}')

    return img_bytes, modelo_usado


def gerar_e_anexar(documento, prompt: str, criado_por=None):
    """
    Gera imagem e cria AnexoDocumento.

    Retorna o AnexoDocumento criado.
    """
    from django.core.files.base import ContentFile

    from apps.workspace.models import AnexoDocumento

    img_bytes, modelo_usado = gerar_imagem(prompt)

    filename = f'ia-{uuid.uuid4().hex[:8]}.png'
    anexo = AnexoDocumento(
        documento=documento,
        tenant=documento.tenant,
        nome_original=filename,
        tipo='imagem',
        mime_type='image/png',
        tamanho_bytes=len(img_bytes),
        gerado_por_ia=True,
        prompt_ia=prompt[:2000],
        modelo_ia=modelo_usado or '',
        criado_por=criado_por,
    )
    anexo.arquivo.save(filename, ContentFile(img_bytes), save=True)
    return anexo
