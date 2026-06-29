"""
Nó Agente IA — uma rodada de conversa de um agente gerenciado.

Referencia um `Agente` (área /automacao/agentes/) por id e roda UM turno: monta o
system prompt do agente + o histórico acumulado + a mensagem do contato, chama o
LLM (`services/ia.chamar_llm`) e devolve a resposta em `output.resposta` (pro nó
seguinte enviar no WhatsApp).

Memória (janela da conversa): o histórico vive em `var._hist_agente_<id>`, acumulado
via `promote`. Como o `Contexto.serializar()` persiste `variaveis`, na retoma da
execução pausada (loop conversacional montado no fluxo com o nó de pergunta/aguardar)
o histórico volta junto — sem tabela nova. Tools (D3) e RAG (D4) ainda não entram.
"""
from .base import BaseNode, NodeResult, registrar
from ..services.ia import chamar_llm, integracao_ia_do_tenant


_MAX_TURNOS = 10  # turnos (par user+assistant) mantidos na janela da conversa


def _erro(msg):
    return NodeResult(status='erro', branch='erro', erro=msg, output={'ok': False})


@registrar
class IaAgenteNode(BaseNode):
    tipo = "ia_agente"
    label = "Agente IA"
    icone = "bi-robot"
    categoria = "atendimento"
    grupo = "IA"
    subgrupo = "Agente"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'agente_id', 'label': 'Agente', 'tipo': 'texto', 'fonte': 'agentes',
             'detalhe': 'agente', 'obrigatorio': True,
             'ajuda': 'Agente gerenciado (criar em /automacao/agentes/).'},
            {'nome': 'mensagem', 'label': 'Mensagem do contato', 'tipo': 'textarea',
             'placeholder': '{{var.conteudo}}',
             'ajuda': 'Vazio = usa {{var.resposta}} (retoma) ou {{var.conteudo}} (entrada).'},
        ]

    def validar_config(self, config) -> list:
        return [] if str(config.get('agente_id') or '').strip() else ['`agente_id` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        from apps.automacao.models import Agente

        agente_id = str(contexto.resolver(config.get('agente_id', '')) or '').strip()
        if not agente_id.isdigit():
            return _erro('agente_id inválido')
        agente = (Agente.all_tenants
                  .filter(tenant=contexto.tenant, pk=int(agente_id), ativo=True)
                  .select_related('integracao_ia').first())
        if agente is None:
            return _erro('agente não encontrado ou inativo')

        integracao = agente.integracao_ia or integracao_ia_do_tenant(contexto.tenant)
        if integracao is None:
            return _erro('sem integração de IA ativa no tenant')

        # Mensagem do contato: config explícita; senão var.resposta (retoma) / var.conteudo (entrada).
        if config.get('mensagem'):
            mensagem = str(contexto.resolver(config['mensagem']) or '').strip()
        else:
            v = contexto.variaveis or {}
            mensagem = str(v.get('resposta') or v.get('conteudo') or '').strip()
        if not mensagem:
            return _erro('mensagem do contato vazia')

        # Memória = as últimas trocas da conversa em que o agente roda (tipo configurável
        # no agente; registry em services/memoria.py). Compartilhada de graça: todos os
        # agentes leem a mesma conversa. Sem conversa/memória → janela vazia (stateless).
        from ..services.memoria import carregar_memoria
        historico = carregar_memoria(getattr(agente, 'memoria', '') or 'conversa', contexto, k=_MAX_TURNOS)

        messages = []
        prompt = str(contexto.resolver(agente.system_prompt or '') or '').strip()
        if prompt:
            messages.append({'role': 'system', 'content': prompt})
        messages.extend(historico)
        # mensagem atual como último turno do user (sem duplicar se já veio no histórico)
        if not (historico and historico[-1].get('role') == 'user'
                and historico[-1].get('content') == mensagem):
            messages.append({'role': 'user', 'content': mensagem})

        # Com tools habilitadas no agente → loop de tool-calling; senão chamada simples.
        chaves_tools = list(getattr(agente, 'tools', None) or [])
        if chaves_tools:
            from ..services.ia import chamar_llm_com_tools
            from ..services.ia_tools import schema_openai, despachar
            schema = schema_openai(chaves_tools)
            if schema:
                resposta = chamar_llm_com_tools(
                    integracao, messages, schema,
                    lambda nome, args: despachar(nome, args, contexto, agente),
                    modelo=agente.modelo or None,
                )
            else:
                resposta = chamar_llm(integracao, messages, modelo=agente.modelo or None)
        else:
            resposta = chamar_llm(integracao, messages, modelo=agente.modelo or None)
        if resposta is None:
            return _erro('falha ao chamar o LLM (cheque credencial/modelo)')

        # Sem write-back de histórico: a memória É a conversa. Em prod, a resposta vira
        # mensagem da conversa (canal); no chat de teste, o painel acumula os turnos.
        return NodeResult(
            output={'resposta': resposta, 'agente': agente.nome},
            branch='sucesso',
        )
