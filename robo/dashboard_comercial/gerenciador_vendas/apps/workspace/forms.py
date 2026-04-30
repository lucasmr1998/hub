"""
Forms do Workspace.

Cada form sanitiza inputs textuais via apps.workspace.markdown_utils.sanitizar_input
quando aplicável. Slug é gerado automaticamente se vazio.
"""
from django import forms
from django.utils.text import slugify

from apps.workspace.markdown_utils import sanitizar_input
from apps.workspace.models import (
    Documento, Etapa, Nota, PastaDocumento, Projeto, Tarefa,
)


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = [
            'titulo', 'slug', 'categoria', 'formato', 'pasta', 'conteudo',
            'arquivo', 'url_externa', 'resumo', 'descricao', 'visivel_agentes', 'ordem',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'field-input', 'maxlength': 200, 'autofocus': True}),
            'slug': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'auto se vazio'}),
            'categoria': forms.Select(attrs={'class': 'field-input'}),
            'formato': forms.Select(attrs={'class': 'field-input'}),
            'pasta': forms.Select(attrs={'class': 'field-input'}),
            'conteudo': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 18, 'placeholder': '# Título\n\nEscreva em markdown ou HTML conforme o formato...'}),
            'url_externa': forms.URLInput(attrs={'class': 'field-input', 'placeholder': 'https://...'}),
            'resumo': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'descricao': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'ordem': forms.NumberInput(attrs={'class': 'field-input'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['pasta'].queryset = PastaDocumento.objects.filter(tenant=tenant)
        self.fields['pasta'].required = False
        self.fields['slug'].required = False
        self.fields['url_externa'].required = False

    def clean_conteudo(self):
        # Sanitização só pra markdown — HTML é sanitizado no render via bleach + CSSSanitizer
        formato = self.data.get('formato', 'markdown')
        conteudo = self.cleaned_data.get('conteudo', '')
        if formato == 'markdown':
            return sanitizar_input(conteudo)
        return conteudo

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('slug') and cleaned.get('titulo'):
            cleaned['slug'] = slugify(cleaned['titulo'])[:200]
        return cleaned


class PastaForm(forms.ModelForm):
    class Meta:
        model = PastaDocumento
        fields = ['nome', 'slug', 'icone', 'cor', 'pai', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'field-input', 'maxlength': 100, 'autofocus': True}),
            'slug': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'auto se vazio'}),
            'icone': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'bi-folder'}),
            'cor': forms.TextInput(attrs={'class': 'field-input', 'type': 'color'}),
            'pai': forms.Select(attrs={'class': 'field-input'}),
            'ordem': forms.NumberInput(attrs={'class': 'field-input'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            qs = PastaDocumento.objects.filter(tenant=tenant)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            self.fields['pai'].queryset = qs
        self.fields['pai'].required = False
        self.fields['slug'].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('slug') and cleaned.get('nome'):
            cleaned['slug'] = slugify(cleaned['nome'])[:120]
        return cleaned


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = [
            'nome', 'descricao', 'status', 'prioridade',
            'objetivo', 'publico_alvo', 'criterios_sucesso',
            'riscos', 'premissas', 'responsavel', 'stakeholders',
            'data_inicio', 'data_fim_prevista', 'orcamento',
            'contexto_agentes', 'ativo',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'field-input', 'autofocus': True}),
            'descricao': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'field-input'}),
            'prioridade': forms.Select(attrs={'class': 'field-input'}),
            'objetivo': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 3}),
            'publico_alvo': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'criterios_sucesso': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 3}),
            'riscos': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 3}),
            'premissas': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'responsavel': forms.Select(attrs={'class': 'field-input'}),
            'stakeholders': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'data_inicio': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
            'data_fim_prevista': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
            'orcamento': forms.NumberInput(attrs={'class': 'field-input', 'step': '0.01'}),
            'contexto_agentes': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        # responsavel: filtrar usuários do tenant atual
        if tenant:
            from django.contrib.auth.models import User
            self.fields['responsavel'].queryset = User.objects.filter(
                permissoes__tenant=tenant
            ).distinct().order_by('first_name', 'username')


class EtapaForm(forms.ModelForm):
    class Meta:
        model = Etapa
        fields = ['nome', 'descricao', 'ordem', 'data_inicio', 'data_fim']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'field-input', 'autofocus': True}),
            'descricao': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'ordem': forms.NumberInput(attrs={'class': 'field-input'}),
            'data_inicio': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ordem'].required = False
        self.fields['data_inicio'].required = False
        self.fields['data_fim'].required = False


class TarefaForm(forms.ModelForm):
    class Meta:
        model = Tarefa
        fields = [
            'titulo', 'descricao', 'etapa', 'responsavel', 'status',
            'prioridade', 'data_limite', 'ordem',
            'objetivo', 'contexto', 'passos', 'entregavel', 'criterios_aceite',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'field-input', 'autofocus': True}),
            'descricao': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 3}),
            'etapa': forms.Select(attrs={'class': 'field-input'}),
            'responsavel': forms.Select(attrs={'class': 'field-input'}),
            'status': forms.Select(attrs={'class': 'field-input'}),
            'prioridade': forms.Select(attrs={'class': 'field-input'}),
            'data_limite': forms.DateInput(attrs={'class': 'field-input', 'type': 'date'}),
            'ordem': forms.NumberInput(attrs={'class': 'field-input'}),
            'objetivo': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'contexto': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'passos': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 3}),
            'entregavel': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
            'criterios_aceite': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 2}),
        }

    def __init__(self, *args, tenant=None, projeto=None, **kwargs):
        super().__init__(*args, **kwargs)
        if projeto:
            self.fields['etapa'].queryset = Etapa.objects.filter(projeto=projeto)
        self.fields['etapa'].required = False
        self.fields['ordem'].required = False
        self.fields['responsavel'].required = False
        if tenant:
            from django.contrib.auth.models import User
            self.fields['responsavel'].queryset = User.objects.filter(
                permissoes__tenant=tenant
            ).distinct().order_by('first_name', 'username')


class NotaForm(forms.ModelForm):
    class Meta:
        model = Nota
        fields = ['texto']
        widgets = {
            'texto': forms.Textarea(attrs={'class': 'field-input field-textarea', 'rows': 3, 'placeholder': 'Escreva uma nota...', 'autofocus': True}),
        }
