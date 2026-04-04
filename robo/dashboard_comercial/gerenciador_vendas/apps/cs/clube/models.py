from django.db import models
from apps.sistema.mixins import TenantMixin

class Cidade(TenantMixin):
    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        ordering = ['nome']
        db_table = 'roleta_cidade'
        unique_together = ('tenant', 'nome')

class PremioRoleta(TenantMixin):
    nome = models.CharField(max_length=255)
    quantidade = models.IntegerField(default=0)
    posicoes = models.CharField(max_length=50, help_text="Posições na roleta (ex: 4,7)", default="1")
    probabilidade = models.IntegerField(default=1, help_text="Peso da probabilidade (ex: 1 para raro, 10 para comum)")
    mensagem_vitoria = models.TextField(blank=True, help_text="Mensagem que aparecerá no alerta ao ganhar este prêmio.", default="Você ganhou um prêmio!")
    cidades_permitidas = models.ManyToManyField(Cidade, blank=True, related_name="premios", help_text="Selecione as cidades permitidas. Se deixar vazio, o prêmio valerá para QUALQUER cidade.")

    def __str__(self):
        cidades = ", ".join([c.nome for c in self.cidades_permitidas.all()]) if self.id and self.cidades_permitidas.exists() else "Todas"
        return f"{self.nome} ({cidades}) - {self.quantidade} restando"

    class Meta:
        verbose_name = "Prêmio da Roleta"
        verbose_name_plural = "Prêmios da Roleta"
        db_table = 'roleta_premioroleta'

class RouletteAsset(TenantMixin):
    ASSET_TYPES = [
        ('frame', 'Frame da Roleta'),
        ('background', 'Fundo da Página'),
        ('logo', 'Logo Central'),
        ('pointer', 'Ponteiro/Seta'),
    ]
    tipo = models.CharField(max_length=20, choices=ASSET_TYPES, default='frame')
    ordem = models.IntegerField(default=0, help_text="0-12 para frames")
    imagem = models.ImageField(upload_to='roleta/assets/')
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo', 'ordem']
        verbose_name = "Asset da Roleta"
        verbose_name_plural = "Assets da Roleta"
        db_table = 'roleta_rouletteasset'

class RoletaConfig(TenantMixin):
    PERIODO_CHOICES = [
        ('total',   'Total (para sempre)'),
        ('diario',  'Diário (por dia corrido)'),
        ('semanal', 'Semanal (últimos 7 dias)'),
        ('mensal',  'Mensal (mês atual)'),
    ]

    custo_giro = models.IntegerField(default=10, help_text="Pontos necessários para girar a roleta")
    xp_por_giro = models.IntegerField(default=5, help_text="Quantidade de XP ganha a cada giro da roleta")
    nome_clube = models.CharField(max_length=100, default="Clube MegaLink")
    limite_giros_por_membro = models.IntegerField(
        default=0,
        help_text="Número máximo de giros permitidos por pessoa. Use 0 para sem limite."
    )
    periodo_limite = models.CharField(
        max_length=10,
        choices=PERIODO_CHOICES,
        default='total',
        help_text="Janela de tempo usada para contar os giros de cada membro."
    )

    def __str__(self):
        return f"Configurações do {self.nome_clube}"

    class Meta:
        verbose_name = "Configuração da Roleta"
        verbose_name_plural = "Configurações da Roleta"
        db_table = 'roleta_roletaconfig'

class NivelClube(TenantMixin):
    nome = models.CharField(max_length=50, help_text="Ex: Bronze, Prata, Ouro")
    xp_necessario = models.IntegerField(default=0, help_text="XP mínimo para alcançar este nível")
    ordem = models.IntegerField(default=1, help_text="Ordem de exibição (1 é o mais baixo)")

    def __str__(self):
        return f"Nível {self.ordem}: {self.nome} ({self.xp_necessario} XP)"

    class Meta:
        ordering = ['ordem']
        verbose_name = "Nível do Clube"
        verbose_name_plural = "Níveis do Clube"
        db_table = 'roleta_nivelclube'


