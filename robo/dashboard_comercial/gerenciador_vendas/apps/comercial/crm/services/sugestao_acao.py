"""
AI-suggested next action pra Oportunidade.

Service que monta contexto do lead/oportunidade e pede pra LLM sugerir a
próxima ação concreta (ligar, mandar WhatsApp, follow-up por email, etc).

Estrutura retornada (em proxima_acao_sugerida):
{
    "tipo": "ligar|whatsapp|email|criar_proposta|followup",
    "titulo": "Ligar pra Maria — proposta enviada há 3 dias",
    "mensagem_sugerida": "Texto pronto pra copiar e colar (português BR)",
    "justificativa": "Por que essa ação agora",
    "urgencia": "alta|media|baixa",
    "gerada_em": "2026-05-05T03:14:00Z",
    "estado": "pendente"
}
"""
import json
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def montar_contexto(oportunidade):
    """Monta dict de contexto pra alimentar o prompt da LLM."""
    lead = oportunidade.lead
    agora = timezone.now()

    dias_no_estagio = (agora - oportunidade.data_entrada_estagio).days if oportunidade.data_entrada_estagio else None
    dias_desde_criacao = (agora - oportunidade.data_criacao).days if oportunidade.data_criacao else None

    contexto = {
        'oportunidade_id': oportunidade.id,
        'titulo': oportunidade.titulo or '',
        'estagio_atual': oportunidade.estagio.nome if oportunidade.estagio_id else '',
        'status': oportunidade.status,
        'valor_estimado': float(oportunidade.valor_estimado) if oportunidade.valor_estimado else None,
        'prioridade': oportunidade.prioridade,
        'dias_no_estagio': dias_no_estagio,
        'dias_desde_criacao': dias_desde_criacao,
        'lead': {
            'nome': lead.nome_razaosocial if lead else '',
            'telefone': lead.telefone if lead else '',
            'cidade': lead.cidade if lead else '',
            'origem': lead.origem if lead else '',
        } if lead else None,
        'responsavel': oportunidade.responsavel.get_full_name() if oportunidade.responsavel_id else None,
    }

    # Última atividade conhecida (notas, tarefas)
    try:
        from apps.comercial.crm.models import HistoricoCRM
        ultimo_evento = (
            HistoricoCRM.objects
            .filter(oportunidade=oportunidade)
            .order_by('-data')
            .first()
        )
        if ultimo_evento:
            dias_inativa = (agora - ultimo_evento.data).days
            contexto['ultima_atividade'] = {
                'tipo': ultimo_evento.tipo,
                'descricao': (ultimo_evento.descricao or '')[:200],
                'dias_atras': dias_inativa,
            }
    except Exception:
        pass

    return contexto


def gerar_sugestao(oportunidade):
    """
    Chama LLM e retorna dict da sugestão estruturada (mesma estrutura
    armazenada em oportunidade.proxima_acao_sugerida).
    Retorna None em caso de falha.
    """
    from apps.integracoes.models import IntegracaoAPI
    import requests as http_requests

    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=oportunidade.tenant,
        tipo__in=['openai', 'anthropic', 'groq'],
        ativa=True,
    ).first()

    if not integracao:
        logger.warning('Sem integração de IA pra tenant %s', oportunidade.tenant_id)
        return None

    api_key = (
        integracao.api_key
        or integracao.configuracoes_extras.get('api_key', '')
        or integracao.access_token
        or ''
    )
    modelo = integracao.configuracoes_extras.get('modelo', 'gpt-4o-mini')
    url = (
        'https://api.openai.com/v1/chat/completions' if integracao.tipo == 'openai'
        else 'https://api.groq.com/openai/v1/chat/completions' if integracao.tipo == 'groq'
        else integracao.base_url
    )

    contexto = montar_contexto(oportunidade)

    system = (
        "Você é um copiloto de vendas pra provedor de internet (ISP) brasileiro. "
        "Sua tarefa: analisar o contexto de uma oportunidade no pipeline e "
        "sugerir UMA ação concreta pro vendedor executar agora. "
        "Responda APENAS um JSON válido, sem texto fora do JSON. "
        "Estrutura: "
        '{"tipo": "ligar|whatsapp|email|criar_proposta|followup", '
        '"titulo": "frase de ação concreta, max 60 chars", '
        '"mensagem_sugerida": "texto curto pronto pra usar (PT-BR)", '
        '"justificativa": "por que agora, max 120 chars", '
        '"urgencia": "alta|media|baixa"}'
    )

    user_prompt = (
        f"Contexto da oportunidade (JSON):\n{json.dumps(contexto, ensure_ascii=False, default=str)}\n\n"
        f"Sugira a próxima ação concreta. Considere: "
        f"oportunidades em mesmo estágio há > 5 dias precisam de followup; "
        f"valor alto merece atenção; lead sem atividade > 3 dias está esfriando."
    )

    try:
        resp = http_requests.post(
            url,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': modelo,
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.3,
                'max_tokens': 350,
                'response_format': {'type': 'json_object'},
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning('LLM retornou %s: %s', resp.status_code, resp.text[:200])
            return None

        content = resp.json()['choices'][0]['message']['content']
        sugestao = json.loads(content)

        # Validar estrutura mínima
        if not all(k in sugestao for k in ('tipo', 'titulo', 'urgencia')):
            return None

        # Adicionar metadata
        sugestao['gerada_em'] = timezone.now().isoformat()
        sugestao['estado'] = 'pendente'
        return sugestao

    except Exception as exc:
        logger.error('Erro ao gerar sugestão pra oportunidade %s: %s', oportunidade.id, exc)
        return None


def deve_regenerar(oportunidade):
    """
    Decide se vale chamar a LLM agora pra esta oportunidade.
    Pula se já tem sugestão pendente recente OU se rejeitada nos últimos 3 dias.
    """
    sug = oportunidade.proxima_acao_sugerida or {}
    if not sug:
        return True

    estado = sug.get('estado')
    gerada_em_str = sug.get('gerada_em')

    if not gerada_em_str:
        return True

    try:
        from datetime import datetime
        gerada_em = datetime.fromisoformat(gerada_em_str.replace('Z', '+00:00'))
    except Exception:
        return True

    agora = timezone.now()
    if agora.tzinfo and gerada_em.tzinfo is None:
        from django.utils.timezone import make_aware
        gerada_em = make_aware(gerada_em)

    dias = (agora - gerada_em).days

    if estado == 'aplicada':
        return dias >= 3  # após aplicar, regenera 3 dias depois
    if estado == 'rejeitada':
        return dias >= 3
    # pendente: regenera só se passou 24h
    return dias >= 1
