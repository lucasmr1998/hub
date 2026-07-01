"""Nó `mover_para_perdido_sem_viabilidade` — move a oportunidade pro estágio perdido
(motivo viabilidade) e preenche o motivo_perda.

Migração da automação do funil (Fase 1): porta a lógica pro motor novo via
`services/acoes.py` (autossuficiente — não importa do motor antigo do CRM, que roda
2 clientes vivos). Precisa de `oportunidade` no contexto do gatilho/fluxo.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import mover_para_perdido_sem_viabilidade


@registrar
class MoverParaPerdidoSemViabilidadeNode(BaseNode):
    tipo = "mover_para_perdido_sem_viabilidade"
    label = "Perder por viabilidade"
    icone = "bi-x-circle"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'motivo_template', 'label': 'Motivo (template)', 'tipo': 'texto',
             'placeholder': 'CEP {cep} sem cobertura tecnica em {cidade}/{uf}',
             'ajuda': 'Placeholders: {cep} {cidade} {uf}. Vazio usa o padrão.'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        template = str(contexto.resolver(config.get('motivo_template', '')) or '')
        try:
            estagio, movido = mover_para_perdido_sem_viabilidade(
                contexto.tenant, oportunidade=contexto.oportunidade, motivo_template=template)
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(
            output={'movido': movido,
                    'estagio': estagio.slug if estagio else None,
                    'motivo': contexto.oportunidade.motivo_perda if movido else None},
            branch='sucesso')
