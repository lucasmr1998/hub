"""Nó `definir_propriedade_lead`: escreve UMA propriedade do lead, escolhida
em dropdown (registry `propriedades_lead.py`).

Espelho exato do `definir_propriedade_oportunidade`, mesmo princípio do
catálogo: escrever propriedade é sempre este UM nó com a propriedade em
select, nunca um nó dedicado por atributo. Propriedade nova = handler novo no
registry, zero nó novo aqui.

Por que existe: o bot de venda coletava CPF, nome, email e endereço e nada
disso chegava na ficha do lead — as respostas ficavam só na tabela do
checklist, e a vendedora abria o lead com os campos vazios.

`aplicado=False` no output é branch de SUCESSO, não erro. Skip por regra de
negócio (campo já preenchido, formato que não parseia, valor vazio) nunca deve
acionar retry: retry é só pra falha transitória.
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class DefinirPropriedadeLeadNode(BaseNode):
    tipo = "definir_propriedade_lead"
    label = "Definir propriedade do lead"
    icone = "bi-person-vcard"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Leads"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'propriedade', 'label': 'Propriedade', 'tipo': 'select',
             'fonte': 'propriedades_lead', 'obrigatorio': True,
             'ajuda': 'Qual campo da ficha do lead escrever.'},
            {'nome': 'valor', 'label': 'Valor', 'tipo': 'texto',
             'ajuda': 'Aceita {{...}}. Ex: {{nodes.validar.valor_processado}}.'},
            {'nome': 'chave', 'label': 'Chave', 'tipo': 'texto',
             'ajuda': 'So para a propriedade Dado custom.'},
            {'nome': 'somente_se_vazio', 'label': 'So se ainda nao tiver valor',
             'tipo': 'booleano',
             'ajuda': 'Padrao ligado: nao sobrescreve o que ja esta preenchido, '
                      'inclusive o que um humano ajustou na ficha.'},
        ]

    def validar_config(self, config) -> list:
        from ..propriedades_lead import PROPRIEDADES
        slug = (config.get('propriedade') or '').strip()
        if '{{' in slug:
            # Propriedade decidida em execução (ver `executar`): não dá pra
            # validar contra o catálogo aqui, o valor só existe rodando.
            return []
        return [] if slug in PROPRIEDADES else ['escolha uma `propriedade` válida.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        from ..propriedades_lead import PROPRIEDADES

        if contexto.lead is None:
            return NodeResult(status='erro', branch='erro', erro='Sem lead no contexto.')

        # A propriedade aceita `{{...}}` de propósito. No bot de venda o fluxo
        # NÃO sabe em tempo de desenho qual campo escrever: depende de qual
        # pergunta o cliente acabou de responder. Como a chave do item do
        # checklist tem o mesmo nome do campo do lead, `{{nodes.validar.chave}}`
        # resolve isso com UM nó, em vez de uma escada de treze `if`.
        slug = str(contexto.resolver(config.get('propriedade', '')) or '').strip()
        prop = PROPRIEDADES.get(slug)
        if prop is None:
            # Chave que não corresponde a campo do lead (`tipo_imovel`,
            # `plano_confirmado`...) é o caso NORMAL quando a propriedade vem
            # de template: a maioria das perguntas não vira campo da ficha.
            # Skip, não erro — erro aqui encheria o log e acionaria retry à toa.
            return NodeResult(
                output={'aplicado': False, 'motivo_skip': 'propriedade_desconhecida',
                        'detalhe': f'{slug!r} não é campo do lead', 'propriedade': slug},
                branch='sucesso',
            )

        valor = contexto.resolver(config.get('valor', ''))
        chave = str(contexto.resolver(config.get('chave', '')) or '')
        # `.get(..., True)` só cai no default quando a chave está AUSENTE da
        # config. Um `somente_se_vazio: False` explícito chega intacto.
        somente_se_vazio = bool(config.get('somente_se_vazio', True))

        try:
            resultado = prop['handler'](
                contexto.tenant, contexto.lead, valor,
                chave=chave, somente_se_vazio=somente_se_vazio)
        except Exception as e:  # noqa: BLE001 (só bug real chega aqui)
            return NodeResult(status='erro', branch='erro', erro=str(e))

        return NodeResult(output={**resultado, 'propriedade': slug}, branch='sucesso')
