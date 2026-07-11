"""Nó `criar_nota`: registra uma nota interna (comentário) na oportunidade.

Ação de domínio único: a lógica de resolver o autor (responsável da op → staff do
tenant → superuser) mora em `services/acoes.py`. Precisa de `oportunidade` no
contexto do gatilho/fluxo.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import criar_nota


@registrar
class CriarNotaNode(BaseNode):
    tipo = "criar_nota"
    label = "Criar nota"
    icone = "bi-journal-text"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'texto', 'label': 'Texto', 'tipo': 'textarea', 'obrigatorio': True,
             'placeholder': 'Nota sobre {{lead.nome}}...'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('texto') or '').strip() else ['`texto` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        texto = str(contexto.resolver(config.get('texto', '')) or '')
        try:
            nota = criar_nota(contexto.tenant, oportunidade=contexto.oportunidade, texto=texto)
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(output={'nota_id': nota.pk, 'conteudo': nota.conteudo}, branch='sucesso')
