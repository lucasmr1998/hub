import logging
import random
import requests
import time
from django.shortcuts import redirect
from django.http import JsonResponse
from django.db import transaction, models
from django.db.models import Q, F
from apps.cs.clube.models import PremioRoleta, ParticipanteRoleta, RouletteAsset, RoletaConfig, MembroClube, RegraPontuacao, ExtratoPontuacao, NivelClube, Cidade
from apps.cs.clube.services.hubsoft_service import HubsoftService
from apps.cs.clube.services.otp_service import OTPService
from apps.cs.clube.services.sorteio_service import SorteioService
from apps.cs.clube.services.gamification_service import GamificationService
from apps.cs.parceiros.models import CupomDesconto, ResgateCupom
from apps.cs.parceiros.services import CupomService
from apps.cs.indicacoes.models import Indicacao, IndicacaoConfig
from apps.cs.indicacoes.services import IndicacaoService

logger = logging.getLogger(__name__)

def roleta_init_dados(request):
    """
    JSON endpoint that provides all initial data for the frontend to render.
    """
    sorteado_pos = request.session.pop('sorteado_pos', None)
    nome_ganhador = request.session.pop('nome_ganhador', None)
    premio_nome = request.session.pop('premio_nome', None)
    mensagem_vitoria = request.session.pop('mensagem_vitoria', None)
    erro = request.session.pop('erro_sorteio', None)
    saldo_atual = request.session.pop('saldo_atual', None)
    limite_giros_config = request.session.pop('limite_giros_config', None)
    periodo_limite_erro = request.session.pop('periodo_limite', None)
    
    auth_membro_id = request.session.get('auth_membro_id')
    is_authenticated = False
    auth_saldo = 0
    auth_nome = ''
    auth_xp = 0
    auth_nivel = 'Iniciante'
    auth_prox_nivel_xp = 0
    auth_progresso_nivel = 0
    missoes = []
    cupons_disponiveis = []
    indicacao_data = {}
    auth_codigo_indicacao = ''
    
    if auth_membro_id:
        try:
            membro = MembroClube.objects.get(id=auth_membro_id, tenant=request.tenant)
            is_authenticated = True
            auth_saldo = membro.saldo
            auth_nome = membro.nome
            auth_xp = membro.xp_total
            auth_nivel = membro.nivel_atual
            prox = membro.proximo_nivel
            
            # Cálculo de progressão
            if prox:
                auth_prox_nivel_xp = prox.xp_necessario
                nivel_anterior = NivelClube.objects.filter(xp_necessario__lte=membro.xp_total).order_by('-xp_necessario').first()
                xp_base = nivel_anterior.xp_necessario if nivel_anterior else 0
                xp_para_subir = prox.xp_necessario - xp_base
                xp_ganho_neste_nivel = membro.xp_total - xp_base
                auth_progresso_nivel = int((xp_ganho_neste_nivel / xp_para_subir) * 100) if xp_para_subir > 0 else 100
            else:
                auth_prox_nivel_xp = auth_xp # MAX LEVEL
                auth_progresso_nivel = 100
                
            # Missões e Extrato — query única para conclusões
            regras_ativas = RegraPontuacao.objects.filter(ativo=True, visivel_na_roleta=True)
            from django.db.models import Count
            conclusoes_map = dict(
                ExtratoPontuacao.objects.filter(membro=membro, regra__in=regras_ativas)
                .values_list('regra_id')
                .annotate(cnt=Count('id'))
                .values_list('regra_id', 'cnt')
            )
            for r in regras_ativas:
                conclusoes = conclusoes_map.get(r.id, 0)
                missoes.append({
                    'id': r.id,
                    'nome': r.nome_exibicao,
                    'gatilho': r.gatilho,
                    'recompensa_giros': r.pontos_saldo,
                    'recompensa_xp': r.pontos_xp,
                    'limite': r.limite_por_membro,
                    'concluidas': conclusoes,
                    'disponivel': r.limite_por_membro == 0 or conclusoes < r.limite_por_membro
                })
            # Cupons disponíveis — query única para resgates do membro
            cupons_list = CupomService.cupons_disponiveis(membro)
            resgates_por_cupom = dict(
                ResgateCupom.objects.filter(membro=membro)
                .exclude(status='cancelado')
                .values_list('cupom_id')
                .annotate(cnt=Count('id'))
                .values_list('cupom_id', 'cnt')
            )
            for cupom in cupons_list:
                resgates_membro = resgates_por_cupom.get(cupom.id, 0)
                if resgates_membro >= cupom.limite_por_membro:
                    continue
                cupons_disponiveis.append({
                    'id': cupom.id,
                    'titulo': cupom.titulo,
                    'descricao': cupom.descricao,
                    'parceiro': cupom.parceiro.nome,
                    'parceiro_logo': cupom.parceiro.logo.url if cupom.parceiro.logo else '',
                    'imagem': cupom.imagem.url if cupom.imagem else '',
                    'tipo_desconto': cupom.tipo_desconto,
                    'valor_desconto': str(cupom.valor_desconto),
                    'modalidade': cupom.modalidade,
                    'custo_pontos': cupom.custo_pontos,
                    'nivel_minimo': cupom.nivel_minimo.nome if cupom.nivel_minimo else None,
                })

            # Indicações — queries otimizadas
            auth_codigo_indicacao = membro.codigo_indicacao or ''
            todas_indicacoes = Indicacao.objects.filter(membro_indicador=membro)
            indicacao_config, _ = IndicacaoConfig.objects.get_or_create(id=1)
            ind_stats = todas_indicacoes.aggregate(
                total=Count('id'),
                convertidas=Count('id', filter=Q(status='convertido')),
                pendentes=Count('id', filter=Q(status='pendente')),
            )
            indicacao_data = {
                'codigo': auth_codigo_indicacao,
                'total': ind_stats['total'],
                'convertidas': ind_stats['convertidas'],
                'pendentes': ind_stats['pendentes'],
                'lista': [
                    {
                        'nome': i.nome_indicado,
                        'status': i.status,
                        'status_display': i.get_status_display(),
                        'data': i.data_indicacao.strftime('%d/%m/%Y'),
                    }
                    for i in todas_indicacoes.order_by('-data_indicacao')[:20]
                ],
                'texto_compartilhar': f"Olá! Sou cliente Megalink e quero te indicar para o clube de fidelidade. Acesse:",
            }

        except MembroClube.DoesNotExist:
            request.session.pop('auth_membro_id', None)
            request.session.pop('auth_membro_nome', None)
            request.session.pop('auth_membro_cpf', None)
    
    config, _ = RoletaConfig.objects.get_or_create(id=1)
    cidades_disponiveis = Cidade.objects.filter(ativo=True).values_list('nome', flat=True).order_by('nome')
    assets = RouletteAsset.objects.filter(ativo=True).order_by('ordem')
    
    asset_list = []
    for a in assets:
        asset_list.append({
            'id': a.id,
            'ordem': a.ordem,
            'tipo': a.tipo,
            'imagem_url': a.imagem.url if a.imagem else ''
        })

    data = {
        'nome_clube': config.nome_clube,
        'custo_giro': config.custo_giro,
        'cidades': sorted(list(cidades_disponiveis)),
        'assets': asset_list,
        'sorteado_pos': sorteado_pos,
        'nome_ganhador': nome_ganhador,
        'premio_nome': premio_nome,
        'mensagem': mensagem_vitoria,
        'saldo_atual': saldo_atual,
        'is_authenticated': is_authenticated,
        'auth_saldo': auth_saldo,
        'auth_nome': auth_nome,
        'auth_xp': auth_xp,
        'auth_nivel': auth_nivel,
        'auth_prox_nivel_xp': auth_prox_nivel_xp,
        'auth_progresso_nivel': auth_progresso_nivel,
        'missoes': missoes,
        'cupons': cupons_disponiveis,
        'indicacao': indicacao_data,
        'erro': erro,
        # Dados de limite de giros
        'limite_giros_por_membro': config.limite_giros_por_membro,
        'periodo_limite': config.periodo_limite,
        'limite_giros_config': limite_giros_config,
        'periodo_limite_erro': periodo_limite_erro,
    }
    return JsonResponse(data)

