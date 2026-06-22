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
from . import mover_estagio  # noqa: F401,E402  (C3 — convergência: mover oportunidade)
from . import criar_oportunidade  # noqa: F401,E402  (C4 — convergência: criar oportunidade)
from . import criar_venda  # noqa: F401,E402  (C5 — convergência: criar venda)
from . import dar_pontos  # noqa: F401,E402  (C6 — convergência: pontos no clube)
from . import atribuir_responsavel  # noqa: F401,E402  (C7 — convergência: round-robin)
from . import matrix_hsm  # noqa: F401,E402  (M1 — Integrações: disparo HSM Matrix)
from . import hubsoft_sincronizar_prospecto  # noqa: F401,E402  (H1 — Integrações: prospecto HubSoft)
from . import hubsoft_consultar_cliente  # noqa: F401,E402  (H2 — Integrações: consultar cliente)
from . import hubsoft_listar_faturas  # noqa: F401,E402  (H3 — Integrações: faturas HubSoft)
from . import hubsoft_planos_cep  # noqa: F401,E402  (H4 — Integrações: planos por CEP)
from . import hubsoft_catalogo  # noqa: F401,E402  (H5 — serviços/vencimentos/modelos contrato)
from . import hubsoft_viabilidade  # noqa: F401,E402  (H6 — viabilidade endereço/coords)
from . import hubsoft_cliente  # noqa: F401,E402  (H7 — atendimentos/OS/extrato/renegociações)
from . import hubsoft_globais  # noqa: F401,E402  (H8 — clientes/OS/atendimentos todos + agenda)
from . import hubsoft_writes  # noqa: F401,E402  (H9 — writes moderados: contrato/renegociação/OS)
