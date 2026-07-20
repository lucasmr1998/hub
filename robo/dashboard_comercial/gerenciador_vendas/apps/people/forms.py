"""
Forms do People.

A validacao de dominio NAO mora aqui. Regra de negocio vive no servico
(`apps.people.services`) e nas constraints do banco, porque o formulario e
apenas uma das portas: existem tambem o link publico, a importacao e a API. O
que fica aqui e o que e mesmo do formulario, tipo normalizar mascara de CEP.
"""
from django import forms

from apps.people.models import Cargo, Unidade
from apps.people.utils import (
    normalizar_cep, normalizar_cpf, normalizar_e164, normalizar_estado,
)


UFS = [
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapa'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceara'), ('DF', 'Distrito Federal'),
    ('ES', 'Espirito Santo'), ('GO', 'Goias'), ('MA', 'Maranhao'),
    ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'), ('MG', 'Minas Gerais'),
    ('PA', 'Para'), ('PB', 'Paraiba'), ('PR', 'Parana'), ('PE', 'Pernambuco'),
    ('PI', 'Piaui'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'), ('RO', 'Rondonia'), ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'), ('SP', 'Sao Paulo'), ('SE', 'Sergipe'),
    ('TO', 'Tocantins'),
]

# Override booleano precisa de tres estados: herdar, ligar e desligar. Um
# checkbox so tem dois, e "desmarcado" seria indistinguivel de "nao configurado".
HERANCA_CHOICES = [
    ('', 'Herdar do tenant'),
    ('sim', 'Sim'),
    ('nao', 'Nao'),
]


class UnidadeForm(forms.ModelForm):
    exige_cpf_no_autocadastro = forms.ChoiceField(
        choices=HERANCA_CHOICES, required=False, label='Exigir CPF no auto cadastro',
        help_text='Vazio herda a configuracao do tenant.',
    )

    class Meta:
        model = Unidade
        fields = [
            'nome', 'codigo', 'cnpj', 'telefone',
            'cep', 'rua', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
            'responsavel', 'ativo',
            'dias_experiencia_padrao', 'dias_primeiro_periodo_experiencia',
            'exige_cpf_no_autocadastro',
        ]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields['responsavel'].required = False

        # Booleano nulavel nao roda em BooleanField do Django: ele colapsa None
        # em False. Por isso o campo virou ChoiceField de tres estados.
        if self.instance and self.instance.pk is not None:
            atual = self.instance.exige_cpf_no_autocadastro
            self.initial['exige_cpf_no_autocadastro'] = (
                '' if atual is None else ('sim' if atual else 'nao')
            )

    def clean_codigo(self):
        codigo = (self.cleaned_data.get('codigo') or '').strip().lower()
        if not codigo:
            return codigo
        # A unique de banco garante de verdade. Isto e so pra mensagem ficar no
        # campo certo em vez de virar IntegrityError na cara do usuario.
        existentes = Unidade.all_tenants.filter(tenant=self.tenant, codigo=codigo)
        if self.instance and self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError('Ja existe uma unidade com este codigo.')
        return codigo

    def clean_cep(self):
        return normalizar_cep(self.cleaned_data.get('cep'))

    def clean_telefone(self):
        return normalizar_e164(self.cleaned_data.get('telefone'))

    def clean_estado(self):
        return normalizar_estado(self.cleaned_data.get('estado'))

    def clean_exige_cpf_no_autocadastro(self):
        valor = self.cleaned_data.get('exige_cpf_no_autocadastro')
        if valor == 'sim':
            return True
        if valor == 'nao':
            return False
        return None


