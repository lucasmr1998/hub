from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum, Avg, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.http import HttpResponse
from django.core.paginator import Paginator
from apps.cs.clube.models import PremioRoleta, ParticipanteRoleta, RouletteAsset, RoletaConfig, MembroClube, NivelClube, RegraPontuacao, ExtratoPontuacao, Cidade, BannerClube, LandingConfig
from apps.cs.indicacoes.models import Indicacao
from apps.cs.parceiros.models import Parceiro, CupomDesconto, ResgateCupom, CategoriaParceiro
import csv
import json
from datetime import datetime, timedelta
from apps.cs.clube.services.hubsoft_service import HubsoftService

def admin_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('dashboard_home')
    else:
        form = AuthenticationForm()
    return render(request, 'clube/dashboard/login.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_home(request):
    PREMIO_SEM_SORTE = 'Não foi dessa vez'

    # ── KPI Cards ────────────────────────────────────────────────────────────
    membros_iniciados = MembroClube.objects.count()
    membros_validados = MembroClube.objects.filter(validado=True).count()
    membros_jogadores = MembroClube.objects.filter(giros__isnull=False).distinct().count()
    total_giros       = ParticipanteRoleta.objects.count()

    # ── Variação percentual (últimos 7 dias vs 7 dias anteriores) ──────────
    hoje = datetime.now().date()
    inicio_atual   = hoje - timedelta(days=6)
    inicio_anterior = hoje - timedelta(days=13)

    def calcular_variacao(qs_atual, qs_anterior):
        atual = qs_atual
        anterior = qs_anterior
        if anterior == 0:
            return (100, 'up') if atual > 0 else (0, 'neutral')
        variacao = round(((atual - anterior) / anterior) * 100)
        if variacao > 0:
            return (variacao, 'up')
        elif variacao < 0:
            return (abs(variacao), 'down')
        return (0, 'neutral')

    # Iniciados
    iniciados_atual = MembroClube.objects.filter(data_cadastro__date__gte=inicio_atual).count()
    iniciados_anterior = MembroClube.objects.filter(data_cadastro__date__gte=inicio_anterior, data_cadastro__date__lt=inicio_atual).count()
    var_iniciados = calcular_variacao(iniciados_atual, iniciados_anterior)

    # Validados
    validados_atual = ExtratoPontuacao.objects.filter(regra__gatilho='telefone_verificado', data_recebimento__date__gte=inicio_atual).count()
    validados_anterior = ExtratoPontuacao.objects.filter(regra__gatilho='telefone_verificado', data_recebimento__date__gte=inicio_anterior, data_recebimento__date__lt=inicio_atual).count()
    var_validados = calcular_variacao(validados_atual, validados_anterior)

    # Jogadores
    jogadores_atual = ParticipanteRoleta.objects.filter(data_criacao__date__gte=inicio_atual).values('cpf').distinct().count()
    jogadores_anterior = ParticipanteRoleta.objects.filter(data_criacao__date__gte=inicio_anterior, data_criacao__date__lt=inicio_atual).values('cpf').distinct().count()
    var_jogadores = calcular_variacao(jogadores_atual, jogadores_anterior)

    # Giros
    giros_atual = ParticipanteRoleta.objects.filter(data_criacao__date__gte=inicio_atual).count()
    giros_anterior = ParticipanteRoleta.objects.filter(data_criacao__date__gte=inicio_anterior, data_criacao__date__lt=inicio_atual).count()
    var_giros = calcular_variacao(giros_atual, giros_anterior)

    # ── Últimos ganhadores (excluindo 'Não foi dessa vez') ───────────────────
    ultimos_ganhadores = (
        ParticipanteRoleta.objects
        .exclude(premio__iexact=PREMIO_SEM_SORTE)
        .order_by('-data_criacao')[:10]
    )

    # ── Gráfico Doughnut — Prêmios distribuídos ──────────────────────────────
    premios_distribuicao = (
        ParticipanteRoleta.objects
        .exclude(premio__iexact=PREMIO_SEM_SORTE)
        .filter(status='ganhou')
        .values('premio')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    labels_premios = [p['premio'] for p in premios_distribuicao]
    data_premios   = [p['total']  for p in premios_distribuicao]

    # ── Gráfico de Linha — 3 séries nos últimos 7 dias ───────────────────────
    dias_semana = [(hoje - timedelta(days=i)) for i in range(6, -1, -1)]
    data_inicio = dias_semana[0]

    # Série 1 – Cadastros
    cadastros_db = (
        MembroClube.objects
        .filter(data_cadastro__date__gte=data_inicio)
        .annotate(dia=TruncDate('data_cadastro'))
        .values('dia').annotate(total=Count('id')).order_by('dia')
    )
    cadastros_dict = {str(r['dia']): r['total'] for r in cadastros_db}

    # Série 2 – Validações (gatilho telefone_verificado)
    validacoes_db = (
        ExtratoPontuacao.objects
        .filter(regra__gatilho='telefone_verificado', data_recebimento__date__gte=data_inicio)
        .annotate(dia=TruncDate('data_recebimento'))
        .values('dia').annotate(total=Count('id')).order_by('dia')
    )
    validacoes_dict = {str(r['dia']): r['total'] for r in validacoes_db}

    # Série 3 – Giros
    giros_db = (
        ParticipanteRoleta.objects
        .filter(data_criacao__date__gte=data_inicio)
        .annotate(dia=TruncDate('data_criacao'))
        .values('dia').annotate(total=Count('id')).order_by('dia')
    )
    giros_dict = {str(r['dia']): r['total'] for r in giros_db}

    labels_giros     = [d.strftime('%d/%m') for d in dias_semana]
    data_cadastros   = [cadastros_dict.get(str(d), 0)  for d in dias_semana]
    data_validacoes  = [validacoes_dict.get(str(d), 0) for d in dias_semana]
    data_giros_chart = [giros_dict.get(str(d), 0)      for d in dias_semana]

    context = {
        'funil_iniciados':       membros_iniciados,
        'funil_validados':       membros_validados,
        'funil_jogadores':       membros_jogadores,
        'total_giros':           total_giros,
        'var_iniciados_valor':   var_iniciados[0],
        'var_iniciados_dir':     var_iniciados[1],
        'var_validados_valor':   var_validados[0],
        'var_validados_dir':     var_validados[1],
        'var_jogadores_valor':   var_jogadores[0],
        'var_jogadores_dir':     var_jogadores[1],
        'var_giros_valor':       var_giros[0],
        'var_giros_dir':         var_giros[1],
        'ganhadores':            ultimos_ganhadores,
        'chart_labels_premios':  json.dumps(labels_premios),
        'chart_data_premios':    json.dumps(data_premios),
        'chart_labels_giros':    json.dumps(labels_giros),
        'chart_data_cadastros':  json.dumps(data_cadastros),
        'chart_data_validacoes': json.dumps(data_validacoes),
        'chart_data_giros':      json.dumps(data_giros_chart),
    }
    return render(request, 'clube/dashboard/home.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_premios(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'novo_premio':
            nome = request.POST.get('nome')
            cidades_ids = request.POST.getlist('cidades')
            quantidade = request.POST.get('quantidade', 0)
            probabilidade = request.POST.get('probabilidade', 1)
            posicoes = request.POST.get('posicoes', '1')
            
            premio = PremioRoleta.objects.create(
                nome=nome,
                quantidade=int(quantidade),
                probabilidade=int(probabilidade),
                posicoes=posicoes
            )
            
            if cidades_ids:
                premio.cidades_permitidas.set(cidades_ids)
                
            messages.success(request, f"Prêmio {nome} adicionado com sucesso!")
            
        elif action == 'excluir_premio':
            premio_id = request.POST.get('premio_id')
            if premio_id:
                get_object_or_404(PremioRoleta, id=premio_id).delete()
                messages.success(request, f"Prêmio removido com sucesso!")
                
        else:
            # Update
            premio_id = request.POST.get('premio_id')
            nova_qtd = request.POST.get('quantidade')
            novas_pos = request.POST.get('posicoes')
            nova_prob = request.POST.get('probabilidade', 1)
            nova_msg = request.POST.get('mensagem_vitoria', '')
            cidades_ids = request.POST.getlist('cidades')

            if premio_id:
                premio = get_object_or_404(PremioRoleta, id=premio_id)
                premio.quantidade = int(nova_qtd)
                premio.probabilidade = int(nova_prob)
                if novas_pos:
                    premio.posicoes = novas_pos
                premio.mensagem_vitoria = nova_msg
                premio.save()

                premio.cidades_permitidas.set(cidades_ids)

                messages.success(request, f"Prêmio {premio.nome} atualizado!")
                
        return redirect('dashboard_premios')
        
    premios = PremioRoleta.objects.prefetch_related('cidades_permitidas').order_by('nome')
    cidades = Cidade.objects.filter(ativo=True).order_by('nome')

    # Calcular soma de pesos e chance percentual para o modal
    soma_pesos = sum(p.probabilidade for p in premios) or 1
    premios_com_chance = []
    for p in premios:
        premios_com_chance.append({
            'nome': p.nome,
            'quantidade': p.quantidade,
            'probabilidade': p.probabilidade,
            'chance': round((p.probabilidade / soma_pesos) * 100, 1),
        })

    return render(request, 'clube/dashboard/premios.html', {
        'premios': premios,
        'cidades': cidades,
        'soma_pesos': soma_pesos,
        'premios_com_chance': premios_com_chance,
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_participantes(request):
    """
    Shows unique members of the Clube MegaLink
    """
    if request.method == 'POST':
        membro_id = request.POST.get('membro_id')
        novo_saldo_input = request.POST.get('saldo')
        if membro_id and novo_saldo_input is not None:
            membro = get_object_or_404(MembroClube, id=membro_id)
            novo_saldo = int(novo_saldo_input)
            saldo_anterior = membro.saldo
            
            if novo_saldo != saldo_anterior:
                membro.saldo = novo_saldo
                membro.save()
                
                # Criar um extrato para registrar a mudança manual
                diferenca = novo_saldo - saldo_anterior
                regra_ajuste, _ = RegraPontuacao.objects.get_or_create(
                    gatilho='ajuste_manual_admin',
                    defaults={
                        'nome_exibicao': 'Ajuste Manual pelo Admin',
                        'pontos_saldo': 0,
                        'pontos_xp': 0,
                        'limite_por_membro': 0,
                        'ativo': True
                    }
                )
                
                ExtratoPontuacao.objects.create(
                    membro=membro,
                    regra=regra_ajuste,
                    pontos_saldo_ganhos=diferenca,
                    pontos_xp_ganhos=0,
                    descricao_extra=f"Ajuste manual de {saldo_anterior} para {novo_saldo}"
                )
                
            messages.success(request, f"Saldo de {membro.nome} atualizado.")
        return redirect('dashboard_participantes')

    q = request.GET.get('q', '')
    cidade = request.GET.get('cidade', '')
    
    membros = MembroClube.objects.annotate(total_giros=Count('giros')).order_by('-data_cadastro')

    if q:
        membros = membros.filter(Q(nome__icontains=q) | Q(cpf__icontains=q))
    if cidade:
        membros = membros.filter(cidade=cidade)

    paginator = Paginator(membros, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    todas_cidades = Cidade.objects.filter(ativo=True).values_list('nome', flat=True).order_by('nome')

    context = {
        'participantes': page_obj,
        'page_obj': page_obj,
        'q': q,
        'cidade': cidade,
        'todas_cidades': sorted(list(todas_cidades))
    }
    return render(request, 'clube/dashboard/participantes.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_extrato_membro(request, membro_id):
    """
    Shows the points history (ExtratoPontuacao) for a specific member
    """
    membro = get_object_or_404(MembroClube, id=membro_id)
    extrato = ExtratoPontuacao.objects.filter(membro=membro).select_related('regra').order_by('-data_recebimento')
    
    return render(request, 'clube/dashboard/extrato_membro.html', {'membro': membro, 'extrato': extrato})

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_giros(request):
    """
    Shows historical log of all roulette spins
    """
    q = request.GET.get('q', '')
    giros = ParticipanteRoleta.objects.select_related('membro').order_by('-data_criacao')

    if q:
        giros = giros.filter(Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(premio__icontains=q))

    paginator = Paginator(giros, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'clube/dashboard/giros.html', {'giros': page_obj, 'page_obj': page_obj, 'q': q})

@login_required
@user_passes_test(lambda u: u.is_staff)
def exportar_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="participantes_roleta.csv"'
    response.write(u'\ufeff'.encode('utf8')) # BOM for Excel

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Nome', 'CPF', 'Email', 'Telefone', 'Cidade', 'Bairro', 'Prêmio', 'Data'])

    for p in ParticipanteRoleta.objects.all():
        writer.writerow([p.nome, p.cpf, p.email, p.telefone, p.cidade, p.bairro, p.premio, p.data_criacao.strftime('%d/%m/%Y %H:%M')])

    return response

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_assets(request):
    if request.method == 'POST':
        asset_id = request.POST.get('asset_id')
        if asset_id:
            asset = get_object_or_404(RouletteAsset, id=asset_id)
            if 'delete' in request.POST:
                asset.delete()
            else:
                asset.ativo = not asset.ativo
                asset.save()
        else:
            tipo = request.POST.get('tipo')
            ordem = request.POST.get('ordem', 0)
            imagem = request.FILES.get('imagem')
            if imagem:
                # Update existing or create new
                RouletteAsset.objects.create(tipo=tipo, ordem=ordem, imagem=imagem)
        return redirect('dashboard_assets')

    frames = RouletteAsset.objects.filter(tipo='frame').order_by('ordem')
    outros = RouletteAsset.objects.exclude(tipo='frame')
    context = {
        'frames': frames,
        'outros': outros
    }
    return render(request, 'clube/dashboard/assets.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_config(request):
    config, _ = RoletaConfig.objects.get_or_create(id=1)
    if request.method == 'POST':
        config.custo_giro = int(request.POST.get('custo_giro', 10))
        config.nome_clube = request.POST.get('nome_clube', 'Clube MegaLink')
        config.xp_por_giro = int(request.POST.get('xp_por_giro', 5))
        config.limite_giros_por_membro = int(request.POST.get('limite_giros_por_membro', 0))
        config.periodo_limite = request.POST.get('periodo_limite', 'total')
        config.save()
        messages.success(request, "Configurações do Clube MegaLink atualizadas!")
        return redirect('dashboard_config')
    
    return render(request, 'clube/dashboard/config.html', {'config': config})

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_gamificacao(request):
    """
    Manage Levels and Point Rules
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Gerenciar Nível
        if action == 'salvar_nivel':
            nivel_id = request.POST.get('nivel_id')
            nome = request.POST.get('nome')
            xp_necessario = int(request.POST.get('xp_necessario', 0))
            ordem = int(request.POST.get('ordem', 1))
            
            if nivel_id:
                nivel = get_object_or_404(NivelClube, id=nivel_id)
                nivel.nome = nome
                nivel.xp_necessario = xp_necessario
                nivel.ordem = ordem
                nivel.save()
                messages.success(request, f"Nível {nome} atualizado!")
            else:
                NivelClube.objects.create(nome=nome, xp_necessario=xp_necessario, ordem=ordem)
                messages.success(request, f"Nível {nome} criado!")
                
        elif action == 'excluir_nivel':
            nivel_id = request.POST.get('nivel_id')
            get_object_or_404(NivelClube, id=nivel_id).delete()
            messages.success(request, "Nível removido!")
            
        # Gerenciar Regras
        elif action == 'salvar_regra':
            regra_id = request.POST.get('regra_id')
            gatilho = request.POST.get('gatilho')
            nome_exibicao = request.POST.get('nome_exibicao')
            pontos_saldo = int(request.POST.get('pontos_saldo', 0))
            pontos_xp = int(request.POST.get('pontos_xp', 0))
            limite = int(request.POST.get('limite_por_membro', 1))
            ativo = request.POST.get('ativo') == 'on'
            
            if regra_id:
                regra = get_object_or_404(RegraPontuacao, id=regra_id)
                regra.gatilho = gatilho
                regra.nome_exibicao = nome_exibicao
                regra.pontos_saldo = pontos_saldo
                regra.pontos_xp = pontos_xp
                regra.limite_por_membro = limite
                regra.ativo = ativo
                regra.save()
                messages.success(request, f"Regra {nome_exibicao} atualizada!")
            else:
                RegraPontuacao.objects.create(
                    gatilho=gatilho, nome_exibicao=nome_exibicao, pontos_saldo=pontos_saldo, 
                    pontos_xp=pontos_xp, limite_por_membro=limite, ativo=ativo
                )
                messages.success(request, f"Regra {nome_exibicao} criada!")
                
        elif action == 'excluir_regra':
            regra_id = request.POST.get('regra_id')
            get_object_or_404(RegraPontuacao, id=regra_id).delete()
            messages.success(request, "Regra removida!")

        return redirect('dashboard_gamificacao')
        
    niveis = NivelClube.objects.all().order_by('xp_necessario')
    regras = RegraPontuacao.objects.all().order_by('-ativo', 'nome_exibicao')
    
    context = {
        'niveis': niveis,
        'regras': regras
    }
    return render(request, 'clube/dashboard/gamificacao.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_cidades(request):
    """
    Gestão de Cidades permitidas para os prêmios.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'nova_cidade':
            nome = request.POST.get('nome')
            ativo = request.POST.get('ativo') == 'on'
            if nome:
                Cidade.objects.get_or_create(nome=nome, defaults={'ativo': ativo})
                messages.success(request, f"Cidade {nome} processada com sucesso!")
                
        elif action == 'excluir_cidade':
            cidade_id = request.POST.get('cidade_id')
            if cidade_id:
                get_object_or_404(Cidade, id=cidade_id).delete()
                messages.success(request, "Cidade removida com sucesso!")
                
        elif action == 'atualizar_cidade':
            cidade_id = request.POST.get('cidade_id')
            nome = request.POST.get('nome')
            ativo = request.POST.get('ativo') == 'on'
            if cidade_id and nome:
                cidade = get_object_or_404(Cidade, id=cidade_id)
                cidade.nome = nome
                cidade.ativo = ativo
                cidade.save()
                messages.success(request, f"Cidade {nome} atualizada!")
                
        return redirect('dashboard_cidades')
        
    cidades = Cidade.objects.all().order_by('nome')
    return render(request, 'clube/dashboard/cidades.html', {'cidades': cidades})


@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_relatorios(request):
    """
    Relatórios analíticos da roleta.
    """
    PREMIO_SEM_SORTE = 'Não foi dessa vez'
    hoje = datetime.now().date()

    # ── Filtro de período ──────────────────────────────────────────────────
    periodo = request.GET.get('periodo', '30')
    if periodo == '7':
        data_inicio = hoje - timedelta(days=7)
    elif periodo == '15':
        data_inicio = hoje - timedelta(days=15)
    elif periodo == '90':
        data_inicio = hoje - timedelta(days=90)
    elif periodo == 'total':
        data_inicio = None
    else:
        data_inicio = hoje - timedelta(days=30)

    # Base querysets com filtro de data
    membros_qs = MembroClube.objects.all()
    giros_qs = ParticipanteRoleta.objects.all()
    if data_inicio:
        membros_qs = membros_qs.filter(data_cadastro__date__gte=data_inicio)
        giros_qs = giros_qs.filter(data_criacao__date__gte=data_inicio)

    # ── 1. Visão por Cidade ────────────────────────────────────────────────
    # Consultar total de clientes Hubsoft por cidade (cache na request)
    hubsoft_clientes_cidade = HubsoftService.consultar_clientes_por_cidade()

    cidades_stats_raw = (
        membros_qs
        .exclude(cidade__isnull=True).exclude(cidade='')
        .values('cidade')
        .annotate(
            total_membros=Count('id'),
            membros_validados=Count('id', filter=Q(validado=True)),
            total_giros=Count('giros'),
            total_xp=Sum('xp_total'),
        )
        .order_by('-total_membros')
    )

    # Enriquecer com dados Hubsoft
    cidades_stats = []
    for c in cidades_stats_raw:
        clientes_hubsoft = hubsoft_clientes_cidade.get(c['cidade'], 0)
        taxa_penetracao = round((c['total_membros'] / clientes_hubsoft * 100), 1) if clientes_hubsoft > 0 else 0
        cidades_stats.append({
            **c,
            'clientes_hubsoft': clientes_hubsoft,
            'taxa_penetracao': taxa_penetracao,
        })

    cidades_labels = [c['cidade'] for c in cidades_stats]
    cidades_membros = [c['total_membros'] for c in cidades_stats]
    cidades_giros = [c['total_giros'] for c in cidades_stats]

    # ── 2. Prêmios Distribuídos (ranking) ──────────────────────────────────
    premios_stats = (
        giros_qs
        .exclude(premio__iexact=PREMIO_SEM_SORTE)
        .values('premio')
        .annotate(total=Count('id'))
        .order_by('-total')[:15]
    )
    premios_labels = [p['premio'] for p in premios_stats]
    premios_data = [p['total'] for p in premios_stats]

    # ── 3. Funil de Conversão ──────────────────────────────────────────────
    funil_leads = membros_qs.count()
    funil_validados = membros_qs.filter(validado=True).count()
    funil_jogadores = membros_qs.filter(giros__isnull=False).distinct().count()
    funil_ganhadores = (
        giros_qs
        .exclude(premio__iexact=PREMIO_SEM_SORTE)
        .values('cpf').distinct().count()
    )

    taxa_validacao = round((funil_validados / funil_leads * 100), 1) if funil_leads > 0 else 0
    taxa_jogo = round((funil_jogadores / funil_validados * 100), 1) if funil_validados > 0 else 0
    taxa_premio = round((funil_ganhadores / funil_jogadores * 100), 1) if funil_jogadores > 0 else 0

    # ── 4. Evolução temporal (respeita o filtro de período) ─────────────
    # Períodos curtos (<=30 dias): agrupamento diário
    # Períodos longos (>30 dias ou total): agrupamento semanal
    usar_diario = periodo in ('7', '15', '30')

    if data_inicio:
        evo_inicio = data_inicio
    else:
        evo_inicio = hoje - timedelta(days=90)  # fallback para "total"

    if usar_diario:
        trunc_fn_cad = TruncDate('data_cadastro')
        trunc_fn_gir = TruncDate('data_criacao')
        campo = 'dia'
    else:
        trunc_fn_cad = TruncWeek('data_cadastro')
        trunc_fn_gir = TruncWeek('data_criacao')
        campo = 'semana'

    evolucao_cadastros = (
        MembroClube.objects.filter(data_cadastro__date__gte=evo_inicio)
        .annotate(**{campo: trunc_fn_cad})
        .values(campo)
        .annotate(total=Count('id'))
        .order_by(campo)
    )
    evolucao_giros_chart = (
        ParticipanteRoleta.objects.filter(data_criacao__date__gte=evo_inicio)
        .annotate(**{campo: trunc_fn_gir})
        .values(campo)
        .annotate(total=Count('id'))
        .order_by(campo)
    )

    evolucao_cad_dict = {}
    for r in evolucao_cadastros:
        d = r[campo]
        if hasattr(d, 'strftime'):
            evolucao_cad_dict[d.strftime('%d/%m')] = r['total']

    evolucao_gir_dict = {}
    for r in evolucao_giros_chart:
        d = r[campo]
        if hasattr(d, 'strftime'):
            evolucao_gir_dict[d.strftime('%d/%m')] = r['total']

    evo_labels = []
    evo_cad_data = []
    evo_gir_data = []

    if usar_diario:
        num_dias = int(periodo)
        for i in range(num_dias):
            d = evo_inicio + timedelta(days=i)
            label = d.strftime('%d/%m')
            evo_labels.append(label)
            evo_cad_data.append(evolucao_cad_dict.get(label, 0))
            evo_gir_data.append(evolucao_gir_dict.get(label, 0))
        evo_titulo = f'Evolução Diária ({periodo} dias)'
    else:
        num_semanas = 12 if periodo == 'total' else (int(periodo) // 7)
        for i in range(num_semanas):
            d = evo_inicio + timedelta(weeks=i)
            d = d - timedelta(days=d.weekday())
            label = d.strftime('%d/%m')
            evo_labels.append(label)
            evo_cad_data.append(evolucao_cad_dict.get(label, 0))
            evo_gir_data.append(evolucao_gir_dict.get(label, 0))
        evo_titulo = f'Evolução Semanal'

    # ── 5. Top 10 Jogadores ────────────────────────────────────────────────
    top_jogadores = (
        MembroClube.objects
        .annotate(total_giros=Count('giros'))
        .filter(total_giros__gt=0)
        .order_by('-total_giros')[:10]
    )

    # ── 6. Prêmios por Cidade (tabela cruzada) ────────────────────────────
    premios_por_cidade = (
        giros_qs
        .exclude(premio__iexact=PREMIO_SEM_SORTE)
        .exclude(cidade__isnull=True).exclude(cidade='')
        .values('cidade', 'premio')
        .annotate(total=Count('id'))
        .order_by('cidade', '-total')
    )

    # Agrupar por cidade
    cidade_premios_map = {}
    for item in premios_por_cidade:
        cidade = item['cidade']
        if cidade not in cidade_premios_map:
            cidade_premios_map[cidade] = []
        cidade_premios_map[cidade].append({
            'premio': item['premio'],
            'total': item['total'],
        })

    # ── 7. Giros por horário (distribuição) ────────────────────────────────
    horas_stats = (
        giros_qs
        .extra(select={'hora': "EXTRACT(hour FROM data_criacao)"})
        .values('hora')
        .annotate(total=Count('id'))
        .order_by('hora')
    )
    horas_dict = {int(h['hora']): h['total'] for h in horas_stats}
    horas_labels = [f"{h}h" for h in range(24)]
    horas_data = [horas_dict.get(h, 0) for h in range(24)]

    # ── Ranking de prêmios (sorteados + estoque) ─────────────────────
    premios_sorteados = (
        giros_qs
        .exclude(premio__iexact=PREMIO_SEM_SORTE)
        .values('premio')
        .annotate(total_sorteados=Count('id'))
        .order_by('-total_sorteados')
    )
    premios_sorteados_dict = {p['premio']: p['total_sorteados'] for p in premios_sorteados}

    premios_ranking = []
    for premio in PremioRoleta.objects.all().order_by('nome'):
        total = premios_sorteados_dict.get(premio.nome, 0)
        premios_ranking.append({
            'nome': premio.nome,
            'total_sorteados': total,
            'estoque': premio.quantidade,
        })
    premios_ranking.sort(key=lambda x: x['total_sorteados'], reverse=True)
    max_sorteados = premios_ranking[0]['total_sorteados'] if premios_ranking else 1

    context = {
        'periodo': periodo,
        'cidades_stats': cidades_stats,
        'chart_cidades_labels': json.dumps(cidades_labels),
        'chart_cidades_membros': json.dumps(cidades_membros),
        'chart_cidades_giros': json.dumps(cidades_giros),
        'chart_premios_labels': json.dumps(premios_labels),
        'chart_premios_data': json.dumps(premios_data),
        'funil_leads': funil_leads,
        'funil_validados': funil_validados,
        'funil_jogadores': funil_jogadores,
        'funil_ganhadores': funil_ganhadores,
        'taxa_validacao': taxa_validacao,
        'taxa_jogo': taxa_jogo,
        'taxa_premio': taxa_premio,
        'evo_titulo': evo_titulo,
        'chart_evo_labels': json.dumps(evo_labels),
        'chart_evo_cad': json.dumps(evo_cad_data),
        'chart_evo_gir': json.dumps(evo_gir_data),
        'top_jogadores': top_jogadores,
        'cidade_premios_map': dict(cidade_premios_map),
        'chart_horas_labels': json.dumps(horas_labels),
        'chart_horas_data': json.dumps(horas_data),
        'premios_ranking': premios_ranking,
        'max_sorteados': max_sorteados,
    }
    return render(request, 'clube/dashboard/relatorios.html', context)


def _get_periodo_filtro(request):
    """Helper para filtro de período reutilizável nos relatórios."""
    hoje = datetime.now().date()
    periodo = request.GET.get('periodo', '30')
    if periodo == '7':
        data_inicio = hoje - timedelta(days=7)
    elif periodo == '15':
        data_inicio = hoje - timedelta(days=15)
    elif periodo == '90':
        data_inicio = hoje - timedelta(days=90)
    elif periodo == 'total':
        data_inicio = None
    else:
        data_inicio = hoje - timedelta(days=30)
    return periodo, data_inicio


@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_relatorios_indicacoes(request):
    """Relatórios de indicações."""
    periodo, data_inicio = _get_periodo_filtro(request)

    hoje = datetime.now().date()
    usar_diario = periodo in ('7', '15', '30')
    evo_inicio = data_inicio if data_inicio else hoje - timedelta(days=90)

    indicacoes_qs = Indicacao.objects.all()
    if data_inicio:
        indicacoes_qs = indicacoes_qs.filter(data_indicacao__date__gte=data_inicio)

    total_indicacoes = indicacoes_qs.count()
    indicacoes_pendentes = indicacoes_qs.filter(status='pendente').count()
    indicacoes_convertidas = indicacoes_qs.filter(status='convertido').count()
    indicacoes_canceladas = indicacoes_qs.filter(status='cancelado').count()
    taxa_conversao_ind = round((indicacoes_convertidas / total_indicacoes * 100), 1) if total_indicacoes > 0 else 0

    # Top 10 embaixadores
    top_embaixadores = (
        MembroClube.objects
        .annotate(
            total_indicacoes=Count('indicacoes_feitas', filter=Q(indicacoes_feitas__data_indicacao__date__gte=data_inicio) if data_inicio else Q()),
            ind_convertidas=Count('indicacoes_feitas', filter=Q(indicacoes_feitas__status='convertido') & (Q(indicacoes_feitas__data_indicacao__date__gte=data_inicio) if data_inicio else Q())),
        )
        .filter(total_indicacoes__gt=0)
        .order_by('-total_indicacoes')[:10]
    )

    # Indicações por cidade
    indicacoes_por_cidade = (
        indicacoes_qs
        .exclude(cidade_indicado='').exclude(cidade_indicado__isnull=True)
        .values('cidade_indicado')
        .annotate(total=Count('id'), convertidas=Count('id', filter=Q(status='convertido')))
        .order_by('-total')[:10]
    )

    # Evolução indicações
    if usar_diario:
        evo_ind = (
            indicacoes_qs
            .annotate(dia=TruncDate('data_indicacao'))
            .values('dia')
            .annotate(total=Count('id'))
            .order_by('dia')
        )
        evo_ind_dict = {}
        for r in evo_ind:
            if r['dia'] and hasattr(r['dia'], 'strftime'):
                evo_ind_dict[r['dia'].strftime('%d/%m')] = r['total']
    else:
        evo_ind = (
            indicacoes_qs
            .annotate(semana=TruncWeek('data_indicacao'))
            .values('semana')
            .annotate(total=Count('id'))
            .order_by('semana')
        )
        evo_ind_dict = {}
        for r in evo_ind:
            if r['semana'] and hasattr(r['semana'], 'strftime'):
                evo_ind_dict[r['semana'].strftime('%d/%m')] = r['total']

    # Evolução labels
    evo_labels = []
    if usar_diario:
        num_dias = int(periodo)
        for i in range(num_dias):
            d = evo_inicio + timedelta(days=i)
            evo_labels.append(d.strftime('%d/%m'))
    else:
        num_semanas = 12 if periodo == 'total' else (int(periodo) // 7)
        for i in range(num_semanas):
            d = evo_inicio + timedelta(weeks=i)
            d = d - timedelta(days=d.weekday())
            evo_labels.append(d.strftime('%d/%m'))

    evo_ind_data = [evo_ind_dict.get(label, 0) for label in evo_labels]

    context = {
        'periodo': periodo,
        'total_indicacoes': total_indicacoes,
        'indicacoes_pendentes': indicacoes_pendentes,
        'indicacoes_convertidas': indicacoes_convertidas,
        'indicacoes_canceladas': indicacoes_canceladas,
        'taxa_conversao_ind': taxa_conversao_ind,
        'top_embaixadores': top_embaixadores,
        'indicacoes_por_cidade': indicacoes_por_cidade,
        'chart_evo_labels': json.dumps(evo_labels),
        'chart_evo_ind': json.dumps(evo_ind_data),
    }
    return render(request, 'clube/dashboard/relatorios_indicacoes.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_relatorios_parceiros(request):
    """Relatórios de parceiros e cupons."""
    periodo, data_inicio = _get_periodo_filtro(request)

    resgates_qs = ResgateCupom.objects.all()
    if data_inicio:
        resgates_qs = resgates_qs.filter(data_resgate__date__gte=data_inicio)

    total_resgates_cupom = resgates_qs.count()
    resgates_utilizados = resgates_qs.filter(status='utilizado').count()
    total_pontos_cupom = resgates_qs.aggregate(t=Sum('pontos_gastos'))['t'] or 0
    total_valor_compras = resgates_qs.filter(valor_compra__isnull=False).aggregate(t=Sum('valor_compra'))['t'] or 0

    # Cupons mais resgatados
    cupons_top = (
        resgates_qs
        .values('cupom__titulo', 'cupom__parceiro__nome')
        .annotate(total=Count('id'), utilizados=Count('id', filter=Q(status='utilizado')))
        .order_by('-total')[:10]
    )

    # Resgates por parceiro
    resgates_por_parceiro = (
        resgates_qs
        .values('cupom__parceiro__nome')
        .annotate(
            total=Count('id'),
            utilizados=Count('id', filter=Q(status='utilizado')),
            pontos=Sum('pontos_gastos'),
            valor=Sum('valor_compra'),
        )
        .order_by('-total')
    )

    parceiros_labels = [r['cupom__parceiro__nome'] for r in resgates_por_parceiro]
    parceiros_resgates_data = [r['total'] for r in resgates_por_parceiro]

    context = {
        'periodo': periodo,
        'total_resgates_cupom': total_resgates_cupom,
        'resgates_utilizados': resgates_utilizados,
        'total_pontos_cupom': total_pontos_cupom,
        'total_valor_compras': total_valor_compras,
        'cupons_top': cupons_top,
        'resgates_por_parceiro': resgates_por_parceiro,
        'chart_parceiros_labels': json.dumps(parceiros_labels),
        'chart_parceiros_data': json.dumps(parceiros_resgates_data),
    }
    return render(request, 'clube/dashboard/relatorios_parceiros.html', context)


# ============================================================
# OPERACAO: Landing Page, Banners, Categorias
# ============================================================

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_landing_config(request):
    """Editar configuracao da landing page publica."""
    config, _ = LandingConfig.objects.get_or_create(id=1)

    if request.method == 'POST':
        config.titulo = request.POST.get('titulo', config.titulo).strip()
        config.subtitulo = request.POST.get('subtitulo', config.subtitulo).strip()
        config.whatsapp_numero = request.POST.get('whatsapp_numero', '').strip()
        config.whatsapp_mensagem = request.POST.get('whatsapp_mensagem', '').strip()
        config.texto_como_funciona = request.POST.get('texto_como_funciona', '').strip()
        config.texto_rodape = request.POST.get('texto_rodape', '').strip()
        config.cor_primaria = request.POST.get('cor_primaria', config.cor_primaria).strip()
        config.cor_secundaria = request.POST.get('cor_secundaria', config.cor_secundaria).strip()
        config.ativo = request.POST.get('ativo') == 'on'
        if request.FILES.get('logo'):
            config.logo = request.FILES['logo']
        config.save()
        messages.success(request, 'Configuracao da landing page salva.')
        return redirect('dashboard_landing_config')

    return render(request, 'clube/dashboard/landing_config.html', {'config': config})


@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_banners(request):
    """CRUD de banners da landing page."""
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar':
            if request.FILES.get('imagem'):
                BannerClube.objects.create(
                    titulo=request.POST.get('titulo', '').strip(),
                    imagem=request.FILES['imagem'],
                    link=request.POST.get('link', '').strip(),
                    ordem=int(request.POST.get('ordem', 0) or 0),
                    ativo=request.POST.get('ativo') == 'on',
                )
                messages.success(request, 'Banner criado.')
            else:
                messages.error(request, 'Selecione uma imagem.')

        elif action == 'editar':
            banner = get_object_or_404(BannerClube, id=request.POST.get('banner_id'))
            banner.titulo = request.POST.get('titulo', '').strip()
            banner.link = request.POST.get('link', '').strip()
            banner.ordem = int(request.POST.get('ordem', 0) or 0)
            banner.ativo = request.POST.get('ativo') == 'on'
            if request.FILES.get('imagem'):
                banner.imagem = request.FILES['imagem']
            banner.save()
            messages.success(request, 'Banner atualizado.')

        elif action == 'excluir':
            get_object_or_404(BannerClube, id=request.POST.get('banner_id')).delete()
            messages.success(request, 'Banner excluido.')

        return redirect('dashboard_banners')

    banners = BannerClube.objects.all().order_by('ordem')
    return render(request, 'clube/dashboard/banners.html', {'banners': banners})


@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_categorias(request):
    """CRUD de categorias de parceiros."""
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar':
            nome = request.POST.get('nome', '').strip()
            slug = request.POST.get('slug', '').strip().lower().replace(' ', '-')
            if nome and slug:
                CategoriaParceiro.objects.create(
                    nome=nome,
                    slug=slug,
                    icone=request.POST.get('icone', 'fas fa-tag').strip(),
                    ordem=int(request.POST.get('ordem', 0) or 0),
                    ativo=request.POST.get('ativo') == 'on',
                )
                messages.success(request, f'Categoria "{nome}" criada.')
            else:
                messages.error(request, 'Nome e slug sao obrigatorios.')

        elif action == 'editar':
            cat = get_object_or_404(CategoriaParceiro, id=request.POST.get('categoria_id'))
            cat.nome = request.POST.get('nome', cat.nome).strip()
            cat.slug = request.POST.get('slug', cat.slug).strip().lower().replace(' ', '-')
            cat.icone = request.POST.get('icone', cat.icone).strip()
            cat.ordem = int(request.POST.get('ordem', 0) or 0)
            cat.ativo = request.POST.get('ativo') == 'on'
            cat.save()
            messages.success(request, f'Categoria "{cat.nome}" atualizada.')

        elif action == 'excluir':
            get_object_or_404(CategoriaParceiro, id=request.POST.get('categoria_id')).delete()
            messages.success(request, 'Categoria excluida.')

        return redirect('dashboard_categorias')

    categorias = CategoriaParceiro.objects.all().order_by('ordem', 'nome')
    return render(request, 'clube/dashboard/categorias.html', {'categorias': categorias})
