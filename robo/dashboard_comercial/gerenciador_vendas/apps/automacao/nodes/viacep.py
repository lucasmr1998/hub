"""Nó `viacep`: busca o endereço de um CEP e traz pro fluxo.

Embrulha `apps.comercial.viabilidade.services.buscar_endereco_por_cep` (ViaCEP),
que já normaliza o CEP e trata falha devolvendo dict vazio.

Por que existe: no bot de venda, o cliente digita o CEP e o próximo passo é
confirmar o endereço ("Confira: {rua}, {bairro}, {cidade}"). Esses campos NÃO
foram perguntados, vêm do CEP. Este nó traz rua/bairro/cidade/uf pro fluxo,
e um `definir_propriedade_lead` logo depois grava no lead, pra que a pergunta
de confirmação (que roda num turno seguinte) encontre os campos preenchidos.

Sem SSRF a tratar: o host do ViaCEP é fixo (viacep.com.br) e o CEP entra como
só dígitos (normalizado no service), nunca uma URL vinda do usuário.
"""
import re

from .base import BaseNode, NodeResult, registrar

# `Contexto.resolver` devolve o `{{...}}` LITERAL quando o caminho não existe
# (decisão do runtime). Um CEP não resolvido é CEP vazio, não um CEP chamado
# "{{var.payload.cep}}". Mesma proteção do `viabilidade_consultar`.
_TEMPLATE_NAO_RESOLVIDO = re.compile(r'^\s*\{\{.*\}\}\s*$', re.S)


@registrar
class ViaCepNode(BaseNode):
    tipo = "viacep"
    label = "ViaCEP: buscar endereço"
    icone = "bi-signpost-2"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Endereço"
    # `nao_encontrado` separado de `erro`: CEP que não existe é caso de negócio
    # (o cliente digitou errado, o fluxo pode reperguntar), não falha técnica.
    saidas = ["encontrado", "nao_encontrado", "erro"]

    # Nomes do ViaCEP → campos do lead. Conhecimento de domínio (fixo do
    # ViaCEP), não config de negócio: `logradouro` vira `rua`, `uf` vira
    # `estado`; bairro e cidade batem direto.
    _MAPA_LEAD = {'logradouro': 'rua', 'bairro': 'bairro', 'cidade': 'cidade', 'uf': 'estado'}

    def campos_config(self) -> list:
        return [
            {'nome': 'cep', 'label': 'CEP', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{nodes.respostas.cep}}',
             'ajuda': 'Aceita {{...}}. Só dígitos ou com máscara, tanto faz.'},
            {'nome': 'gravar_no_lead', 'label': 'Gravar endereço no lead', 'tipo': 'booleano',
             'ajuda': 'Grava rua/bairro/cidade/uf na ficha do lead, pra uma pergunta de '
                      'confirmação num turno seguinte já encontrar o endereço preenchido. '
                      'Não sobrescreve campo que já tem valor.'},
        ]

    def validar_config(self, config) -> list:
        return [] if (config.get('cep') or '').strip() else ['`cep` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        from apps.comercial.viabilidade.services import buscar_endereco_por_cep

        cep = str(contexto.resolver(config.get('cep', '')) or '').strip()
        if not cep or _TEMPLATE_NAO_RESOLVIDO.match(cep):
            return NodeResult(status='erro', branch='erro', erro='CEP vazio.')

        try:
            endereco = buscar_endereco_por_cep(cep)
        except Exception as exc:  # o service não promete, mas rede é rede
            return NodeResult(status='erro', branch='erro', erro=str(exc))

        if not endereco:
            # Dict vazio = CEP inválido (menos de 8 dígitos) ou não encontrado.
            return NodeResult(output={'cep': cep}, branch='nao_encontrado')

        if bool(config.get('gravar_no_lead')) and contexto.lead is not None:
            self._gravar_no_lead(contexto.lead, endereco)

        return NodeResult(output=endereco, branch='encontrado')

    def _gravar_no_lead(self, lead, endereco):
        """Persiste o endereço na ficha, sem sobrescrever campo que já tem valor
        (um humano pode ter corrigido). `save` só dos campos que mudaram."""
        alterados = []
        for chave_viacep, campo_lead in self._MAPA_LEAD.items():
            valor = (endereco.get(chave_viacep) or '').strip()
            if valor and not (getattr(lead, campo_lead, None) or '').strip():
                setattr(lead, campo_lead, valor)
                alterados.append(campo_lead)
        if alterados:
            lead.save(update_fields=alterados)
