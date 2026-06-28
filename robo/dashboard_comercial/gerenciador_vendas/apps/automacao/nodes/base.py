"""
Contrato de nó da engine de automação unificada + registry.

Todo bloco ("quadradinho" estilo n8n) é uma subclasse de `BaseNode` registrada
via `@registrar`. O runtime itera/recupera nós pelo `REGISTRY`. Adicionar um nó
novo = criar uma classe + decorator. Zero mudança no runtime.

Mesmo padrão de registry usado em
`apps/comercial/crm/services/automacao_condicoes.py`.
"""
from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# RESULTADO DE UM NÓ
# ============================================================================

@dataclass
class NodeResult:
    """O que um nó devolve ao runtime.

    - output: JSON produzido pelo nó, endereçável por `{{nodes.<id>.<campo>}}`.
      Se tiver headers/secrets, já vem MASCARADO (princípio de segurança).
    - status: 'ok' | 'erro' | 'aguardando' (aguardando = nó pausou, ex: delay).
    - branch: aresta de saída a seguir ('sucesso' | 'erro' | 'true' | 'false' | ...).
    - promote: vars a fundir em `contexto.variaveis` (ponte do `salvar_em`).
    - erro: mensagem quando status == 'erro'.
    """
    output: dict = field(default_factory=dict)
    status: str = "ok"
    branch: Optional[str] = None
    promote: Optional[dict] = None
    erro: Optional[str] = None
    # Quando status == 'aguardando', descreve a espera:
    #   {'tipo': 'timer', 'segundos': N}                    → retoma por tempo (delay)
    #   {'tipo': 'resposta', 'chave': '<tel>', 'segundos': N} → retoma quando o contato responde
    #                                                           (segundos = timeout; 0 = sem limite)
    espera: Optional[dict] = None


# ============================================================================
# REGISTRY
# ============================================================================

REGISTRY = {}


def registrar(cls):
    """Decorator: instancia o nó e registra pelo seu `tipo`."""
    if not getattr(cls, 'tipo', ''):
        raise ValueError(f"Nó {cls.__name__} precisa de um `tipo` não-vazio.")
    REGISTRY[cls.tipo] = cls()
    return cls


def tipo_por_slug(tipo):
    """Retorna a instância do nó pelo slug, ou None."""
    return REGISTRY.get(tipo)


def todos_tipos():
    """Lista (tipo, label, grupo, subgrupo, categoria) pra UI/catálogo."""
    return [
        (t, inst.label, inst.grupo, inst.subgrupo, inst.categoria)
        for t, inst in REGISTRY.items()
    ]


# ============================================================================
# CONTRATO DE NÓ
# ============================================================================

class BaseNode:
    """Interface que todo nó implementa.

    Subclasse define `tipo` (slug único), `categoria` (gating por tenant futuro),
    `label`, e implementa `executar()`. `validar_config()` é opcional.
    """
    tipo = ""
    label = ""
    icone = "bi-box"     # Bootstrap Icon (bi-*) mostrado no card e na paleta
    categoria = "core"   # gating por tenant (futuro): core|comercial|marketing|atendimento
    grupo = "Core"       # categoria no menu do editor (taxonomia n8n-style)
    subgrupo = ""        # subcategoria no menu
    saidas = ["sucesso"] # branches que o nó pode emitir (portas de saída no editor)
    is_trigger = False   # gatilho? (sem porta de entrada; é o início do fluxo)

    # Saídas dinâmicas (config-driven): quando True, as portas do nó vêm de um campo
    # da config (`campo_saidas`) em vez de `saidas` fixo. Ex: o `switch` deriva os
    # ramos dos "casos". Genérico — qualquer nó pode optar. `saidas` segue como base.
    saidas_dinamicas = False
    campo_saidas = ""    # nome do campo de config que lista os ramos (str por linha OU lista)

    def saidas_de(self, config) -> list:
        """Saídas reais deste nó dada sua config. Estático → `self.saidas`.

        Dinâmico → ramos do campo `campo_saidas` (textarea um-por-linha ou lista de
        valores) + `default` no fim (rede de segurança pro que não casar).
        """
        if not self.saidas_dinamicas:
            return self.saidas
        raw = (config or {}).get(self.campo_saidas) or ''
        if isinstance(raw, str):
            nomes = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        elif isinstance(raw, (list, tuple)):
            nomes = [(x.get('valor') if isinstance(x, dict) else x) for x in raw]
            nomes = [str(x).strip() for x in nomes if str(x or '').strip()]
        else:
            nomes = []
        vistos, ordenados = set(), []
        for n in nomes:
            if n not in vistos and n != 'default':
                vistos.add(n)
                ordenados.append(n)
        return ordenados + ['default']

    def validar_config(self, config) -> list:
        """Retorna lista de erros de config (vazia = válida)."""
        return []

    def campos_config(self) -> list:
        """Schema dos campos de config — o editor renderiza o formulário a partir disto.

        Cada campo: {nome, label, tipo, opcoes?, placeholder?, ajuda?}.
        Tipos: texto | textarea | numero | booleano | select | keyvalue | lista_campos.
        Campos `texto`/`textarea` aceitam expressões `{{...}}`.
        """
        return []

    def executar(self, config, entrada, contexto) -> NodeResult:
        """Executa o nó.

        - config: dict de configuração do nó (com templates `{{...}}` por resolver).
        - entrada: output do nó anterior (dict), quando aplicável.
        - contexto: `apps.automacao.nodes.context.Contexto` (tenant obrigatório).
        """
        raise NotImplementedError(f"Nó {self.tipo!r} não implementou executar().")
