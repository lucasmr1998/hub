"""Nó `criar_oportunidade` — cria oportunidade no CRM pro lead (via service).

Convergência do motor de marketing (`_acao_criar_oportunidade`). Idempotente:
não duplica se o lead já tem oportunidade.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import criar_oportunidade


@registrar
class CriarOportunidadeNode(BaseNode):
    tipo = "criar_oportunidade"
    label = "Criar oportunidade (CRM)"
    icone = "bi-kanban"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'titulo', 'label': 'Título', 'tipo': 'texto', 'placeholder': '{{lead.nome}}'},
            {'nome': 'pipeline_slug', 'label': 'Pipeline (opcional)', 'tipo': 'texto',
             'fonte': 'pipelines', 'ajuda': 'Vazio = pipeline padrão do tenant.'},
            {'nome': 'estagio_slug', 'label': 'Estágio (opcional)', 'tipo': 'texto',
             'fonte': 'estagios', 'ajuda': 'Vazio = primeiro estágio do pipeline.'},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        if contexto.lead is None:
            return NodeResult(status='erro', branch='erro', erro='Sem lead no contexto.')
        titulo = str(contexto.resolver(config.get('titulo', '')) or '')
        pipeline_slug = str(contexto.resolver(config.get('pipeline_slug', '')) or '')
        estagio_slug = str(contexto.resolver(config.get('estagio_slug', '')) or '')
        try:
            oport, criada = criar_oportunidade(
                contexto.tenant, lead=contexto.lead, titulo=titulo,
                pipeline_slug=pipeline_slug, estagio_slug=estagio_slug,
            )
        except Exception as e:
            return NodeResult(status='erro', branch='erro', erro=str(e))
        return NodeResult(output={'oportunidade_id': oport.pk, 'criada': criada}, branch='sucesso')
