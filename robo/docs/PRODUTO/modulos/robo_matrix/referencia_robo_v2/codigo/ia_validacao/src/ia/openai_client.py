"""Cliente OpenAI com retry e logging."""
import json
import logging
from typing import Optional
from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from src.config import config

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self):
        self._cliente: Optional[OpenAI] = None

    @property
    def cliente(self) -> OpenAI:
        if self._cliente is None:
            if not config.OPENAI_API_KEY:
                raise RuntimeError('OPENAI_API_KEY não configurada')
            self._cliente = OpenAI(
                api_key=config.OPENAI_API_KEY,
                timeout=config.OPENAI_TIMEOUT,
            )
        return self._cliente

    def chat_json(
        self,
        system: str,
        user: str,
        modelo: Optional[str] = None,
        temperatura: float = 0.3,
        max_tokens: int = 500,
        max_retries: int = 2,
    ) -> dict:
        """Chama o modelo e força retorno JSON. Retorna dict parseado."""
        modelo = modelo or config.OPENAI_MODEL

        for tentativa in range(max_retries + 1):
            try:
                resp = self.cliente.chat.completions.create(
                    model=modelo,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperatura,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                conteudo = resp.choices[0].message.content or '{}'
                return json.loads(conteudo)

            except (APITimeoutError, RateLimitError) as e:
                logger.warning(f"OpenAI tentativa {tentativa+1} falhou: {e}")
                if tentativa == max_retries:
                    raise
            except APIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise
            except json.JSONDecodeError as e:
                logger.error(f"OpenAI retornou JSON inválido: {e}")
                return {}


client = OpenAIClient()
