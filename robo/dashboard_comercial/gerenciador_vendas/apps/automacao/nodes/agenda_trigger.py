"""Nó de gatilho Agenda (varredura) — dispara em ciclo, não por evento.

Config: `intervalo_minutos` (a cada quanto tempo a varredura roda) + `varredura`
(o que buscar, registry em `..varreduras`) + `varredura_config` (parâmetros livres
da varredura escolhida) + freios (`max_por_lead`/`cooldown_horas`, mesmo contrato
do nó `evento`) + `max_por_rodada` (teto de itens enfileirados por rodada).

Cada item devolvido pela varredura vira UMA execução do fluxo. O dispatch (achar
o fluxo vencido, rodar a varredura, aplicar freios) é feito por
`gatilhos.despachar_agendas` — aqui o nó só carrega a config e, em teste, passa
adiante (mesmo padrão do `evento_trigger`).
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class AgendaTriggerNode(BaseNode):
    tipo = "agenda"
    label = "Agenda (varredura)"
    icone = "bi-alarm"
    categoria = "core"
    grupo = "Gatilho"
    subgrupo = "Varredura"
    saidas = ["default"]
    is_trigger = True

    def campos_config(self) -> list:
        return [
            {'nome': 'intervalo_minutos', 'label': 'Intervalo (min)', 'tipo': 'numero', 'obrigatorio': True,
             'ajuda': 'A cada quanto tempo a varredura roda.'},
            {'nome': 'varredura', 'label': 'Varredura', 'tipo': 'select', 'fonte': 'varreduras', 'obrigatorio': True,
             'ajuda': 'O que buscar a cada rodada. Cada item encontrado vira UMA execução.'},
            {'nome': 'varredura_config', 'label': 'Parâmetros da varredura', 'tipo': 'keyvalue',
             'ajuda': 'Depende da varredura (ex: janela_dias_min=30, motivo_categoria=sem_retorno).'},
            {'nome': 'max_por_rodada', 'label': 'Máx. execuções por rodada', 'tipo': 'numero',
             'ajuda': 'Teto de itens enfileirados por rodada. Vazio = 25.'},
            {'nome': 'max_por_lead', 'label': 'Máx. disparos por lead', 'tipo': 'numero',
             'ajuda': 'Freio: recomendado 1. Sem freio a rodada é pulada com aviso.'},
            {'nome': 'cooldown_horas', 'label': 'Cooldown (horas)', 'tipo': 'numero',
             'ajuda': 'Freio alternativo/complementar ao acima.'},
        ]

    def validar_config(self, config) -> list:
        from ..varreduras import VARREDURAS
        erros = []
        if (config.get('varredura') or '') not in VARREDURAS:
            erros.append('escolha uma `varredura` válida.')
        try:
            if int(config.get('intervalo_minutos') or 0) <= 0:
                erros.append('`intervalo_minutos` precisa ser > 0.')
        except (TypeError, ValueError):
            erros.append('`intervalo_minutos` inválido.')
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        return NodeResult(output={'varredura': config.get('varredura')}, branch='default')
