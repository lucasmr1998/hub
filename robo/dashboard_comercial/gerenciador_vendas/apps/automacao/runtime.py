"""
Runtime da engine de automação — o "andador do grafo".

Pega um fluxo (grafo de nós + conexões) e executa: liga os nós, passa o output
de um pro outro (contrato híbrido), ramifica pela saída do nó, pausa quando um nó
pede espera, e protege contra loop. Síncrono, sem fila — o despacho real-time vem
de signals e a retoma de delays vem de um cron (próxima fase, com persistência).

Sem models/DB aqui: o fluxo é um dict em memória. A `handle` de cada nó é a
CHAVE dele em `nodes` — é o identificador visível e o que `{{nodes.<handle>}}`
referencia.

Formato do fluxo:
    {
        "inicio": "n1",
        "nodes": {
            "n1": {"tipo": "set_fields", "config": {...}},
            "n2": {"tipo": "http_request", "config": {...}},
        },
        "conexoes": [
            {"de": "n1", "para": "n2", "saida": "sucesso"},
        ],
    }
"""
from dataclasses import dataclass, field
from typing import Optional

from .nodes import tipo_por_slug
from .nodes.base import NodeResult


class FluxoInvalido(Exception):
    """Fluxo malformado (nó inicial ausente, aresta apontando pra nó inexistente, etc.)."""


@dataclass
class PassoTrace:
    handle: str
    tipo: str
    status: str
    branch: Optional[str]
    erro: Optional[str] = None


@dataclass
class RunResult:
    status: str                       # completado | aguardando | erro
    passos: list = field(default_factory=list)   # [PassoTrace]
    aguardando: Optional[dict] = None  # {'retomar_em': <handle>, 'estado': contexto.serializar()}
    erro: Optional[str] = None


def validar_fluxo(fluxo) -> list:
    """Retorna lista de erros estruturais do fluxo (vazia = ok)."""
    erros = []
    nodes = fluxo.get('nodes') or {}
    if not nodes:
        erros.append('fluxo sem nós')
    inicio = fluxo.get('inicio')
    if not inicio or inicio not in nodes:
        erros.append(f"nó inicial '{inicio}' não existe")
    for handle, definicao in nodes.items():
        tipo = (definicao or {}).get('tipo')
        if tipo_por_slug(tipo) is None:
            erros.append(f"nó '{handle}': tipo '{tipo}' não registrado")
    for c in fluxo.get('conexoes') or []:
        de = c.get('de')
        if de not in nodes:
            erros.append(f"conexão com origem inexistente: {de}")
        if c.get('para') not in nodes:
            erros.append(f"conexão com destino inexistente: {c.get('para')}")
        # F4: a saída usada tem que ser uma saída declarada pelo nó de origem.
        # `saidas_de(config)` resolve saídas dinâmicas (ex: casos do switch).
        if de in nodes:
            no_def = nodes[de] or {}
            no = tipo_por_slug(no_def.get('tipo'))
            saida = c.get('saida', 'default')
            validas = no.saidas_de(no_def.get('config') or {}) if no is not None else []
            if no is not None and saida not in (validas or []) and saida != 'default':
                erros.append(f"nó '{de}': saída '{saida}' não existe (válidas: {', '.join(validas)})")
    return erros


def executar_fluxo(fluxo, contexto, *, inicio=None, entrada=None, max_passos=1000) -> RunResult:
    """Percorre o grafo a partir de `inicio` (ou `fluxo['inicio']`) até o fim, uma
    pausa (`aguardando`) ou um erro. Não levanta por erro de nó — devolve no RunResult.
    """
    erros_estruturais = validar_fluxo(fluxo)
    if erros_estruturais and inicio is None:
        raise FluxoInvalido('; '.join(erros_estruturais))

    nodes = fluxo['nodes']
    handle = inicio or fluxo['inicio']
    entrada = entrada or {}
    passos = []

    for _ in range(max_passos):
        definicao = nodes.get(handle)
        if definicao is None:
            return RunResult('erro', passos, erro=f"nó '{handle}' não existe")

        tipo = definicao.get('tipo')
        no = tipo_por_slug(tipo)
        if no is None:
            return RunResult('erro', passos, erro=f"tipo de nó '{tipo}' não registrado ({handle})")

        config = definicao.get('config') or {}
        erros_cfg = no.validar_config(config)
        if erros_cfg:
            return RunResult('erro', passos,
                             erro=f"config inválida em '{handle}': {'; '.join(erros_cfg)}")

        # F3: nó que estoura exceção vira erro controlado (não derruba o fluxo/endpoint).
        try:
            resultado = no.executar(config, entrada, contexto)
        except Exception as exc:  # noqa: BLE001 — qualquer falha do nó é tratada como branch erro
            resultado = NodeResult(
                status='erro', branch='erro', output={},
                erro=f"exceção em '{handle}': {exc}",
            )
        # contrato híbrido: registra output sob o handle + funde promote + funde
        # entidades de domínio (`NodeResult.entidades`, ex: um nó `carregar_lead`
        # injeta `contexto.lead` no meio do grafo — ver `Contexto.aplicar_resultado`).
        contexto.aplicar_resultado(handle, resultado)
        passos.append(PassoTrace(handle, tipo, resultado.status, resultado.branch, resultado.erro))

        proximo = _proxima(fluxo, handle, resultado.branch)

        if resultado.status == 'aguardando':
            espera = resultado.espera or {
                'tipo': 'timer',
                'segundos': (resultado.output or {}).get('aguardar_segundos', 0),
            }
            return RunResult('aguardando', passos, aguardando={
                'no_pausado': handle,             # nó que pausou (resume sai daqui)
                'estado': contexto.serializar(),
                'espera': espera,
            })

        if proximo is None:
            if resultado.status == 'erro':
                return RunResult('erro', passos,
                                 erro=resultado.erro or f"erro não tratado em '{handle}'")
            return RunResult('completado', passos)

        entrada = resultado.output
        handle = proximo

    return RunResult('erro', passos, erro=f'limite de {max_passos} passos (possível loop)')


def _proxima(fluxo, handle, branch):
    """Aresta de saída a seguir: casa pela `branch`; senão tenta 'default'; senão fim."""
    conexoes = fluxo.get('conexoes') or []
    branch = branch or 'default'
    for c in conexoes:
        if c.get('de') == handle and c.get('saida') == branch:
            return c.get('para')
    for c in conexoes:
        if c.get('de') == handle and c.get('saida', 'default') == 'default':
            return c.get('para')
    return None