@transaction.atomic
def cadastrar_participante(request):
    if request.method == 'POST':

        # Check if user is already authenticated via session
        auth_membro_id = request.session.get('auth_membro_id')
        membro = None
        created = False
        config, _ = RoletaConfig.objects.get_or_create(id=1)

        if auth_membro_id:
            try:
                membro = MembroClube.objects.get(id=auth_membro_id, tenant=request.tenant)
            except MembroClube.DoesNotExist:
                pass

        if membro:
            # Use data from the established authenticated session
            nome = membro.nome
            cpf = membro.cpf
            email = membro.email
            telefone = membro.telefone
            cep = membro.cep
            cidade = membro.cidade
            estado = membro.estado
            bairro = membro.bairro
            endereco_completo = membro.endereco
            canal = request.POST.get('canal', 'Online (Sessão)')
            perfil = 'sim'
            id_cliente_hubsoft = membro.id_cliente_hubsoft
        else:
            # Normal POST data parsing
            nome = request.POST.get('nome') or "Participante"
            cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')
            email = request.POST.get('email')
            telefone = request.POST.get('telefone')
            cep = request.POST.get('cep')

            # Fetch Real City from Hubsoft PostgreSQL
            from apps.cs.clube.services.hubsoft_service import HubsoftService
            cidade_hubsoft = HubsoftService.consultar_cidade_cliente_cpf(cpf)
            if cidade_hubsoft:
                cidade = cidade_hubsoft
            else:
                cidade = request.POST.get('cidade') or "Cidade Não Informada"

            estado = request.POST.get('estado')
            bairro = request.POST.get('bairro')
            rua = request.POST.get('rua')
            numero_casa = request.POST.get('numero_casa')
            canal = request.POST.get('canal', 'Online')
            perfil = request.POST.get('perfil_cliente', 'nao')
            id_cliente_hubsoft = request.POST.get('id_cliente_hubsoft')
            if not id_cliente_hubsoft: id_cliente_hubsoft = None

            # SEGURANÇA: Verificar OTP para clientes existentes apenas se não tiver auth_membro_id
            if perfil == 'sim':
                if not request.session.get('otp_validado'):
                    request.session['erro_sorteio'] = "Verificação de segurança necessária."
                    return redirect('roleta_index')
                # Resetado para segurança
                request.session['otp_validado'] = False

            endereco_completo = f"{rua} Nº {numero_casa}"

            # Get or create Member
            membro, created = MembroClube.objects.update_or_create(
                cpf=cpf,
                defaults={
                    'nome': nome,
                    'email': email,
                    'telefone': telefone,
                    'cep': cep,
                    'endereco': endereco_completo,
                    'bairro': bairro,
                    'cidade': cidade,
                    'estado': estado,
                    'id_cliente_hubsoft': int(id_cliente_hubsoft) if id_cliente_hubsoft else None,
                }
            )
            if created:
                from apps.cs.clube.models import RegraPontuacao
                from apps.cs.clube.services.gamification_service import GamificationService

                RegraPontuacao.objects.get_or_create(
                    gatilho='cadastro_inicial',
                    defaults={
                        'nome_exibicao': 'Bônus de Cadastro Inicial',
                        'pontos_saldo': config.custo_giro,
                        'pontos_xp': 0,
                        'limite_por_membro': 1,
                        'ativo': True
                    }
                )

                membro.saldo = 0
                membro.save()

                GamificationService.atribuir_pontos(membro, 'cadastro_inicial', 'Primeiro acesso ao clube')

                membro.validado = True
                membro.save()

            if request.session.get('otp_validado'):
                membro.validado = True
                membro.save()

        request.session['otp_validado'] = False

        # Assegura a autenticação na sessão
        request.session['auth_membro_id'] = membro.id
        request.session['auth_membro_nome'] = membro.nome
        request.session['auth_membro_cpf'] = membro.cpf
        request.session.modified = True

        acao = request.POST.get('acao')
        if acao != 'girar':
            return redirect('roleta_index')

        # ── Verificar saldo (com lock para evitar race condition) ──────────
        membro = MembroClube.objects.select_for_update().get(id=membro.id)
        has_sufficient_points = membro.saldo >= config.custo_giro

        if not has_sufficient_points:
            error_msg = 'saldo_insuficiente'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg,
                    'custo': config.custo_giro,
                    'saldo': membro.saldo
                })
            request.session['erro_sorteio'] = error_msg
            return redirect('roleta_index')

        # Se tem saldo, mas já ganhou algo (e a regra for apenas uma participação,
        # mas como temos sistema de pontos, esta trava pode ser opcional ou específica)
        # No momento, mantemos como trava de segurança se necessário.

        # ── Verificação de limite de giros ────────────────────────────────
        if config.limite_giros_por_membro > 0:
            from django.utils import timezone as tz
            from datetime import timedelta
            giros_q = ParticipanteRoleta.objects.filter(membro=membro)
            periodo = config.periodo_limite
            if periodo == 'diario':
                giros_q = giros_q.filter(data_criacao__date=tz.now().date())
            elif periodo == 'semanal':
                giros_q = giros_q.filter(data_criacao__gte=tz.now() - timedelta(days=7))
            elif periodo == 'mensal':
                giros_q = giros_q.filter(
                    data_criacao__year=tz.now().year,
                    data_criacao__month=tz.now().month
                )
            qtd_giros = giros_q.count()
            if qtd_giros >= config.limite_giros_por_membro:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'limite_giros',
                        'limite': config.limite_giros_por_membro,
                        'periodo': periodo
                    })
                request.session['erro_sorteio'] = 'limite_giros'
                request.session['limite_giros_config'] = config.limite_giros_por_membro
                request.session['periodo_limite'] = periodo
                return redirect('roleta_index')
        # ─────────────────────────────────────────────────────────────────

        # Determine locality for prizes
        localidade = membro.cidade
        if not localidade:
            localidade = "Cidade Não Informada"

        # Find available prizes for the locality
        # Estoque protegido via update atômico com F() — select_for_update não pode ser usado com distinct()
        premios_disponiveis = list(PremioRoleta.objects.filter(
            Q(cidades_permitidas__nome__iexact=localidade) | Q(cidades_permitidas__isnull=True),
            quantidade__gt=0
        ).distinct())

        if not premios_disponiveis:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'acabou_premio'})
            request.session['erro_sorteio'] = 'acabou_premio'
            return redirect('roleta_index')

        new_saldo, premio_selecionado, roleta_pos = SorteioService.executar_giro_roleta(
            membro=membro,
            premios_disponiveis=premios_disponiveis,
            custo_giro=config.custo_giro
        )

        membro.saldo = new_saldo
        membro.xp_total += config.xp_por_giro
        membro.save()

        # Update atômico do estoque via F() — protege contra race condition
        rows_updated = PremioRoleta.objects.filter(
            id=premio_selecionado.id,
            quantidade__gt=0  # Só decrementa se ainda há estoque (guarda dupla)
        ).update(quantidade=F('quantidade') - 1)

        if rows_updated == 0:
            # Outro processo zerou o estoque entre o SELECT e o UPDATE
            # Reverter saldo do membro e rejeitar o giro
            membro.saldo = membro.saldo + custo_giro  # Reverte localmente antes do save
            # O @transaction.atomic garante rollback completo ao lançar a exceção
            from django.db import IntegrityError
            raise IntegrityError("Estoque esgotado — tente novamente.")

        perfil_cliente = request.POST.get('perfil_cliente', 'nao')
        id_cliente_hubsoft_final = request.POST.get('id_cliente_hubsoft') or None

        # Create spin record
        ParticipanteRoleta.objects.create(
            membro=membro,
            nome=nome,
            cpf=cpf,
            email=email,
            telefone=telefone,
            cep=cep,
            endereco=endereco_completo,
            bairro=bairro,
            cidade=cidade,
            estado=estado,
            premio=premio_selecionado.nome,
            canal_origem=canal,
            perfil_cliente=perfil_cliente,
            id_cliente_hubsoft=id_cliente_hubsoft_final,
            saldo=new_saldo,
            status='reservado'
        )

        # Se for requisição AJAX (authSpinForm), retornar JSON SEM salvar na sessão
        # (a animação será disparada pelo JSON — salvar na sessão causaria double-spin)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and acao == 'girar':
            return JsonResponse({
                'success': True,
                'sorteado_pos': roleta_pos,
                'premio_nome': premio_selecionado.nome,
                'mensagem': premio_selecionado.mensagem_vitoria,
                'saldo_atual': new_saldo
            })

        # Fluxo não-AJAX: salvar na sessão e redirecionar para roleta_index exibir resultado
        request.session['sorteado_pos'] = roleta_pos
        request.session['nome_ganhador'] = nome
        request.session['premio_nome'] = premio_selecionado.nome
        request.session['mensagem_vitoria'] = premio_selecionado.mensagem_vitoria
        request.session['saldo_atual'] = new_saldo
        request.session.modified = True

        return redirect('roleta_index')

    return redirect('roleta_index')

