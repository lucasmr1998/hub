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
        for nome in ['unidade', 'cargo', 'colaborador_substituido']:
            self.fields[nome].empty_label = 'Selecione'
        for nome in ['turno', 'modelo_trabalho', 'justificativa']:
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
    config = catalogo.normalizar_config(vaga.config_campos)
    campos_config = [
        {**campo, **config[campo['nome']]}
        for campo in catalogo.CAMPOS_SISTEMA
    ]

    return render(request, 'people/vaga_form.html', {
        'pagetitle': vaga.nome_exibido,
        'form': form,
        'vaga': vaga,
        'requisitos': vaga.requisitos.all(),
        'form_requisito': RequisitoForm(),
        'links': vaga.links.all(),
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


@require_POST
@requer_people('people.gerir_vagas')
def campos_salvar(request, pk):
    """
    Grava quais campos a candidatura desta vaga pede.

    Campo travado (nome, WhatsApp) nao aparece no POST porque nao da pra
    desligar; o normalizar_config forca solicitar=obrigatorio=True neles de
    qualquer jeito, entao nao ha como quebrar por form incompleto.
    """
    from apps.people import campos_candidatura as catalogo

    vaga = get_object_or_404(Vaga.objects, pk=pk)

    config = {}
    for campo in catalogo.CAMPOS_SISTEMA:
        nome = campo['nome']
        config[nome] = {
            'solicitar': request.POST.get(f'solicitar_{nome}') == 'on',
            'obrigatorio': request.POST.get(f'obrigatorio_{nome}') == 'on',
        }

    vaga.config_campos = catalogo.normalizar_config(config)
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
