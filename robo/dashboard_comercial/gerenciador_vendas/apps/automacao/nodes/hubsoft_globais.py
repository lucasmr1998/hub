"""Nós HubSoft globais (read, paginados) + agenda: clientes/OS/atendimentos
'todos' e horários de agenda de OS."""
from .base import registrar
from .hubsoft_base import HubsoftNode, _txt, _int

_PAG = [
    {'nome': 'data_inicio', 'label': 'Data início (YYYY-MM-DD)', 'tipo': 'texto'},
    {'nome': 'data_fim', 'label': 'Data fim (YYYY-MM-DD)', 'tipo': 'texto'},
    {'nome': 'pagina', 'label': 'Página', 'tipo': 'numero', 'placeholder': '0'},
    {'nome': 'itens_por_pagina', 'label': 'Itens por página', 'tipo': 'numero', 'placeholder': '100'},
]


def _pag_kwargs(contexto, config):
    kw = {
        'pagina': _int(contexto.resolver(config.get('pagina', '')), 0),
        'itens_por_pagina': _int(contexto.resolver(config.get('itens_por_pagina', '')), 100),
    }
    for c in ('data_inicio', 'data_fim'):
        v = _txt(contexto, config, c)
        if v:
            kw[c] = v
    return kw


@registrar
class HubsoftListarClientesTodos(HubsoftNode):
    tipo = "hubsoft_listar_clientes_todos"
    label = "HubSoft: listar clientes (todos)"
    icone = "bi-people"
    saida_chave = "clientes"

    def campos_config(self) -> list:
        return _PAG + [
            {'nome': 'cancelado', 'label': 'Cancelado (sim/nao)', 'tipo': 'texto'},
            {'nome': 'servico_status', 'label': 'Status do serviço', 'tipo': 'texto'},
            {'nome': 'relacoes', 'label': 'Relações (extra)', 'tipo': 'texto'},
        ]

    def _chamar(self, svc, config, contexto):
        kw = _pag_kwargs(contexto, config)
        for c in ('cancelado', 'servico_status', 'relacoes'):
            v = _txt(contexto, config, c)
            if v:
                kw[c] = v
        return (svc.listar_clientes_todos(**kw) or {}).get('clientes', [])


@registrar
class HubsoftListarOsTodos(HubsoftNode):
    tipo = "hubsoft_listar_os_todos"
    label = "HubSoft: listar OS (todas)"
    icone = "bi-card-checklist"
    saida_chave = "ordens_servico"

    def campos_config(self) -> list:
        return _PAG

    def _chamar(self, svc, config, contexto):
        return (svc.listar_os_todos(**_pag_kwargs(contexto, config)) or {}).get('ordens_servico', [])


@registrar
class HubsoftListarAtendimentosTodos(HubsoftNode):
    tipo = "hubsoft_listar_atendimentos_todos"
    label = "HubSoft: listar atendimentos (todos)"
    icone = "bi-chat-left-text"
    saida_chave = "atendimentos"

    def campos_config(self) -> list:
        return _PAG + [{'nome': 'relacoes', 'label': 'Relações (extra)', 'tipo': 'texto'}]

    def _chamar(self, svc, config, contexto):
        kw = _pag_kwargs(contexto, config)
        rel = _txt(contexto, config, 'relacoes')
        if rel:
            kw['relacoes'] = rel
        return (svc.listar_atendimentos_todos(**kw) or {}).get('atendimentos', [])


@registrar
class HubsoftHorariosAgenda(HubsoftNode):
    tipo = "hubsoft_horarios_agenda"
    label = "HubSoft: horários de agenda (OS)"
    icone = "bi-calendar-week"
    saida_chave = "horarios"

    def campos_config(self) -> list:
        return [
            {'nome': 'id_agenda_ordem_servico', 'label': 'ID da agenda de OS', 'tipo': 'numero'},
            {'nome': 'descricao', 'label': 'Descrição da agenda', 'tipo': 'texto'},
            {'nome': 'data_inicio', 'label': 'Data início (YYYY-MM-DD)', 'tipo': 'texto'},
            {'nome': 'dias', 'label': 'Dias', 'tipo': 'numero', 'placeholder': '1'},
        ]

    def validar_config(self, config) -> list:
        if not (str(config.get('id_agenda_ordem_servico', '')).strip()
                or str(config.get('descricao', '')).strip()):
            return ['informe `id_agenda_ordem_servico` ou `descricao`.']
        return []

    def _chamar(self, svc, config, contexto):
        kw = {'dias': _int(contexto.resolver(config.get('dias', '')), 1)}
        ida = _int(contexto.resolver(config.get('id_agenda_ordem_servico', '')), None)
        if ida:
            kw['id_agenda_ordem_servico'] = ida
        desc = _txt(contexto, config, 'descricao')
        if desc:
            kw['descricao'] = desc
        di = _txt(contexto, config, 'data_inicio')
        if di:
            kw['data_inicio'] = di
        return svc.consultar_horarios_agenda(**kw)