@transaction.atomic
def verificar_cliente(request):
    if request.method == 'POST':
        cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')
        if not cpf:
            return JsonResponse({'error': 'CPF não fornecido'}, status=400)
            
        # Get existing member if any
        config, _ = RoletaConfig.objects.get_or_create(id=1)
            
        cliente_data = HubsoftService.consultar_cliente(cpf)
        if cliente_data:

            # Cidade: tenta primeiro pelo webhook, se vier vazia busca direto no PostgreSQL Hubsoft
            # A cidade do PostgreSQL é a fonte mais confiável (cruza endereço de instalação)
            cidade_webhook = cliente_data.get('nome_cidade') or cliente_data.get('cidade') or ''
            if not cidade_webhook:
                cidade_postgres = HubsoftService.consultar_cidade_cliente_cpf(cpf)
                cidade_final = cidade_postgres or ''
            else:
                # Mesmo que o webhook retorne, confirma com o PostgreSQL (instalação é a verdade)
                cidade_postgres = HubsoftService.consultar_cidade_cliente_cpf(cpf)
                cidade_final = cidade_postgres or cidade_webhook

            # PERSISTÊNCIA IMEDIATA
            # Se não existe, cria. Se existe, atualiza com dados do Hubsoft
            membro, created = MembroClube.objects.update_or_create(
                cpf=cpf,
                defaults={
                    'nome': cliente_data.get('nome_razaosocial', 'Participante'),
                    'email': cliente_data.get('email_principal'),
                    'telefone': cliente_data.get('telefone_primario', ''),
                    'cep': cliente_data.get('cep'),
                    'endereco': cliente_data.get('endereco'),
                    'bairro': cliente_data.get('bairro'),
                    'cidade': cidade_final,
                    'id_cliente_hubsoft': cliente_data.get('id_cliente')
                }
            )
            if created:
                from apps.cs.clube.models import RegraPontuacao
                from apps.cs.clube.services.gamification_service import GamificationService

                RegraPontuacao.objects.get_or_create(
                    gatilho='cadastro_inicial',
                    defaults={
                        'nome_exibicao': 'Bônus de Cadastro Inicial',
                        'pontos_saldo': config.custo_giro,
                        'pontos_xp': 0,
                        'limite_por_membro': 1,
                        'ativo': True
                    }
                )

                membro.saldo = 0
                membro.validado = False
                membro.save()

                membro.refresh_from_db()
                saldo_final = membro.saldo
            else:
                saldo_final = membro.saldo

            return JsonResponse({
                'is_client': True,
                'nome_razaosocial': cliente_data.get('nome_razaosocial'),
                'email_principal': cliente_data.get('email_principal'),
                'telefone_primario': cliente_data.get('telefone_primario', ''),
                'masked_tel': cliente_data.get('masked_tel', ''),
                'id_cliente': cliente_data.get('id_cliente'),
                'saldo': saldo_final,
                'cep': cliente_data.get('cep'),
                'endereco': cliente_data.get('endereco'),
                'numero': cliente_data.get('numero'),
                'bairro': cliente_data.get('bairro'),
                'cidade': cidade_final
            })
        
        return JsonResponse({'is_client': False})
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

