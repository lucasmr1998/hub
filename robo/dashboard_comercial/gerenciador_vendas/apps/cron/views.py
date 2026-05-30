"""Views do painel admin de Cron Jobs (rodam em /aurora-admin/cron/).
Acesso: superuser apenas (cron e infra cross-tenant)."""
from datetime import timedelta

from django.contrib import messages as dj_messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import CronJob, ExecucaoCron
from .services import cron_humanizar, validar_expressao


def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(login_required(view_func))


@superuser_required
def lista_view(request):
    jobs = list(CronJob.objects.all().order_by('-ativo', 'nome'))

    # banner: o dispatcher tem que ter rodado nos ultimos ~3min
    ultima_exec = ExecucaoCron.objects.order_by('-inicio').first()
    dispatcher_saudavel = False
    if ultima_exec:
        delta = (timezone.now() - ultima_exec.inicio).total_seconds()
        dispatcher_saudavel = delta < 180  # 3min

    # KPIs gerais
    agora = timezone.now()
    last_24h = agora - timedelta(hours=24)
    execucoes_24h = ExecucaoCron.objects.filter(inicio__gte=last_24h)
    kpis = {
        'jobs_ativos': sum(1 for j in jobs if j.ativo),
        'jobs_total': len(jobs),
        'execucoes_24h': execucoes_24h.count(),
        'erros_24h': execucoes_24h.filter(status__in=['erro', 'timeout']).count(),
    }

    # enriquece cada job com `schedule_humano` e tempo desde ultima execucao
    for j in jobs:
        j.schedule_humano = cron_humanizar(j.schedule)
        if j.last_run_at:
            secs = (agora - j.last_run_at).total_seconds()
            if secs < 60:
                j.last_run_human = f'ha {int(secs)}s'
            elif secs < 3600:
                j.last_run_human = f'ha {int(secs // 60)}min'
            elif secs < 86400:
                j.last_run_human = f'ha {int(secs // 3600)}h'
            else:
                j.last_run_human = f'ha {int(secs // 86400)}d'
        else:
            j.last_run_human = 'nunca'

    return render(request, 'cron/lista.html', {
        'jobs': jobs,
        'dispatcher_saudavel': dispatcher_saudavel,
        'ultima_exec_dispatcher': ultima_exec,
        'kpis': kpis,
        'page_title': 'Cron Jobs',
    })


@superuser_required
def detalhe_view(request, pk):
    job = get_object_or_404(CronJob, pk=pk)
    job.schedule_humano = cron_humanizar(job.schedule)

    execucoes = list(job.execucoes.order_by('-inicio')[:50])

    # stats das ultimas 50
    total = len(execucoes)
    sucessos = sum(1 for e in execucoes if e.status == 'success')
    erros = sum(1 for e in execucoes if e.status in ('erro', 'timeout'))
    dur_media = None
    durs = [e.duracao_segundos for e in execucoes if e.duracao_segundos]
    if durs:
        dur_media = round(sum(durs) / len(durs), 2)

    return render(request, 'cron/detalhe.html', {
        'job': job,
        'execucoes': execucoes,
        'stats': {'total': total, 'sucessos': sucessos, 'erros': erros, 'dur_media': dur_media},
        'page_title': f'Cron · {job.nome}',
    })


@superuser_required
@require_POST
def toggle_view(request, pk):
    job = get_object_or_404(CronJob, pk=pk)
    job.ativo = not job.ativo
    job.save(update_fields=['ativo', 'atualizado_em'])
    dj_messages.success(
        request,
        f'{job.nome} {"ATIVADO" if job.ativo else "DESATIVADO"}.'
    )
    next_url = request.POST.get('next') or 'cron:lista'
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(next_url)


@superuser_required
@require_POST
def run_now_view(request, pk):
    """Executa o job sincronamente, ja registrando como manual:<user>.
    Bloqueia a view ate terminar (ate `timeout_segundos` do job)."""
    job = get_object_or_404(CronJob, pk=pk)

    from .management.commands.dispatcher_cron import Command as DispatcherCmd
    dispatcher = DispatcherCmd()
    # Stub do stdout pra nao printar nada na response
    class _DevNull:
        def write(self, *a, **kw): pass
        def flush(self, *a, **kw): pass
    dispatcher.stdout = _DevNull()
    dispatcher.stderr = _DevNull()

    exec_row = dispatcher._dispatch(job, disparado_por=f'manual:{request.user.username}')
    if exec_row.status == 'success':
        dj_messages.success(request, f'{job.nome}: OK em {exec_row.duracao_segundos:.2f}s.')
    elif exec_row.status == 'timeout':
        dj_messages.warning(request, f'{job.nome}: TIMEOUT apos {job.timeout_segundos}s.')
    else:
        dj_messages.error(request, f'{job.nome}: ERRO (rc={exec_row.return_code}). Veja stderr.')
    return redirect('cron:detalhe', pk=job.pk)


@superuser_required
@require_POST
def editar_view(request, pk):
    """Edita schedule, args, timeout, descricao do job."""
    job = get_object_or_404(CronJob, pk=pk)
    schedule = (request.POST.get('schedule') or '').strip()
    args = (request.POST.get('args') or '').strip()
    descricao = (request.POST.get('descricao') or '').strip()
    try:
        timeout = int(request.POST.get('timeout_segundos') or job.timeout_segundos)
    except ValueError:
        timeout = job.timeout_segundos

    if schedule:
        ok, msg = validar_expressao(schedule)
        if not ok:
            dj_messages.error(request, f'Schedule invalido: {msg}')
            return redirect('cron:detalhe', pk=job.pk)
        job.schedule = schedule
    job.args = args
    job.descricao = descricao
    job.timeout_segundos = max(10, timeout)
    job.save(update_fields=['schedule', 'args', 'descricao', 'timeout_segundos', 'atualizado_em'])
    dj_messages.success(request, 'Config salva.')
    return redirect('cron:detalhe', pk=job.pk)
