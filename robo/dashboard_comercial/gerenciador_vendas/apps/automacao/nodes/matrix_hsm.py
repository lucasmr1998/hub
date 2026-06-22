"""Nó `matrix_hsm` — dispara um template HSM (WhatsApp) pela Matrix Brasil.

⚠️ Outbound REAL: cria atendimento e envia mensagem pro contato. Provedor Matrix
(canal do tenant, ex: Nuvyon). Fora da janela 24h o WhatsApp exige template
aprovado (HSM) — por isso este nó pede `hsm` (id do template) + `variaveis`.

Reusa `MatrixBrasilService.enviar_hsm` (via `services.matrix.matrix_do_tenant`).
Tenant vem de `contexto.tenant` (engine roda fora de request).
"""
from .base import BaseNode, NodeResult, registrar
from ..services.matrix import matrix_do_tenant


def _erro(msg):
    return NodeResult(status='erro', branch='erro', erro=msg, output={'ok': False})


@registrar
class MatrixHsmNode(BaseNode):
    tipo = "matrix_hsm"
    label = "Matrix: disparar HSM (WhatsApp)"
    icone = "bi-whatsapp"
    categoria = "atendimento"
    grupo = "Integrações"
    subgrupo = "Matrix"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'cod_conta', 'label': 'Conta WhatsApp (cod_conta)', 'tipo': 'numero',
             'obrigatorio': True, 'ajuda': 'ID da conta WhatsApp na Matrix do tenant.'},
            {'nome': 'hsm', 'label': 'Template HSM (id)', 'tipo': 'numero', 'obrigatorio': True,
             'ajuda': 'ID do template aprovado, cadastrado na Matrix.'},
            {'nome': 'telefone', 'label': 'Telefone', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{var.telefone}}'},
            {'nome': 'nome', 'label': 'Nome do contato', 'tipo': 'texto', 'placeholder': '{{lead.nome}}'},
            {'nome': 'variaveis', 'label': 'Variáveis do template ({{1}}, {{2}}…)', 'tipo': 'keyvalue',
             'ajuda': 'Chave = número do placeholder; valor aceita {{...}}.'},
            {'nome': 'tipo_envio', 'label': 'Tipo de envio', 'tipo': 'select',
             'opcoes': ['2', '1', '3'], 'ajuda': '2 = notificação · 1 = automático · 3 = fila.'},
            {'nome': 'url_file', 'label': 'URL da mídia (opcional)', 'tipo': 'texto',
             'ajuda': 'Só se o template tiver header de mídia.'},
        ]

    def validar_config(self, config) -> list:
        erros = []
        if not str(config.get('cod_conta', '')).strip():
            erros.append('`cod_conta` é obrigatório.')
        if not str(config.get('hsm', '')).strip():
            erros.append('`hsm` (template) é obrigatório.')
        if not (config.get('telefone') or '').strip():
            erros.append('`telefone` é obrigatório.')
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        svc = matrix_do_tenant(contexto.tenant)
        if svc is None:
            return _erro('tenant sem integração Matrix ativa')

        telefone = str(contexto.resolver(config.get('telefone', '')) or '').strip()
        if not telefone:
            return _erro('telefone vazio')

        try:
            cod_conta = int(str(contexto.resolver(config.get('cod_conta', ''))).strip())
            hsm = int(str(contexto.resolver(config.get('hsm', ''))).strip())
            tipo_envio = int(str(config.get('tipo_envio') or 2))
        except (ValueError, TypeError):
            return _erro('cod_conta/hsm/tipo_envio inválidos')

        contato = {'telefone': telefone}
        nome = str(contexto.resolver(config.get('nome', '')) or '').strip()
        if nome:
            contato['nome'] = nome
        variaveis = contexto.resolver(config.get('variaveis') or {}) or None
        url_file = str(contexto.resolver(config.get('url_file', '')) or '').strip() or None

        try:
            resp = svc.enviar_hsm(
                cod_conta=cod_conta, hsm=hsm, contato=contato,
                tipo_envio=tipo_envio, variaveis=variaveis, url_file=url_file,
            )
        except Exception as exc:
            return _erro(f'falha Matrix: {exc}')

        return NodeResult(
            output={'ok': True, 'cod_atendimento': resp.get('cod_atendimento')},
            branch='sucesso',
        )
