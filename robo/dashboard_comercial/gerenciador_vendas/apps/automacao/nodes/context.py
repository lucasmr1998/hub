"""
Contexto global do fluxo + resolvedor de template `{{ ... }}`.

Contrato híbrido: o `Contexto` carrega o estado global da execução (tenant, lead,
oportunidade, conversa, variaveis acumuladas) e o mapa `nodes` (output de cada nó
já executado, endereçável por `{{nodes.<id>.<campo>}}`).

O resolvedor é NOVO (dot-notation). O motor antigo usa chave achatada
(`{{lead_nome}}`); aqui é `{{lead.nome}}`. O *padrão de walk* é emprestado de
`apps/comercial/atendimento/engine.py:_resolver_campo_contexto`, mas sem o
fallback de chave achatada (contrato dot-notation puro).
"""
import json
import re


# Marcador interno: caminho não resolvido (distingue "chave ausente" de "valor None").
_UNRESOLVED = object()

# Captura `{{ caminho.com.pontos }}` (sem chaves aninhadas dentro).
_TOKEN = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')


class Contexto:
    """Estado global de uma execução de fluxo.

    `tenant` é OBRIGATÓRIO: a engine roda fora de request (cron/command/signal),
    onde o thread-local do TenantMiddleware está vazio ou sujo. Nenhum nó deve
    confiar em `get_current_tenant()` — tudo passa por `contexto.tenant`.
    """

    def __init__(self, tenant, *, lead=None, oportunidade=None, conversa=None,
                 variaveis=None, nodes=None):
        if tenant is None:
            raise ValueError(
                "Contexto exige tenant explícito (a engine roda fora de request)."
            )
        self.tenant = tenant
        self.lead = lead
        self.oportunidade = oportunidade
        self.conversa = conversa
        self.variaveis = dict(variaveis or {})
        self.nodes = dict(nodes or {})

    # -- escopo de resolução -------------------------------------------------

    def _escopo(self):
        return {
            'tenant': self.tenant,
            'lead': self.lead,
            'oportunidade': self.oportunidade,
            'conversa': self.conversa,
            'var': self.variaveis,
            'nodes': self.nodes,
        }

    # -- resolução de template ----------------------------------------------

    def resolver(self, valor):
        """Resolve templates `{{...}}` recursivamente em str/dict/list.

        - str com um único token (full-match) → devolve o valor BRUTO (preserva
          tipo: dict/list/int passam inteiros entre nós).
        - str com texto misto → interpola (dict/list→JSON, None→'', resto→str).
        - dict/list → resolve as folhas.
        - outros tipos → passam inteiros.
        """
        if isinstance(valor, str):
            return self._interpolar(valor)
        if isinstance(valor, dict):
            return {k: self.resolver(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [self.resolver(v) for v in valor]
        return valor

    def _interpolar(self, texto):
        if not texto:
            return texto

        full = _TOKEN.fullmatch(texto)
        if full:
            resolvido = self._resolver_caminho(full.group(1).strip())
            if resolvido is _UNRESOLVED:
                return texto  # literal
            return resolvido  # tipo bruto preservado

        def _sub(m):
            resolvido = self._resolver_caminho(m.group(1).strip())
            if resolvido is _UNRESOLVED:
                return m.group(0)  # mantém `{{...}}` literal
            return self._stringificar(resolvido)

        return _TOKEN.sub(_sub, texto)

    def _resolver_caminho(self, caminho):
        obj = self._escopo()
        for parte in caminho.split('.'):
            obj = self._passo(obj, parte)
            if obj is _UNRESOLVED:
                return _UNRESOLVED
        return obj

    @staticmethod
    def _passo(obj, parte):
        if obj is None or obj is _UNRESOLVED:
            return _UNRESOLVED
        getter = getattr(obj, 'get', None)
        if callable(getter):
            try:
                return getter(parte, _UNRESOLVED)
            except TypeError:
                valor = getter(parte)
                return _UNRESOLVED if valor is None else valor
        if hasattr(obj, parte):
            return getattr(obj, parte)
        return _UNRESOLVED

    @staticmethod
    def _stringificar(valor):
        if valor is None:
            return ''
        if isinstance(valor, (dict, list)):
            return json.dumps(valor, ensure_ascii=False)
        return str(valor)

    # -- mutação / ponte de promoção ----------------------------------------

    def promover(self, nome, valor):
        """Funde uma var no namespace global (vira `{{var.<nome>}}`)."""
        self.variaveis[nome] = valor

    def registrar_saida(self, node_id, output):
        """Guarda o output de um nó (vira `{{nodes.<node_id>.<campo>}}`)."""
        self.nodes[node_id] = output

    def aplicar_resultado(self, node_id, resultado):
        """Aplica um NodeResult ao contexto: registra output + aplica promote."""
        self.registrar_saida(node_id, resultado.output)
        if resultado.promote:
            self.variaveis.update(resultado.promote)

    # -- serialização (contrato de persistência: id, não objeto) ------------

    def serializar(self):
        """Estado JSON-serializável pra retoma assíncrona futura.

        Persiste tenant_id + variaveis + nodes + refs por id das entidades.
        Na retoma, re-hidrata por (model, id, tenant).
        """
        return {
            'tenant_id': getattr(self.tenant, 'pk', None),
            'variaveis': self.variaveis,
            'nodes': self.nodes,
            'entidades': {
                'lead': getattr(self.lead, 'pk', None),
                'oportunidade': getattr(self.oportunidade, 'pk', None),
                'conversa': getattr(self.conversa, 'pk', None),
            },
        }
