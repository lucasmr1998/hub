"""Nó `matrix_atendimento` — transcript de um atendimento Matrix Brasil.

Read-only (enriquecimento): consulta o atendimento por código e monta um
texto legível das mensagens (`{{nodes.<id>.transcript}}`), útil pra alimentar
um agente IA que precise entender a conversa anterior. Provedor Matrix sob
Integrações. PII do texto é mascarada por padrão (LGPD).
"""
from .base import BaseNode, NodeResult, registrar
from ..services.matrix import consultar_atendimento, formatar_transcript


def _mensagens_de(detalhe):
    """Normaliza a resposta de `consultar_atendimento` (dict ou lista de 1
    dict, mesma tolerância do command `extrair_historico_matrix`)."""
    rec = detalhe[0] if isinstance(detalhe, list) and detalhe else detalhe
    if not isinstance(rec, dict):
        return None, []
    mensagens = rec.get('mensagens') or []
    if isinstance(mensagens, dict):
        mensagens = [mensagens]
    return rec, mensagens


def _max_mensagens(config):
    try:
        return int(config.get('max_mensagens', 0) or 0)
    except (TypeError, ValueError):
        return 0


@registrar
class MatrixAtendimentoNode(BaseNode):
    tipo = "matrix_atendimento"
    label = "Matrix: transcript do atendimento"
    icone = "bi-chat-square-text"
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "Matrix"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'codigo', 'label': 'Código do atendimento', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{var.id_atendimento_matrix}}'},
            {'nome': 'anonimizar', 'label': 'Anonimizar PII', 'tipo': 'booleano',
             'ajuda': 'Mascara nome/CPF/telefone/email no transcript. Padrão: sim.'},
            {'nome': 'max_mensagens', 'label': 'Máx. mensagens', 'tipo': 'numero',
             'ajuda': 'Vazio = todas.'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('codigo') or '').strip() else ['`codigo` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        codigo = str(contexto.resolver(config.get('codigo', '')) or '').strip()
        if not codigo:
            return NodeResult(status='erro', branch='erro', erro='Código do atendimento vazio.')
        anonimizar = bool(config.get('anonimizar', True))
        max_mensagens = _max_mensagens(config)
        try:
            detalhe = consultar_atendimento(contexto.tenant, codigo)
        except Exception as exc:
            return NodeResult(status='erro', branch='erro', erro=str(exc))
        rec, mensagens = _mensagens_de(detalhe)
        if rec is None:
            return NodeResult(status='erro', branch='erro',
                               erro='Resposta do Matrix em formato inesperado.')
        transcript = formatar_transcript(mensagens, anonimizar=anonimizar, max_mensagens=max_mensagens)
        output = {
            'transcript': transcript,
            'total_mensagens': len(mensagens),
            'status': rec.get('status'),
            'agente': rec.get('agente'),
        }
        return NodeResult(output=output, branch='sucesso')
