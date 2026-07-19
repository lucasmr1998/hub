"""Carrega definições de fluxo de arquivos YAML."""
import yaml
from pathlib import Path
from functools import lru_cache

from src.config import config


@lru_cache(maxsize=8)
def carregar_fluxo(nome: str) -> dict:
    """Carrega fluxo YAML por nome (sem extensão)."""
    arquivo = config.FLUXOS_DIR / f"{nome}.yaml"
    if not arquivo.exists():
        return {}
    with open(arquivo, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def obter_etapa(fluxo_nome: str, etapa_id: str) -> dict | None:
    fluxo = carregar_fluxo(fluxo_nome)
    for etapa in fluxo.get('etapas', []):
        if etapa.get('id') == etapa_id:
            return etapa
    return None


def listar_fluxos() -> list[str]:
    return [p.stem for p in config.FLUXOS_DIR.glob('*.yaml')]