def solicitar_otp(request):
    if request.method == 'POST':
        # Basic rate limiting (60 seconds)
        last_request_time = request.session.get('last_otp_request_time')
        current_time = time.time()
        if last_request_time and (current_time - last_request_time) < 60:
            segundos_restantes = 60 - int(current_time - last_request_time)
            return JsonResponse({'error': f'Aguarde {segundos_restantes}s para solicitar um novo código.'}, status=429)

        cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')
        telefone = request.POST.get('telefone', '')

        if not cpf or not telefone:
            return JsonResponse({'error': 'CPF e Telefone são obrigatórios'}, status=400)

        # Update the rate limit timestamp
        request.session['last_otp_request_time'] = current_time

        # Gerar código via OTPService
        otp_code = OTPService.gerar_codigo()

        # Save to session (com timestamp para expiração)
        request.session['otp_code'] = otp_code
        request.session['otp_cpf'] = cpf
        request.session['otp_gerado_em'] = current_time  # BUG-05: expiração de 10 min

        # Send via n8n webhook module
        sucesso, msg = OTPService.enviar_otp_whatsapp(cpf, telefone, otp_code)

        if sucesso:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': msg}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)

def validar_otp(request):
    if request.method == 'POST':
        codigo_usuario = str(request.POST.get('codigo', '')).strip()
        codigo_sessao = str(request.session.get('otp_code', '')).strip()
        cpf = request.session.get('otp_cpf')

        # BUG-05: Verificar expiração do OTP (10 minutos)
        otp_gerado_em = request.session.get('otp_gerado_em')
        otp_expirado = otp_gerado_em and (time.time() - otp_gerado_em) > 600
        if otp_expirado:
            return JsonResponse({'success': False, 'error': 'Código expirado. Solicite um novo código.'})

        if codigo_usuario and codigo_usuario == codigo_sessao:
            request.session['otp_validado'] = True
            if cpf:
                membro = MembroClube.objects.filter(cpf=cpf).first()
                if membro:
                    eh_primeira_validacao = not membro.validado
                    membro.validado = True
                    membro.save()

                    # PERSIST AUTHENTICATED STATE
                    request.session['auth_membro_id'] = membro.id
                    request.session['auth_membro_nome'] = membro.nome
                    request.session['auth_membro_cpf'] = membro.cpf
                    request.session.modified = True

                    if eh_primeira_validacao:
                        # Garante que a regra existe
                        from apps.cs.clube.models import RegraPontuacao
                        RegraPontuacao.objects.get_or_create(
                            gatilho='telefone_verificado',
                            defaults={
                                'nome_exibicao': 'Validou seu WhatsApp',
                                'pontos_saldo': 1,
                                'pontos_xp': 10,
                                'limite_por_membro': 1,
                                'ativo': True
                            }
                        )
                        GamificationService.atribuir_pontos(membro, 'telefone_verificado', 'Validou WhatsApp')

                    # MÓDULO DE SINCRONIZAÇÃO HUBSOFT (Sempre que validar)
                    try:
                        from apps.cs.clube.services.hubsoft_service import HubsoftService
                        from apps.cs.clube.models import RegraPontuacao, ExtratoPontuacao
                        from django.utils import timezone

                        # Garantir que as regras base existam
                        regras = [
                            {'gatilho': 'hubsoft_recorrencia', 'nome': 'Ativou Pagamento Recorrente', 'pts': 3, 'xp': 30, 'lim': 1},
                            {'gatilho': 'hubsoft_adiantado', 'nome': 'Pagou Fatura Adiantada', 'pts': 5, 'xp': 50, 'lim': 0},
                            {'gatilho': 'hubsoft_app', 'nome': 'Baixou e usou o APP Central', 'pts': 2, 'xp': 20, 'lim': 1}
                        ]
                        for r in regras:
                            RegraPontuacao.objects.get_or_create(
                                gatilho=r['gatilho'],
                                defaults={
                                    'nome_exibicao': r['nome'], 'pontos_saldo': r['pts'],
                                    'pontos_xp': r['xp'], 'limite_por_membro': r['lim'], 'ativo': True
                                }
                            )

                        status_pontos = HubsoftService.checar_pontos_extras_cpf(membro.cpf)
                        if status_pontos:
                            # RECORRÊNCIA
                            if status_pontos.get('hubsoft_recorrencia'):
                                r_rec = RegraPontuacao.objects.get(gatilho='hubsoft_recorrencia')
                                if not ExtratoPontuacao.objects.filter(membro=membro, regra=r_rec).exists():
                                    GamificationService.atribuir_pontos(membro, 'hubsoft_recorrencia', 'Sincronização Hubsoft')
                            # APP
                            if status_pontos.get('hubsoft_app'):
                                r_app = RegraPontuacao.objects.get(gatilho='hubsoft_app')
                                if not ExtratoPontuacao.objects.filter(membro=membro, regra=r_app).exists():
                                    GamificationService.atribuir_pontos(membro, 'hubsoft_app', 'Sincronização Hubsoft')
                            # ADIANTADO (Mensal)
                            if status_pontos.get('hubsoft_adiantado'):
                                r_adi = RegraPontuacao.objects.get(gatilho='hubsoft_adiantado')
                                ja_ganhou_mes = ExtratoPontuacao.objects.filter(
                                    membro=membro, regra=r_adi,
                                    data_recebimento__year=timezone.now().year,
                                    data_recebimento__month=timezone.now().month
                                ).exists()
                                if not ja_ganhou_mes:
                                    desc = f"Mês {timezone.now().month}/{timezone.now().year}"

                                    # Incrementar datas se disponíveis
                                    d_pgto = status_pontos.get('data_pagamento_adiantado')
                                    d_venc = status_pontos.get('data_vencimento_adiantado')
                                    if d_pgto and d_venc:
                                        try:
                                            desc += f" (Venc: {d_venc.strftime('%d/%m')}, Pago: {d_pgto.strftime('%d/%m')})"
                                        except:
                                            desc += f" (Pago Adiantado)"

                                    GamificationService.atribuir_pontos(membro, 'hubsoft_adiantado', desc)

                    except Exception:
                        pass

            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Código inválido'})

    return JsonResponse({'success': False, 'error': 'Método inválido'}, status=405)

