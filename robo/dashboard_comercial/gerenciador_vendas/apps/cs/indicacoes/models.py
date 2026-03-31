from django.db import models
from apps.sistema.mixins import TenantMixin


class IndicacaoConfig(TenantMixin):
    """Configurações visuais da página pública de indicação (singleton id=1)."""
    titulo = models.CharField(max_length=255, default="Megalink", help_text="Título principal da página")
    subtitulo = models.CharField(max_length=255, default="Clube de Fidelidade", help_text="Subtítulo abaixo do título")
    texto_indicador = models.CharField(max_length=255, default="Você foi indicado por", help_text="Texto acima do nome do indicador")
    texto_botao = models.CharField(max_length=100, default="Enviar Indicação", help_text="Texto do botão de envio")
    texto_sucesso_titulo = models.CharField(max_length=255, default="Indicação Registrada!", help_text="Título da mensagem de sucesso")
    texto_sucesso_msg = models.TextField(default="Sua indicação foi recebida com sucesso. Em breve a equipe da Megalink entrará em contato.", help_text="Mensagem de sucesso")
    logo = models.ImageField(upload_to='indicacoes/', null=True, blank=True, help_text="Logo exibida no topo da página")
    imagem_fundo = models.ImageField(upload_to='indicacoes/', null=True, blank=True, help_text="Imagem de fundo da página")
    cor_fundo = models.CharField(max_length=7, default="#0f1b2d", help_text="Cor de fundo (hex). Ignorada se tiver imagem de fundo")
    cor_botao = models.CharField(max_length=7, default="#0f1b2d", help_text="Cor do botão de envio (hex)")
    mostrar_campo_cpf = models.BooleanField(default=True, help_text="Exibir campo de CPF no formulário")
    mostrar_campo_cidade = models.BooleanField(default=True, help_text="Exibir campo de Cidade no formulário")

    def __str__(self):
        return "Configuração da Página de Indicação"

    class Meta:
        verbose_name = "Configuração de Indicação"
        verbose_name_plural = "Configurações de Indicação"
        db_table = 'indicacoes_indicacaoconfig'


class Indicacao(TenantMixin):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('contato_feito', 'Contato Feito'),
        ('convertido', 'Convertido'),
        ('cancelado', 'Cancelado'),
    ]

    membro_indicador = models.ForeignKey(
        'clube.MembroClube', on_delete=models.CASCADE, related_name='indicacoes_feitas'
    )
    nome_indicado = models.CharField(max_length=255)
    telefone_indicado = models.CharField(max_length=20)
    cpf_indicado = models.CharField(max_length=14, blank=True)
    cidade_indicado = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', db_index=True)
    membro_indicado = models.ForeignKey(
        'clube.MembroClube', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='indicacao_recebida'
    )
    pontos_creditados = models.BooleanField(default=False)
    data_indicacao = models.DateTimeField(auto_now_add=True)
    data_conversao = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.membro_indicador.nome} indicou {self.nome_indicado}"

    class Meta:
        verbose_name = "Indicação"
        verbose_name_plural = "Indicações"
        db_table = 'indicacoes_indicacao'
        ordering = ['-data_indicacao']
        unique_together = ['membro_indicador', 'telefone_indicado']
