"""Nó `assinar_contrato_hubsoft` — aceita o contrato JÁ EXISTENTE do lead no HubSoft.

Migração da automação do funil (Fase 1): porta a lógica pro motor novo via
`services/contrato_hubsoft.assinar_contrato` (autossuficiente — reusa os helpers de
domínio, não importa do motor antigo). Diferente de `gerar_contrato_hubsoft`: NÃO
cria o contrato (no Nuvyon ele é auto-criado com o cliente/serviço). ⚠️ Outbound
REAL no ERP. Precisa de `oportunidade` no contexto. Tem seletor de credencial.
"""
from .base import BaseNode, NodeResult, registrar
from .hubsoft_base import campo_conta_hubsoft, integ_id_de
from ..services.contrato_hubsoft import assinar_contrato


@registrar
class AssinarContratoHubsoftNode(BaseNode):
    tipo = "assinar_contrato_hubsoft"
    label = "HubSoft: assinar contrato"
    icone = "bi-file-earmark-check"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Contrato"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'ativar_servico_apos_aceite', 'label': 'Ativar serviço após o aceite',
             'tipo': 'booleano',
             'ajuda': 'O aceite sozinho pode não mover o status do serviço; ative pra tentar destravar a OS.'},
            campo_conta_hubsoft(),
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        ativar = bool(config.get('ativar_servico_apos_aceite'))
        try:
            feito, info = assinar_contrato(
                contexto.tenant, oportunidade=contexto.oportunidade,
                ativar_servico_apos_aceite=ativar, integ_id=integ_id_de(config, contexto))
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(
            output={'feito': feito, 'motivo': info.get('motivo'),
                    'id_contrato': info.get('id_contrato'),
                    'servico_ativado': info.get('servico_ativado')},
            branch='sucesso')
