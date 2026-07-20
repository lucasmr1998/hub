"""Excecoes do modulo People. Python puro, sem Django, pra poder ser importado
por estados.py sem arrastar o ORM junto."""


class PeopleError(Exception):
    """Base de tudo que o People levanta."""


class TransicaoInvalida(PeopleError):
    """A transicao pedida nao existe na maquina de estados."""


class TransicaoNaoAutorizada(PeopleError):
    """
    Alguem tentou mudar `situacao` sem passar por `mover_situacao()`.

    Nao e erro do usuario, e erro de programacao: a situacao e a espinha do
    modulo e toda mudanca dela precisa gerar historico e telemetria.
    """


class CampoObrigatorioFaltando(PeopleError):
    """A transicao exige um campo que nao foi informado nem esta preenchido."""

    def __init__(self, campos, de, para):
        self.campos = list(campos)
        self.de = de
        self.para = para
        faltando = ', '.join(self.campos)
        super().__init__(
            f'Transicao de "{de}" para "{para}" exige: {faltando}.'
        )