class MembroClube(TenantMixin):
    nome = models.CharField(max_length=255)
    cpf = models.CharField(max_length=14)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    cep = models.CharField(max_length=10, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    bairro = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    saldo = models.IntegerField(default=0, help_text="Saldo acumulado de pontos (Giros)")
    xp_total = models.IntegerField(default=0, help_text="Experiência acumulada (Define o Nível)")
    data_cadastro = models.DateTimeField(auto_now_add=True)
    id_cliente_hubsoft = models.IntegerField(null=True, blank=True, db_index=True)
    validado = models.BooleanField(default=False, db_index=True, help_text="Se o membro já validou o OTP")
    codigo_indicacao = models.CharField(max_length=10, blank=True, null=True, help_text="Código único para link de indicação")

    def save(self, *args, **kwargs):
        if not self.codigo_indicacao:
            import uuid
            self.codigo_indicacao = uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    @property
    def nivel_atual(self):
        nivel = NivelClube.objects.filter(xp_necessario__lte=self.xp_total).order_by('-xp_necessario').first()
        return nivel.nome if nivel else "Iniciante"

    @property
    def proximo_nivel(self):
        prox = NivelClube.objects.filter(xp_necessario__gt=self.xp_total).order_by('xp_necessario').first()
        return prox

    def __str__(self):
        return f"{self.nome} ({self.cpf})"

    class Meta:
        verbose_name = "Membro do Clube"
        verbose_name_plural = "Membros do Clube"
        db_table = 'roleta_membroclube'
        unique_together = ('tenant', 'cpf')

class RegraPontuacao(TenantMixin):
    gatilho = models.CharField(max_length=50, help_text="Identificador único (ex: cadastro, indicacao)")
    nome_exibicao = models.CharField(max_length=100, help_text="Ex: Bônus de Boas Vindas")
    pontos_saldo = models.IntegerField(default=0, help_text="Quantos Giros/Saldo a pessoa ganha")
    pontos_xp = models.IntegerField(default=0, help_text="Quanto XP a pessoa ganha")
    limite_por_membro = models.IntegerField(default=1, help_text="Quantas vezes um mesmo membro pode ganhar? (0 para iimitado)")
    ativo = models.BooleanField(default=True, db_index=True)
    visivel_na_roleta = models.BooleanField(default=True, help_text="Se marcado, esta missão aparecerá na lista da roleta para o usuário.")

    def __str__(self):
        return f"{self.nome_exibicao} ({self.pontos_saldo} Saldo | {self.pontos_xp} XP)"

    class Meta:
        verbose_name = "Regra de Pontuação"
        verbose_name_plural = "Regras de Pontuação"
        db_table = 'roleta_regrapontuacao'
        unique_together = ('tenant', 'gatilho')

class ExtratoPontuacao(TenantMixin):
    membro = models.ForeignKey(MembroClube, on_delete=models.CASCADE, related_name='extratos')
    regra = models.ForeignKey(RegraPontuacao, on_delete=models.CASCADE)
    pontos_saldo_ganhos = models.IntegerField(default=0)
    pontos_xp_ganhos = models.IntegerField(default=0)
    descricao_extra = models.CharField(max_length=255, null=True, blank=True, help_text="Ex: Indicou CPF 123456789")
    data_recebimento = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.membro.nome} - {self.regra.nome_exibicao} ({self.data_recebimento.strftime('%d/%m/%Y')})"

    class Meta:
        verbose_name = "Extrato de Pontuação"
        verbose_name_plural = "Extratos de Pontuação"
        db_table = 'roleta_extratopontuacao'


class ParticipanteRoleta(TenantMixin):
    STATUS_CHOICES = [
        ('reservado', 'Reservado'),
        ('ganhou', 'Ganhou'),
        ('inviavel_tec', 'Inviável Tecnicamente'),
        ('inviavel_cani', 'Inviável Cani'),
    ]

    membro = models.ForeignKey(MembroClube, on_delete=models.CASCADE, related_name='giros', null=True, blank=True)
    nome = models.CharField(max_length=255, null=True, blank=True)
    cpf = models.CharField(max_length=14)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    cep = models.CharField(max_length=10, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    bairro = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    premio = models.CharField(max_length=255)
    canal_origem = models.CharField(max_length=100, default='Online')
    perfil_cliente = models.CharField(max_length=10, default='nao')
    id_cliente_hubsoft = models.IntegerField(null=True, blank=True)
    saldo = models.IntegerField(default=0, help_text="Saldo de pontos do membro")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='reservado', db_index=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.premio}"

    class Meta:
        verbose_name = "Participante da Roleta"
        verbose_name_plural = "Participantes da Roleta"
        db_table = 'roleta_participanteroleta'


class BannerClube(TenantMixin):
    """Banners rotativos da landing page publica."""
    titulo = models.CharField(max_length=200, blank=True)
    imagem = models.ImageField(upload_to='banners/')
    link = models.URLField(blank=True, help_text="URL ao clicar no banner (opcional)")
    ordem = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo or f'Banner #{self.id}'

    class Meta:
        verbose_name = "Banner"
        verbose_name_plural = "Banners"
        ordering = ['ordem']
        db_table = 'roleta_bannerclube'


class LandingConfig(TenantMixin):
    """Configuracao da pagina publica do clube (singleton)."""
    titulo = models.CharField(max_length=200, default='Clube Megalink')
    subtitulo = models.CharField(max_length=300, default='Seu programa de fidelidade')
    whatsapp_numero = models.CharField(max_length=20, blank=True, help_text="Numero com DDD (ex: 5586999999999)")
    whatsapp_mensagem = models.CharField(max_length=300, default='Quero participar do Clube Megalink!')
    texto_como_funciona = models.TextField(blank=True, help_text="Texto da secao Como Funciona (markdown)")
    texto_rodape = models.CharField(max_length=300, blank=True)
    cor_primaria = models.CharField(max_length=10, default='#000b4a')
    cor_secundaria = models.CharField(max_length=10, default='#f59e0b')
    logo = models.ImageField(upload_to='landing/', blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Configuracao Landing Page"
        verbose_name_plural = "Configuracao Landing Page"
        db_table = 'roleta_landingconfig'
