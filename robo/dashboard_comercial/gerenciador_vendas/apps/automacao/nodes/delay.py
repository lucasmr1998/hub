"""Nó `delay` — pausa o fluxo por um tempo.

Devolve `status='aguardando'`: o runtime para e serializa o estado. A retomada
efetiva (agendar + continuar do nó seguinte) é responsabilidade do cron, na fase
de execução persistida.
"""
from .base import BaseNode, NodeResult, registrar

UNIDADES = {'segundos': 1, 'minutos': 60, 'horas': 3600, 'dias': 86400}


@registrar
class DelayNode(BaseNode):
    tipo = "delay"
    label = "Aguardar"
    icone = "bi-hourglass-split"
    categoria = "core"
    grupo = "Fluxo"
    subgrupo = "Controle"
    saidas = ["default"]

    def campos_config(self) -> list:
        return [
            {'nome': 'valor', 'label': 'Quantidade', 'tipo': 'numero'},
            {'nome': 'unidade', 'label': 'Unidade', 'tipo': 'select',
             'opcoes': list(UNIDADES)},
        ]

    def validar_config(self, config) -> list:
        erros = []
        if config.get('unidade', 'minutos') not in UNIDADES:
            erros.append(f"`unidade` inválida (use: {', '.join(UNIDADES)}).")
        try:
            int(config.get('valor', 0) or 0)
        except (ValueError, TypeError):
            erros.append("`valor` deve ser número.")
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        valor = int(config.get('valor', 0) or 0)
        unidade = config.get('unidade', 'minutos')
        segundos = valor * UNIDADES.get(unidade, 60)
        return NodeResult(
            output={'aguardar_segundos': segundos, 'unidade': unidade, 'valor': valor},
            status='aguardando',
            branch='default',
            espera={'tipo': 'timer', 'segundos': segundos},
        )
