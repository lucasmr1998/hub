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
