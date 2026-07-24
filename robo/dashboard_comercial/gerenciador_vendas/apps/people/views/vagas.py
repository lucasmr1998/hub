"""
Vagas de recrutamento.

A vaga e a fonte da verdade da divulgacao (ver o docstring do model): requisito,
cargo e criterio vivem aqui, e o link de candidatura do passo 3 vai derivar
disto. Por isso os requisitos sao editados dentro da propria vaga, e nao numa
tela separada.
"""
import io
import secrets

from django import forms
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import TransicaoInvalida
from apps.people.models import (
    Cargo, Colaborador, LinkCandidatura, RequisitoVaga, Unidade, Vaga,
)
from apps.people.models_recrutamento import (
    CANAL_CHOICES, JUSTIFICATIVA_SUBSTITUICAO,
)
from apps.people import estados
from apps.people.permissoes import pode_acessar, requer_people
from apps.people.services import vagas as servicos_vaga
from apps.sistema.utils import registrar_acao


class VagaForm(forms.ModelForm):
    class Meta:
        model = Vaga
        fields = ['unidade', 'cargo', 'titulo', 'tipo_contratacao', 'turno',
                  'modelo_trabalho', 'carga_horaria', 'remuneracao',
                  'descricao', 'justificativa', 'colaborador_substituido',
                  'limite_aprovados', 'observacoes']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant

        # Os selects so podem oferecer o que e do tenant. Sem isto o formulario
        # aceitaria pk de outro tenant vindo por POST forjado, e o
        # ForeignKey.validate() nao pega, porque ele so confere existencia.
        self.fields['unidade'].queryset = Unidade.all_tenants.filter(
            tenant=tenant, ativo=True).order_by('nome')
        self.fields['cargo'].queryset = Cargo.all_tenants.filter(
            tenant=tenant, ativo=True).order_by('ordem', 'nome')
        self.fields['colaborador_substituido'].queryset = (
            Colaborador.all_tenants.filter(
                tenant=tenant, situacao__in=estados.SITUACOES_ATIVAS)
            .order_by('nome_completo'))
        self.fields['colaborador_substituido'].required = False

        # O Django rotula a opcao vazia como "---------". O resto do modulo usa
        # "Selecione" (ver o formulario publico), entao aqui tambem.
        #
        # O `if nome in self.fields` existe porque o RequisicaoVagaForm herda
        # daqui com um SUBCONJUNTO de campos: sem a guarda, o form do gestor
        # estouraria KeyError em `turno` na hora de instanciar.
        for nome in ['unidade', 'cargo', 'colaborador_substituido']:
            if nome in self.fields:
                self.fields[nome].empty_label = 'Selecione'
        for nome in ['turno', 'modelo_trabalho', 'justificativa']:
            if nome in self.fields:
                self.fields[nome].choices = [
                    ('', 'Selecione'),
                    *[(v, r) for v, r in self.fields[nome].choices if v],
                ]

    def clean(self):
        """
        Espelha em mensagem o que a CheckConstraint ja garante no banco.

        Sem isto o usuario levaria um IntegrityError na cara. Com isto, erro no
        campo certo. A constraint continua sendo a garantia; esta validacao e a
        cortesia.
        """
        dados = super().clean()
        justificativa = dados.get('justificativa')
        substituido = dados.get('colaborador_substituido')

        if substituido and justificativa != JUSTIFICATIVA_SUBSTITUICAO:
            self.add_error(
                'colaborador_substituido',
                'So faz sentido indicar quem esta sendo substituido quando a '
                'justificativa e substituição.')

        if justificativa == JUSTIFICATIVA_SUBSTITUICAO and not substituido:
            self.add_error(
                'colaborador_substituido',
                'Indique quem está sendo substituído. É o que evita a loja '
                'contratar e esquecer de desligar a pessoa que sai.')

        return dados


