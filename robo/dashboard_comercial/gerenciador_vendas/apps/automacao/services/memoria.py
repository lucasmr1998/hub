"""Memória de agente — registry extensível (mesmo padrão de nodes/tools).

Cada tipo de memória sabe CARREGAR a janela de contexto que vai pro LLM. A 1ª (e por
ora única) é `conversa`: as mensagens da conversa em que o agente está rodando — inbox
em prod, turnos do chat de teste em dev. Adicionar um tipo novo (resumo, store
persistente, etc.) = registrar aqui, SEM mexer no agente nem no nó.

Princípio: o classificador não "polui" a memória de graça — a memória são as MENSAGENS
da conversa (o que o cliente mandou + o que o bot respondeu). O classificador não
responde nada ao cliente → não vira mensagem → não entra na memória.
"""

_MEMORIAS = {}


def registrar_memoria(chave, label):
    def deco(fn):
        _MEMORIAS[chave] = {'chave': chave, 'label': label, 'carregar': fn}
        return fn
    return deco


def memorias_disponiveis():
    """[(chave, label)] — alimenta o seletor de memória no editor do agente."""
    return [(m['chave'], m['label']) for m in _MEMORIAS.values()]


def carregar_memoria(chave, contexto, k=10):
    """Janela [{role, content}] pra alimentar o LLM. Tipo desconhecido cai pra
    `conversa`. Nunca levanta — sem memória/erro vira lista vazia (degrada gracioso)."""
    m = _MEMORIAS.get(chave) or _MEMORIAS.get('conversa')
    if not m:
        return []
    try:
        return m['carregar'](contexto, k)
    except Exception:  # noqa: BLE001
        return []


# ----------------------------------------------------------------------------
# Tipo 1: conversa
# ----------------------------------------------------------------------------

_REMETENTE_ROLE = {'contato': 'user', 'bot': 'assistant', 'agente': 'assistant'}


@registrar_memoria('conversa', 'Conversa (mensagens da conversa atual)')
def _memoria_conversa(contexto, k=10):
    # Prod: a conversa do inbox que está no contexto.
    conversa = getattr(contexto, 'conversa', None)
    if conversa is not None:
        return _da_conversa(conversa, k)
    # Teste / fluxo sem inbox: os turnos que o chat de teste passa nas variáveis.
    turnos = (getattr(contexto, 'variaveis', None) or {}).get('_memoria_turnos')
    return list(turnos)[-(k * 2):] if isinstance(turnos, list) else []


def _da_conversa(conversa, k):
    """Últimas k trocas da conversa do inbox → [{role, content}] em ordem cronológica."""
    msgs = (conversa.mensagens
            .exclude(remetente_tipo='sistema')
            .filter(tipo_conteudo='texto')
            .order_by('-id')[:k * 2])
    historico = []
    for m in reversed(list(msgs)):
        role = _REMETENTE_ROLE.get(m.remetente_tipo)
        conteudo = (m.conteudo or '').strip()
        if role and conteudo:
            historico.append({'role': role, 'content': conteudo})
    return historico
