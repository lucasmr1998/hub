"""No `definir_propriedade_oportunidade`: escreve UMA propriedade da
oportunidade, escolhida em dropdown (registry `propriedades_oportunidade.py`).

Principio do catalogo: escrever propriedade de um recurso e sempre este UM no
com a propriedade em select, nunca um no dedicado por atributo (isso viraria
dezenas de nos quase identicos). No dedicado fica reservado pra COMPORTAMENTO
(mover estagio, reabrir, atribuir responsavel, criar nota...). Propriedade
nova = handler novo no registry, zero no novo aqui.

`aplicado=False` no output e branch de SUCESSO, nao erro. Skip por regra de
negocio (motivo fora do catalogo, oportunidade nao esta perdida, campo ja
preenchido, valor invalido) nunca deve acionar retry, retry e so pra falha
transitoria (rede, timeout). Achado do piloto fluxo 25: o no antigo
`definir_motivo_perda` levantava `ValueError` pra motivo invalido, um erro
deterministico que o runtime tratava como falha e reexecutava à toa.
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class DefinirPropriedadeOportunidadeNode(BaseNode):
    tipo = "definir_propriedade_oportunidade"
    label = "Definir propriedade da oportunidade"
    icone = "bi-pencil-square"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Oportunidades"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'propriedade', 'label': 'Propriedade', 'tipo': 'select',
             'fonte': 'propriedades_oportunidade', 'obrigatorio': True,
             'ajuda': 'Qual atributo da oportunidade escrever.'},
            {'nome': 'valor', 'label': 'Valor', 'tipo': 'texto',
             'ajuda': 'Aceita {{...}}. Vazio + propriedade Marcador = timestamp atual.'},
            {'nome': 'chave', 'label': 'Chave', 'tipo': 'texto',
             'ajuda': 'So para a propriedade Marcador.'},
            {'nome': 'somente_se_vazio', 'label': 'So se ainda nao tiver valor', 'tipo': 'booleano',
             'ajuda': 'Padrao ligado: nao sobrescreve o que ja esta preenchido.'},
        ]

    def validar_config(self, config) -> list:
        from ..propriedades_oportunidade import PROPRIEDADES
        slug = (config.get('propriedade') or '').strip()
        return [] if slug in PROPRIEDADES else ['escolha uma `propriedade` válida.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        from ..propriedades_oportunidade import PROPRIEDADES

        if contexto.oportunidade is None:
            return NodeResult(status='erro', branch='erro', erro='Sem oportunidade no contexto.')

        slug = (config.get('propriedade') or '').strip()
        prop = PROPRIEDADES.get(slug)
        if prop is None:
            return NodeResult(status='erro', branch='erro', erro=f'propriedade desconhecida: {slug}')

        valor = contexto.resolver(config.get('valor', ''))
        chave = str(contexto.resolver(config.get('chave', '')) or '')
        # `.get(..., True)` só cai no default quando a chave está AUSENTE da config.
        # Um `somente_se_vazio: False` explícito (usuário desligou) chega intacto.
        somente_se_vazio = bool(config.get('somente_se_vazio', True))

        try:
            resultado = prop['handler'](
                contexto.tenant, contexto.oportunidade, valor,
                chave=chave, somente_se_vazio=somente_se_vazio)
        except Exception as e:  # noqa: BLE001 (só bug real chega aqui; regra de negócio nunca levanta)
            return NodeResult(status='erro', branch='erro', erro=str(e))

        return NodeResult(output={**resultado, 'propriedade': slug}, branch='sucesso')
