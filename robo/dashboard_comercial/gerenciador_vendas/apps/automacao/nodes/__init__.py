"""
Nós da engine de automação unificada.

Re-exporta o contrato + registry e importa cada módulo de nó concreto pra
populá-lo no boot. Adicionar um nó = criar o módulo e importá-lo aqui.
"""
from .base import (  # noqa: F401
    BaseNode,
    NodeResult,
    REGISTRY,
    registrar,
    tipo_por_slug,
    todos_tipos,
)
from .context import Contexto  # noqa: F401

# Nós concretos (importados pra registrar no REGISTRY):
from . import set_fields  # noqa: F401,E402  (D2 — nó de referência)
from . import http_request  # noqa: F401,E402  (D4)
from . import if_node  # noqa: F401,E402  (P2 — condição)
from . import delay  # noqa: F401,E402  (P2 — espera)
from . import webhook_trigger  # noqa: F401,E402  (T1 — gatilho webhook)
from . import evento_trigger  # noqa: F401,E402  (EV — gatilho evento)
from . import whatsapp  # noqa: F401,E402  (W — nós Uazapi/WhatsApp)
from . import criar_tarefa  # noqa: F401,E402  (C1 — convergência marketing: ação CRM)
from . import notificacao_sistema  # noqa: F401,E402  (C2 — convergência: notificar equipe)