class ColaboradorForm(forms.Form):
    """
    Cadastro de colaborador pelo RH.

    E `Form` e nao `ModelForm` de proposito: ModelForm oferece `.save()`, que
    criaria o registro direto e pularia o dedup. Aqui o form so junta e limpa os
    dados; quem cria e `registrar_colaborador`, que pesquisa antes.
    """

    nome_completo = forms.CharField(max_length=200, label='Nome completo')
    cpf = forms.CharField(max_length=14, required=False, label='CPF')
    telefone = forms.CharField(max_length=20, required=False, label='Telefone')
    email = forms.EmailField(required=False, label='Email')
    data_nascimento = forms.DateField(required=False, label='Data de nascimento')
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.none(), label='Unidade')
    cargo = forms.ModelChoiceField(
        queryset=Cargo.objects.none(), required=False, label='Cargo')
    regime_contratacao = forms.ChoiceField(required=False, label='Regime de contratacao')
    data_admissao = forms.DateField(required=False, label='Data de admissao')

    def __init__(self, *args, tenant=None, situacao_inicial=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.people import estados
        from apps.people.models import REGIME_CONTRATACAO_CHOICES

        self.tenant = tenant
        self.situacao_inicial = situacao_inicial
        self.fields['unidade'].queryset = Unidade.objects.filter(ativo=True)
        self.fields['cargo'].queryset = Cargo.objects.filter(ativo=True)
        self.fields['regime_contratacao'].choices = [('', 'Nao definido')] + list(
            REGIME_CONTRATACAO_CHOICES)

        # A exigencia vem da maquina de estados, nao de uma regra escrita aqui.
        # Entrar direto em admissao ou experiencia precisa de data de admissao.
        exigidos = estados.campos_exigidos(
            estados.SITUACAO_CADASTRO, situacao_inicial or estados.SITUACAO_CADASTRO)
        for campo in exigidos:
            if campo in self.fields:
                self.fields[campo].required = True

    def clean_cpf(self):
        return normalizar_cpf(self.cleaned_data.get('cpf'))

    def clean_telefone(self):
        return normalizar_e164(self.cleaned_data.get('telefone'))

    def dados_do_servico(self):
        """Payload pro registrar_colaborador, sem chave vazia."""
        dados = dict(self.cleaned_data)
        dados.pop('unidade', None)
        return {chave: valor for chave, valor in dados.items() if valor not in (None, '')}


class ColaboradorDadosForm(forms.ModelForm):
    """
    Edicao dos dados de uma pessoa que JA existe.

    Aqui ModelForm e seguro, diferente do cadastro: nao ha criacao, entao nao ha
    dedup a furar. O `save()` cai no `Colaborador.save()`, e a guarda de situacao
    nao dispara porque nenhum campo de fase esta no form.

    O que NAO entra: situacao, ponto_entrada e as datas de vinculo. Elas mudam
    por transicao, no board, pra que cada mudanca gere historico. Editar aqui
    seria um caminho paralelo sem rastro.
    """

    class Meta:
        from apps.people.models import Colaborador as _Colaborador
        model = _Colaborador
        fields = [
            'nome_completo', 'primeiro_nome', 'cpf', 'rg', 'pis', 'data_nascimento',
            'telefone', 'email',
            'cep', 'rua', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
            'tipo_chave_pix', 'chave_pix',
            'cargo', 'regime_contratacao',
            'elegivel_recontratacao', 'observacoes',
        ]

    def clean_cpf(self):
        """
        A unique de CPF por tenant tambem vale na edicao. Sem esta checagem, o
        RH corrigindo um CPF pra um que ja existe tomaria IntegrityError 500 em
        vez de uma mensagem no campo.
        """
        from apps.people.models import Colaborador

        cpf = normalizar_cpf(self.cleaned_data.get('cpf'))
        if not cpf:
            return None

        conflito = (Colaborador.all_tenants
                    .filter(tenant_id=self.instance.tenant_id, cpf=cpf)
                    .exclude(pk=self.instance.pk)
                    .first())
        if conflito is not None:
            raise forms.ValidationError(
                f'Este CPF ja e de {conflito.nome_completo}. '
                f'Se for a mesma pessoa, o cadastro dela deve ser reaproveitado.'
            )
        return cpf

    def clean_telefone(self):
        return normalizar_e164(self.cleaned_data.get('telefone'))

    def clean_estado(self):
        return normalizar_estado(self.cleaned_data.get('estado'))

    def clean_cep(self):
        return normalizar_cep(self.cleaned_data.get('cep'))
