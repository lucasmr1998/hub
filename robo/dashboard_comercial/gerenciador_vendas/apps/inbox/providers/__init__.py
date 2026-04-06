"""
Provider Registry — Factory pattern para provedores de mensageria.

Uso:
    from apps.inbox.providers import get_provider
    provider = get_provider(canal)  # CanalInbox → Provider instance
    provider.enviar_texto('5589...', 'Olá!')
"""

_REGISTRY = {}


def register_provider(cls):
    """Decorator para registrar um provider no registry."""
    _REGISTRY[cls.slug] = cls
    return cls


def get_provider(canal):
    """
    Factory: dado um CanalInbox, retorna a instância do provider correto.
    Fallback para GenericWebhookProvider se provedor não registrado.
    """
    provedor_slug = canal.provedor
    if not provedor_slug and canal.integracao:
        provedor_slug = canal.integracao.tipo

    cls = _REGISTRY.get(provedor_slug)
    if cls is None:
        from .webhook import GenericWebhookProvider
        return GenericWebhookProvider(canal)
    return cls(canal)


def get_provider_class(slug):
    """Retorna a classe do provider pelo slug."""
    return _REGISTRY.get(slug)


def available_providers():
    """Retorna dict {slug: display_name} dos providers registrados."""
    return {slug: cls.display_name for slug, cls in _REGISTRY.items()}


# Auto-import dos providers para que o @register_provider funcione
from . import uazapi as _uazapi  # noqa: F401, E402
from . import webhook as _webhook  # noqa: F401, E402
