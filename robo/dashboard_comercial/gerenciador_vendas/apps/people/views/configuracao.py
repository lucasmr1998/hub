"""
Configuracao do modulo: fluxo do departamento pessoal e templates de formulario.

A tela de fluxo espelha a de origem: sete etapas fixas, e a configuracao
acontece dentro de cada uma. Recurso que ainda nao existe em codigo aparece
marcado como em construcao, em vez de sumir da tela. E deliberado: o mapa do
modulo fica visivel desde o inicio, e a tela nao mente sobre o tamanho do
produto.
"""
from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.people import estados
from apps.people.campos_formulario import CAMPOS_SISTEMA, config_padrao, normalizar_config
from apps.people.models import (
    ConfiguracaoPeople, MensagemEtapa, TemplateFormulario, Unidade,
)
from apps.people.permissoes import pode_acessar, requer_people
from apps.sistema.utils import registrar_acao


# ── Home das configuracoes ───────────────────────────────────────────────────

@requer_people()
def home(request):
    return render(request, 'people/config_home.html', {
        'pagetitle': 'Configuracoes',
        'pode_gerir': pode_acessar(request, 'people.gerir_unidades'),
    })


# ── Fluxo do departamento pessoal ────────────────────────────────────────────

@requer_people()
def fluxo(request):
    """As sete etapas, com quantos recursos cada uma tem."""
    mensagens = {
        m.etapa: m
        for m in MensagemEtapa.objects.filter(ativo=True)
    }

    etapas = []
    for etapa in estados.ETAPAS_FLUXO:
        disponiveis = [r for r in etapa['recursos'] if r in estados.RECURSOS_DISPONIVEIS]
        etapas.append({
            **etapa,
            'rotulo_situacao': estados.rotulo(etapa['situacao']),
            'total_recursos': len(etapa['recursos']),
            'recursos_prontos': len(disponiveis),
            'tem_mensagem': etapa['situacao'] in mensagens,
        })

    return render(request, 'people/config_fluxo.html', {
        'pagetitle': 'Fluxo do Departamento Pessoal',
        'etapas': etapas,
        'pode_gerir': pode_acessar(request, 'people.gerir_unidades'),
    })


@requer_people()
def fluxo_etapa(request, situacao):
    """Recursos configuraveis de uma etapa."""
    etapa = estados.etapa_por_situacao(situacao)
    if etapa is None:
        raise Http404

    recursos = [
        {
            'chave': chave,
            'rotulo': estados.ROTULOS_RECURSO.get(chave, chave),
            'descricao': estados.DESCRICOES_RECURSO.get(chave, ''),
            'disponivel': chave in estados.RECURSOS_DISPONIVEIS,
        }
        for chave in etapa['recursos']
    ]

    return render(request, 'people/config_fluxo_etapa.html', {
        'pagetitle': etapa['nome'],
        'etapa': etapa,
        'recursos': recursos,
        'pode_gerir': pode_acessar(request, 'people.gerir_unidades'),
    })


class MensagemEtapaForm(forms.ModelForm):
    class Meta:
        model = MensagemEtapa
        fields = ['texto', 'escopo', 'unidades', 'ativo']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidades'].queryset = Unidade.objects.filter(ativo=True)
        self.fields['unidades'].required = False


