"""Nó `enviar_venda_whatsapp` — manda o resumo da venda + documentos por WhatsApp.

Migração da automação do funil (Fase 1): porta a lógica pro motor novo via
`services/whatsapp.enviar_venda` (autossuficiente — reusa o service de domínio de
leads, não importa do motor antigo do CRM). Precisa de `oportunidade` no contexto.

Integração (uazapi) → tem seletor de credencial (qual conta enviar).
"""
from .base import BaseNode, NodeResult, registrar
from ..services.whatsapp import enviar_venda


@registrar
class EnviarVendaWhatsappNode(BaseNode):
    tipo = "enviar_venda_whatsapp"
    label = "WhatsApp: enviar resumo da venda"
    icone = "bi-whatsapp"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Vendas"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'telefone', 'label': 'Telefone destino', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.telefone}}'},
            {'nome': 'integracao_id', 'label': 'Conta (Uazapi)', 'tipo': 'texto',
             'fonte': 'integracoes_uazapi',
             'ajuda': 'Qual conta/integração Uazapi enviar. Vazio = a primeira ativa do tenant.'},
        ]

    def validar_config(self, config) -> list:
        return [] if str(config.get('telefone', '')).strip() else ['`telefone` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        telefone = str(contexto.resolver(config.get('telefone', '')) or '').strip()
        if not telefone:
            return NodeResult(status='erro', branch='erro', erro='telefone vazio.')
        integ_id = str(contexto.resolver(config.get('integracao_id', '')) or '').strip() or None
        try:
            enviou, resultado = enviar_venda(
                contexto.tenant, oportunidade=contexto.oportunidade, telefone=telefone, integ_id=integ_id)
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(
            output={'enviou': enviou,
                    'docs_enviados': resultado.get('docs_enviados'),
                    'motivo': resultado.get('motivo')},
            branch='sucesso')
