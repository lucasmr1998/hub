"""Nó `gerar_contrato_hubsoft` — gera contrato no HubSoft (criar → anexar → aceitar).

Migração da automação do funil (Fase 1): porta a lógica pro motor novo via
`services/contrato_hubsoft.gerar_contrato` (autossuficiente — reusa os helpers de
domínio, não importa do motor antigo). ⚠️ Outbound REAL no ERP. Precisa de
`oportunidade` no contexto. Integração HubSoft → tem seletor de credencial.
"""
from .base import BaseNode, NodeResult, registrar
from .hubsoft_base import campo_conta_hubsoft, integ_id_de
from ..services.contrato_hubsoft import gerar_contrato


@registrar
class GerarContratoHubsoftNode(BaseNode):
    tipo = "gerar_contrato_hubsoft"
    label = "HubSoft: gerar contrato"
    icone = "bi-file-earmark-medical"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Contrato"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'id_contrato_modelo', 'label': 'ID modelo de contrato', 'tipo': 'numero',
             'ajuda': 'Vazio usa o configuracoes_extras[hubsoft][id_contrato_modelo] da integração.'},
            {'nome': 'id_empresa', 'label': 'ID empresa (HubSoft)', 'tipo': 'numero',
             'ajuda': 'Vazio usa o configuracoes_extras[hubsoft][id_empresa_padrao] da integração.'},
            campo_conta_hubsoft(),
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        modelo = str(contexto.resolver(config.get('id_contrato_modelo', '')) or '').strip() or None
        empresa = str(contexto.resolver(config.get('id_empresa', '')) or '').strip() or None
        try:
            feito, info = gerar_contrato(
                contexto.tenant, oportunidade=contexto.oportunidade,
                id_contrato_modelo=modelo, id_empresa=empresa,
                integ_id=integ_id_de(config, contexto))
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(
            output={'feito': feito, 'motivo': info.get('motivo'),
                    'id_contrato': info.get('id_contrato')},
            branch='sucesso')
