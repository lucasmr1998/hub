"""
Ficha do candidato.

Duas abas, Perfil e Historico, no mesmo padrao da ficha do colaborador do DP
(pagina propria com tabs, e nao modal): quem chega pelo board clica no nome e
navega, e o botao Voltar traz de volta.

A ficha so mostra o que o candidato realmente informou. Campo em branco aparece
como travessao em vez de sumir, pra o RH saber que foi perguntado e nao
respondido, que e diferente de nao ter sido perguntado.
"""
import mimetypes

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import CampoCandidatura, Candidato, Cargo
from apps.people.permissoes import pode_acessar, requer_people
from apps.sistema.utils import registrar_acao
from apps.people.services.admissao import AdmissaoInvalida, admitir_candidato
from apps.people.services.triagem_ia import (
    TriagemIndisponivel, analisar_candidato,
)


def _respostas_custom(candidato):
    """
    As respostas dos campos do tenant, com o rotulo de cada uma.

    Resolve pelo `CampoCandidatura` pra mostrar o rotulo, e nao a chave crua do
    JSON. Resposta cujo campo foi apagado NAO aparece: sem o campo nao ha rotulo,
    e exibir "cnh_2: sim" e pior que omitir. Ela continua no banco, e a tela de
    campos e que impede apagar campo ja respondido.
    """
    dados = candidato.dados_custom or {}
    if not dados:
        return []

    campos = CampoCandidatura.all_tenants.filter(
        tenant_id=candidato.tenant_id, slug__in=list(dados)).order_by(
            'ordem', 'nome')
    return [{'rotulo': campo.nome, 'valor': dados.get(campo.slug)}
            for campo in campos]


def _abas_do_processo(candidato, historico):
    """
    As abas da ficha, GERADAS a partir das etapas configuradas do tenant.

    A tela de origem tem abas fixas (Perfil comportamental, Entrevista RH, Teste
    Pratico...), porque la o pipeline e fixo. Aqui etapa e DADO: o cliente cria,
    renomeia e reordena em /people/fluxo/. Chumbar as abas quebraria isso no
    primeiro cliente que mudar o fluxo, e ele muda: e a razao de a tela de fluxo
    existir.

    Devolve `(etapas, tabs)`. `etapas` carrega a anotacao e um marcador de onde
    o candidato esta, pra o template so exibir.
    """
    from apps.people.models import AnotacaoEtapa, EtapaPipeline

    escopo = EtapaPipeline.do_escopo(candidato.tenant, candidato.unidade)
    lista = list(escopo.order_by('ordem', 'id'))

    anotacoes = {a.etapa_id: a for a in AnotacaoEtapa.objects.filter(
        candidato=candidato).select_related('atualizado_por')}

    # Ate onde o candidato ja chegou. Etapa posterior a atual aparece, porem
    # apagada: o RH ve o caminho inteiro, e nao so o pedaco andado.
    ordem_atual = candidato.etapa.ordem if candidato.etapa_id else -1

    etapas = []
    for etapa in lista:
        anotacao = anotacoes.get(etapa.pk)
        etapas.append({
            'etapa': etapa,
            'anotacao': anotacao,
            'atual': candidato.etapa_id == etapa.pk and not candidato.saida,
            'passou': etapa.ordem < ordem_atual,
            'tem_anotacao': bool(anotacao and anotacao.texto.strip()),
        })

    tabs = [{'id': 'tab-perfil', 'label': 'Perfil', 'icon': 'bi-person',
             'active': True}]
    for item in etapas:
        tabs.append({
            'id': f'tab-etapa-{item["etapa"].pk}',
            'label': item['etapa'].nome,
            # Bolinha na aba da etapa ATUAL: com sete abas, saber onde a pessoa
            # esta sem ler todas e a informacao mais pedida da tela.
            'icon': 'bi-record-circle' if item['atual'] else 'bi-circle',
            'badge': '•' if item['tem_anotacao'] else '',
        })
    # "Movimentacoes", e nao "Historico": uma das etapas PADRAO se chama
    # Historico, e duas abas com o mesmo rotulo significando coisas diferentes
    # (a etapa versus o log de movimento) e confusao garantida. O nome tambem e
    # mais preciso: aqui so entra transicao, nao conteudo de trabalho.
    tabs.append({'id': 'tab-historico', 'label': 'Movimentações',
                 'icon': 'bi-clock-history',
                 'badge': str(historico.count()) if historico.exists() else ''})

    return etapas, tabs


