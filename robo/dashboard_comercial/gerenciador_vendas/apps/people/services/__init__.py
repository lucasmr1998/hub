"""
API publica do modulo People.

Todo consumo de People, de dentro ou de fora do app, passa por aqui. Em
especial: nenhuma outra Tool escreve em `Colaborador` direto, porque o dedup
(a regra que sustenta o modulo) mora no servico, nao nas telas.

Os nomes exportados sao poucos de proposito. Se voce precisou importar algo de
um submodulo daqui, provavelmente esta faltando um servico.
"""
from apps.people.services.admissao import admitir_candidato
from apps.people.services.colaboradores import (
    Candidato,
    ResultadoCadastro,
    buscar_colaborador,
    marcar_revisado,
    mover_situacao,
    registrar_colaborador,
)
from apps.people.services.configuracao import config_efetiva, unidade_sentinela
from apps.people.services.links import (
    criar_link,
    desativar_link,
    link_ativo,
    links_ativos,
    reativar_link,
    registrar_submissao,
    resolver_por_token,
    rotacionar_link,
)

__all__ = [
    'Candidato',
    'ResultadoCadastro',
    'buscar_colaborador',
    'config_efetiva',
    'admitir_candidato',
    'criar_link',
    'desativar_link',
    'link_ativo',
    'links_ativos',
    'marcar_revisado',
    'mover_situacao',
    'reativar_link',
    'registrar_colaborador',
    'registrar_submissao',
    'resolver_por_token',
    'rotacionar_link',
    'unidade_sentinela',
]
