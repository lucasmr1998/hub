"""Nó de ação `criar_tarefa` — cria uma TarefaCRM via service de domínio único.

Convergência do motor de marketing (`_acao_criar_tarefa`): a lógica de criar a
tarefa mora em `services/acoes.py`; este nó só resolve os templates e chama o
service. Tenant vem de `contexto.tenant` (a engine roda fora de request).
"""
from .base import BaseNode, NodeResult, registrar
from ..services.acoes import criar_tarefa

_TIPOS = ['ligacao', 'whatsapp', 'email', 'visita', 'followup',
          'proposta', 'instalacao', 'suporte', 'outro']
_PRIORIDADES = ['baixa', 'normal', 'alta', 'urgente']


def _int(v, default):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError, AttributeError):
        return default


@registrar
class CriarTarefaNode(BaseNode):
    tipo = "criar_tarefa"
    label = "Criar tarefa (CRM)"
    icone = "bi-check2-square"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Tarefas"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'titulo', 'label': 'Título', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': 'Follow-up: {{lead.nome}}'},
            {'nome': 'tipo', 'label': 'Tipo', 'tipo': 'select', 'opcoes': _TIPOS},
            {'nome': 'prioridade', 'label': 'Prioridade', 'tipo': 'select', 'opcoes': _PRIORIDADES},
            {'nome': 'prazo_dias', 'label': 'Prazo (dias)', 'tipo': 'numero', 'placeholder': '1'},
            {'nome': 'descricao', 'label': 'Descrição', 'tipo': 'textarea',
             'ajuda': 'Contexto pra quem vai executar. Aceita {{...}}.'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('titulo') or '').strip() else ['`titulo` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        titulo = contexto.resolver(config.get('titulo', '')) or ''
        if not str(titulo).strip():
            return NodeResult(status='erro', branch='erro', erro='Título vazio.')
        tipo = contexto.resolver(config.get('tipo', '')) or 'followup'
        prioridade = contexto.resolver(config.get('prioridade', '')) or 'normal'
        prazo = _int(contexto.resolver(config.get('prazo_dias', '')), 1)
        descricao = contexto.resolver(config.get('descricao', '')) or ''
        try:
            tarefa = criar_tarefa(
                contexto.tenant,
                titulo=str(titulo), tipo=str(tipo), prioridade=str(prioridade),
                lead=contexto.lead, oportunidade=contexto.oportunidade, prazo_dias=prazo,
                descricao=str(descricao),
            )
        except Exception as e:
            return NodeResult(status='erro', branch='erro', erro=str(e))
        responsavel_nome = tarefa.responsavel.get_full_name() or tarefa.responsavel.username
        return NodeResult(
            output={'tarefa_id': tarefa.pk, 'titulo': tarefa.titulo, 'responsavel': responsavel_nome},
            branch='sucesso',
        )