@requer_people()
def detalhe(request, pk):
    candidato = get_object_or_404(
        Candidato.objects.select_related(
            'vaga', 'vaga__cargo', 'unidade', 'etapa', 'link_origem',
            'colaborador'),
        pk=pk)

    historico = (candidato.historico
                 .select_related('usuario')
                 .order_by('-criado_em'))

    etapas, tabs = _abas_do_processo(candidato, historico)

    return render(request, 'people/candidato_detalhe.html', {
        'pagetitle': candidato.nome_completo,
        'candidato': candidato,
        'respostas_custom': _respostas_custom(candidato),
        # Sugestao pra etapa (ou saida) em que o candidato esta AGORA. Vazia
        # quando ninguem configurou mensagem pra esta fase, e ai o bloco some.
        'mensagem_sugerida': candidato.mensagem_sugerida(),
        'tem_whatsapp': bool(candidato.link_whatsapp()),
        # Pares, e nao dicts: components/select.html desempacota.
        'cargos_opcoes': list(
            Cargo.objects.filter(ativo=True).values_list('pk', 'nome')),
        # Ultima analise, e nao todas: a ficha mostra a atual. O historico
        # fica no banco pra quando alguem precisar auditar a decisao.
        'analise': candidato.analises.first(),
        'pode_analisar': pode_acessar(request, 'people.gerir_vagas'),
        'pode_admitir': (
            not candidato.colaborador_id
            and not candidato.anonimizado_em
            and pode_acessar(request, 'people.gerir_vagas')),
        'historico': historico,
        'tabs': tabs,
        'etapas': etapas,
        'saidas': [{'valor': v, 'rotulo': r} for v, r in estados_rs.SAIDAS],
        'pode_mover': pode_acessar(request, 'people.gerir_vagas'),
        # Anotar e permissao PROPRIA: o supervisor que entrevista registra
        # a impressao dele sem poder mover no pipeline nem admitir.
        'pode_anotar': pode_acessar(request, 'people.avaliar'),
    })


@requer_people()
def curriculo(request, pk):
    """
    Serve o curriculo do candidato.

    O arquivo vive em storage privado (PrivateCurriculoStorage), fora de
    MEDIA_ROOT, justamente porque a rota `/media/` serve qualquer arquivo sem
    autenticacao. Aqui passa pelo login, pela permissao do modulo e pelo escopo
    de tenant do `Candidato.objects`, entao um pk de outro tenant da 404 em vez
    de entregar o PDF.

    `?download=1` forca o Content-Disposition como attachment. Sem ele, abre no
    navegador: PDF e imagem sao os formatos que o RH quer so olhar.

    Mesmo desenho do `api_midia` do Inbox, que resolveu isto antes pra RG e
    comprovante.
    """
    candidato = get_object_or_404(Candidato.objects, pk=pk)

    if not candidato.curriculo:
        raise Http404('Candidato sem currículo')
    if candidato.anonimizado_em:
        # Expurgo LGPD ja apagou o arquivo; a linha sobrevive so como numero.
        raise Http404('Currículo removido por retenção')

    tipo = mimetypes.guess_type(candidato.curriculo.name)[0] or 'application/octet-stream'
    resposta = FileResponse(candidato.curriculo.open('rb'), content_type=tipo)

    extensao = candidato.curriculo.name.rsplit('.', 1)[-1]
    nome = f'curriculo-{candidato.nome_completo}.{extensao}'.replace(' ', '-')
    disposicao = 'attachment' if request.GET.get('download') else 'inline'
    resposta['Content-Disposition'] = f'{disposicao}; filename="{nome}"'
    return resposta


