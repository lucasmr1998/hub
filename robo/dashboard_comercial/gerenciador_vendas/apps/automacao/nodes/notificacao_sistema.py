"""Nó de ação `notificacao_sistema` — notifica a equipe (broadcast) via service.

Convergência do motor de marketing (`_acao_notificacao_sistema`): reusa o service
de domínio `apps.notificacoes.services.criar_notificacao` (através de
`services/acoes.notificar`). O nó só resolve os templates e chama o service.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import notificar


@registrar
class NotificacaoSistemaNode(BaseNode):
    tipo = "notificacao_sistema"
    label = "Notificar equipe"
    icone = "bi-bell"
    categoria = "core"
    grupo = "Notificações"
    subgrupo = "Sistema"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'titulo', 'label': 'Título', 'tipo': 'texto',
             'placeholder': 'Novo lead: {{lead.nome}}'},
            {'nome': 'mensagem', 'label': 'Mensagem', 'tipo': 'textarea', 'obrigatorio': True,
             'placeholder': '{{lead.nome}} entrou pela origem {{lead.origem}}'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('mensagem') or '').strip() else ['`mensagem` é obrigatória.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        mensagem = str(contexto.resolver(config.get('mensagem', '')) or '')
        if not mensagem.strip():
            return NodeResult(status='erro', branch='erro', erro='Mensagem vazia.')
        titulo = str(contexto.resolver(config.get('titulo', '')) or '').strip() or 'Automação'
        try:
            notif = notificar(contexto.tenant, titulo=titulo, mensagem=mensagem)
        except Exception as e:
            return NodeResult(status='erro', branch='erro', erro=str(e))
        if not notif:
            return NodeResult(
                status='erro', branch='erro',
                erro='Tipo de notificação não cadastrado pro tenant (rode seedar_notificacoes).',
            )
        return NodeResult(output={'notificacao_id': notif.pk}, branch='sucesso')
