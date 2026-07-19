"""Nó `checklist_validar`: roda a cascata DETERMINÍSTICA de validação de uma
resposta contra um item do checklist (opções, cpf/cnpj, cep, email, número,
data, regex), reusando `apps.comercial.atendimento_ia.services.validacao.validar`
por inteiro (motor de verdade, não reimplementado aqui). Quando válida e
`registrar=True`, grava via `services/checklist.registrar_resposta` (mesmo
service que a API do bot usa).

IMPORTANTE (decisão de arquitetura): este nó NUNCA chama LLM por conta própria.
A cascata que ele reusa só escala pra IA quando o PRÓPRIO item está configurado
assim (`tipo_validacao='ia'`, ou `instrucoes_ia` preenchida como segunda
opinião depois de uma reprovação determinística); esse comportamento já existe
e é auditado em `validacao.py`, não é uma chamada nova daqui. Quando o
checklist não está configurado assim e o fluxo ainda precisa de julgamento
semântico livre, quem decide encadear o nó `ia_agente` antes ou depois deste é
o GRAFO, nunca este nó.
"""
from .base import BaseNode, NodeResult, registrar
from .checklist_base import campo_checklist, campo_entidade, carregar_checklist, entidade_de
from ..models import Checklist, ItemChecklist
from ..services.checklist import registrar_resposta
from apps.comercial.atendimento_ia.services.validacao import validar


@registrar
class ChecklistValidarNode(BaseNode):
    tipo = "checklist_validar"
    label = "Checklist: validar resposta"
    icone = "bi-check2-circle"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Checklist"
    saidas = ["valida", "invalida", "erro"]

    def campos_config(self) -> list:
        return [
            campo_checklist(),
            {'nome': 'item_id', 'label': 'Item', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{nodes.proximo.item_id}}'},
            {'nome': 'resposta', 'label': 'Resposta', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{var.resposta_cliente}}'},
            campo_entidade(),
            {'nome': 'registrar', 'label': 'Registrar quando válida', 'tipo': 'booleano',
             'ajuda': 'Padrão ligado: grava a resposta no checklist quando ela valida.'},
        ]

    def validar_config(self, config) -> list:
        erros = []
        if not (config.get('checklist') or '').strip():
            erros.append('`checklist` é obrigatório.')
        if str(config.get('item_id') or '').strip() == '':
            erros.append('`item_id` é obrigatório.')
        if str(config.get('resposta') or '').strip() == '':
            erros.append('`resposta` é obrigatória.')
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        entidade_tipo, entidade = entidade_de(config, contexto)
        if entidade is None:
            return NodeResult(status='erro', branch='erro', erro=f'Sem {entidade_tipo} no contexto.')

        try:
            checklist = carregar_checklist(contexto.tenant, config, contexto)
        except Checklist.DoesNotExist:
            slug = config.get('checklist') or ''
            return NodeResult(status='erro', branch='erro', erro=f'checklist {slug!r} não encontrado.')

        item_id = contexto.resolver(config.get('item_id', ''))
        if item_id in (None, ''):
            return NodeResult(status='erro', branch='erro', erro='`item_id` vazio.')
        try:
            item = ItemChecklist.all_tenants.get(pk=item_id, checklist=checklist, tenant=contexto.tenant)
        except (ItemChecklist.DoesNotExist, ValueError, TypeError):
            return NodeResult(status='erro', branch='erro',
                               erro=f'item {item_id!r} não pertence ao checklist {checklist.slug!r}.')

        resposta = contexto.resolver(config.get('resposta', ''))
        resultado = validar(item, resposta, contexto.tenant)
        # `valida=None` (cascata sem IA disponível pra 2ª opinião, ver docstring
        # de `validacao.py`) segue tratado como "aceita com ressalva": mesma
        # decisão já tomada no fluxo humano (atendimento_ia/views.py::validar).
        valida = resultado['valida'] is not False

        if valida and bool(config.get('registrar', True)):
            registrar_resposta(
                checklist, item, entidade_tipo, entidade.pk, resposta,
                valor_processado=resultado['valor_processado'], origem='bot',
            )

        output = {
            'valida': valida,
            'valor_processado': resultado['valor_processado'],
            'fonte': resultado['fonte'],
            'erro': resultado['erro'],
            'chave': item.chave,
            'item_id': item.pk,
            # Texto da pergunta original: o grafo precisa disso pra dar contexto
            # a um nó `ia_agente` de segunda opiniao (a resposta sozinha, sem a
            # pergunta, nao da pro LLM julgar nada).
            'pergunta': item.pergunta,
        }
        return NodeResult(output=output, branch='valida' if valida else 'invalida')