@transaction.atomic
def pre_cadastrar(request):
    if request.method == 'POST':
        data = request.POST.dict()
        cpf = data.get('cpf', '').replace('.', '').replace('-', '')
        if cpf:
            config, _ = RoletaConfig.objects.get_or_create(id=1)
            defaults = {
                'nome': data.get('nome') or "Participante",
                'telefone': data.get('telefone'),
                'email': data.get('email'),
            }
            # Adiciona endereço se presente (vindo do Step 3 ou Hubsoft)
            # BUG-11: garantir cidade consultando PostgreSQL Hubsoft se não veio no POST
            cidade_post = data.get('cidade')
            if cidade_post:
                defaults['cidade'] = cidade_post
            else:
                from apps.cs.clube.services.hubsoft_service import HubsoftService
                cidade_pg = HubsoftService.consultar_cidade_cliente_cpf(cpf)
                if cidade_pg:
                    defaults['cidade'] = cidade_pg
            if data.get('cep'): defaults['cep'] = data.get('cep')
            # Rua + Numero
            rua = data.get('rua')
            num = data.get('numero_casa') or data.get('numero')
            if rua: defaults['endereco'] = f"{rua} {num}" if num else rua
            if data.get('bairro'): defaults['bairro'] = data.get('bairro')
            if data.get('id_cliente'): defaults['id_cliente_hubsoft'] = data.get('id_cliente')

            membro, created = MembroClube.objects.update_or_create(
                cpf=cpf,
                defaults=defaults
            )
            if created:
                from apps.cs.clube.models import RegraPontuacao
                from apps.cs.clube.services.gamification_service import GamificationService

                # Garante que a regra de cadastro existe
                RegraPontuacao.objects.get_or_create(
                    gatilho='cadastro_inicial',
                    defaults={
                        'nome_exibicao': 'Bônus de Cadastro Inicial',
                        'pontos_saldo': config.custo_giro,
                        'pontos_xp': 0,
                        'limite_por_membro': 1,
                        'ativo': True
                    }
                )

                membro.saldo = 0
                membro.save()

                GamificationService.atribuir_pontos(membro, 'cadastro_inicial', 'Primeiro acesso ao clube')

                membro.validado = False
                membro.save()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False})