class RequisitoForm(forms.ModelForm):
    class Meta:
        model = RequisitoVaga
        fields = ['texto', 'obrigatorio', 'aparece_no_anuncio', 'usar_na_triagem']

    def clean(self):
        dados = super().clean()
        if not dados.get('aparece_no_anuncio') and not dados.get('usar_na_triagem'):
            raise forms.ValidationError(
                'Marque pelo menos um uso. Um requisito que não aparece no '
                'anúncio nem serve de critério não faz nada.')
        return dados


class RequisicaoVagaForm(VagaForm):
    """
    O que o GESTOR preenche ao PEDIR uma vaga (gap 16).

    Subconjunto do VagaForm de proposito. Titulo, descricao, remuneracao e
    carga horaria sao o ANUNCIO, e o anuncio e trabalho do RH depois de
    aprovar: pedir isso ao gestor faria a requisicao parecer uma vaga pronta e
    reduziria a chance de ele simplesmente pedir. Aqui ele diz o essencial de
    governanca: qual cargo, em qual loja, e por que.

    `justificativa` vira OBRIGATORIA aqui (no VagaForm ela e opcional, porque o
    RH abrindo direto ja responde pelo custo). E o campo que da sentido a
    requisicao.
    """
    class Meta(VagaForm.Meta):
        fields = ['unidade', 'cargo', 'justificativa',
                  'colaborador_substituido', 'observacoes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['justificativa'].required = True
        self.fields['observacoes'].label = 'Contexto do pedido'
        self.fields['observacoes'].help_text = (
            'O que o RH precisa saber pra decidir. Ex: turno, urgência, se '
            'já houve tentativa anterior.')


@requer_people()
def lista(request):
    vagas = Vaga.objects.select_related('unidade', 'cargo').annotate(
        total_requisitos=Count('requisitos', distinct=True),
    )

    status = (request.GET.get('status') or '').strip()
    if status in estados_rs.VALORES_STATUS_VAGA:
        vagas = vagas.filter(status=status)

    unidade_id = (request.GET.get('unidade') or '').strip()
    if unidade_id.isdigit():
        vagas = vagas.filter(unidade_id=int(unidade_id))

    return render(request, 'people/vagas_lista.html', {
        'pagetitle': 'Vagas',
        'vagas': vagas,
        # Pares, nao dicts: o components/select.html desempacota com
        # `for valor, rotulo in options`. Dict ali renderiza as CHAVES.
        'status_opcoes': estados_rs.STATUS_VAGA,
        'status_selecionado': status,
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
        'unidade_selecionada': unidade_id,
        'pode_gerir': pode_acessar(request, 'people.gerir_vagas'),
        # Gap 16. O form vive na LISTA porque a solicitacao acontece num modal
        # ali mesmo: cadastro e botao + modal, e nao pagina propria.
        'pode_solicitar': pode_acessar(request, 'people.solicitar_vaga'),
        'form_requisicao': RequisicaoVagaForm(tenant=request.tenant),
        # Fila do RH em destaque: requisicao esperando decisao e o unico estado
        # em que alguem esta bloqueado esperando outra pessoa.
        'aguardando': vagas.filter(
            status=estados_rs.STATUS_VAGA_AGUARDANDO).count(),
        'STATUS_AGUARDANDO': estados_rs.STATUS_VAGA_AGUARDANDO,
        'STATUS_REJEITADA': estados_rs.STATUS_VAGA_REJEITADA,
    })


@requer_people('people.gerir_vagas')
def criar(request):
    form = VagaForm(request.POST or None, tenant=request.tenant)

    if request.method == 'POST' and form.is_valid():
        vaga = form.save(commit=False)
        vaga.tenant = request.tenant
        vaga.criada_por = request.user
        vaga.save()
        registrar_acao('people', 'criar', 'vaga', vaga.pk,
                       f'Vaga "{vaga.nome_exibido}" aberta em {vaga.unidade.nome}.',
                       request=request)
        messages.success(
            request,
            f'Vaga "{vaga.nome_exibido}" criada. Agora defina os requisitos.')
        # Vai pra edicao, e nao pra lista: a vaga sem requisito ainda nao serve
        # pra publicar, e mandar pra lista faria o usuario achar que acabou.
        return redirect('people:vaga_editar', pk=vaga.pk)

    return render(request, 'people/vaga_form.html', {
        'pagetitle': 'Nova vaga', 'form': form, 'vaga': None,
    })


@requer_people('people.gerir_vagas')
def editar(request, pk):
    vaga = get_object_or_404(
        Vaga.objects.select_related('unidade', 'cargo'), pk=pk)
    form = VagaForm(request.POST or None, instance=vaga, tenant=request.tenant)

    if request.method == 'POST' and form.is_valid():
        form.save()
        registrar_acao('people', 'editar', 'vaga', vaga.pk,
                       f'Vaga "{vaga.nome_exibido}" editada.', request=request)
        messages.success(request, 'Vaga salva.')
        return redirect('people:vaga_editar', pk=vaga.pk)

    from apps.people import campos_candidatura as catalogo
    extras = vaga.campos_extras()
    config = catalogo.normalizar_config(vaga.config_campos, extras)
    campos_config = [
        {**campo, **config[campo['nome']]}
        for campo in catalogo.catalogo(extras)
    ]

    requisitos = list(vaga.requisitos.all())
    # URL absoluta por link, pro botao de copiar (o candidato precisa do link
    # completo, nao so do caminho).
    links = [{'link': l, 'url': request.build_absolute_uri(l.caminho_publico)}
             for l in vaga.links.all()]

    # Tabs, no padrao dos outros modulos de configuracao. Badge so quando ha
    # conteudo, pra nao poluir com "0".
    tabs = [
        {'id': 'tab-dados', 'label': 'Dados da vaga', 'icon': 'bi-card-text',
         'active': True},
        {'id': 'tab-requisitos', 'label': 'Requisitos', 'icon': 'bi-list-check',
         'badge': str(len(requisitos)) if requisitos else ''},
        {'id': 'tab-formulario', 'label': 'Formulário',
         'icon': 'bi-ui-checks-grid'},
        {'id': 'tab-divulgacao', 'label': 'Divulgação', 'icon': 'bi-megaphone',
         'badge': str(len(links)) if links else ''},
    ]

    return render(request, 'people/vaga_form.html', {
        'pagetitle': vaga.nome_exibido,
        'form': form,
        'vaga': vaga,
        'requisitos': requisitos,
        'form_requisito': RequisitoForm(),
        'links': links,
        'tabs': tabs,
        'canais': CANAL_CHOICES,
        'campos_config': campos_config,
        # Ordem canonica da maquina, e nao alfabetica. Alfabetica punha
        # "Encerrada", que e irreversivel, antes de "Publicada", que e a acao
        # que o usuario quer 9 vezes em 10.
        'transicoes': [
            {'valor': destino,
             'rotulo': estados_rs.rotulo_status_vaga(destino),
             'destrutiva': destino == estados_rs.STATUS_VAGA_ENCERRADA}
            for destino in estados_rs.VALORES_STATUS_VAGA
            if destino in estados_rs.TRANSICOES_VAGA.get(vaga.status, set())
        ],
    })


@require_POST
@requer_people('people.gerir_vagas')
def mudar_status(request, pk):
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    destino = (request.POST.get('status') or '').strip()

    try:
        vaga.mudar_status(destino)
    except TransicaoInvalida as erro:
        messages.error(request, str(erro))
        return redirect('people:vaga_editar', pk=vaga.pk)

    rotulo = estados_rs.rotulo_status_vaga(vaga.status)
    registrar_acao('people', 'editar', 'vaga', vaga.pk,
                   f'Vaga "{vaga.nome_exibido}" agora esta {rotulo}.',
                   request=request)
    messages.success(request, f'Vaga {rotulo.lower()}.')
    return redirect('people:vaga_editar', pk=vaga.pk)


# ── Requisicao de vaga com aprovacao (gap 16) ───────────────────────────────
#
# Quem SOLICITA usa `people.solicitar_vaga`; quem DECIDE usa
# `people.gerir_vagas`. A separacao e o ponto do fluxo: com a mesma permissao
# nos dois lados, a aprovacao vira carimbo do proprio pedido.


@require_POST
@requer_people('people.solicitar_vaga')
def solicitar(request):
    """
    O gestor pede a vaga. Nasce em `aguardando_aprovacao`, sem passar por
    rascunho: rascunho e vaga aprovada esperando anuncio, e misturar os dois
    faria a fila do RH conter coisa que ninguem pediu.
    """
    form = RequisicaoVagaForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        for erros in form.errors.values():
            for erro in erros:
                messages.error(request, erro)
        return redirect('people:vagas_lista')

    vaga = form.save(commit=False)
    vaga.tenant = request.tenant
    vaga.criada_por = request.user   # criada_por E o solicitante
    vaga.status = estados_rs.STATUS_VAGA_AGUARDANDO
    vaga.save()

    try:
        servicos_vaga.solicitar(vaga, usuario=request.user, request=request)
    except servicos_vaga.RequisicaoInvalida as erro:
        vaga.delete()
        messages.error(request, str(erro))
        return redirect('people:vagas_lista')

    messages.success(
        request,
        f'Requisição de "{vaga.nome_exibido}" enviada para aprovação do RH.')
    return redirect('people:vagas_lista')


@require_POST
@requer_people('people.solicitar_vaga')
def reenviar(request, pk):
    """Requisicao rejeitada volta pra fila depois que o gestor ajusta."""
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    try:
        servicos_vaga.solicitar(vaga, usuario=request.user, request=request)
    except (servicos_vaga.RequisicaoInvalida, TransicaoInvalida) as erro:
        messages.error(request, str(erro))
        return redirect('people:vagas_lista')

    messages.success(request, 'Requisição reenviada para aprovação.')
    return redirect('people:vagas_lista')


@require_POST
@requer_people('people.gerir_vagas')
def aprovar(request, pk):
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    try:
        servicos_vaga.aprovar(vaga, usuario=request.user, request=request)
    except (servicos_vaga.RequisicaoInvalida, TransicaoInvalida) as erro:
        messages.error(request, str(erro))
        return redirect('people:vagas_lista')

    messages.success(
        request,
        f'Requisição aprovada. "{vaga.nome_exibido}" está em rascunho: '
        f'revise o anúncio e publique.')
    # Vai pra edicao, e nao pra lista: aprovar e o meio do caminho, e o passo
    # seguinte (escrever o anuncio) e do RH que acabou de aprovar.
    return redirect('people:vaga_editar', pk=vaga.pk)


@require_POST
@requer_people('people.gerir_vagas')
def rejeitar(request, pk):
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    try:
        servicos_vaga.rejeitar(vaga, usuario=request.user,
                               motivo=request.POST.get('motivo', ''),
                               request=request)
    except (servicos_vaga.RequisicaoInvalida, TransicaoInvalida) as erro:
        messages.error(request, str(erro))
        return redirect('people:vagas_lista')

    messages.success(request, 'Requisição rejeitada. O gestor vê o motivo e '
                              'pode corrigir e reenviar.')
    return redirect('people:vagas_lista')


@require_POST
@requer_people('people.gerir_vagas')
def campos_salvar(request, pk):
    """
    Grava quais campos a candidatura desta vaga pede.

    Campo travado (nome, WhatsApp) aparece na tela com cadeado e sem checkbox,
    entao nao chega no POST; o normalizar_config forca solicitar=obrigatorio=True
    neles de qualquer jeito, e nao ha como quebrar por form incompleto.

    Os campos que o tenant inventou entram pelo mesmo caminho dos de sistema. E
    o ponto da divisao de papel: o tenant define o campo, a vaga decide se pede.
    """
    from apps.people import campos_candidatura as catalogo

    vaga = get_object_or_404(Vaga.objects, pk=pk)
    extras = vaga.campos_extras()

    config = {}
    for campo in catalogo.catalogo(extras):
        nome = campo['nome']
        config[nome] = {
            'solicitar': request.POST.get(f'solicitar_{nome}') == 'on',
            'obrigatorio': request.POST.get(f'obrigatorio_{nome}') == 'on',
        }

    vaga.config_campos = catalogo.normalizar_config(config, extras)
    vaga.save(update_fields=['config_campos', 'atualizado_em'])

    registrar_acao('people', 'editar', 'vaga', vaga.pk,
                   f'Campos da candidatura de "{vaga.nome_exibido}" ajustados.',
                   request=request)
    messages.success(request, 'Campos da candidatura salvos.')
    return redirect('people:vaga_editar', pk=vaga.pk)


@require_POST
@requer_people('people.gerir_vagas')
def requisito_criar(request, pk):
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    form = RequisitoForm(request.POST)

    if not form.is_valid():
        # O form de requisito e um bloco dentro da pagina da vaga, entao nao ha
        # tela propria pra devolver com erro de campo. Vira mensagem.
        for erros in form.errors.values():
            for erro in erros:
                messages.error(request, erro)
        return redirect('people:vaga_editar', pk=vaga.pk)

    requisito = form.save(commit=False)
    requisito.tenant = request.tenant
    requisito.vaga = vaga
    ultimo = vaga.requisitos.order_by('-ordem').first()
    requisito.ordem = (ultimo.ordem + 1) if ultimo else 1
    requisito.save()

    messages.success(request, 'Requisito adicionado.')
    return redirect('people:vaga_editar', pk=vaga.pk)


@require_POST
@requer_people('people.gerir_vagas')
def requisito_remover(request, pk, requisito_pk):
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    requisito = get_object_or_404(RequisitoVaga.objects, pk=requisito_pk, vaga=vaga)

    texto = requisito.texto
    requisito.delete()

    messages.success(request, f'Requisito "{texto}" removido.')
    return redirect('people:vaga_editar', pk=vaga.pk)


# ── Divulgacao ───────────────────────────────────────────────────────────────
#
# Os links vivem DENTRO da pagina da vaga, e nao numa tela de configuracao
# separada. E a correcao que a spec de origem pede: la os dois sao fluxos
# distintos e a propria criadora aponta como defeito, porque obriga a redigitar
# no link o que ja foi cadastrado na vaga.

@require_POST
@requer_people('people.gerir_vagas')
def link_criar(request, pk):
    vaga = get_object_or_404(Vaga.objects.select_related('unidade'), pk=pk)

    canal = (request.POST.get('canal') or '').strip()
    if canal not in dict(CANAL_CHOICES):
        messages.error(request, 'Escolha um canal para o link.')
        return redirect('people:vaga_editar', pk=vaga.pk)

    link = LinkCandidatura(
        tenant=request.tenant,
        vaga=vaga,
        unidade=vaga.unidade,
        canal=canal,
        apelido_interno=(request.POST.get('apelido_interno') or '').strip(),
        cta=(request.POST.get('cta') or '').strip(),
        telefone_contato=(request.POST.get('telefone_contato') or '').strip(),
        token=secrets.token_urlsafe(32),
        criado_por=request.user,
    )
    # Texto derivado da vaga, no ato da criacao. Fica editavel depois: a vaga
    # continua sendo a fonte, e o texto e um retrato dela que o RH pode ajustar.
    link.texto_compartilhamento = link.texto_padrao()
    link.save()

    registrar_acao('people', 'criar', 'link_candidatura', link.pk,
                   f'Link de {link.get_canal_display()} criado para '
                   f'"{vaga.nome_exibido}".', request=request)
    messages.success(request, f'Link de {link.get_canal_display()} criado.')
    return redirect('people:vaga_editar', pk=vaga.pk)


@require_POST
@requer_people('people.gerir_vagas')
def link_desativar(request, pk, link_pk):
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    link = get_object_or_404(LinkCandidatura.objects, pk=link_pk, vaga=vaga)

    link.desativar()

    registrar_acao('people', 'editar', 'link_candidatura', link.pk,
                   f'Link de {link.get_canal_display()} desativado.',
                   request=request)
    messages.success(
        request,
        f'Link de {link.get_canal_display()} desativado. QR já impresso para '
        f'de funcionar.')
    return redirect('people:vaga_editar', pk=vaga.pk)


@require_POST
@requer_people('people.gerir_vagas')
def link_remover(request, pk, link_pk):
    """
    Apaga o link, e SO se ninguem tiver se candidatado por ele.

    Link com candidatura nao se apaga: a atribuicao de canal ("qual canal
    trouxe esta pessoa") mora nele, e apagar reescreveria a analise de origem
    pra tras. Pra tirar de circulacao com candidatura dentro, o caminho e
    desativar, que ja existe.
    """
    vaga = get_object_or_404(Vaga.objects, pk=pk)
    link = get_object_or_404(LinkCandidatura.objects, pk=link_pk, vaga=vaga)

    if link.candidaturas:
        messages.error(
            request,
            f'Este link ja trouxe {link.candidaturas} candidatura(s). Apagar '
            f'apagaria de onde essas pessoas vieram. Use Desativar.')
        return redirect('people:vaga_editar', pk=vaga.pk)

    canal = link.get_canal_display()
    link.delete()
    registrar_acao('people', 'excluir', 'link_candidatura', link_pk,
                   f'Link de {canal} removido (sem candidaturas).', request=request)
    messages.success(request, f'Link de {canal} removido.')
    return redirect('people:vaga_editar', pk=vaga.pk)


@requer_people('people.gerir_vagas')
def link_qr(request, pk, link_pk):
    """
    QR do link, em SVG.

    SVG e nao PNG pelo mesmo motivo do link do DP: o uso real e cartaz na parede
    da loja, e precisa escalar sem borrar na impressao. Uma campanha citada na
    origem abriu a sexta loja com QR impresso em ponto de onibus.
    """
    import segno

    vaga = get_object_or_404(Vaga.objects, pk=pk)
    link = get_object_or_404(LinkCandidatura.objects, pk=link_pk, vaga=vaga)
    url = request.build_absolute_uri(link.caminho_publico)

    buffer = io.BytesIO()
    segno.make(url, error='m').save(buffer, kind='svg', scale=8, border=2)

    resposta = HttpResponse(buffer.getvalue(), content_type='image/svg+xml')
    resposta['Content-Disposition'] = (
        f'attachment; filename="qr-{link.canal}-{link.pk}.svg"')
    return resposta


@requer_people()
def banco_talentos_links(request):
    """
    Links de captacao continua: sem vaga, alimentando o banco de talentos.

    `LinkCandidatura.vaga` sempre aceitou nulo, o help_text documentava e a view
    publica ja tratava o caso, com testes. So nao havia porta de entrada: o
    unico caminho de criacao era de dentro de uma vaga, e ele sempre setava a
    vaga. Capacidade completa no backend, sem botao. Esta tela e o botao.

    Tem valor proprio: um QR fixo no balcao da loja capta o ano inteiro, sem
    depender de haver vaga aberta naquele dia.
    """
    return redirect('/people/fluxo/?tab=captacao')


def contexto_captacao(request):
    """
    Contexto da aba Captacao continua, namespaceado com prefixo `captacao_`.

    `unidades_opcoes` fica sem prefixo de proposito: e a MESMA lista de unidades
    que a aba Etapas usa, e duplicar seria duas consultas pro mesmo dado. O hub
    monta essa chave uma vez.
    """
    links = (LinkCandidatura.objects
             .filter(vaga__isnull=True)
             .select_related('unidade')
             .order_by('-ativo', '-criado_em'))

    return {
        'captacao_links': [
            {'link': l, 'url': request.build_absolute_uri(l.caminho_publico)}
            for l in links],
        'captacao_canais': CANAL_CHOICES,
    }


@require_POST
@requer_people('people.gerir_vagas')
def banco_talentos_link_criar(request):
    """Cria um link sem vaga. Quem chega por ele cai no banco de talentos."""
    canal = (request.POST.get('canal') or '').strip()
    unidade_id = (request.POST.get('unidade') or '').strip()

    if canal not in dict(CANAL_CHOICES):
        messages.error(request, 'Escolha um canal para o link.')
        return redirect('/people/fluxo/?tab=captacao')

    # A unidade e obrigatoria mesmo sem vaga: o candidato do banco precisa estar
    # ligado a uma loja, senao nao ha como o RH daquela loja encontrar ele.
    unidade = Unidade.objects.filter(pk=unidade_id).first() if unidade_id.isdigit() else None
    if unidade is None:
        messages.error(request, 'Escolha a unidade que vai receber os candidatos.')
        return redirect('/people/fluxo/?tab=captacao')

    link = LinkCandidatura(
        tenant=request.tenant,
        vaga=None,
        unidade=unidade,
        canal=canal,
        apelido_interno=(request.POST.get('apelido_interno') or '').strip(),
        cta=(request.POST.get('cta') or '').strip(),
        telefone_contato=(request.POST.get('telefone_contato') or '').strip(),
        token=secrets.token_urlsafe(32),
        criado_por=request.user,
    )
    link.texto_compartilhamento = link.texto_padrao()
    link.save()

    registrar_acao('people', 'criar', 'link_candidatura', link.pk,
                   f'Link de captação contínua ({link.get_canal_display()}) '
                   f'criado para {unidade.nome}.', request=request)
    messages.success(request, f'Link de {link.get_canal_display()} criado.')
    return redirect('/people/fluxo/?tab=captacao')


@requer_people()
def banco_talentos_link_qr(request, link_pk):
    """
    QR do link de captacao continua.

    Rota propria porque a de vaga exige a vaga na URL, e estes links nao tem
    uma. Mesmo SVG, pelo mesmo motivo: o uso real e cartaz no balcao da loja.
    """
    import segno

    link = get_object_or_404(LinkCandidatura.objects, pk=link_pk,
                             vaga__isnull=True)
    url = request.build_absolute_uri(link.caminho_publico)

    buffer = io.BytesIO()
    segno.make(url, error='m').save(buffer, kind='svg', scale=8, border=2)

    resposta = HttpResponse(buffer.getvalue(), content_type='image/svg+xml')
    resposta['Content-Disposition'] = (
        f'attachment; filename="qr-captacao-{link.canal}-{link.pk}.svg"')
    return resposta


@require_POST
@requer_people('people.gerir_vagas')
def banco_talentos_link_alternar(request, link_pk):
    """
    Liga e desliga o link de captacao.

    Nao apaga: as candidaturas que chegaram por ele apontam pra ele, e apagar
    destruiria a atribuicao de canal. Mesma regra dos links de vaga.
    """
    link = get_object_or_404(LinkCandidatura.objects, pk=link_pk,
                             vaga__isnull=True)
    link.ativo = not link.ativo
    link.desativado_em = None if link.ativo else timezone.now()
    link.save(update_fields=['ativo', 'desativado_em'])

    estado = 'reativado' if link.ativo else 'desativado'
    registrar_acao('people', 'editar', 'link_candidatura', link.pk,
                   f'Link de captação contínua {estado}.', request=request)
    messages.success(request, f'Link {estado}.')
    return redirect('people:banco_talentos_links')
