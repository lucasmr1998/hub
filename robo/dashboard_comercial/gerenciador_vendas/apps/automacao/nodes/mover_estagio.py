"""Nó `mover_estagio` — move uma oportunidade de estágio no funil (via service).

Convergência do motor de marketing (`_acao_mover_estagio`). Precisa de
`oportunidade` no contexto do gatilho/fluxo.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import mover_estagio


@registrar
class MoverEstagioNode(BaseNode):
    tipo = "mover_estagio"
    label = "Mover de estágio"
    icone = "bi-arrow-right-circle"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'estagio_slug', 'label': 'Estágio', 'tipo': 'texto',
             'fonte': 'estagios', 'obrigatorio': True, 'placeholder': 'negociacao'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('estagio_slug') or '').strip() else ['`estagio_slug` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        slug = str(contexto.resolver(config.get('estagio_slug', '')) or '').strip()
        try:
            estagio = mover_estagio(contexto.tenant, oportunidade=contexto.oportunidade, estagio_slug=slug)
        except Exception as e:
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(output={'estagio': estagio.slug, 'estagio_nome': estagio.nome}, branch='sucesso')