def api_resgatar_cupom(request):
    """API para membro resgatar cupom via frontend."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método inválido'}, status=405)

    auth_membro_id = request.session.get('auth_membro_id')
    if not auth_membro_id:
        return JsonResponse({'success': False, 'error': 'Não autenticado'}, status=401)

    cupom_id = request.POST.get('cupom_id')
    if not cupom_id:
        return JsonResponse({'success': False, 'error': 'Cupom não informado'})

    try:
        membro = MembroClube.objects.get(id=auth_membro_id, tenant=request.tenant)
    except MembroClube.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Membro não encontrado'})

    sucesso, msg, resgate = CupomService.resgatar_cupom(membro, cupom_id)
    if sucesso:
        return JsonResponse({
            'success': True,
            'message': msg,
            'codigo': resgate.codigo_unico,
            'saldo_atual': membro.saldo,
        })
    return JsonResponse({'success': False, 'error': msg})


def api_criar_indicacao(request):
    """API para membro criar indicação via frontend."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método inválido'}, status=405)

    auth_membro_id = request.session.get('auth_membro_id')
    if not auth_membro_id:
        return JsonResponse({'success': False, 'error': 'Não autenticado'}, status=401)

    try:
        membro = MembroClube.objects.get(id=auth_membro_id, tenant=request.tenant)
    except MembroClube.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Membro não encontrado'})

    nome = request.POST.get('nome', '').strip()
    telefone = request.POST.get('telefone', '').strip()
    cpf = request.POST.get('cpf', '').strip()
    cidade = request.POST.get('cidade', '').strip()

    if not nome or not telefone:
        return JsonResponse({'success': False, 'error': 'Nome e telefone são obrigatórios'})

    sucesso, msg, indicacao = IndicacaoService.criar_indicacao(
        membro_indicador=membro,
        nome=nome,
        telefone=telefone,
        cpf=cpf,
        cidade=cidade,
    )
    return JsonResponse({'success': sucesso, 'message': msg})