@require_POST
@requer_people('people.gerir_vagas')
def admitir(request, pk):
    """
    Envia o candidato pro Departamento Pessoal.

    E o unico ponto do modulo onde um Candidato vira Colaborador. As condicoes
    sao COPIADAS da vaga, e nao referenciadas: mudar a vaga depois nao altera o
    que ficou registrado pra quem ja entrou.

    Conflito de dedup NAO e erro: a pessoa pode ja existir no DP (ex-funcionario
    voltando), e o certo e o RH decidir se e a mesma, nao o sistema criar uma
    segunda linha por conta propria.
    """
    candidato = get_object_or_404(Candidato.objects, pk=pk)

    cargo_id = (request.POST.get('cargo') or '').strip()
    data_inicio = (request.POST.get('data_inicio') or '').strip() or None
    cargo = Cargo.objects.filter(pk=cargo_id).first() if cargo_id.isdigit() else None

    try:
        resultado = admitir_candidato(
            candidato, cargo=cargo, data_inicio=data_inicio,
            usuario=request.user, request=request)
    except AdmissaoInvalida as erro:
        messages.error(request, str(erro))
        return redirect('people:candidato_detalhe', pk=pk)

    if not resultado.ok:
        messages.error(
            request,
            f'Já existe alguém no Departamento Pessoal que pode ser esta '
            f'pessoa ({resultado.motivo_conflito or "dados parecidos"}). '
            f'Confira no cadastro antes de admitir, pra não criar duplicata.')
        return redirect('people:candidato_detalhe', pk=pk)

    messages.success(
        request,
        f'{candidato.nome_completo} enviado para o Departamento Pessoal. '
        f'Falta o CPF e os documentos, que o formulário de cadastro coleta.')
    return redirect('people:colaborador_detalhe', pk=resultado.colaborador.pk)


@require_POST
@requer_people('people.gerir_vagas')
def analisar(request, pk):
    """
    Pede a analise da IA. SOB DEMANDA, e NUNCA move o candidato.

    Sincrono de proposito: e um botao que o usuario apertou e esta esperando, e
    nao um evento de fundo. Fila aqui so acrescentaria complexidade sem
    beneficio, ja que ninguem mais depende do resultado.
    """
    candidato = get_object_or_404(Candidato.objects, pk=pk)

    try:
        analise = analisar_candidato(candidato, usuario=request.user)
    except TriagemIndisponivel as erro:
        messages.error(request, str(erro))
        return redirect('people:candidato_detalhe', pk=pk)

    registrar_acao('people', 'analisar', 'candidato', candidato.pk,
                   f'Triagem por IA de "{candidato.nome_completo}": '
                   f'{analise.get_veredito_display()}.', request=request)
    messages.success(request,
                     f'Análise pronta: {analise.get_veredito_display()}. '
                     f'É sugestão, a decisão continua sua.')
    return redirect('people:candidato_detalhe', pk=pk)


@require_POST
@requer_people('people.avaliar')
def anotar_etapa(request, pk, etapa_pk):
    """
    Grava o que o RH anotou numa etapa.

    Uma anotacao por etapa por candidato, sobrescrita a cada salvamento. Nao e
    log: e o registro de trabalho daquela fase, e enquanto a pessoa esta nela o
    texto muda. O `HistoricoCandidato` e que guarda movimento.
    """
    from apps.people.models import AnotacaoEtapa, EtapaPipeline

    candidato = get_object_or_404(Candidato.objects, pk=pk)
    etapa = get_object_or_404(EtapaPipeline.objects, pk=etapa_pk)
    texto = (request.POST.get('texto') or '').strip()

    if texto:
        AnotacaoEtapa.all_tenants.update_or_create(
            candidato=candidato, etapa=etapa,
            defaults={'tenant': candidato.tenant, 'texto': texto,
                      'atualizado_por': request.user})
    else:
        # Texto vazio apaga: anotacao em branco e indistinguivel de nao ter
        # anotacao, e deixar as duas conviverem faria a bolinha da aba mentir.
        AnotacaoEtapa.objects.filter(candidato=candidato, etapa=etapa).delete()

    messages.success(request, f'Anotação de "{etapa.nome}" salva.')
    return redirect('people:candidato_detalhe', pk=pk)
