"""Nó `reabrir_oportunidade`: tira a oportunidade do estágio perdido e move de
volta pro funil.

Ação de domínio único: mantém motivo_perda/motivo_perda_ref/responsavel como
auditoria da perda anterior (não limpa). Idempotente: se a op não está perdida, não
é erro. Precisa de `oportunidade` no contexto.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import reabrir_oportunidade


@registrar
class ReabrirOportunidadeNode(BaseNode):
    tipo = "reabrir_oportunidade"
    label = "Reabrir oportunidade"
    icone = "bi-arrow-counterclockwise"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'estagio_slug', 'label': 'Estágio', 'tipo': 'texto',
             'fonte': 'estagios', 'obrigatorio': True, 'placeholder': 'negociacao'},
            {'nome': 'motivo', 'label': 'Motivo da reabertura', 'tipo': 'texto'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('estagio_slug') or '').strip() else ['`estagio_slug` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')
        slug = str(contexto.resolver(config.get('estagio_slug', '')) or '').strip()
        motivo = str(contexto.resolver(config.get('motivo', '')) or '')
        try:
            estagio, reabriu = reabrir_oportunidade(
                contexto.tenant, oportunidade=contexto.oportunidade, estagio_slug=slug, motivo=motivo)
        except Exception as e:  # noqa: BLE001
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(
            output={'reaberta': reabriu, 'estagio': estagio.slug if estagio else None},
            branch='sucesso')
