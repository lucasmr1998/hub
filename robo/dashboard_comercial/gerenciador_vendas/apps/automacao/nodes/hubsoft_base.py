"""Base compartilhada dos nós HubSoft.

Resolve o `HubsoftService` por tenant (via `hubsoft_do_tenant`), trata "sem
integração" + exceção como saída `erro`, e embrulha o retorno. O nó concreto só
implementa `_chamar(svc, config, contexto)` chamando o método do service — a
lógica de domínio mora em `apps.integracoes.services.hubsoft` (sem 2ª cópia).
"""
from .base import BaseNode, NodeResult
from ..services.hubsoft import hubsoft_do_tenant


class HubsoftNode(BaseNode):
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "HubSoft"
    saidas = ["sucesso", "erro"]
    saida_chave = "dados"   # chave do output

    def _chamar(self, svc, config, contexto):
        raise NotImplementedError

    def executar(self, config, entrada, contexto) -> NodeResult:
        svc = hubsoft_do_tenant(contexto.tenant)
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
