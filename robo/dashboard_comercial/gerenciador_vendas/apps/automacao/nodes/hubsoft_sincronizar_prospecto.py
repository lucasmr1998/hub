"""Nó `hubsoft_sincronizar_prospecto` — cria/atualiza o prospecto do lead no HubSoft.

⚠️ Outbound REAL no ERP: cria rascunho (se `lead.id_hubsoft` vazio) ou atualiza o
existente. É o core do pipeline Nuvyon (Matrix → Hubtrix → HubSoft). Converge a
ação `sincronizar_prospecto_hubsoft` do motor de marketing — mesma fonte (não há
2ª cópia). Precisa de um `lead` real (com pk) no contexto.
"""
from .base import BaseNode, NodeResult, registrar
from .hubsoft_base import campo_conta_hubsoft, integ_id_de
from ..services.hubsoft import sincronizar_prospecto


@registrar
class HubsoftSincronizarProspectoNode(BaseNode):
    tipo = "hubsoft_sincronizar_prospecto"
    label = "HubSoft: sincronizar prospecto"
    icone = "bi-person-vcard"
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "HubSoft"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [campo_conta_hubsoft()]

    def executar(self, config, entrada, contexto) -> NodeResult:
        lead = contexto.lead
        if lead is None or not getattr(lead, 'pk', None):
            return NodeResult(status='erro', branch='erro', erro='Sem lead (com pk) no contexto.')
        try:
            r = sincronizar_prospecto(lead, integ_id=integ_id_de(config, contexto))
        except Exception as exc:
            return NodeResult(status='erro', branch='erro', erro=str(exc))
        out = {'acao': r.acao, 'id_prospecto': r.id_prospecto}
        if r.ok:
            return NodeResult(output=out, branch='sucesso')
        return NodeResult(status='erro', branch='erro', erro=r.motivo or r.acao, output=out)
