"""Nó `dar_pontos` — soma pontos no Clube de Benefícios do contato (via service).

Convergência do motor de marketing (`_acao_dar_pontos`). Usa o CPF do config ou,
se vazio, o `cpf_cnpj` do lead do contexto.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import dar_pontos


def _int(v, default=0):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError, AttributeError):
        return default


@registrar
class DarPontosNode(BaseNode):
    tipo = "dar_pontos"
    label = "Dar pontos (Clube)"
    icone = "bi-gift"
    categoria = "cs"
    grupo = "CS"
    subgrupo = "Clube"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'pontos', 'label': 'Pontos', 'tipo': 'numero', 'obrigatorio': True,
             'placeholder': '10'},
            {'nome': 'cpf', 'label': 'CPF (opcional)', 'tipo': 'texto',
             'ajuda': 'Vazio = usa o CPF do lead do contexto.'},
        ]

    def validar_config(self, config) -> list:
        return [] if str(config.get('pontos', '')).strip() else ['`pontos` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        pontos = _int(contexto.resolver(config.get('pontos', '')), 0)
        if not pontos:
            return NodeResult(status='erro', branch='erro', erro='Pontos inválido (zero ou não numérico).')
        cpf = str(contexto.resolver(config.get('cpf', '')) or '').strip()
        if not cpf and contexto.lead is not None:
            cpf = str(getattr(contexto.lead, 'cpf_cnpj', '') or '')
        try:
            membro = dar_pontos(contexto.tenant, cpf=cpf, pontos=pontos)
        except Exception as e:
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(output={'membro': membro.nome, 'saldo': membro.saldo}, branch='sucesso')
