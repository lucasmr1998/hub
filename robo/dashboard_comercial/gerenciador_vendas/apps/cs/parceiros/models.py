from django.db import models
from django.contrib.auth.models import User
from apps.sistema.mixins import TenantMixin
from apps.sistema.validators import tenant_upload_path


class CategoriaParceiro(TenantMixin):
    """Categoria para agrupar parceiros (ex: Alimentacao, Beleza, Esporte)."""
    nome = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icone = models.CharField(max_length=50, default='fas fa-tag', help_text="Classe FontAwesome")
    ordem = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Categoria de Parceiro"
        verbose_name_plural = "Categorias de Parceiros"
        ordering = ['ordem', 'nome']
        db_table = 'parceiros_categoriaparceiro'


class Parceiro(TenantMixin):
    nome = models.CharField(max_length=255)
    logo = models.ImageField(upload_to=tenant_upload_path, null=True, blank=True)
    descricao = models.TextField(blank=True)
    contato_nome = models.CharField(max_length=255, blank=True)
    contato_telefone = models.CharField(max_length=20, blank=True)
    contato_email = models.EmailField(blank=True)
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='parceiro', help_text="Usuário Django vinculado para acesso ao painel")
    categoria = models.ForeignKey(CategoriaParceiro, on_delete=models.SET_NULL, null=True, blank=True, related_name='parceiros')
    cidades = models.ManyToManyField('clube.Cidade', blank=True, related_name='parceiros')
    ativo = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Parceiro"
        verbose_name_plural = "Parceiros"
        ordering = ['nome']
        db_table = 'parceiros_parceiro'


class CupomDesconto(TenantMixin):
    TIPO_DESCONTO = [
        ('percentual', 'Percentual (%)'),
        ('fixo', 'Valor Fixo (R$)'),
    ]
    MODALIDADE_CHOICES = [
        ('gratuito', 'Gratuito'),
        ('pontos', 'Custo em Pontos'),
        ('nivel', 'Bônus de Nível'),
    ]

    parceiro = models.ForeignKey(Parceiro, on_delete=models.CASCADE, related_name='cupons')
    titulo = models.CharField(max_length=255, help_text="Ex: 20% off no Restaurante X")
    descricao = models.TextField(blank=True)
    imagem = models.ImageField(upload_to=tenant_upload_path, null=True, blank=True)
    codigo = models.CharField(max_length=50, unique=True)
    tipo_desconto = models.CharField(max_length=15, choices=TIPO_DESCONTO)
    valor_desconto = models.DecimalField(max_digits=10, decimal_places=2)
    modalidade = models.CharField(max_length=15, choices=MODALIDADE_CHOICES, default='gratuito')
    custo_pontos = models.IntegerField(default=0, help_text="Usado quando modalidade = Pontos")
    nivel_minimo = models.ForeignKey(
        'clube.NivelClube', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Usado quando modalidade = Nível"
    )
    quantidade_total = models.IntegerField(default=0, help_text="0 = ilimitado")
    quantidade_resgatada = models.IntegerField(default=0)
    limite_por_membro = models.IntegerField(default=1)
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField(db_index=True)
    cidades_permitidas = models.ManyToManyField('clube.Cidade', blank=True, related_name='cupons')
    STATUS_APROVACAO = [
        ('aprovado', 'Aprovado'),
        ('pendente', 'Aguardando Aprovação'),
        ('rejeitado', 'Rejeitado'),
    ]
    ativo = models.BooleanField(default=True, db_index=True)
    status_aprovacao = models.CharField(max_length=15, choices=STATUS_APROVACAO, default='aprovado', db_index=True, help_text="Cupons solicitados por parceiros ficam pendentes até aprovação")
    motivo_rejeicao = models.TextField(blank=True, help_text="Motivo da rejeição (preenchido pelo admin)")
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titulo} ({self.parceiro.nome})"

    @property
    def estoque_disponivel(self):
        if self.quantidade_total == 0:
            return True
        return self.quantidade_resgatada < self.quantidade_total

    @property
    def estoque_restante(self):
        if self.quantidade_total == 0:
            return "Ilimitado"
        return self.quantidade_total - self.quantidade_resgatada

    class Meta:
        verbose_name = "Cupom de Desconto"
        verbose_name_plural = "Cupons de Desconto"
        ordering = ['-data_cadastro']
        db_table = 'parceiros_cupomdesconto'


class ResgateCupom(TenantMixin):
    STATUS_CHOICES = [
        ('resgatado', 'Resgatado'),
        ('utilizado', 'Utilizado'),
        ('expirado', 'Expirado'),
        ('cancelado', 'Cancelado'),
    ]

    membro = models.ForeignKey('clube.MembroClube', on_delete=models.CASCADE, related_name='resgates_cupom')
    cupom = models.ForeignKey(CupomDesconto, on_delete=models.CASCADE, related_name='resgates')
    codigo_unico = models.CharField(max_length=20, unique=True)
    pontos_gastos = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='resgatado', db_index=True)
    valor_compra = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Valor total da compra no estabelecimento")
    data_resgate = models.DateTimeField(auto_now_add=True, db_index=True)
    data_utilizacao = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.membro.nome} - {self.cupom.titulo} ({self.codigo_unico})"

    class Meta:
        verbose_name = "Resgate de Cupom"
        verbose_name_plural = "Resgates de Cupom"
        ordering = ['-data_resgate']
        db_table = 'parceiros_resgatecupom'
