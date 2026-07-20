"""
Forms do People.

A validacao de dominio NAO mora aqui. Regra de negocio vive no servico
(`apps.people.services`) e nas constraints do banco, porque o formulario e
apenas uma das portas: existem tambem o link publico, a importacao e a API. O
que fica aqui e o que e mesmo do formulario, tipo normalizar mascara de CEP.
"""
from django import forms

from apps.people.models import Unidade
from apps.people.utils import normalizar_cep, normalizar_e164, normalizar_estado


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
