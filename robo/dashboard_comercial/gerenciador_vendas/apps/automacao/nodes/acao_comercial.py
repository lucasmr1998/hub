"""Nó `acao_comercial` — executa uma ação da engine comercial (CRM) sobre a
oportunidade do contexto. Saídas sucesso/erro.

Convergência: reusa o registry `_EXECUTORES_ACAO` de
`apps.comercial.crm.services.automacao_pipeline` — **todas** as ações do pipeline
(criar_venda, atribuir_agente, gerar/assinar contrato HubSoft, enviar venda
WhatsApp, mover p/ perdido sem viabilidade, sincronizar prospecto) num só nó, via
`tipo_acao`. Os parâmetros vão no `config` (chave/valor, aceitam {{...}}).
Sem 2ª cópia da lógica.

⚠️ Algumas ações são outbound real (ex: `enviar_venda_whatsapp`, contratos HubSoft).
"""
from .base import BaseNode, NodeResult, registrar


def _tipos_acao():
    try:
        from apps.comercial.crm.services import automacao_pipeline
        return sorted(automacao_pipeline._EXECUTORES_ACAO.keys())
    except Exception:
        return []


@registrar
class AcaoComercialNode(BaseNode):
    tipo = "acao_comercial"
    label = "Ação comercial (CRM)"
    icone = "bi-briefcase-fill"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Pipeline"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'tipo_acao', 'label': 'Ação', 'tipo': 'select',
             'opcoes': _tipos_acao(), 'obrigatorio': True},
            {'nome': 'config', 'label': 'Parâmetros da ação', 'tipo': 'keyvalue',
             'ajuda': 'Pares chave/valor passados pra ação (aceitam {{...}}).'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('tipo_acao') or '').strip() else ['`tipo_acao` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        from apps.comercial.crm.services import automacao_pipeline

        oportunidade = contexto.oportunidade
        if oportunidade is None or not getattr(oportunidade, 'pk', None):
            return NodeResult(status='erro', branch='erro',
                              erro='Sem oportunidade no contexto.', output={'ok': False})
        slug = (config.get('tipo_acao') or '').strip()
        executor = automacao_pipeline._EXECUTORES_ACAO.get(slug)
        if executor is None:
            return NodeResult(status='erro', branch='erro',
                              erro=f'ação desconhecida: {slug}', output={'ok': False})

        params = contexto.resolver(config.get('config') or {})
        if not isinstance(params, dict):
            params = {}
        try:
            ret = executor(oportunidade, params)
        except Exception as exc:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(exc), output={'ok': False})

        # contrato das actions: False = pulou idempotente; True/None = efetivou
        return NodeResult(output={'ok': True, 'efetivou': ret is not False}, branch='sucesso')
