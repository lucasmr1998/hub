"""
Nó `set_fields` — define/edita variáveis do fluxo.

Nó de REFERÊNCIA (template canônico que a skill `/criar-no-automacao` espelha).
Sem rede, sem ORM, risco zero. Resolve templates `{{...}}` nos valores e promove
o resultado pro namespace global `variaveis` (vira `{{var.<nome>}}` adiante).

Config aceita:
- `campos`: [{ "nome": "...", "valor": "<template>" }, ...]   (forma preferida)
- ou `campo` + `valor`: atalho pra um único campo
"""
from .base import BaseNode, NodeResult, registrar


@registrar
class SetFieldsNode(BaseNode):
    tipo = "set_fields"
    label = "Definir variáveis"
    icone = "bi-pencil-square"
    categoria = "core"
    grupo = "Transformação"
    subgrupo = "Campos"

    def campos_config(self) -> list:
        return [
            {'nome': 'campos', 'label': 'Campos a definir', 'tipo': 'lista_campos',
             'ajuda': 'Cada valor aceita expressões {{var.x}}, {{nodes.id.campo}}.'},
        ]

    def _campos(self, config):
        campos = config.get('campos')
        if campos is None and 'campo' in config:
            campos = [{'nome': config.get('campo'), 'valor': config.get('valor', '')}]
        return campos or []

    def validar_config(self, config) -> list:
        erros = []
        campos = self._campos(config)
        if not campos:
            erros.append(
                "Informe ao menos um campo (`campos: [{nome, valor}]` ou `campo`/`valor`)."
            )
        for i, c in enumerate(campos):
            if not isinstance(c, dict) or not c.get('nome'):
                erros.append(f"Campo #{i} sem `nome`.")
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        valores = {}
        for c in self._campos(config):
            valores[c['nome']] = contexto.resolver(c.get('valor', ''))
        # set_fields existe pra escrever variáveis: promove tudo que definiu.
        return NodeResult(output=valores, promote=valores, branch='sucesso')