@requer_people('people.gerir_unidades')
def mensagem_etapa(request, situacao):
    """
    Mensagem sugerida ao RH quando o colaborador chega na etapa.

    NADA E ENVIADO AUTOMATICAMENTE. E decisao de produto copiada da tela de
    origem, que avisa isso em dois lugares. Quem quiser automatizar de verdade
    monta fluxo na engine escutando o evento da transicao; os dois caminhos
    convivem.
    """
    etapa = estados.etapa_por_situacao(situacao)
    if etapa is None:
        raise Http404

    instancia = MensagemEtapa.objects.filter(etapa=situacao).first()
    form = MensagemEtapaForm(request.POST or None, instance=instancia,
                             tenant=request.tenant)

    if request.method == 'POST' and form.is_valid():
        mensagem = form.save(commit=False)
        mensagem.tenant = request.tenant
        mensagem.etapa = situacao
        mensagem.save()
        form.save_m2m()
        registrar_acao('people', 'editar', 'mensagem_etapa', mensagem.pk,
                       f'Mensagem da etapa {etapa["nome"]} salva.', request=request)
        messages.success(request, 'Mensagem salva.')
        return redirect('people:config_fluxo_etapa', situacao=situacao)

    if instancia is None and not form.data:
        form.initial['texto'] = (
            f'Ola, {{{{nome}}}}! Voce esta na etapa "{etapa["nome"]}" '
            f'do seu processo com a gente.'
        )

    return render(request, 'people/config_mensagem_etapa.html', {
        'pagetitle': f'Mensagem de {etapa["nome"]}',
        'etapa': etapa,
        'form': form,
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
    })


# ── Templates de formulario ──────────────────────────────────────────────────

@requer_people()
def templates(request):
    return render(request, 'people/config_templates.html', {
        'pagetitle': 'Formularios e dados',
        'templates': TemplateFormulario.objects.all(),
        'pode_gerir': pode_acessar(request, 'people.gerir_links'),
    })


@requer_people('people.gerir_links')
def template_editar(request, pk=None):
    """
    Editor do formulario: por campo, se e solicitado, se e obrigatorio e com que
    rotulo aparece.

    O catalogo de campos e codigo (cada campo tem coluna no Colaborador), entao
    o que se edita aqui e a configuracao, nao a lista.
    """
    template = None
    if pk is not None:
        template = get_object_or_404(TemplateFormulario.objects, pk=pk)

    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        if not nome:
            messages.error(request, 'O template precisa de um nome.')
        else:
            config = {}
            for campo in CAMPOS_SISTEMA:
                chave = campo['nome']
                travado = campo.get('travado', False)
                config[chave] = {
                    'solicitar': travado or bool(request.POST.get(f'solicitar_{chave}')),
                    'obrigatorio': travado or bool(request.POST.get(f'obrigatorio_{chave}')),
                    'rotulo': (request.POST.get(f'rotulo_{chave}') or '').strip()
                              or campo['rotulo_padrao'],
                }

            if template is None:
                template = TemplateFormulario(tenant=request.tenant)
            template.nome = nome
            template.descricao = (request.POST.get('descricao') or '').strip()
            template.campos = normalizar_config(config)
            template.ativo = bool(request.POST.get('ativo'))
            template.save()

            registrar_acao('people', 'editar', 'template_formulario', template.pk,
                           f'Template "{template.nome}" salvo.', request=request)
            messages.success(request, f'Template "{template.nome}" salvo.')
            return redirect('people:config_templates')

    config = template.config() if template else normalizar_config(config_padrao())
    campos = [
        {**campo, **config.get(campo['nome'], {}), 'travado': campo.get('travado', False)}
        for campo in CAMPOS_SISTEMA
    ]

    return render(request, 'people/config_template_form.html', {
        'pagetitle': template.nome if template else 'Novo template',
        'template': template,
        'campos': campos,
    })


# ── Defaults do tenant ───────────────────────────────────────────────────────

class ConfiguracaoPeopleForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoPeople
        fields = [
            'dias_experiencia_padrao', 'dias_primeiro_periodo_experiencia',
            'exige_cpf_no_autocadastro', 'texto_consentimento_lgpd',
            'versao_consentimento_lgpd', 'link_expira_em_dias',
        ]


@requer_people('people.gerir_unidades')
def geral(request):
    config = ConfiguracaoPeople.get_config(request.tenant)
    form = ConfiguracaoPeopleForm(request.POST or None, instance=config)

    if request.method == 'POST' and form.is_valid():
        form.save()
        registrar_acao('people', 'editar', 'configuracao', config.pk,
                       'Configuracao geral do People salva.', request=request)
        messages.success(request, 'Configuracao salva.')
        return redirect('people:config_geral')

    return render(request, 'people/config_geral.html', {
        'pagetitle': 'Configuracao geral',
        'form': form,
    })
