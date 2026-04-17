"""
ContextoLogado: dict wrapper que registra cada mutacao.

Transparente para quem consome — continua usando contexto['x'] = y, .get(), etc.
Mas loga cada set/del com nome_nodo e timestamp. Util para debug quando um nodo
sobrescreve uma variavel de outro e nao e obvio onde aconteceu.

Uso:
    contexto = ContextoLogado({'lead_nome': 'Maria'})
    contexto['classificacao'] = 'ACAO'  # registra evento

    # Consumir o log:
    for ev in contexto.historico():
        print(ev)  # {'op': 'set', 'chave': 'classificacao', 'valor_anterior': None, 'valor_novo': 'ACAO', 'nodo': 55, 'timestamp': ...}

O timestamp e o nodo atual sao injetados automaticamente via set_nodo_atual().
"""
from collections.abc import MutableMapping
from datetime import datetime


class ContextoLogado(MutableMapping):
    """Dict com log de mutacoes. API identica a dict."""

    def __init__(self, data=None):
        self._data = dict(data) if data else {}
        self._historico = []
        self._nodo_atual = None  # pk do nodo que esta executando

    # ── API de dict ──

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        valor_anterior = self._data.get(key)
        self._data[key] = value
        # Nao logar chaves internas repetitivas
        if key in ('var',):
            return
        if valor_anterior != value:
            self._historico.append({
                'op': 'set',
                'chave': key,
                'valor_anterior': _serializar(valor_anterior),
                'valor_novo': _serializar(value),
                'nodo': self._nodo_atual,
                'timestamp': datetime.now().isoformat(),
            })

    def __delitem__(self, key):
        valor_anterior = self._data.get(key)
        del self._data[key]
        self._historico.append({
            'op': 'del',
            'chave': key,
            'valor_anterior': _serializar(valor_anterior),
            'nodo': self._nodo_atual,
            'timestamp': datetime.now().isoformat(),
        })

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    # Spread (**contexto) funciona via keys() + __getitem__, o MutableMapping ja cobre.
    # dict(contexto) e copy() tambem.

    def copy(self):
        """Copia rasa. O novo contexto tem historico proprio (vazio)."""
        novo = ContextoLogado(self._data)
        novo._nodo_atual = self._nodo_atual
        return novo

    # ── API de log ──

    def set_nodo_atual(self, nodo_pk):
        """Define qual nodo esta executando. Todas mutacoes seguintes sao atribuidas a ele."""
        self._nodo_atual = nodo_pk

    def historico(self):
        """Retorna lista de eventos (nao modifica)."""
        return list(self._historico)

    def historico_por_nodo(self, nodo_pk):
        """Eventos de um nodo especifico."""
        return [ev for ev in self._historico if ev.get('nodo') == nodo_pk]

    def raw(self):
        """Retorna o dict interno (para serializar ou comparar)."""
        return dict(self._data)


def _serializar(valor):
    """Converte valor para JSON-safe (string truncada se for objeto complexo)."""
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, (list, tuple)):
        return [_serializar(v) for v in valor][:10]
    if isinstance(valor, dict):
        return {k: _serializar(v) for k, v in list(valor.items())[:20]}
    # Objetos do Django (models, etc.)
    s = str(valor)
    return s[:200] if len(s) > 200 else s
