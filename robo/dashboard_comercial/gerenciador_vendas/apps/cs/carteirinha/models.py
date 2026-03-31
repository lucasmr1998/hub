from django.db import models
from apps.sistema.mixins import TenantMixin
from apps.sistema.validators import tenant_upload_path


class ModeloCarteirinha(TenantMixin):
    """Modelo visual de carteirinha. Admin cria varios e atribui por regra."""
    TIPO_FUNDO_CHOICES = [
        ('cor', 'Cores / Gradiente'),
        ('imagem', 'Imagem de Fundo'),
    ]

    nome = models.CharField(max_length=100, help_text="Nome interno do modelo (ex: Cartao Ouro)")
    descricao = models.TextField(blank=True)

    # Visual — Fundo
    tipo_fundo = models.CharField(max_length=10, choices=TIPO_FUNDO_CHOICES, default='cor')
    cor_fundo_primaria = models.CharField(max_length=7, default='#000b4a', help_text="Cor primaria do fundo (ou inicio do gradiente)")
    cor_fundo_secundaria = models.CharField(max_length=7, default='#1a2d4a', help_text="Cor secundaria (fim do gradiente). Igual a primaria = cor solida")
    imagem_fundo = models.ImageField(upload_to=tenant_upload_path, null=True, blank=True, help_text="Imagem de fundo (600x380px). Usado quando tipo_fundo = imagem")

    # Visual — Cores de texto e elementos
    cor_texto = models.CharField(max_length=7, default='#ffffff', help_text="Cor do texto principal")
    cor_texto_secundario = models.CharField(max_length=7, default='#94a3b8', help_text="Cor do texto secundario (labels)")
    cor_destaque = models.CharField(max_length=7, default='#fbbf24', help_text="Cor de destaque (nivel, badges)")

    # Visual — Logo e decoracao
    logo = models.ImageField(upload_to=tenant_upload_path, null=True, blank=True, help_text="Logo exibido no cartao")
    texto_marca = models.CharField(max_length=100, default='Clube Megalink', help_text="Texto da marca (usado se nao tiver logo)")

    # Campos visiveis (configuravel)
    mostrar_nome = models.BooleanField(default=True)
    mostrar_cpf = models.BooleanField(default=True)
    mostrar_nivel = models.BooleanField(default=True)
    mostrar_data_emissao = models.BooleanField(default=True)
    mostrar_data_validade = models.BooleanField(default=False)
    mostrar_qr_code = models.BooleanField(default=True, help_text="QR Code com link de validacao")
    mostrar_foto = models.BooleanField(default=False, help_text="Exibir foto do membro")
    mostrar_pontos = models.BooleanField(default=False)
    mostrar_cidade = models.BooleanField(default=False)

    # Texto customizavel
    texto_rodape = models.CharField(max_length=255, blank=True, default='um clube filiado', help_text="Texto pequeno no rodape")

    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Modelo de Carteirinha"
        verbose_name_plural = "Modelos de Carteirinha"
        db_table = 'carteirinha_modelocarteirinha'
        ordering = ['nome']


class RegraAtribuicao(TenantMixin):
    """Define qual modelo de carteirinha e atribuido a quem."""
    TIPO_CHOICES = [
        ('nivel', 'Por Nível'),
        ('pontuacao_minima', 'Por Pontuação Mínima'),
        ('cidade', 'Por Cidade'),
        ('todos', 'Todos os Membros'),
        ('manual', 'Atribuição Manual'),
    ]

    modelo = models.ForeignKey(ModeloCarteirinha, on_delete=models.CASCADE, related_name='regras')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nivel = models.ForeignKey('clube.NivelClube', on_delete=models.SET_NULL, null=True, blank=True, help_text="Usado quando tipo = nivel")
    pontuacao_minima = models.IntegerField(default=0, help_text="Usado quando tipo = pontuacao_minima (XP minimo)")
    cidade = models.CharField(max_length=100, blank=True, help_text="Usado quando tipo = cidade")
    prioridade = models.IntegerField(default=0, help_text="Maior prioridade vence quando membro se encaixa em varias regras")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        if self.tipo == 'nivel':
            return f"{self.modelo.nome} → Nível {self.nivel.nome if self.nivel else '?'}"
        elif self.tipo == 'pontuacao_minima':
            return f"{self.modelo.nome} → XP >= {self.pontuacao_minima}"
        elif self.tipo == 'cidade':
            return f"{self.modelo.nome} → {self.cidade}"
        elif self.tipo == 'todos':
            return f"{self.modelo.nome} → Todos"
        else:
            return f"{self.modelo.nome} → Manual"

    class Meta:
        verbose_name = "Regra de Atribuição"
        verbose_name_plural = "Regras de Atribuição"
        db_table = 'carteirinha_regraatribuicao'
        ordering = ['-prioridade']


class CarteirinhaMembro(TenantMixin):
    """Carteirinha emitida para um membro (atribuicao manual ou cache da automatica)."""
    membro = models.ForeignKey('clube.MembroClube', on_delete=models.CASCADE, related_name='carteirinhas')
    modelo = models.ForeignKey(ModeloCarteirinha, on_delete=models.CASCADE, related_name='emissoes')
    foto = models.ImageField(upload_to=tenant_upload_path, null=True, blank=True)
    data_emissao = models.DateTimeField(auto_now_add=True)
    data_validade = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.membro.nome} — {self.modelo.nome}"

    class Meta:
        verbose_name = "Carteirinha do Membro"
        verbose_name_plural = "Carteirinhas dos Membros"
        db_table = 'carteirinha_carteirinhamembro'
        ordering = ['-data_emissao']
