"""Base compartilhada dos nós HubSoft.

Resolve o `HubsoftService` por tenant (via `hubsoft_do_tenant`), trata "sem
integração" + exceção como saída `erro`, e embrulha o retorno. O nó concreto só
implementa `_chamar(svc, config, contexto)` chamando o método do service — a
lógica de domínio mora em `apps.integracoes.services.hubsoft` (sem 2ª cópia).

Seletor de credencial (padrão do uazapi): todo nó HubSoft ganha o campo "Conta
(HubSoft)" automático (via `campos_config` → `_campos_extra` + a conta). O nó
concreto declara só os campos dele em `_campos_extra`; a conta é anexada aqui.
"""
from .base import BaseNode, NodeResult
from ..services.hubsoft import hubsoft_do_tenant


def campo_conta_hubsoft():
    """Campo "conta/credencial" (o seletor de credential do n8n): escolhe qual
    IntegracaoAPI HubSoft usar. Vazio = a primeira ativa do tenant. Compartilhado
    pelos nós que não herdam `HubsoftNode` (Família 2, com `executar` próprio)."""
    return {'nome': 'integracao_id', 'label': 'Conta (HubSoft)', 'tipo': 'texto',
            'fonte': 'integracoes_hubsoft',
            'ajuda': 'Qual conta/integração HubSoft usar. Vazio = a primeira ativa do tenant.'}


def integ_id_de(config, contexto):
    """Resolve o `integracao_id` do config (aceita {{...}}); vazio → None."""
    return str(contexto.resolver(config.get('integracao_id', '')) or '').strip() or None


class HubsoftNode(BaseNode):
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "HubSoft"
    saidas = ["sucesso", "erro"]
    saida_chave = "dados"   # chave do output

    def _campos_extra(self) -> list:
        """Campos específicos do nó (sem a conta — ela é anexada por `campos_config`)."""
        return []

    def campos_config(self) -> list:
        return self._campos_extra() + [campo_conta_hubsoft()]

    def _chamar(self, svc, config, contexto):
        raise NotImplementedError

    def executar(self, config, entrada, contexto) -> NodeResult:
        svc = hubsoft_do_tenant(contexto.tenant, integ_id_de(config, contexto))
        if svc is None:
            return NodeResult(status='erro', branch='erro',
                              erro='tenant sem integração HubSoft ativa', output={'ok': False})
        try:
            dados = self._chamar(svc, config, contexto)
        except Exception as exc:  # noqa: BLE001 — falha do service vira saída erro
            return NodeResult(status='erro', branch='erro', erro=str(exc), output={'ok': False})
        out = {self.saida_chave: dados}
        if isinstance(dados, list):
            out['total'] = len(dados)
        return NodeResult(output=out, branch='sucesso')


def _txt(contexto, config, nome, default=''):
    """Resolve {{...}} de um campo texto e tira espaços."""
    return str(contexto.resolver(config.get(nome, default)) or '').strip()


def _int(v, default):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError, AttributeError):
        return default


def _faltando(config, obrigatorios):
    """Lista de erros pra campos obrigatórios vazios."""
    return [f"`{c}` é obrigatório." for c in obrigatorios if not str(config.get(c, '')).strip()]
