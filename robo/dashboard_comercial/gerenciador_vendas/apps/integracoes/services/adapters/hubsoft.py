"""
Adapter HubSoft → ClienteConsolidado.

Lê do ClienteHubsoft existente e popula a tabela normalizada.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from .base import upsert_consolidado

logger = logging.getLogger(__name__)

NOME_ORIGEM = 'hubsoft'


def sync_cliente(cliente_hubsoft):
    """Normaliza um ClienteHubsoft em ClienteConsolidado."""
    from apps.inbox.models import Conversa

    # === Pessoa ===
    telefone = (
        cliente_hubsoft.telefone_primario
        or cliente_hubsoft.telefone_secundario
        or cliente_hubsoft.telefone_terciario
        or ''
    )
    email = cliente_hubsoft.email_principal or cliente_hubsoft.email_secundario or ''

    # === Cliente ===
    data_virou = cliente_hubsoft.data_cadastro_hubsoft
    meses = None
    if data_virou:
        meses = round((timezone.now() - data_virou).days / 30, 1)

    # === Inadimplência (parse de alerta_mensagens) ===
    inadimplente = False
    dias_atraso = None
    alerta_msgs = cliente_hubsoft.alerta_mensagens or []
    if cliente_hubsoft.alerta and isinstance(alerta_msgs, list):
        msg_str = ' '.join(str(m) for m in alerta_msgs).lower()
        if any(p in msg_str for p in ('atraso', 'cobranca', 'cobrança', 'pendencia', 'pendência', 'inadimpl', 'vencido')):
            inadimplente = True
            # Tenta extrair dias de atraso de strings tipo "atraso de 23 dias"
            import re
            m = re.search(r'(\d+)\s*dias?', msg_str)
            if m:
                try:
                    dias_atraso = int(m.group(1))
                except ValueError:
                    pass

    # === Contratos / serviços ===
    valor_mensal = None
    contratos_qtd = 0
    planos_resumo = []
    try:
        servicos = cliente_hubsoft.servicos.filter(status='ativo')
        contratos_qtd = servicos.count()
        if contratos_qtd:
            total = Decimal('0')
            for s in servicos:
                if s.valor:
                    total += Decimal(str(s.valor))
                planos_resumo.append({
                    'nome': s.nome or '',
                    'valor': float(s.valor) if s.valor else 0,
                    'velocidade': f'{s.velocidade_download or 0}/{s.velocidade_upload or 0}',
                    'status': s.status,
                })
            valor_mensal = total
    except Exception as exc:
        logger.debug('Não foi possível ler serviços do cliente %s: %s', cliente_hubsoft.id, exc)

    # === Suporte ===
    tickets_abertos = 0
    tickets_30d = 0
    try:
        from apps.suporte.models import Ticket
        if cliente_hubsoft.lead:
            agora = timezone.now()
            janela_30d = agora - timedelta(days=30)
            tickets_abertos = Ticket.objects.filter(
                lead=cliente_hubsoft.lead,
            ).exclude(status__in=['fechado', 'resolvido']).count()
            tickets_30d = Ticket.objects.filter(
                lead=cliente_hubsoft.lead,
                criado_em__gte=janela_30d,
            ).count()
    except Exception as exc:
        logger.debug('Não foi possível ler tickets do cliente %s: %s', cliente_hubsoft.id, exc)

    # === Engajamento (última conversa) ===
    ultima_conversa = None
    try:
        if telefone:
            sufixo = telefone[-9:]  # últimos 9 dígitos pra match flexível
            ultima = (
                Conversa.objects
                .filter(tenant=cliente_hubsoft.tenant, contato_telefone__icontains=sufixo)
                .order_by('-criado_em')
                .first()
            )
            if ultima:
                ultima_conversa = ultima.criado_em
    except Exception as exc:
        logger.debug('Não foi possível ler conversas do cliente %s: %s', cliente_hubsoft.id, exc)

    dados = {
        'origem': NOME_ORIGEM,
        'id_origem': cliente_hubsoft.id_cliente,
        'cpf_cnpj': cliente_hubsoft.cpf_cnpj or '',
        'nome': cliente_hubsoft.nome_razaosocial or cliente_hubsoft.nome_fantasia or '',
        'email': email,
        'telefone': telefone,
        'lead': cliente_hubsoft.lead,
        'data_virou_cliente': data_virou,
        'meses_como_cliente': meses,
        'cliente_ativo': cliente_hubsoft.ativo,
        'cliente_suspenso': False,  # HubSoft não diferencia suspensão; pode evoluir
        'contratos_ativos_qtd': contratos_qtd,
        'valor_mensal_total': valor_mensal,
        'planos_resumo': planos_resumo,
        'inadimplente': inadimplente,
        'dias_em_atraso': dias_atraso,
        'historico_atrasos_qtd': 0,  # HubSoft não expõe contagem direta; precisa endpoint próprio
        'forma_cobranca': '',  # idem
        'tickets_abertos_qtd': tickets_abertos,
        'tickets_30d_qtd': tickets_30d,
        'tecnologia': '',  # HubSoft pode ter, requer mapeamento por servico.tecnologia
        'cto_id_origem': '',
        'uso_banda_pct_queda_60d': None,
        'ultima_conversa_em': ultima_conversa,
        'nps_ultimo': None,
        'sync_origem_em': timezone.now(),
        'dados_brutos': {
            'alerta_mensagens': cliente_hubsoft.alerta_mensagens or [],
        },
    }

    return upsert_consolidado(tenant=cliente_hubsoft.tenant, dados=dados)


def iter_clientes_ativos(tenant):
    """Iterador sobre ClienteHubsoft ativos do tenant."""
    from apps.integracoes.models import ClienteHubsoft
    return ClienteHubsoft.objects.filter(tenant=tenant, ativo=True).select_related('lead')
