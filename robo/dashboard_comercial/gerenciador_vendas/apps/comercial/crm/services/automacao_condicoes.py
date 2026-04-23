"""
Registry de tipos de condicao pra o motor de Automacoes do Pipeline.

Cada tipo é uma classe que se registra via decorator `@registrar`. O engine
itera pelo registry pra construir contexto e pra avaliar condicoes. Adicionar
um tipo novo = criar uma classe + decorator. Zero mudanca no engine.

Estrutura de cada classe:
- `slug`: identificador do tipo (usado no JSON das regras)
- `label`: nome amigavel pra UI
- `coletar_contexto(oportunidade, contexto)`: popula o dict de contexto
  com os dados que a avaliacao vai precisar (minimiza queries)
- `avaliar(operador, valor, campo, contexto)`: retorna bool

Operadores sao strings: igual, diferente, existe, nao_existe, todas_iguais,
nenhuma_com. Os comparadores estao no final deste modulo.
"""
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# REGISTRY
# ============================================================================

REGISTRY = {}


def registrar(cls):
    """Decorator que registra uma classe de condicao pelo seu `slug`."""
    instance = cls()
    REGISTRY[cls.slug] = instance
    return cls


def todos_tipos():
    """Retorna lista de (slug, label) pra UI — mesma assinatura da constante antiga."""
    return [(slug, inst.label) for slug, inst in REGISTRY.items()]


def tipo_por_slug(slug):
    return REGISTRY.get(slug)


# ============================================================================
# COMPARADORES COMPARTILHADOS
# ============================================================================

def comparar_conjunto(conjunto, operador, valor):
    if operador == 'igual':
        return valor in conjunto
    if operador == 'diferente':
        return valor not in conjunto
    if operador == 'existe':
        return len(conjunto) > 0
    if operador == 'nao_existe':
        return len(conjunto) == 0
    return False


def comparar_valor(valor_atual, operador, valor_esperado):
    if operador == 'igual':
        return str(valor_atual).strip() == str(valor_esperado).strip()
    if operador == 'diferente':
        return str(valor_atual).strip() != str(valor_esperado).strip()
    if operador == 'existe':
        return bool(valor_atual)
    if operador == 'nao_existe':
        return not bool(valor_atual)
    return False


def comparar_bool(valor_campo, operador, valor_esperado):
    campo_bool = bool(valor_campo)
    esperado_bool = bool(valor_esperado)
    if operador in ('igual', 'existe'):
        return campo_bool == esperado_bool
    if operador in ('diferente', 'nao_existe'):
        return campo_bool != esperado_bool
    return False


# ============================================================================
# TIPOS DE CONDICAO
# ============================================================================

@registrar
class CondicaoTag:
    slug = 'tag'
    label = 'Tag'

    def coletar_contexto(self, oportunidade, contexto):
        contexto['tags'] = set(oportunidade.tags.values_list('nome', flat=True))

    def avaliar(self, operador, valor, campo, contexto):
        return comparar_conjunto(contexto['tags'], operador, valor)


@registrar
class CondicaoHistoricoStatus:
    slug = 'historico_status'
    label = 'Status do histórico de contato'

    def coletar_contexto(self, oportunidade, contexto):
        from apps.comercial.leads.models import HistoricoContato
        lead_id = oportunidade.lead_id
        if not lead_id:
            contexto.setdefault('historico_statuses', set())
            return
        contexto['historico_statuses'] = set(
            HistoricoContato.all_tenants
            .filter(tenant=oportunidade.tenant, lead_id=lead_id)
            .values_list('status', flat=True)
        )

    def avaliar(self, operador, valor, campo, contexto):
        return comparar_conjunto(contexto.get('historico_statuses', set()), operador, valor)


@registrar
class CondicaoLeadStatusApi:
    slug = 'lead_status_api'
    label = 'Status API do lead'

    def coletar_contexto(self, oportunidade, contexto):
        lead = oportunidade.lead
        contexto['_lead'] = lead

    def avaliar(self, operador, valor, campo, contexto):
        lead = contexto.get('_lead')
        status_atual = getattr(lead, 'status_api', '') if lead else ''
        return comparar_valor(status_atual or '', operador, valor)


@registrar
class CondicaoLeadCampo:
    slug = 'lead_campo'
    label = 'Campo do lead'

    def coletar_contexto(self, oportunidade, contexto):
        contexto['_lead'] = oportunidade.lead

    def avaliar(self, operador, valor, campo, contexto):
        lead = contexto.get('_lead')
        valor_campo = getattr(lead, campo, None) if lead else None
        if isinstance(valor_campo, bool) or isinstance(valor, bool):
            return comparar_bool(valor_campo, operador, valor)
        return comparar_valor(valor_campo, operador, valor)


@registrar
class CondicaoServicoStatus:
    slug = 'servico_status'
    label = 'Status do serviço HubSoft'

    def coletar_contexto(self, oportunidade, contexto):
        lead_id = oportunidade.lead_id
        if not lead_id:
            contexto.setdefault('servico_statuses', set())
            return
        try:
            from apps.integracoes.models import ServicoClienteHubsoft
        except Exception:
            contexto.setdefault('servico_statuses', set())
            return
        try:
            contexto['servico_statuses'] = set(
                ServicoClienteHubsoft.all_tenants
                .filter(tenant=oportunidade.tenant, cliente__lead_id=lead_id)
                .values_list('status_prefixo', flat=True)
            )
        except Exception:
            contexto.setdefault('servico_statuses', set())

    def avaliar(self, operador, valor, campo, contexto):
        return comparar_conjunto(contexto.get('servico_statuses', set()), operador, valor)


@registrar
class CondicaoConverteuVenda:
    slug = 'converteu_venda'
    label = 'Converteu em venda'

    def coletar_contexto(self, oportunidade, contexto):
        from apps.comercial.leads.models import HistoricoContato
        lead_id = oportunidade.lead_id
        if not lead_id:
            contexto['tem_conversao_venda'] = False
            return
        contexto['tem_conversao_venda'] = HistoricoContato.all_tenants.filter(
            tenant=oportunidade.tenant, lead_id=lead_id, converteu_venda=True,
        ).exists()

    def avaliar(self, operador, valor, campo, contexto):
        tem = contexto.get('tem_conversao_venda', False)
        if operador in ('igual', 'existe'):
            return tem == bool(valor)
        if operador in ('diferente', 'nao_existe'):
            return tem != bool(valor)
        return False


@registrar
class CondicaoImagemStatus:
    slug = 'imagem_status'
    label = 'Status de imagem/documento'

    def coletar_contexto(self, oportunidade, contexto):
        from apps.comercial.leads.models import ImagemLeadProspecto
        lead_id = oportunidade.lead_id
        if not lead_id:
            contexto['imagens_statuses'] = []
            return
        contexto['imagens_statuses'] = list(
            ImagemLeadProspecto.all_tenants
            .filter(tenant=oportunidade.tenant, lead_id=lead_id)
            .values_list('status_validacao', flat=True)
        )

    def avaliar(self, operador, valor, campo, contexto):
        imagens = contexto.get('imagens_statuses', [])
        if operador == 'igual':
            return valor in imagens
        if operador == 'diferente':
            return valor not in imagens
        if operador == 'todas_iguais':
            return len(imagens) > 0 and all(s == valor for s in imagens)
        if operador == 'nenhuma_com':
            return valor not in imagens
        if operador == 'existe':
            return len(imagens) > 0
        if operador == 'nao_existe':
            return len(imagens) == 0
        return False
