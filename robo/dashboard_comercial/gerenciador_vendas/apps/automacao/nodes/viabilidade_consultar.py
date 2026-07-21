"""Nó `viabilidade_consultar`: o endereço tem cobertura?

Embrulha `apps.comercial.viabilidade.services.consultar_viabilidade`, que já é
o executor de domínio da casa: consulta o HubSoft, cai pra `CidadeViabilidade`
local quando a integração não responde, completa o endereço que faltar pelo
ViaCEP (o mesmo papel que a BrasilAPI faz no fluxo N8N) e NUNCA levanta
exceção.

Por que não usar o `hubsoft_viabilidade_endereco` cru: a resposta do HubSoft é
traiçoeira de interpretar. O campo `projetos` vem como LISTA quando há projeto
compatível e como TEXTO ("Nenhum Projeto foi compatível com a localização.")
quando não há. Um `if` de "não vazio" em cima disso responde "tem cobertura"
nos DOIS casos (verificado contra a conta da Nuvyon em 20/07). Além disso,
projeto compatível não significa porta livre: o service confere as portas
disponíveis antes de dizer que atende.

Saídas separam "não atende" de "não sei": resposta que não sabemos interpretar
vira `pendente_revisao`, não `fora_cobertura`. Decidir que não há cobertura em
cima de resposta desconhecida manda o lead pra Perdido calado.
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class ViabilidadeConsultarNode(BaseNode):
    tipo = "viabilidade_consultar"
    label = "Viabilidade: consultar cobertura"
    icone = "bi-geo-alt"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Viabilidade"
    saidas = ["cobertura_ok", "fora_cobertura", "pendente_revisao", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'cep', 'label': 'CEP', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.cep}}',
             'ajuda': 'Único campo obrigatório. Os demais são completados pelo ViaCEP '
                      'quando vierem vazios.'},
            {'nome': 'logradouro', 'label': 'Logradouro', 'tipo': 'texto',
             'placeholder': '{{lead.rua}}'},
            {'nome': 'numero', 'label': 'Número', 'tipo': 'texto',
             'placeholder': '{{lead.numero_residencia}}'},
            {'nome': 'bairro', 'label': 'Bairro', 'tipo': 'texto',
             'placeholder': '{{lead.bairro}}'},
            {'nome': 'cidade', 'label': 'Cidade', 'tipo': 'texto',
             'placeholder': '{{lead.cidade}}'},
            {'nome': 'uf', 'label': 'UF', 'tipo': 'texto', 'placeholder': '{{lead.estado}}'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('cep') or '').strip() else ['`cep` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        from apps.comercial.viabilidade.services import consultar_viabilidade

        def txt(nome):
            return str(contexto.resolver(config.get(nome, '')) or '').strip()

        cep = txt('cep')
        if not cep:
            return NodeResult(status='erro', branch='erro', erro='CEP vazio.')

        try:
            resultado = consultar_viabilidade(
                contexto.tenant, cep,
                logradouro=txt('logradouro'), numero=txt('numero'), bairro=txt('bairro'),
                cidade=txt('cidade'), uf=txt('uf'),
            )
        except Exception as exc:  # o service promete não levantar, mas não custa
            return NodeResult(status='erro', branch='erro', erro=str(exc))

        saida = resultado.to_dict()
        # `endereco_incompleto`/`nao_consultado` também caem em pendente_revisao:
        # não são "fora de cobertura", são "não deu pra decidir".
        branch = {
            'cobertura_ok': 'cobertura_ok',
            'fora_cobertura': 'fora_cobertura',
            'erro': 'erro',
        }.get(resultado.status, 'pendente_revisao')
        return NodeResult(output=saida, branch=branch)
