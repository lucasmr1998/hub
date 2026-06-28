"""Executor de domínio único pra abrir Ticket de suporte a partir da engine.

Nó e tool chamam ESTE service — nunca o ORM direto. Centraliza o que a engine não
tem de graça: o `solicitante` (Ticket exige um User, mas quem reporta é um contato,
não um usuário) e a categoria por nome (get-or-create tenant-scoped). Tenant sempre
explícito (sem thread-local — a engine roda fora de request).
"""
from django.utils.text import slugify


def _solicitante_padrao(tenant):
    """Um User do tenant pra figurar como solicitante do ticket automático.
    Prefere staff; cai pra qualquer usuário do tenant."""
    perfis = tenant.usuarios.select_related('user')
    perfil = perfis.filter(user__is_staff=True).first() or perfis.first()
    return perfil.user if perfil else None


def _categoria(tenant, nome):
    """Resolve/cria a CategoriaTicket por nome (slug tenant-scoped)."""
    from apps.suporte.models import CategoriaTicket
    nome = (nome or '').strip()
    if not nome:
        return None
    slug = (slugify(nome) or 'geral')[:50]
    cat = CategoriaTicket.all_tenants.filter(tenant=tenant, slug=slug).first()
    if cat is None:
        cat = CategoriaTicket.objects.create(
            tenant=tenant, slug=slug, nome=nome[:100], ativo=True)
    return cat


def criar_ticket(tenant, titulo, descricao, *, categoria=None, prioridade='normal',
                 solicitante=None, tenant_cliente=None):
    """Cria e salva um Ticket. `numero` é gerado pelo próprio `Ticket.save()`.

    Levanta ValueError se o tenant não tiver nenhum usuário (sem solicitante possível).
    """
    from apps.suporte.models import Ticket

    if solicitante is None:
        solicitante = _solicitante_padrao(tenant)
    if solicitante is None:
        raise ValueError('tenant sem usuário pra ser solicitante do ticket')

    prio = prioridade if prioridade in dict(Ticket.PRIORIDADE_CHOICES) else 'normal'
    ticket = Ticket(
        tenant=tenant,
        titulo=(str(titulo).strip() or 'Sem título')[:255],
        descricao=str(descricao or '').strip(),
        prioridade=prio,
        solicitante=solicitante,
        tenant_cliente=tenant_cliente,
    )
    cat = _categoria(tenant, categoria)
    if cat is not None:
        ticket.categoria = cat
    ticket.save()
    return ticket
