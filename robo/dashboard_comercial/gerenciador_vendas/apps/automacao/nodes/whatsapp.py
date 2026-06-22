"""
Nós de WhatsApp (Uazapi).

Reusam `UazapiService` (via `services.whatsapp.uazapi_do_tenant`) e as credenciais
por tenant. Cada nó resolve a integração do tenant; se não houver, vira erro
controlado (não estoura). Saídas: sucesso/erro.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.whatsapp import uazapi_do_tenant, chave_telefone


def _erro(msg):
    return NodeResult(status='erro', branch='erro', erro=msg, output={'ok': False})


class _WhatsappBase(BaseNode):
    categoria = "atendimento"   # gating por tenant (futuro): só quem tem Uazapi
    grupo = "WhatsApp"
    icone = "bi-whatsapp"
    saidas = ["sucesso", "erro"]

    def _telefone(self, config, contexto):
        return str(contexto.resolver(config.get('telefone', '')) or '').strip()


@registrar
class WhatsappTextoNode(_WhatsappBase):
    tipo = "whatsapp_texto"
    label = "WhatsApp: enviar mensagem"
    subgrupo = "Enviar"

    def campos_config(self) -> list:
        return [
            {'nome': 'telefone', 'label': 'Telefone', 'tipo': 'texto', 'obrigatorio': True, 'placeholder': '{{var.telefone}}'},
            {'nome': 'mensagem', 'label': 'Mensagem', 'tipo': 'textarea', 'placeholder': 'Oi {{lead.nome}}!'},
        ]

    def validar_config(self, config) -> list:
        return [] if config.get('telefone') else ['`telefone` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        uaz = uazapi_do_tenant(contexto.tenant)
        if uaz is None:
            return _erro('tenant sem integração Uazapi ativa')
        telefone = self._telefone(config, contexto)
        if not telefone:
            return _erro('telefone vazio')
        mensagem = str(contexto.resolver(config.get('mensagem', '')) or '')
        try:
            uaz.enviar_texto(telefone, mensagem)
        except Exception as exc:
            return _erro(f'falha Uazapi: {exc}')
        return NodeResult(output={'ok': True, 'telefone': telefone}, branch='sucesso')


@registrar
class WhatsappMidiaNode(_WhatsappBase):
    tipo = "whatsapp_midia"
    label = "WhatsApp: enviar mídia"
    subgrupo = "Enviar"
    icone = "bi-image"

    def campos_config(self) -> list:
        return [
            {'nome': 'telefone', 'label': 'Telefone', 'tipo': 'texto', 'obrigatorio': True, 'placeholder': '{{var.telefone}}'},
            {'nome': 'url', 'label': 'URL da mídia', 'tipo': 'texto', 'obrigatorio': True},
            {'nome': 'tipo', 'label': 'Tipo', 'tipo': 'select',
             'opcoes': ['image', 'document', 'audio', 'video']},
            {'nome': 'legenda', 'label': 'Legenda', 'tipo': 'texto'},
        ]

    def validar_config(self, config) -> list:
        erros = []
        if not config.get('telefone'):
            erros.append('`telefone` é obrigatório.')
        if not config.get('url'):
            erros.append('`url` é obrigatória.')
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        uaz = uazapi_do_tenant(contexto.tenant)
        if uaz is None:
            return _erro('tenant sem integração Uazapi ativa')
        telefone = self._telefone(config, contexto)
        url = str(contexto.resolver(config.get('url', '')) or '').strip()
        if not telefone or not url:
            return _erro('telefone/url vazios')
        try:
            uaz.enviar_midia(
                telefone, url,
                tipo=config.get('tipo', 'image'),
                legenda=str(contexto.resolver(config.get('legenda', '')) or ''),
            )
        except Exception as exc:
            return _erro(f'falha Uazapi: {exc}')
        return NodeResult(output={'ok': True, 'telefone': telefone}, branch='sucesso')


@registrar
class WhatsappPresencaNode(_WhatsappBase):
    tipo = "whatsapp_presenca"
    label = "WhatsApp: digitando/presença"
    subgrupo = "Presença"
    icone = "bi-three-dots"

    def campos_config(self) -> list:
        return [
            {'nome': 'telefone', 'label': 'Telefone', 'tipo': 'texto', 'obrigatorio': True, 'placeholder': '{{var.telefone}}'},
            {'nome': 'tipo', 'label': 'Presença', 'tipo': 'select',
             'opcoes': ['composing', 'recording', 'available', 'unavailable']},
        ]

    def executar(self, config, entrada, contexto) -> NodeResult:
        uaz = uazapi_do_tenant(contexto.tenant)
        if uaz is None:
            return _erro('tenant sem integração Uazapi ativa')
        telefone = self._telefone(config, contexto)
        if not telefone:
            return _erro('telefone vazio')
        try:
            uaz.enviar_presenca(telefone, config.get('tipo', 'composing'))
        except Exception as exc:
            return _erro(f'falha Uazapi: {exc}')
        return NodeResult(output={'ok': True}, branch='sucesso')


@registrar
class WhatsappPerguntaNode(_WhatsappBase):
    tipo = "whatsapp_pergunta"
    label = "WhatsApp: enviar e aguardar resposta"
    subgrupo = "Conversa"
    icone = "bi-chat-dots"
    saidas = ["resposta", "timeout"]

    def campos_config(self) -> list:
        return [
            {'nome': 'telefone', 'label': 'Telefone', 'tipo': 'texto', 'obrigatorio': True, 'placeholder': '{{var.telefone}}'},
            {'nome': 'mensagem', 'label': 'Pergunta', 'tipo': 'textarea'},
            {'nome': 'timeout_min', 'label': 'Timeout (min, 0 = sem limite)', 'tipo': 'numero'},
        ]

    def validar_config(self, config) -> list:
        return [] if config.get('telefone') else ['`telefone` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        uaz = uazapi_do_tenant(contexto.tenant)
        if uaz is None:
            return _erro('tenant sem integração Uazapi ativa')
        telefone = self._telefone(config, contexto)
        if not telefone:
            return _erro('telefone vazio')
        mensagem = str(contexto.resolver(config.get('mensagem', '')) or '')
        try:
            uaz.enviar_texto(telefone, mensagem)
        except Exception as exc:
            return _erro(f'falha Uazapi: {exc}')
        try:
            timeout_min = int(config.get('timeout_min', 0) or 0)
        except (ValueError, TypeError):
            timeout_min = 0
        # Pausa esperando a resposta daquele contato (saídas: resposta / timeout).
        return NodeResult(
            output={'pergunta': mensagem},
            status='aguardando',
            espera={'tipo': 'resposta', 'chave': chave_telefone(telefone), 'segundos': timeout_min * 60},
        )
