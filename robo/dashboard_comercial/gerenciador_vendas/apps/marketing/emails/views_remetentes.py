"""
Views de gestao de Dominios e Remetentes de email.

Fluxo:
  1. Tenant cria DominioRemetente (ex: meuprovedor.com.br)
  2. Hubtrix chama Resend.create_domain → recebe DNS records
  3. Tela mostra os 3 registros pra cliente copiar
  4. Cliente adiciona no DNS dele
  5. Cliente volta e clica "Verificar" — Hubtrix chama Resend.verify_domain
  6. Quando verificado, cliente cadastra RemetenteEmail (atendimento@, etc.)
  7. Marca um remetente como padrao
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import registrar_acao

from .models import DominioRemetente, RemetenteEmail
from .services import resend_service

logger = logging.getLogger(__name__)


def _check_perm(request, codigo='marketing.editar_emails'):
    if request.user.is_superuser:
        return True
    return user_tem_funcionalidade(request, codigo)


# ─── Dominios ─────────────────────────────────────────────────────────────────

@login_required
def dominios_lista(request):
    if not _check_perm(request, 'marketing.ver_emails'):
        return HttpResponseForbidden()
    dominios = DominioRemetente.objects.all().order_by('-criado_em')
    return render(request, 'emails/dominios/lista.html', {
        'dominios': dominios,
        'pagetitle': 'Dominios de envio',
    })


@login_required
def dominio_criar(request):
    if not _check_perm(request):
        return HttpResponseForbidden()

    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        dominio_str = (request.POST.get('dominio') or '').strip().lower()
        nome_amigavel = (request.POST.get('nome_amigavel') or '').strip()

        if not dominio_str:
            messages.error(request, 'Informe o dominio.')
            return redirect('marketing_emails:dominio_criar')

        # Sanitizacao basica
        dominio_str = dominio_str.replace('http://', '').replace('https://', '').rstrip('/')
        if dominio_str.startswith('www.'):
            dominio_str = dominio_str[4:]

        # Ja existe?
        if DominioRemetente.objects.filter(dominio=dominio_str).exists():
            messages.error(request, f'Dominio {dominio_str} ja foi adicionado.')
            return redirect('marketing_emails:dominios_lista')

        # Cria no Resend
        try:
            r = resend_service.create_domain(dominio_str)
        except Exception as e:
            logger.exception('Erro ao criar dominio no Resend')
            messages.error(request, f'Falha ao criar no provedor: {e}')
            return redirect('marketing_emails:dominio_criar')

        # Persiste
        dom = DominioRemetente.objects.create(
            tenant=tenant,
            dominio=dominio_str,
            nome_amigavel=nome_amigavel,
            resend_domain_id=r.get('id', ''),
            registros_dns=r.get('records', []),
            status='pendente_dns',
        )
        registrar_acao('marketing', 'criar', 'dominio_remetente', dom.id,
            f'Dominio {dominio_str} adicionado', request=request)
        messages.success(request, f'Dominio adicionado. Configure os registros DNS.')
        return redirect('marketing_emails:dominio_detalhe', pk=dom.pk)

    return render(request, 'emails/dominios/criar.html', {
        'pagetitle': 'Adicionar dominio',
    })


@login_required
def dominio_detalhe(request, pk):
    if not _check_perm(request, 'marketing.ver_emails'):
        return HttpResponseForbidden()
    dom = get_object_or_404(DominioRemetente, pk=pk)
    remetentes = dom.remetentes.order_by('local_part')
    return render(request, 'emails/dominios/detalhe.html', {
        'dom': dom,
        'remetentes': remetentes,
        'pagetitle': dom.dominio,
    })


@login_required
@require_POST
def dominio_verificar(request, pk):
    if not _check_perm(request):
        return HttpResponseForbidden()
    dom = get_object_or_404(DominioRemetente, pk=pk)

    if not dom.resend_domain_id:
        messages.error(request, 'Dominio sem ID Resend — recriar.')
        return redirect('marketing_emails:dominio_detalhe', pk=pk)

    try:
        # Dispara verificacao
        resend_service.verify_domain(dom.resend_domain_id)
        # Pega status atualizado
        info = resend_service.get_domain(dom.resend_domain_id)
    except Exception as e:
        logger.exception('Erro ao verificar dominio')
        dom.status = 'falhou'
        dom.falha_motivo = str(e)[:500]
        dom.ultima_verificacao = timezone.now()
        dom.save()
        messages.error(request, f'Falha ao verificar: {e}')
        return redirect('marketing_emails:dominio_detalhe', pk=pk)

    novo_status_resend = (info.get('status') or '').lower()
    dom.ultima_verificacao = timezone.now()
    if novo_status_resend == 'verified':
        dom.status = 'verificado'
        dom.validado_em = timezone.now()
        dom.falha_motivo = ''
        messages.success(request, 'Dominio verificado.')
    elif novo_status_resend in ('pending', 'not_started'):
        dom.status = 'validando'
        messages.info(request, 'DNS ainda propagando. Tenta de novo em alguns minutos.')
    else:
        dom.status = 'falhou'
        dom.falha_motivo = f'Resend retornou: {novo_status_resend}'
        messages.warning(request, f'Verificacao falhou: {novo_status_resend}')

    # Atualiza records caso tenham mudado
    if info.get('records'):
        dom.registros_dns = info['records']

    dom.save()
    registrar_acao('marketing', 'verificar', 'dominio_remetente', dom.id,
        f'Dominio {dom.dominio} verificado: {dom.status}', request=request)
    return redirect('marketing_emails:dominio_detalhe', pk=pk)


@login_required
@require_POST
def dominio_excluir(request, pk):
    if not _check_perm(request):
        return HttpResponseForbidden()
    dom = get_object_or_404(DominioRemetente, pk=pk)
    nome = dom.dominio

    # Apaga no Resend tambem
    if dom.resend_domain_id:
        try:
            resend_service.delete_domain(dom.resend_domain_id)
        except Exception as e:
            logger.warning('Falha ao apagar dominio no Resend: %s', e)

    dom.delete()
    registrar_acao('marketing', 'excluir', 'dominio_remetente', pk,
        f'Dominio {nome} excluido', request=request)
    messages.success(request, f'Dominio {nome} removido.')
    return redirect('marketing_emails:dominios_lista')


@login_required
@require_POST
def dominio_toggle_flag(request, pk):
    """Atualiza flags de bounce/complaint/auto-remover."""
    if not _check_perm(request):
        return HttpResponseForbidden()
    dom = get_object_or_404(DominioRemetente, pk=pk)
    dom.capturar_bounces = request.POST.get('capturar_bounces') == 'on'
    dom.capturar_complaints = request.POST.get('capturar_complaints') == 'on'
    dom.auto_remover_lista = request.POST.get('auto_remover_lista') == 'on'
    dom.save()
    messages.success(request, 'Configuracoes atualizadas.')
    return redirect('marketing_emails:dominio_detalhe', pk=pk)


# ─── Remetentes ───────────────────────────────────────────────────────────────

@login_required
def remetente_criar(request, dominio_pk):
    if not _check_perm(request):
        return HttpResponseForbidden()
    dom = get_object_or_404(DominioRemetente, pk=dominio_pk)

    if not dom.esta_verificado:
        messages.error(request, 'Dominio precisa estar verificado pra adicionar remetentes.')
        return redirect('marketing_emails:dominio_detalhe', pk=dom.pk)

    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        local = (request.POST.get('local_part') or '').strip().lower()
        nome = (request.POST.get('nome_exibicao') or '').strip()
        reply_to = (request.POST.get('reply_to') or '').strip()
        padrao = request.POST.get('padrao') == 'on'

        if not local or not nome:
            messages.error(request, 'Local part e nome de exibicao sao obrigatorios.')
            return redirect('marketing_emails:remetente_criar', dominio_pk=dom.pk)

        # Validacao basica do local part
        import re
        if not re.match(r'^[a-z0-9._-]+$', local):
            messages.error(request, 'Local part deve conter apenas a-z, 0-9, ponto, hifen, underscore.')
            return redirect('marketing_emails:remetente_criar', dominio_pk=dom.pk)

        if RemetenteEmail.objects.filter(dominio=dom, local_part=local).exists():
            messages.error(request, f'{local}@{dom.dominio} ja existe.')
            return redirect('marketing_emails:dominio_detalhe', pk=dom.pk)

        rem = RemetenteEmail.objects.create(
            tenant=tenant, dominio=dom,
            local_part=local, nome_exibicao=nome,
            reply_to=reply_to, padrao=padrao, ativo=True,
        )
        registrar_acao('marketing', 'criar', 'remetente_email', rem.id,
            f'Remetente {rem.email_completo} criado', request=request)
        messages.success(request, f'Remetente {rem.email_completo} adicionado.')
        return redirect('marketing_emails:dominio_detalhe', pk=dom.pk)

    return render(request, 'emails/dominios/remetente_criar.html', {
        'dom': dom,
        'pagetitle': f'Novo remetente em {dom.dominio}',
    })


@login_required
@require_POST
def remetente_excluir(request, pk):
    if not _check_perm(request):
        return HttpResponseForbidden()
    rem = get_object_or_404(RemetenteEmail, pk=pk)
    dom_pk = rem.dominio.pk
    rem.delete()
    registrar_acao('marketing', 'excluir', 'remetente_email', pk,
        f'Remetente excluido', request=request)
    messages.success(request, 'Remetente removido.')
    return redirect('marketing_emails:dominio_detalhe', pk=dom_pk)


@login_required
@require_POST
def remetente_set_padrao(request, pk):
    if not _check_perm(request):
        return HttpResponseForbidden()
    rem = get_object_or_404(RemetenteEmail, pk=pk)
    rem.padrao = True
    rem.save()  # save() automaticamente desmarca os outros
    messages.success(request, f'{rem.email_completo} agora e o remetente padrao.')
    return redirect('marketing_emails:dominio_detalhe', pk=rem.dominio.pk)
