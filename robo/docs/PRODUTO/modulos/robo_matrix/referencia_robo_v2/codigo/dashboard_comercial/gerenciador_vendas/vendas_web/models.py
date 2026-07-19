from django.db import models
from django.core.validators import RegexValidator, EmailValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import timedelta, time

# Adicionar campo telefone ao modelo User
User.add_to_class('telefone', models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone"))


class LeadProspecto(models.Model):
    """
    Modelo para armazenar informações de leads e prospectos
    """
    STATUS_API_CHOICES = [
        ('pendente', 'Pendente'),
        ('processado', 'Processado'),
        ('erro', 'Erro'),
        ('sucesso', 'Sucesso'),
        ('rejeitado', 'Rejeitado'),
        ('aguardando_retry', 'Aguardando Retry'),
        ('processamento_manual', 'Processamento Manual'),
        # Status de pipeline CRM
        ('aguardando_assinatura', 'Aguardando Assinatura'),
        ('em_instalacao', 'Em Instalação'),
        ('instalado', 'Instalado'),
        ('cancelado', 'Cancelado'),
        ('inativo', 'Inativo'),
    ]
    
    ORIGEM_CHOICES = [
        ('site', 'Site'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('google', 'Google Ads'),
        ('whatsapp', 'WhatsApp'),
        ('indicacao', 'Indicação'),
        ('wifeed', 'Wifeed'),
        ('telefone', 'Telefone'),
        ('email', 'Email'),
        ('outros', 'Outros'),
    ]
    
    TIPO_ENTRADA_CHOICES = [
        ('contato_whatsapp', 'Contato WhatsApp'),
        ('cadastro_site', 'Cadastro Site'),
        ('telefone', 'Telefone'),
        ('formulario', 'Formulário'),
        ('importacao', 'Importação'),
        ('api_externa', 'API Externa'),
    ]
    
    # Campos principais
    nome_razaosocial = models.CharField(
        max_length=255,
        verbose_name="Nome/Razão Social",
        help_text="Nome completo ou razão social do cliente"
    )

    nome_confirmado = models.BooleanField(
        default=False,
        verbose_name="Nome confirmado",
        help_text="True quando o nome foi COLETADO pelo fluxo (coleta_nome) ou "
                  "digitado pelo operador — nome pré-preenchido (push name do "
                  "WhatsApp) NÃO conta: o robô sempre pergunta o nome completo.",
    )


    email = models.EmailField(
        max_length=255,
        validators=[EmailValidator()],
        verbose_name="Email",
        help_text="Email válido do cliente",
        null=True,
        blank=True
    )
    
    telefone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Telefone deve estar no formato: '+999999999'. Até 15 dígitos permitidos."
    )
    telefone = models.CharField(
        validators=[telefone_validator],
        max_length=17,
        verbose_name="Telefone",
        help_text="Telefone de contato"
    )
    
    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        verbose_name="Valor",
        help_text="Valor em reais associado ao lead"
    )
    
    empresa = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Empresa",
        help_text="Nome da empresa do cliente"
    )
    
    origem = models.CharField(
        max_length=50,
        choices=ORIGEM_CHOICES,
        default='site',
        verbose_name="Origem",
        help_text="Canal de origem do lead"
    )
    
    data_cadastro = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Cadastro",
        help_text="Data e hora do cadastro"
    )
    
    status_api = models.CharField(
        max_length=30,
        default='pendente',
        verbose_name="Status API",
        help_text="Status do processamento na API"
    )
    
    # Identificador no Hubsoft para cruzamento automático com Prospecto
    id_hubsoft = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID Hubsoft",
        help_text="Identificador do lead no Hubsoft para relacionar automaticamente com prospectos",
        db_index=True,
    )
    
    # Identificador da origem externa do lead
    id_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID Origem",
        help_text="Identificador único do lead no sistema de origem (Facebook Ads, Google Ads, etc)",
        db_index=True,
    )
    
    # Identificador do serviço de origem do lead
    id_origem_servico = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID Origem Serviço",
        help_text="Identificador do serviço específico de origem do lead",
        db_index=True,
    )
    
    # Campos adicionais para completar o modelo
    cpf_cnpj = models.CharField(
        max_length=18,
        null=True,
        blank=True,
        verbose_name="CPF/CNPJ",
        help_text="CPF ou CNPJ do cliente"
    )
    
    rg = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        verbose_name="RG",
        help_text="Número do RG do cliente"
    )
    
    endereco = models.TextField(
        null=True,
        blank=True,
        verbose_name="Endereço",
        help_text="Endereço completo do cliente"
    )
    
    rua = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Rua",
        help_text="Logradouro do endereço"
    )
    
    numero_residencia = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Número da Residência",
        help_text="Número do endereço"
    )
    
    bairro = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        verbose_name="Bairro",
        help_text="Bairro do endereço"
    )
    
    cidade = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Cidade"
    )
    
    estado = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        verbose_name="Estado",
        help_text="UF do estado"
    )
    
    cep = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="CEP"
    )
    
    ponto_referencia = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Ponto de Referência",
        help_text="Ponto de referência para facilitar a localização"
    )

    # Dados adicionais de relacionamento com RP/Comercial
    id_plano_rp = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID Plano (RP)",
        help_text="Identificador do plano no sistema RP"
    )
    
    id_dia_vencimento = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID Dia de Vencimento",
        help_text="Identificador do dia de vencimento no RP"
    )
    
    id_vendedor_rp = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ID Vendedor (RP)",
        help_text="Identificador do vendedor no sistema RP"
    )
    
    data_nascimento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Nascimento"
    )
    
    observacoes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações",
        help_text="Observações adicionais sobre o lead"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )

    data_ultima_tentativa_sync_hubsoft = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Última tentativa de sync Hubsoft",
        help_text="Atualizado a cada tentativa de sincronizar com Hubsoft (sucesso ou não)",
    )
    data_primeira_tentativa_sync_hubsoft = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Primeira tentativa de sync Hubsoft",
        help_text="Set apenas na 1ª tentativa. Usado pra liberar uma janela de 15min de "
                  "retries antes de aplicar o backoff longo (6h) em leads não encontrados.",
    )

    # ── Campos do fluxo dinâmico de venda (coletados pela IA) ──
    tipo_imovel = models.CharField(
        max_length=20, blank=True,
        choices=[('casa', 'Casa / Residencial'), ('empresa', 'Empresa / Comercial')],
        verbose_name='Tipo do imóvel',
        help_text='Coletado pela regra `tipo_imovel` no fluxo de vendas',
    )
    turno_instalacao = models.CharField(
        max_length=10, blank=True,
        choices=[('manha', 'Manhã'), ('tarde', 'Tarde')],
        verbose_name='Turno de instalação',
        help_text='Coletado pela regra `escolha_turno`',
    )
    data_instalacao = models.DateField(
        null=True, blank=True,
        verbose_name='Data de instalação',
        help_text='Coletado pela regra `escolha_data` (data escolhida pelo cliente)',
    )
    endereco_confirmado = models.BooleanField(
        null=True, blank=True,
        verbose_name='Endereço confirmado pelo cliente',
        help_text='True=confirmou ViaCEP; False=precisa preencher manualmente; None=ainda não perguntou',
    )
    doc_selfie_recebida = models.BooleanField(
        null=True, blank=True, default=None,
        verbose_name='Selfie com documento recebida',
        help_text='True=upload feito; None=ainda não solicitado',
    )
    doc_frente_recebida = models.BooleanField(
        null=True, blank=True, default=None,
        verbose_name='Frente do documento recebida',
        help_text='True=upload feito; None=ainda não solicitado',
    )
    doc_verso_recebida = models.BooleanField(
        null=True, blank=True, default=None,
        verbose_name='Verso do documento recebida',
        help_text='True=upload feito; None=ainda não solicitado',
    )
    dados_confirmados = models.BooleanField(
        null=True, blank=True,
        verbose_name='Dados finais confirmados pelo cliente',
        help_text='True=confirmou tudo; False=negou (transbordo); None=ainda não perguntou',
    )
    plano_confirmado = models.BooleanField(
        null=True, blank=True,
        verbose_name='Plano confirmado pelo cliente',
        help_text='True=confirmou após ver descrição; False=negou (volta a perguntar); '
                  'None=ainda não perguntou',
    )
    tipo_residencia = models.CharField(
        max_length=20, blank=True, default='',
        choices=[
            ('casa_terrea',  'Casa térrea / Sobrado'),
            ('apartamento',  'Apartamento'),
            ('condominio',   'Condomínio fechado'),
        ],
        verbose_name='Tipo de residência',
        help_text='Sub-tipo de imóvel residencial (só relevante se tipo_imovel=casa). '
                  'Determina quais detalhes pedir no complemento de endereço.',
    )
    tipo_ajuste = models.CharField(
        max_length=20, blank=True, default='',
        choices=[
            ('endereco', 'Endereço'),
            ('dados_pessoais', 'Dados pessoais'),
            ('plano', 'Plano selecionado'),
        ],
        verbose_name='Tipo de ajuste solicitado',
        help_text='Setado quando cliente nega dados_confirmados e indica o que quer corrigir. '
                  'Após API limpar os campos correspondentes, é zerado.',
    )

    # Novos campos para rastreamento melhorado
    canal_entrada = models.CharField(
        max_length=50,
        choices=ORIGEM_CHOICES,
        null=True,
        blank=True,
        verbose_name="Canal de Entrada",
        help_text="Canal por onde o lead entrou no sistema"
    )
    
    tipo_entrada = models.CharField(
        max_length=50,
        choices=TIPO_ENTRADA_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo de Entrada",
        help_text="Tipo específico de entrada no sistema"
    )

    # Código único de quem indicou este lead (pipeline de Indicações, operado
    # manualmente pelos operadores). Preenchido quando canal_entrada='indicacao'.
    id_indicador = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        verbose_name="ID do Indicador",
        help_text="Código único que identifica quem indicou este lead"
    )

    # Campos de Campanhas de Tráfego Pago
    campanha_origem = models.ForeignKey(
        'CampanhaTrafego',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_origem',
        verbose_name="Campanha de Origem",
        help_text="Campanha pela qual o lead entrou pela primeira vez"
    )
    
    campanha_conversao = models.ForeignKey(
        'CampanhaTrafego',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_convertidos',
        verbose_name="Campanha de Conversão",
        help_text="Campanha ativa quando o lead converteu em cliente"
    )
    
    total_campanhas_detectadas = models.IntegerField(
        default=0,
        verbose_name="Total de Campanhas Detectadas",
        help_text="Contador de quantas campanhas foram detectadas para este lead"
    )
    
    metadata_campanhas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadata de Campanhas",
        help_text="Dados adicionais sobre campanhas detectadas"
    )
    
    score_qualificacao = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Score de Qualificação",
        help_text="Score de 1 a 10 baseado na qualificação do lead"
    )
    
    tentativas_contato = models.PositiveIntegerField(
        default=0,
        verbose_name="Tentativas de Contato",
        help_text="Número de tentativas de contato realizadas"
    )
    
    data_ultimo_contato = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data do Último Contato"
    )
    
    motivo_rejeicao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Motivo da Rejeição",
        help_text="Motivo detalhado caso tenha sido rejeitado"
    )
    
    custo_aquisicao = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Custo de Aquisição",
        help_text="Custo investido para adquirir este lead"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Indica se o lead está ativo"
    )
    
    # Campos para documentação
    documentacao_completa = models.BooleanField(
        default=False,
        verbose_name="Documentação Completa",
        help_text="Indica se toda documentação foi enviada"
    )
    
    documentacao_validada = models.BooleanField(
        default=False,
        verbose_name="Documentação Validada",
        help_text="Indica se a documentação foi validada"
    )
    
    data_documentacao_completa = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Documentação Completa"
    )
    
    data_documentacao_validada = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Documentação Validada"
    )
    
    # Campos para controle de contrato
    contrato_aceito = models.BooleanField(
        default=False,
        verbose_name="Contrato Aceito",
        help_text="Indica se o contrato foi aceito"
    )
    
    data_aceite_contrato = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Aceite do Contrato"
    )
    
    ip_aceite_contrato = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Aceite do Contrato"
    )

    # ── PDF da conversa ──────────────────────────────────────────────────
    # Gerado automaticamente quando todos os documentos forem validados.
    # A URL usa codigo_atendimento e protocolo_atendimento do HistoricoContato mais recente.
    url_pdf_conversa = models.URLField(
        max_length=1024,
        null=True,
        blank=True,
        verbose_name="URL PDF da Conversa",
        help_text="Link do PDF da conversa gerado após validação dos documentos",
    )
    data_geracao_pdf = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Geração do PDF",
    )
    html_conversa_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Caminho HTML da Conversa",
        help_text="Caminho relativo do arquivo HTML gerado do atendimento",
    )
    data_geracao_html = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Geração do HTML",
    )
    anexos_contrato_enviados = models.BooleanField(
        default=False,
        verbose_name="Anexos do Contrato Enviados",
        help_text="Indica se os documentos e o HTML do atendimento foram anexados ao contrato no HubSoft",
    )

    PDF_BASE_URL = 'https://megalink.matrixdobrasil.ai/atendimento/export-to-pdf/id/{codigo}/protocolo/{protocolo}'

    def gerar_url_pdf(self):
        """
        Busca o HistoricoContato mais recente do lead que tenha codigo_atendimento
        e protocolo_atendimento preenchidos, monta e salva a URL do PDF.
        """
        contato = self.historico_contatos.filter(
            codigo_atendimento__isnull=False,
            protocolo_atendimento__isnull=False,
        ).exclude(
            codigo_atendimento='',
            protocolo_atendimento='',
        ).order_by('-data_hora_contato').first()

        if not contato:
            return None

        url = self.PDF_BASE_URL.format(
            codigo=contato.codigo_atendimento,
            protocolo=contato.protocolo_atendimento,
        )
        self.url_pdf_conversa = url
        self.data_geracao_pdf = timezone.now()
        self.save(update_fields=['url_pdf_conversa', 'data_geracao_pdf'])
        return url

    class Meta:
        db_table = 'leads_prospectos'
        verbose_name = "Lead/Prospecto"
        verbose_name_plural = "📊 01. Leads/Prospectos"
        ordering = ['-data_cadastro']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['telefone']),
            models.Index(fields=['data_cadastro']),
            models.Index(fields=['status_api']),
            models.Index(fields=['origem']),
            models.Index(fields=['id_hubsoft']),
            models.Index(fields=['id_origem']),
            models.Index(fields=['id_origem_servico']),
            # Novos índices para campos adicionados
            models.Index(fields=['canal_entrada']),
            models.Index(fields=['tipo_entrada']),
            models.Index(fields=['score_qualificacao']),
            models.Index(fields=['data_ultimo_contato']),
            models.Index(fields=['tentativas_contato']),
            # Índices compostos para consultas mais eficientes
            models.Index(fields=['canal_entrada', 'data_cadastro']),
            models.Index(fields=['score_qualificacao', 'status_api']),
            models.Index(fields=['tipo_entrada', 'ativo']),
            models.Index(fields=['data_ultimo_contato', 'tentativas_contato']),
        ]
    
    def __str__(self):
        return f"{self.nome_razaosocial} - {self.email}"

    def get_status_api_display(self):  # compatível com chamadas existentes
        try:
            return StatusConfiguravel.get_label('lead_status_api', self.status_api)
        except Exception:
            # fallback para rótulo definido em STATUS_API_CHOICES se existir
            mapping = dict(self.STATUS_API_CHOICES)
            return mapping.get(self.status_api, self.status_api)
    
    def get_valor_formatado(self):
        """Retorna o valor formatado em reais"""
        if self.valor:
            return f"R$ {self.valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return "R$ 0,00"
    
    def get_historico_contatos_relacionados(self):
        """
        Retorna o histórico de contatos relacionados a este lead/prospecto
        Busca por telefone e também por relacionamento direto
        """
        contatos_diretos = self.historico_contatos.all()
        contatos_por_telefone = HistoricoContato.objects.filter(
            telefone=self.telefone
        ).exclude(
            id__in=contatos_diretos.values_list('id', flat=True)
        )
        
        # Combina os dois querysets e ordena por data
        from django.db.models import Q
        todos_contatos = HistoricoContato.objects.filter(
            Q(lead=self) | Q(telefone=self.telefone)
        ).distinct().order_by('-data_hora_contato')
        
        return todos_contatos
    
    def get_primeiro_contato(self):
        """Retorna o primeiro contato relacionado a este lead"""
        contatos = self.get_historico_contatos_relacionados()
        return contatos.last() if contatos.exists() else None
    
    def get_ultimo_contato(self):
        """Retorna o último contato relacionado a este lead"""
        contatos = self.get_historico_contatos_relacionados()
        return contatos.first() if contatos.exists() else None
    
    def get_total_contatos(self):
        """Retorna o número total de contatos relacionados"""
        return self.get_historico_contatos_relacionados().count()
    
    def get_contatos_bem_sucedidos(self):
        """Retorna contatos que tiveram sucesso (finalizaram fluxo ou foram transferidos)"""
        return self.get_historico_contatos_relacionados().filter(
            status__in=['fluxo_finalizado', 'transferido_humano', 'convertido_lead', 'venda_confirmada']
        )
    
    def get_taxa_sucesso_contatos(self):
        """Calcula a taxa de sucesso dos contatos deste lead"""
        total = self.get_total_contatos()
        if total == 0:
            return 0
        sucessos = self.get_contatos_bem_sucedidos().count()
        return (sucessos / total) * 100
    
    def marcar_como_convertido_de_contato(self, contato_id):
        """
        Marca um contato específico como convertido em lead
        e atualiza o relacionamento
        """
        try:
            contato = HistoricoContato.objects.get(id=contato_id)
            contato.lead = self
            contato.converteu_lead = True
            contato.data_conversao_lead = timezone.now()
            contato.status = 'convertido_lead'
            contato.save()
            return True
        except HistoricoContato.DoesNotExist:
            return False
    
    # Novos métodos de business logic
    def calcular_score_qualificacao(self):
        """
        Calcula score de qualificação baseado em dados do lead
        Retorna valor entre 1 e 10
        """
        score = 5  # Score base
        
        # Fatores que aumentam o score
        if self.empresa:
            score += 1
        if self.valor and self.valor > 1000:
            score += 1
        if self.origem in ['indicacao', 'telefone']:
            score += 1
        if self.get_total_contatos() > 0:
            score += 1
        if self.get_taxa_sucesso_contatos() > 50:
            score += 1
            
        # Fatores que diminuem o score
        if self.tentativas_contato > 3:
            score -= 1
        if self.status_api == 'erro':
            score -= 1
        if self.motivo_rejeicao:
            score -= 2
            
        # Garantir que o score esteja entre 1 e 10
        return max(1, min(10, score))
    
    def pode_reprocessar(self):
        """
        Verifica se o lead pode ser reprocessado
        """
        if not self.ativo:
            return False
        if self.status_api == 'sucesso':
            return False
        if self.tentativas_contato >= 5:
            return False
        return True
    
    def incrementar_tentativa_contato(self, observacoes=None):
        """
        Incrementa contador de tentativas e atualiza data do último contato
        """
        self.tentativas_contato += 1
        self.data_ultimo_contato = timezone.now()
        if observacoes and not self.observacoes:
            self.observacoes = observacoes
        elif observacoes:
            self.observacoes += f"\n{timezone.now().strftime('%d/%m/%Y %H:%M')}: {observacoes}"
        
        # Atualizar score após tentativa
        self.score_qualificacao = self.calcular_score_qualificacao()
        self.save()
    
    def definir_canal_entrada_automatico(self):
        """
        Define canal_entrada baseado na origem se não estiver definido
        """
        if not self.canal_entrada:
            self.canal_entrada = self.origem
            self.save()
    
    def get_custo_aquisicao_formatado(self):
        """Retorna o custo de aquisição formatado em reais"""
        if self.custo_aquisicao:
            return f"R$ {self.custo_aquisicao:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return "R$ 0,00"
    
    def get_score_qualificacao_display(self):
        """Retorna descrição textual do score de qualificação"""
        if not self.score_qualificacao:
            return "Não avaliado"
        
        score_descriptions = {
            (1, 3): "Baixa Qualificação",
            (4, 6): "Qualificação Média",
            (7, 8): "Boa Qualificação",
            (9, 10): "Excelente Qualificação"
        }
        
        for range_tuple, description in score_descriptions.items():
            if range_tuple[0] <= self.score_qualificacao <= range_tuple[1]:
                return description
        return "Qualificação não definida"
    
    def get_documentos_por_tipo(self):
        """Retorna documentos organizados por tipo"""
        documentos = {}
        for doc in self.documentos.all():
            tipo = doc.tipo_documento
            if tipo not in documentos:
                documentos[tipo] = []
            documentos[tipo].append(doc)
        return documentos
    
    def tem_documento_tipo(self, tipo):
        """Verifica se tem documento de um tipo específico"""
        return self.documentos.filter(tipo_documento=tipo).exists()
    
    def get_documento_mais_recente(self, tipo):
        """Retorna o documento mais recente de um tipo"""
        return self.documentos.filter(tipo_documento=tipo).order_by('-data_upload').first()
    
    def validar_documentacao_completa(self):
        """Verifica se tem todos os documentos necessários"""
        tipos_obrigatorios = ['selfie', 'doc_frente', 'doc_verso']
        for tipo in tipos_obrigatorios:
            if not self.tem_documento_tipo(tipo):
                return False
        
        self.documentacao_completa = True
        self.data_documentacao_completa = timezone.now()
        self.save()
        return True
    
    def aceitar_contrato(self, ip_address=None):
        """Registra aceite do contrato"""
        self.contrato_aceito = True
        self.data_aceite_contrato = timezone.now()
        if ip_address:
            self.ip_aceite_contrato = ip_address
        self.save()
        return True

class ImagemLeadProspecto(models.Model):
    """Imagens (URLs externas) vinculadas a um LeadProspecto."""

    STATUS_PENDENTE        = 'pendente'
    STATUS_APROVADO_IA     = 'aprovado_ia'   # IA aprovou — aguarda validação humana
    STATUS_VALIDO          = 'documentos_validos'
    STATUS_REJEITADO       = 'documentos_rejeitados'

    STATUS_VALIDACAO_CHOICES = [
        (STATUS_PENDENTE,    'Pendente'),
        (STATUS_APROVADO_IA, 'Aprovado pela IA (aguardando validação humana)'),
        (STATUS_VALIDO,      'Documentos Válidos'),
        (STATUS_REJEITADO,   'Documentos Rejeitados'),
    ]

    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.CASCADE,
        related_name='imagens',
        verbose_name="Lead",
    )
    link_url = models.URLField(
        max_length=1024,
        verbose_name="URL da Imagem",
    )
    descricao = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Descrição",
    )
    status_validacao = models.CharField(
        max_length=30,
        choices=STATUS_VALIDACAO_CHOICES,
        default=STATUS_PENDENTE,
        verbose_name="Status de Validação",
        db_index=True,
    )
    observacao_validacao = models.TextField(
        blank=True,
        default='',
        verbose_name="Observação da Validação",
    )
    data_validacao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data da Validação",
    )
    validado_por = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name="Validado por",
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação",
    )

    class Meta:
        db_table = 'imagens_lead_prospecto'
        verbose_name = "Imagem do Lead"
        verbose_name_plural = "Imagens do Lead"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['lead']),
        ]

    def __str__(self):
        return f"Imagem #{self.pk} — Lead {self.lead_id} [{self.status_validacao}]"

class Prospecto(models.Model):
    """
    Modelo para controle de processamento de prospectos
    """
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('processando', 'Processando'),
        ('processado', 'Processado'),
        ('erro', 'Erro'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
        # Novos status para validação
        ('aguardando_validacao', 'Aguardando Validação'),
        ('validacao_aprovada', 'Validação Aprovada'),
        ('validacao_rejeitada', 'Validação Rejeitada'),
    ]
    
    # Referência ao lead original (opcional)
    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='prospectos',
        verbose_name="Lead Relacionado"
    )
    
    nome_prospecto = models.CharField(
        max_length=255,
        verbose_name="Nome do Prospecto"
    )
    
    id_prospecto_hubsoft = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        verbose_name="ID Prospecto Hubsoft",
        help_text="ID único no sistema Hubsoft"
    )
    
    status = models.CharField(
        max_length=20,
        default='pendente',
        verbose_name="Status",
        help_text="Status atual do processamento"
    )
    
    data_criacao = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Criação"
    )
    
    data_processamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Processamento",
        help_text="Data e hora do último processamento"
    )
    
    tentativas_processamento = models.PositiveIntegerField(
        default=0,
        verbose_name="Tentativas de Processamento",
        help_text="Número de tentativas de processamento"
    )
    
    tempo_processamento = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Tempo de Processamento",
        help_text="Tempo de processamento em segundos"
    )
    
    erro_processamento = models.TextField(
        null=True,
        blank=True,
        verbose_name="Erro de Processamento",
        help_text="Detalhes do erro durante o processamento"
    )
    
    # Novos campos para controle melhorado
    data_inicio_processamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Início Processamento"
    )
    
    data_fim_processamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Fim Processamento"
    )
    
    usuario_processamento = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Usuário que Processou"
    )
    
    score_conversao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score de Conversão",
        help_text="Probabilidade de conversão calculada (0-100%)"
    )
    
    # Campos adicionais
    prioridade = models.PositiveIntegerField(
        default=1,
        verbose_name="Prioridade",
        help_text="Prioridade do processamento (1=baixa, 5=alta)"
    )
    
    dados_processamento = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Dados de Processamento",
        help_text="Dados JSON com informações do processamento"
    )
    
    resultado_processamento = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado do Processamento",
        help_text="Resultado JSON do processamento"
    )
    
    class Meta:
        db_table = 'prospectos'
        verbose_name = "Prospecto"
        verbose_name_plural = "📊 02. Prospectos"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['data_criacao']),
            models.Index(fields=['id_prospecto_hubsoft']),
            models.Index(fields=['tentativas_processamento']),
            # Novos índices para campos adicionados
            models.Index(fields=['data_inicio_processamento']),
            models.Index(fields=['data_fim_processamento']),
            models.Index(fields=['usuario_processamento']),
            models.Index(fields=['score_conversao']),
            # Índices compostos para consultas mais eficientes
            models.Index(fields=['status', 'data_inicio_processamento']),
            models.Index(fields=['prioridade', 'data_criacao']),
            models.Index(fields=['score_conversao', 'status']),
        ]
    
    def __str__(self):
        return f"{self.nome_prospecto} - {self.status}"

    def get_status_display(self):  # compatível com chamadas existentes
        try:
            return StatusConfiguravel.get_label('prospecto_status', self.status)
        except Exception:
            mapping = dict(self.STATUS_CHOICES)
            return mapping.get(self.status, self.status)
    
    def get_tempo_processamento_formatado(self):
        """Retorna o tempo de processamento formatado"""
        if self.tempo_processamento:
            if self.tempo_processamento < 60:
                return f"{self.tempo_processamento:.1f}s"
            else:
                minutos = int(self.tempo_processamento // 60)
                segundos = self.tempo_processamento % 60
                return f"{minutos}m {segundos:.1f}s"
        return "N/A"
    
    # Novos métodos de business logic
    def iniciar_processamento(self, usuario=None):
        """
        Marca início do processamento
        """
        self.status = 'processando'
        self.data_inicio_processamento = timezone.now()
        if usuario:
            self.usuario_processamento = usuario
        self.save()
    
    def finalizar_processamento(self, sucesso=True, erro=None, resultado=None):
        """
        Marca fim do processamento
        """
        self.data_fim_processamento = timezone.now()
        
        if sucesso:
            self.status = 'processado'
        else:
            self.status = 'erro'
            if erro:
                self.erro_processamento = erro
        
        if resultado:
            self.resultado_processamento = resultado
            
        # Calcular tempo de processamento
        if self.data_inicio_processamento:
            tempo_delta = self.data_fim_processamento - self.data_inicio_processamento
            self.tempo_processamento = tempo_delta.total_seconds()
            
        self.save()
    
    def calcular_tempo_processamento_total(self):
        """
        Calcula tempo total de processamento incluindo todas as tentativas
        """
        if self.data_inicio_processamento and self.data_fim_processamento:
            tempo_delta = self.data_fim_processamento - self.data_inicio_processamento
            return tempo_delta.total_seconds()
        return 0
    
    def pode_reprocessar(self):
        """
        Verifica se o prospecto pode ser reprocessado
        """
        return self.status in ['erro', 'pendente'] and self.tentativas_processamento < 3
    
    def incrementar_tentativa(self):
        """
        Incrementa tentativas de processamento
        """
        self.tentativas_processamento += 1
        self.save()
    
    def calcular_score_conversao_automatico(self):
        """
        Calcula score de conversão baseado nos dados disponíveis
        """
        if not self.lead:
            return 50.0  # Score padrão sem lead
            
        score = 50.0  # Base
        
        # Fatores do lead que influenciam conversão
        if self.lead.score_qualificacao:
            score += (self.lead.score_qualificacao - 5) * 5  # +/- 25 pontos baseado no score
            
        if self.lead.empresa:
            score += 10
            
        if self.lead.get_total_contatos() > 0:
            score += 15
            
        if self.lead.get_taxa_sucesso_contatos() > 70:
            score += 10
            
        # Fatores que diminuem
        if self.tentativas_processamento > 1:
            score -= self.tentativas_processamento * 5
            
        if self.status == 'erro':
            score -= 20
            
        return max(0, min(100, score))
    
    def atualizar_score_conversao(self):
        """
        Atualiza o score de conversão automaticamente
        """
        self.score_conversao = self.calcular_score_conversao_automatico()
        self.save()
    
    def get_score_conversao_display(self):
        """Retorna descrição textual do score de conversão"""
        if not self.score_conversao:
            return "Não calculado"
        
        if self.score_conversao >= 80:
            return f"{self.score_conversao:.1f}% - Muito Alta"
        elif self.score_conversao >= 60:
            return f"{self.score_conversao:.1f}% - Alta"
        elif self.score_conversao >= 40:
            return f"{self.score_conversao:.1f}% - Média"
        elif self.score_conversao >= 20:
            return f"{self.score_conversao:.1f}% - Baixa"
        else:
            return f"{self.score_conversao:.1f}% - Muito Baixa"

class HistoricoContato(models.Model):
    """
    Modelo para histórico de contatos/chamadas no funil de vendas
    Fluxo: Inicializado → Finalizado/Transferido → Lead/Prospecto → Venda
    """
    STATUS_CHOICES = [
        # Status principais do fluxo
        ('fluxo_inicializado', 'Fluxo Inicializado'),
        ('fluxo_finalizado', 'Fluxo Finalizado'),
        ('transferido_humano', 'Transferido para Humano'),
        
        # Status de abandono/problemas
        ('chamada_perdida', 'Chamada Perdida'),
        ('ocupado', 'Ocupado'),
        ('desligou', 'Desligou'),
        ('nao_atendeu', 'Não Atendeu'),
        ('abandonou_fluxo', 'Abandonou o Fluxo'),
        ('numero_invalido', 'Número Inválido'),
        ('erro_sistema', 'Erro do Sistema'),
        
        # Status de conversão
        ('convertido_lead', 'Convertido em Lead'),
        ('venda_confirmada', 'Venda Confirmada'),
        ('venda_rejeitada', 'Venda Rejeitada'),
        
        # Novos status expandidos
        ('venda_sem_viabilidade', 'Venda Sem Viabilidade'),
        ('cliente_desistiu', 'Cliente Desistiu'),
        ('aguardando_validacao', 'Aguardando Validação'),
        ('followup_agendado', 'Follow-up Agendado'),
        ('nao_qualificado', 'Não Qualificado'),

        # Status de pipeline CRM
        ('instalacao_agendada', 'Instalação Agendada'),
        ('documentacao_enviada', 'Documentação Enviada'),
        ('proposta_enviada', 'Proposta Enviada'),
        ('proposta_aceita', 'Proposta Aceita'),
        ('contrato_assinado', 'Contrato Assinado'),
        ('em_negociacao', 'Em Negociação'),
        ('retorno_agendado', 'Retorno Agendado'),
        ('cancelamento_solicitado', 'Cancelamento Solicitado'),
        ('reativacao', 'Reativação'),
    ]
    
    # Relacionamento opcional com lead
    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='historico_contatos',
        verbose_name="Lead Relacionado"
    )
    
    telefone = models.CharField(
        max_length=17,
        verbose_name="Telefone",
        help_text="Número de telefone do contato"
    )
    
    data_hora_contato = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data/Hora do Contato"
    )
    
    status = models.CharField(
        max_length=30,
        verbose_name="Status do Contato"
    )
    
    nome_contato = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Nome do Contato",
        help_text="Nome identificado durante o contato"
    )
    
    # Campos adicionais para melhor controle
    duracao_segundos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duração (segundos)",
        help_text="Duração da chamada em segundos"
    )
    
    transcricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Transcrição",
        help_text="Transcrição da conversa"
    )
    
    observacoes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações",
        help_text="Observações sobre o contato"
    )
    
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem",
        help_text="IP de onde partiu a chamada"
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent",
        help_text="User agent do sistema que fez a chamada"
    )
    
    dados_extras = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Dados Extras",
        help_text="Dados JSON com informações extras do contato"
    )
    
    # Campos para rastreamento do funil de vendas
    sucesso = models.BooleanField(
        default=False,
        verbose_name="Sucesso",
        help_text="Indica se o contato foi bem-sucedido"
    )
    
    converteu_lead = models.BooleanField(
        default=False,
        verbose_name="Converteu em Lead",
        help_text="Indica se este contato gerou um lead/prospecto"
    )
    
    data_conversao_lead = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Conversão em Lead",
        help_text="Data quando foi convertido em lead/prospecto"
    )
    
    converteu_venda = models.BooleanField(
        default=False,
        verbose_name="Converteu em Venda",
        help_text="Indica se este lead se tornou uma venda confirmada"
    )
    
    data_conversao_venda = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Conversão em Venda",
        help_text="Data quando foi confirmada a venda"
    )
    
    valor_venda = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor da Venda",
        help_text="Valor em reais da venda confirmada"
    )
    
    origem_contato = models.CharField(
        max_length=50,
        choices=LeadProspecto.ORIGEM_CHOICES,
        null=True,
        blank=True,
        verbose_name="Origem do Contato",
        help_text="Canal de origem do contato"
    )
    
    # Campo para identificar contatos relacionados (mesmo cliente, múltiplos contatos)
    identificador_cliente = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Identificador do Cliente",
        help_text="Hash ou ID único para agrupar contatos do mesmo cliente"
    )
    
    # Campos adicionais de atendimento
    id_conta = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID da Conta",
        help_text="Identificador da conta do cliente no sistema",
        db_index=True
    )
    
    numero_conta = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Número da Conta",
        help_text="Número da conta do cliente",
        db_index=True
    )
    
    ultima_mensagem = models.TextField(
        null=True,
        blank=True,
        verbose_name="Última Mensagem",
        help_text="Última mensagem enviada ou recebida no contato"
    )
    
    protocolo_atendimento = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Protocolo de Atendimento",
        help_text="Número de protocolo do atendimento",
        db_index=True
    )
    
    codigo_atendimento = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Código de Atendimento",
        help_text="Código único do atendimento",
        db_index=True
    )
    
    class Meta:
        db_table = 'historico_contato'
        verbose_name = "Histórico de Contato"
        verbose_name_plural = "📊 03. Histórico de Contatos"
        ordering = ['-data_hora_contato']
        indexes = [
            models.Index(fields=['telefone']),
            models.Index(fields=['data_hora_contato']),
            models.Index(fields=['status']),
            models.Index(fields=['sucesso']),
            models.Index(fields=['converteu_lead']),
            models.Index(fields=['converteu_venda']),
            models.Index(fields=['data_conversao_lead']),
            models.Index(fields=['data_conversao_venda']),
            models.Index(fields=['origem_contato']),
            models.Index(fields=['identificador_cliente']),
            models.Index(fields=['id_conta']),
            models.Index(fields=['numero_conta']),
            models.Index(fields=['protocolo_atendimento']),
            models.Index(fields=['codigo_atendimento']),
            # Índices compostos para consultas de funil
            models.Index(fields=['data_hora_contato', 'status']),
            models.Index(fields=['converteu_lead', 'data_conversao_lead']),
            models.Index(fields=['converteu_venda', 'data_conversao_venda']),
        ]
    
    def __str__(self):
        return f"{self.telefone} - {self.status} - {self.data_hora_contato.strftime('%d/%m/%Y %H:%M')}"

    def get_status_display(self):  # compatível com chamadas existentes
        try:
            return StatusConfiguravel.get_label('historico_status', self.status)
        except Exception:
            mapping = dict(self.STATUS_CHOICES)
            return mapping.get(self.status, self.status)


# ============================================================================
# HISTÓRICO DE STATUS_API — auditoria de mudanças (de→para)
# ============================================================================

class HistoricoStatusLead(models.Model):
    """Histórico de mudanças do `LeadProspecto.status_api`.

    `status_api` não tem `choices` fixos (é ajustado livremente por vários
    pontos: admin, endpoints de API, integrações, motor de IA do WhatsApp) e
    muda com muita frequência durante o atendimento — por isso os campos
    aqui são texto livre, não FK/choices. Gravado automaticamente por signal
    (`vendas_web/signals.py`) sempre que o valor muda via `.save()`, e
    manualmente nos poucos pontos que usam `.update()` em massa (bypassa
    signal do Django).
    """

    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.CASCADE,
        related_name='historico_status',
        verbose_name="Lead",
    )
    status_anterior = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Status anterior",
    )
    status_novo = models.CharField(max_length=50, verbose_name="Status novo")
    origem = models.CharField(
        max_length=30, blank=True, default='sistema', db_index=True,
        verbose_name="Origem",
        help_text="Quem disparou a mudança (ex: sistema, admin, hubsoft_sync, whatsapp_bot)",
    )
    alterado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name="Alterado por",
    )
    observacao = models.CharField(max_length=255, blank=True, null=True)
    data_alteracao = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Histórico de Status do Lead"
        verbose_name_plural = "Histórico de Status dos Leads"
        ordering = ['-data_alteracao']
        app_label = 'vendas_web'
        indexes = [
            models.Index(fields=['lead', '-data_alteracao']),
        ]

    def __str__(self):
        return f"Lead {self.lead_id}: {self.status_anterior} → {self.status_novo}"


class StatusConfiguravel(models.Model):
    """
    Tabela para gerenciar valores de status/labels via admin.
    grupos esperados:
      - lead_status_api
      - prospecto_status
      - historico_status
    """
    GRUPO_CHOICES = [
        ('lead_status_api', 'Lead: Status API'),
        ('prospecto_status', 'Prospecto: Status'),
        ('historico_status', 'Histórico: Status'),
        ('atendimento_status', 'Atendimento: Status'),
        ('fluxo_status', 'Fluxo: Status'),
    ]

    grupo = models.CharField(max_length=50, choices=GRUPO_CHOICES, db_index=True)
    codigo = models.CharField(max_length=50, db_index=True)
    rotulo = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'status_configuravel'
        verbose_name = "Status Configurável"
        verbose_name_plural = "⚙️ 05. Status Configuráveis"
        unique_together = [('grupo', 'codigo')]
        ordering = ['grupo', 'ordem', 'codigo']

    def __str__(self):
        return f"{self.grupo}:{self.codigo} -> {self.rotulo} ({'ativo' if self.ativo else 'inativo'})"

    @classmethod
    def get_label(cls, grupo: str, codigo: str) -> str:
        registro = cls.objects.filter(grupo=grupo, codigo=codigo, ativo=True).first()
        return registro.rotulo if registro else codigo
    
    def get_duracao_formatada(self):
        """Retorna a duração formatada"""
        if self.duracao_segundos:
            if self.duracao_segundos < 60:
                return f"{self.duracao_segundos}s"
            else:
                minutos = self.duracao_segundos // 60
                segundos = self.duracao_segundos % 60
                return f"{minutos}m {segundos}s"
        return "N/A"
    
    def get_tempo_relativo(self):
        """Retorna o tempo relativo do contato"""
        from django.utils.timesince import timesince
        return timesince(self.data_hora_contato)
    
    def get_valor_venda_formatado(self):
        """Retorna o valor da venda formatado em reais"""
        if self.valor_venda:
            return f"R$ {self.valor_venda:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return "R$ 0,00"
    
    def get_status_display_color(self):
        """Retorna cor para exibição do status no dashboard"""
        status_colors = {
            'fluxo_inicializado': '#3498db',  # Azul
            'fluxo_finalizado': '#2ecc71',    # Verde
            'transferido_humano': '#f39c12',  # Laranja
            'convertido_lead': '#9b59b6',     # Roxo
            'venda_confirmada': '#27ae60',    # Verde escuro
            'venda_rejeitada': '#e74c3c',     # Vermelho
            'abandonou_fluxo': '#95a5a6',     # Cinza
            'erro_sistema': '#e67e22',        # Laranja escuro
        }
        return status_colors.get(self.status, '#7f8c8d')  # Cinza padrão
    
    def is_contato_bem_sucedido(self):
        """Verifica se o contato foi bem-sucedido (finalizou fluxo ou foi transferido)"""
        return self.status in ['fluxo_finalizado', 'transferido_humano', 'convertido_lead', 'venda_confirmada']
    
    def is_conversao_completa(self):
        """Verifica se houve conversão completa (de contato até venda)"""
        return self.converteu_venda and self.valor_venda and self.valor_venda > 0
    
    @classmethod
    def get_funil_insights(cls, data_inicio=None, data_fim=None):
        """
        Retorna insights do funil de vendas para um período específico
        """
        from django.utils import timezone
        from django.db.models import Count, Sum, Q
        from datetime import datetime, timedelta
        
        # Se não especificado, usa últimos 30 dias
        if not data_fim:
            data_fim = timezone.now()
        if not data_inicio:
            data_inicio = data_fim - timedelta(days=30)
        
        queryset = cls.objects.filter(
            data_hora_contato__gte=data_inicio,
            data_hora_contato__lte=data_fim
        )
        
        insights = {
            'total_contatos': queryset.count(),
            'fluxos_inicializados': queryset.filter(status='fluxo_inicializado').count(),
            'fluxos_finalizados': queryset.filter(status='fluxo_finalizado').count(),
            'transferidos_humano': queryset.filter(status='transferido_humano').count(),
            'convertidos_lead': queryset.filter(converteu_lead=True).count(),
            'vendas_confirmadas': queryset.filter(converteu_venda=True).count(),
            'valor_total_vendas': queryset.filter(converteu_venda=True).aggregate(
                total=Sum('valor_venda')
            )['total'] or 0,
            'abandonos': queryset.filter(status__in=[
                'abandonou_fluxo', 'desligou', 'nao_atendeu', 'chamada_perdida'
            ]).count(),
        }
        
        # Cálculos de taxa de conversão
        if insights['fluxos_inicializados'] > 0:
            insights['taxa_finalizacao'] = (
                (insights['fluxos_finalizados'] + insights['transferidos_humano']) / 
                insights['fluxos_inicializados'] * 100
            )
        else:
            insights['taxa_finalizacao'] = 0
            
        if insights['convertidos_lead'] > 0:
            insights['taxa_conversao_venda'] = (
                insights['vendas_confirmadas'] / insights['convertidos_lead'] * 100
            )
        else:
            insights['taxa_conversao_venda'] = 0
            
        # Taxa de conversão geral (contato → venda)
        if insights['total_contatos'] > 0:
            insights['taxa_conversao_geral'] = (
                insights['vendas_confirmadas'] / insights['total_contatos'] * 100
            )
        else:
            insights['taxa_conversao_geral'] = 0
        
        return insights

class ConfiguracaoSistema(models.Model):
    """
    Modelo para configurações gerais do sistema
    """
    chave = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Chave",
        help_text="Chave única da configuração"
    )
    
    valor = models.TextField(
        verbose_name="Valor",
        help_text="Valor da configuração"
    )
    
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição da configuração"
    )
    
    tipo = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
            ('decimal', 'Decimal'),
        ],
        default='string',
        verbose_name="Tipo",
        help_text="Tipo do valor da configuração"
    )
    
    data_criacao = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    class Meta:
        db_table = 'configuracao_sistema'
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "📈 04. Configurações do Sistema"
        ordering = ['chave']
    
    def __str__(self):
        return f"{self.chave}: {self.valor[:50]}"

class LogSistema(models.Model):
    """
    Modelo para logs do sistema
    """
    NIVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    nivel = models.CharField(
        max_length=10,
        choices=NIVEL_CHOICES,
        default='INFO',
        verbose_name="Nível"
    )
    
    modulo = models.CharField(
        max_length=100,
        verbose_name="Módulo",
        help_text="Módulo/função que gerou o log"
    )
    
    mensagem = models.TextField(
        verbose_name="Mensagem"
    )
    
    dados_extras = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Dados Extras",
        help_text="Dados JSON com informações extras"
    )
    
    usuario = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Usuário",
        help_text="Usuário relacionado ao log"
    )
    
    ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP"
    )
    
    data_criacao = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Criação"
    )
    
    class Meta:
        db_table = 'log_sistema'
        verbose_name = "Log do Sistema"
        verbose_name_plural = "📈 03. Logs do Sistema"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['nivel']),
            models.Index(fields=['data_criacao']),
            models.Index(fields=['modulo']),
        ]
    
    def __str__(self):
        return f"{self.nivel} - {self.modulo} - {self.data_criacao.strftime('%d/%m/%Y %H:%M')}"

class FluxoAtendimento(models.Model):
    """
    Modelo para definir fluxos de atendimento personalizáveis
    Cada fluxo pode ter múltiplas questões em ordem específica
    """
    TIPO_FLUXO_CHOICES = [
        ('qualificacao', 'Qualificação de Lead'),
        ('vendas', 'Vendas'),
        ('suporte', 'Suporte'),
        ('onboarding', 'Onboarding'),
        ('pesquisa', 'Pesquisa de Satisfação'),
        ('customizado', 'Customizado'),
        ('upgrade', 'Upgrade de Plano'),
    ]
    
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('rascunho', 'Rascunho'),
        ('teste', 'Em Teste'),
    ]
    
    nome = models.CharField(
        max_length=255,
        verbose_name="Nome do Fluxo",
        help_text="Nome identificador do fluxo de atendimento"
    )
    
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada do fluxo"
    )
    
    tipo_fluxo = models.CharField(
        max_length=20,
        choices=TIPO_FLUXO_CHOICES,
        default='qualificacao',
        verbose_name="Tipo de Fluxo"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='rascunho',
        verbose_name="Status"
    )
    
    # Configurações do fluxo
    max_tentativas = models.PositiveIntegerField(
        default=3,
        verbose_name="Máximo de Tentativas",
        help_text="Número máximo de tentativas para completar o fluxo"
    )
    
    tempo_limite_minutos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo Limite (minutos)",
        help_text="Tempo máximo para completar o fluxo (opcional)"
    )
    
    permite_pular_questoes = models.BooleanField(
        default=False,
        verbose_name="Permite Pular Questões",
        help_text="Se o usuário pode pular questões opcionais"
    )
    
    # Campos de controle
    data_criacao = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    criado_por = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Criado Por"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    class Meta:
        db_table = 'fluxos_atendimento'
        verbose_name = "Fluxo de Atendimento"
        verbose_name_plural = "🤖 01. Fluxos de Atendimento"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['tipo_fluxo']),
            models.Index(fields=['status']),
            models.Index(fields=['ativo']),
        ]
    
    def __str__(self):
        return f"{self.nome} ({self.get_tipo_fluxo_display()})"
    
    def get_questoes_ordenadas(self):
        """Retorna questões ordenadas por índice"""
        return self.questoes.filter(ativo=True).order_by('indice')
    
    def get_total_questoes(self):
        """Retorna total de questões ativas"""
        return self.questoes.filter(ativo=True).count()
    
    def get_questao_por_indice(self, indice):
        """Retorna questão específica por índice"""
        return self.questoes.filter(indice=indice, ativo=True).first()
    
    def get_proxima_questao(self, indice_atual):
        """Retorna próxima questão após o índice atual"""
        return self.questoes.filter(
            indice__gt=indice_atual,
            ativo=True
        ).order_by('indice').first()
    
    def get_questao_anterior(self, indice_atual):
        """Retorna questão anterior ao índice atual"""
        return self.questoes.filter(
            indice__lt=indice_atual,
            ativo=True
        ).order_by('indice').last()
    
    def pode_ser_usado(self):
        """Verifica se o fluxo pode ser usado"""
        return self.status == 'ativo' and self.ativo and self.get_total_questoes() > 0
    
    def get_estatisticas(self):
        """Retorna estatísticas básicas do fluxo"""
        from django.db.models import Count, Avg
        
        atendimentos = self.atendimentos.all()
        total_atendimentos = atendimentos.count()
        atendimentos_completados = atendimentos.filter(status='completado').count()
        
        if total_atendimentos > 0:
            taxa_completacao = (atendimentos_completados / total_atendimentos) * 100
        else:
            taxa_completacao = 0
        
        tempo_medio = atendimentos.filter(
            tempo_total__isnull=False
        ).aggregate(
            tempo_medio=Avg('tempo_total')
        )['tempo_medio'] or 0
        
        return {
            'total_atendimentos': total_atendimentos,
            'atendimentos_completados': atendimentos_completados,
            'taxa_completacao': round(taxa_completacao, 2),
            'tempo_medio_segundos': round(tempo_medio, 2) if tempo_medio else 0,
        }

class QuestaoFluxo(models.Model):
    """
    Modelo para questões individuais dentro de um fluxo inteligente
    Suporte completo para roteamento condicional e integração com IA
    """
    TIPO_QUESTAO_CHOICES = [
        ('texto', 'Texto Livre'),
        ('numero', 'Número'),
        ('email', 'Email'),
        ('telefone', 'Telefone'),
        ('cpf_cnpj', 'CPF/CNPJ'),
        ('cep', 'CEP'),
        ('endereco', 'Endereço'),
        ('select', 'Seleção Única'),
        ('multiselect', 'Seleção Múltipla'),
        ('data', 'Data'),
        ('hora', 'Hora'),
        ('data_hora', 'Data e Hora'),
        ('boolean', 'Sim/Não'),
        ('escala', 'Escala (1-10)'),
        ('arquivo', 'Upload de Arquivo'),
        # Novos tipos para integração
        ('planos_internet', 'Seleção de Planos Internet'),
        ('vencimentos', 'Seleção de Vencimentos'),
        ('opcoes_dinamicas', 'Opções Dinâmicas'),
        ('ia_validacao', 'Validação por IA'),
        ('condicional_complexa', 'Condicional Complexa'),
    ]
    
    TIPO_VALIDACAO_CHOICES = [
        ('obrigatoria', 'Obrigatória'),
        ('opcional', 'Opcional'),
        ('condicional', 'Condicional'),
        ('ia_assistida', 'IA Assistida'),
        ('validacao_customizada', 'Validação Customizada'),
    ]
    
    ESTRATEGIA_ERRO_CHOICES = [
        ('repetir', 'Repetir Questão'),
        ('pular', 'Pular Questão'),
        ('redirecionar', 'Redirecionar'),
        ('finalizar', 'Finalizar Fluxo'),
        ('escalar_humano', 'Escalar para Humano'),
    ]
    
    fluxo = models.ForeignKey(
        FluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='questoes',
        verbose_name="Fluxo"
    )
    
    indice = models.PositiveIntegerField(
        verbose_name="Índice",
        help_text="Ordem da questão no fluxo (1, 2, 3...)"
    )
    
    titulo = models.CharField(
        max_length=255,
        verbose_name="Título da Questão",
        help_text="Texto da pergunta para o usuário"
    )
    
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição adicional ou instruções"
    )
    
    tipo_questao = models.CharField(
        max_length=20,
        choices=TIPO_QUESTAO_CHOICES,
        default='texto',
        verbose_name="Tipo de Questão"
    )
    
    tipo_validacao = models.CharField(
        max_length=25,
        choices=TIPO_VALIDACAO_CHOICES,
        default='obrigatoria',
        verbose_name="Tipo de Validação"
    )
    
    # Configurações de resposta
    opcoes_resposta = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Opções de Resposta",
        help_text="Lista de opções para questões de seleção"
    )
    
    resposta_padrao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Resposta Padrão",
        help_text="Resposta padrão ou placeholder"
    )
    
    # Validações
    regex_validacao = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Regex de Validação",
        help_text="Expressão regular para validação customizada"
    )
    
    tamanho_minimo = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tamanho Mínimo",
        help_text="Tamanho mínimo da resposta"
    )
    
    tamanho_maximo = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tamanho Máximo",
        help_text="Tamanho máximo da resposta"
    )
    
    valor_minimo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor Mínimo",
        help_text="Valor mínimo para questões numéricas"
    )
    
    valor_maximo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor Máximo",
        help_text="Valor máximo para questões numéricas"
    )
    
    # Lógica condicional básica (mantida para compatibilidade)
    questao_dependencia = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Questão de Dependência",
        help_text="Questão que deve ser respondida antes desta"
    )
    
    valor_dependencia = models.TextField(
        null=True,
        blank=True,
        verbose_name="Valor de Dependência",
        help_text="Valor específico da questão de dependência para mostrar esta"
    )
    
    # Sistema de roteamento inteligente
    roteamento_respostas = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name="Roteamento por Respostas",
        help_text="Mapeamento de respostas para próximas questões: {resposta: questao_id}"
    )
    
    questao_padrao_proxima = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questoes_anteriores_padrao',
        verbose_name="Questão Padrão Próxima",
        help_text="Questão padrão caso resposta não tenha roteamento específico"
    )
    
    # Configurações de validação por IA
    prompt_ia_validacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Prompt para IA",
        help_text="Prompt específico para validação da resposta por IA"
    )
    
    criterios_ia = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Critérios de IA",
        help_text="Critérios específicos para validação: {criterio: peso}"
    )
    
    # Controle de repetições e erros
    max_tentativas = models.PositiveIntegerField(
        default=3,
        verbose_name="Máximo de Tentativas",
        help_text="Número máximo de tentativas antes de aplicar estratégia de erro"
    )
    
    estrategia_erro = models.CharField(
        max_length=20,
        choices=ESTRATEGIA_ERRO_CHOICES,
        default='repetir',
        verbose_name="Estratégia de Erro"
    )
    
    questao_erro_redirecionamento = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questoes_erro_origem',
        verbose_name="Questão para Redirecionamento de Erro"
    )
    
    # Mensagens personalizadas
    mensagem_erro_padrao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem de Erro Padrão",
        help_text="Mensagem exibida quando resposta é inválida"
    )
    
    mensagem_tentativa_esgotada = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem Tentativas Esgotadas",
        help_text="Mensagem quando máximo de tentativas é atingido"
    )
    
    instrucoes_resposta_correta = models.TextField(
        null=True,
        blank=True,
        verbose_name="Instruções para Resposta Correta",
        help_text="Orientações sobre como responder corretamente"
    )
    
    # Campos de controle
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativa"
    )
    
    permite_voltar = models.BooleanField(
        default=True,
        verbose_name="Permite Voltar",
        help_text="Se o usuário pode voltar para esta questão"
    )
    
    permite_editar = models.BooleanField(
        default=True,
        verbose_name="Permite Editar",
        help_text="Se a resposta pode ser editada após enviada"
    )
    
    ordem_exibicao = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordem de Exibição",
        help_text="Ordem para exibição na interface"
    )
    
    # Integração com N8N
    webhook_n8n_validacao = models.URLField(
        null=True,
        blank=True,
        verbose_name="Webhook N8N para Validação",
        help_text="URL do webhook N8N para validação customizada"
    )
    
    webhook_n8n_pos_resposta = models.URLField(
        null=True,
        blank=True,
        verbose_name="Webhook N8N Pós-Resposta",
        help_text="URL do webhook N8N executado após resposta válida"
    )
    
    # Configurações dinâmicas
    opcoes_dinamicas_fonte = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('planos_internet', 'Planos de Internet'),
            ('opcoes_vencimento', 'Opções de Vencimento'),
            ('api_externa', 'API Externa'),
            ('query_customizada', 'Query Customizada'),
            ('servicos_ativos_cliente', 'Serviços Ativos do Cliente (HubSoft)'),
            ('planos_upgrade_disponiveis', 'Planos Disponíveis pra Upgrade'),
        ],
        verbose_name="Fonte de Opções Dinâmicas"
    )
    
    query_opcoes_dinamicas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Query para Opções Dinâmicas",
        help_text="Query SQL ou configuração para buscar opções dinamicamente"
    )
    
    # Configurações de contexto
    variaveis_contexto = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name="Variáveis de Contexto",
        help_text="Variáveis que podem ser usadas na questão: {nome: valor}"
    )
    
    template_questao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Template da Questão",
        help_text="Template com variáveis: 'Olá {{nome}}, qual seu plano preferido?'"
    )
    
    class Meta:
        db_table = 'questoes_fluxo'
        verbose_name = "Questão do Fluxo"
        verbose_name_plural = "🤖 02. Questões do Fluxo"
        ordering = ['fluxo', 'indice']
        unique_together = [('fluxo', 'indice')]
        indexes = [
            models.Index(fields=['fluxo', 'indice']),
            models.Index(fields=['tipo_questao']),
            models.Index(fields=['ativo']),
        ]
    
    def __str__(self):
        return f"{self.fluxo.nome} - Q{self.indice}: {self.titulo}"
    
    def get_opcoes_formatadas(self, contexto=None):
        """Retorna opções de resposta formatadas (estáticas ou dinâmicas)"""
        # Opções dinâmicas
        if self.opcoes_dinamicas_fonte:
            return self._get_opcoes_dinamicas(contexto)
        
        # Opções estáticas
        if self.opcoes_resposta and isinstance(self.opcoes_resposta, list):
            return self.opcoes_resposta
        return []
    
    def _get_opcoes_dinamicas(self, contexto=None):
        """Busca opções dinâmicas baseadas na fonte configurada"""
        if self.opcoes_dinamicas_fonte == 'planos_internet':
            planos = PlanoInternet.objects.filter(ativo=True).order_by('ordem_exibicao', 'valor_mensal')
            opcoes = []
            for plano in planos:
                opcoes.append({
                    'valor': str(plano.id),
                    'texto': f"{plano.nome} - {plano.get_velocidade_formatada()} - {plano.get_valor_formatado()}",
                    'dados_extras': {
                        'id_sistema_externo': plano.id_sistema_externo,
                        'valor_mensal': float(plano.valor_mensal),
                        'velocidade': plano.velocidade_download
                    }
                })
            # Adicionar opção "Ver mais"
            opcoes.append({
                'valor': 'ver_mais_planos',
                'texto': '📋 Ver mais opções de planos',
                'tipo': 'acao_especial'
            })
            return opcoes
            
        elif self.opcoes_dinamicas_fonte == 'opcoes_vencimento':
            vencimentos = OpcaoVencimento.objects.filter(ativo=True).order_by('ordem_exibicao')
            opcoes = []
            for venc in vencimentos:
                opcoes.append({
                    'valor': str(venc.id),
                    'texto': f"Dia {venc.dia_vencimento} - {venc.descricao}",
                    'dados_extras': {
                        'dia_vencimento': venc.dia_vencimento
                    }
                })
            # Adicionar opção "Ver mais"
            opcoes.append({
                'valor': 'ver_mais_vencimentos',
                'texto': '📅 Ver mais opções de vencimento',
                'tipo': 'acao_especial'
            })
            return opcoes
            
        elif self.opcoes_dinamicas_fonte == 'servicos_ativos_cliente':
            return self._get_opcoes_servicos_ativos_cliente(contexto)

        elif self.opcoes_dinamicas_fonte == 'planos_upgrade_disponiveis':
            return self._get_opcoes_planos_upgrade(contexto)

        elif self.opcoes_dinamicas_fonte == 'query_customizada' and self.query_opcoes_dinamicas:
            return self._executar_query_customizada(contexto)

        return []

    def _get_opcoes_servicos_ativos_cliente(self, contexto=None):
        """Lista serviços ativos do ClienteHubsoft vinculado ao lead.

        Contexto esperado: {'lead_id': <int>} OU {'atendimento_id': <int>}.
        Retorna [{valor=id_cliente_servico, texto=nome+status, dados_extras={...}}]
        Considera "ativo" qualquer serviço cujo status_prefixo contenha
        "Habilitado" ou cuja data_cancelamento esteja vazia.
        """
        from integracoes.models import ClienteHubsoft

        if not contexto:
            return []

        lead_id = contexto.get('lead_id')
        if not lead_id and contexto.get('atendimento_id'):
            try:
                atd = AtendimentoFluxo.objects.select_related('lead').get(
                    pk=contexto['atendimento_id'])
                lead_id = atd.lead_id
            except AtendimentoFluxo.DoesNotExist:
                return []

        if not lead_id:
            return []

        cliente = ClienteHubsoft.objects.filter(
            lead_id=lead_id, ativo=True,
        ).order_by('-data_sync').first()
        if not cliente:
            # O vínculo ClienteHubsoft.lead aponta pro ÚLTIMO lead sincronizado.
            # Outro lead do MESMO CPF (mesmo cliente em sessão/telefone diferente)
            # ficava sem opções e o upgrade transbordava — cai pra busca por CPF.
            cpf = (LeadProspecto.objects.filter(pk=lead_id)
                   .values_list('cpf_cnpj', flat=True).first() or '').strip()
            if cpf:
                cliente = ClienteHubsoft.objects.filter(
                    cpf_cnpj=cpf, ativo=True,
                ).order_by('-data_sync').first()
        if not cliente:
            return []

        servicos = (
            cliente.servicos
            .filter(data_cancelamento__isnull=True)
            .exclude(status_prefixo__iexact='cancelado')
            .exclude(status_prefixo__iexact='inativo')
            .order_by('-data_habilitacao')
        )

        opcoes = []
        for s in servicos:
            # Separador ASCII " - " (o travessão "—" não sobrevive no WhatsApp/Matrix).
            valor_txt = (f"R$ {s.valor:.2f}".replace('.', ',') + "/mês") if s.valor else ""
            partes = [p for p in (s.nome, valor_txt) if p]
            texto = " - ".join(partes)
            if s.status:
                texto += f" ({s.status})"
            opcoes.append({
                'valor': str(s.id_cliente_servico),
                'texto': texto,
                'dados_extras': {
                    'id_cliente_servico': s.id_cliente_servico,
                    'id_servico_hubsoft': s.id_servico,
                    'plano_atual_nome': s.nome,
                    'valor_atual': float(s.valor) if s.valor else None,
                },
            })
        return opcoes

    def _get_opcoes_planos_upgrade(self, contexto=None):
        """Lista planos disponíveis pra upgrade (PlanoInternet ativos)
        excluindo o plano atual (id_servico_hubsoft / id_sistema_externo).

        Contexto esperado: {'id_servico_hubsoft_atual': <int|str>}
        Pode também receber {'id_cliente_servico_atual': <int>} e
        resolveremos o id_servico_hubsoft via ServicoClienteHubsoft.
        """
        from integracoes.models import ServicoClienteHubsoft

        if not contexto:
            return []

        id_servico_atual = contexto.get('id_servico_hubsoft_atual')
        if id_servico_atual is None and contexto.get('id_cliente_servico_atual'):
            scs = ServicoClienteHubsoft.objects.filter(
                id_cliente_servico=contexto['id_cliente_servico_atual']
            ).first()
            if scs and scs.id_servico:
                id_servico_atual = scs.id_servico

        id_servico_atual_str = str(id_servico_atual) if id_servico_atual is not None else None

        planos = PlanoInternet.objects.filter(ativo=True)
        if id_servico_atual_str:
            # Exclui plano cujo id_sistema_externo é igual ao atual
            planos = planos.exclude(id_sistema_externo=id_servico_atual_str)

        planos = planos.order_by('ordem_exibicao', 'valor_mensal')

        opcoes = []
        vistos = set()  # dedup por id_sistema_externo (catálogo tem planos repetidos)
        for p in planos:
            valor = str(p.id_sistema_externo or p.id)
            if valor in vistos:
                continue
            vistos.add(valor)
            # Usa o NOME do plano (diferencia "Fibra 1 Giga" de "1 Giga + Ponto
            # Adicional", que têm a MESMA velocidade) + preço. Cai p/ velocidade
            # se o nome estiver vazio.
            rotulo = (p.nome or '').strip() or p.get_velocidade_formatada()
            opcoes.append({
                'valor': valor,
                'texto': f"{rotulo} - {p.get_valor_formatado()}/mês",
                'dados_extras': {
                    'plano_id_local': p.id,
                    'plano_nome': p.nome,
                    'id_servico_hubsoft': int(p.id_sistema_externo) if (p.id_sistema_externo or '').isdigit() else None,
                    'valor_mensal': float(p.valor_mensal),
                    'velocidade': p.velocidade_download,
                },
            })
        return opcoes
    
    def _executar_query_customizada(self, contexto=None):
        """Executa query customizada para buscar opções"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(self.query_opcoes_dinamicas)
                resultados = cursor.fetchall()
                opcoes = []
                for resultado in resultados:
                    opcoes.append({
                        'valor': str(resultado[0]),
                        'texto': str(resultado[1]),
                        'dados_extras': resultado[2] if len(resultado) > 2 else {}
                    })
                return opcoes
        except Exception as e:
            print(f"Erro ao executar query customizada: {e}")
            return []
    
    def get_questao_renderizada(self, contexto=None):
        """Retorna a questão com template processado"""
        if self.template_questao and contexto:
            try:
                from django.template import Template, Context
                template = Template(self.template_questao)
                return template.render(Context(contexto))
            except:
                pass
        return self.titulo
    
    def validar_resposta(self, resposta, contexto=None, tentativa=1):
        """
        Valida uma resposta baseada nas regras da questão (com IA e roteamento)
        Retorna (valido, mensagem_erro, dados_extras)
        """
        if not resposta and self.tipo_validacao == 'obrigatoria':
            return False, self._get_mensagem_erro_personalizada("obrigatoria"), {}
        
        if not resposta:
            return True, "", {}
        
        # Validação por IA primeiro (se configurada)
        if self.tipo_validacao == 'ia_assistida' and self.prompt_ia_validacao:
            resultado_ia = self._validar_com_ia(resposta, contexto)
            if not resultado_ia['valido']:
                return False, resultado_ia['mensagem'], resultado_ia
        
        # Validações tradicionais
        resultado_tradicional = self._validar_tradicional(resposta)
        if not resultado_tradicional[0]:
            return resultado_tradicional
        
        # Validação específica para opções dinâmicas
        if self.opcoes_dinamicas_fonte:
            resultado_dinamico = self._validar_opcoes_dinamicas(resposta, contexto)
            if not resultado_dinamico[0]:
                return resultado_dinamico
        
        # Webhook N8N para validação customizada
        if self.webhook_n8n_validacao:
            resultado_webhook = self._validar_com_webhook_n8n(resposta, contexto, tentativa)
            if not resultado_webhook[0]:
                return resultado_webhook
        
        return True, "", {'resposta_processada': resposta}
    
    def _validar_tradicional(self, resposta):
        """Validações tradicionais (mantidas para compatibilidade)"""
        # Validação de tamanho
        if self.tamanho_minimo and len(str(resposta)) < self.tamanho_minimo:
            return False, f"Resposta deve ter pelo menos {self.tamanho_minimo} caracteres", {}
        
        if self.tamanho_maximo and len(str(resposta)) > self.tamanho_maximo:
            return False, f"Resposta deve ter no máximo {self.tamanho_maximo} caracteres", {}
        
        # Validação de regex
        if self.regex_validacao:
            import re
            if not re.match(self.regex_validacao, str(resposta)):
                return False, self._get_mensagem_erro_personalizada("formato"), {}
        
        # Validação de valores numéricos
        if self.tipo_questao == 'numero':
            try:
                valor = float(resposta)
                if self.valor_minimo is not None and valor < self.valor_minimo:
                    return False, f"Valor deve ser maior ou igual a {self.valor_minimo}", {}
                if self.valor_maximo is not None and valor > self.valor_maximo:
                    return False, f"Valor deve ser menor ou igual a {self.valor_maximo}", {}
            except ValueError:
                return False, "Resposta deve ser um número válido", {}
        
        # Validação de email
        if self.tipo_questao == 'email':
            from django.core.validators import EmailValidator
            validator = EmailValidator()
            try:
                validator(resposta)
            except:
                return False, "Email inválido", {}
        
        # Validação de opções estáticas
        if self.tipo_questao in ['select', 'multiselect'] and self.opcoes_resposta:
            if self.tipo_questao == 'select':
                if resposta not in self.opcoes_resposta:
                    return False, "Opção selecionada não é válida", {}
            else:  # multiselect
                if not isinstance(resposta, list):
                    return False, "Resposta deve ser uma lista de opções", {}
                for opcao in resposta:
                    if opcao not in self.opcoes_resposta:
                        return False, f"Opção '{opcao}' não é válida", {}
        
        return True, "", {}
    
    def _validar_opcoes_dinamicas(self, resposta, contexto=None):
        """Valida respostas para opções dinâmicas"""
        opcoes = self.get_opcoes_formatadas(contexto)
        valores_validos = [opcao['valor'] for opcao in opcoes]
        
        if resposta not in valores_validos:
            return False, "Opção selecionada não é válida para as opções disponíveis", {}
        
        # Verificar se é uma ação especial
        opcao_selecionada = next((op for op in opcoes if op['valor'] == resposta), None)
        if opcao_selecionada and opcao_selecionada.get('tipo') == 'acao_especial':
            return True, "", {
                'acao_especial': True,
                'tipo_acao': opcao_selecionada['valor'],
                'dados_opcao': opcao_selecionada
            }
        
        return True, "", {'opcao_selecionada': opcao_selecionada}
    
    def _validar_com_ia(self, resposta, contexto=None):
        """Validação usando IA (implementação base - integrar com seu provedor de IA)"""
        try:
            # Aqui você integraria com sua IA (OpenAI, Claude, etc.)
            # Por enquanto, retorna validação básica
            prompt = self.prompt_ia_validacao.replace('{{resposta}}', str(resposta))
            if contexto:
                for chave, valor in contexto.items():
                    prompt = prompt.replace(f'{{{{{chave}}}}}', str(valor))
            
            # Implementar chamada para IA aqui
            # resultado_ia = chamar_ia(prompt, self.criterios_ia)
            
            return {
                'valido': True,
                'mensagem': '',
                'confianca': 0.95,
                'sugestoes': []
            }
        except Exception as e:
            return {
                'valido': False,
                'mensagem': f"Erro na validação por IA: {str(e)}",
                'confianca': 0.0,
                'sugestoes': []
            }
    
    def _validar_com_webhook_n8n(self, resposta, contexto=None, tentativa=1):
        """Validação usando webhook N8N"""
        try:
            import requests
            import json
            
            payload = {
                'questao_id': self.id,
                'resposta': resposta,
                'contexto': contexto or {},
                'tentativa': tentativa,
                'dados_questao': {
                    'titulo': self.titulo,
                    'tipo': self.tipo_questao,
                    'criterios_ia': self.criterios_ia
                }
            }
            
            response = requests.post(
                self.webhook_n8n_validacao,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                resultado = response.json()
                return resultado.get('valido', True), resultado.get('mensagem', ''), resultado
            else:
                return False, "Erro na validação externa", {}
                
        except Exception as e:
            # Em caso de erro, não bloquear o fluxo
            return True, "", {'erro_webhook': str(e)}
    
    def _get_mensagem_erro_personalizada(self, tipo_erro):
        """Retorna mensagem de erro personalizada"""
        if self.mensagem_erro_padrao:
            return self.mensagem_erro_padrao
        
        mensagens = {
            'obrigatoria': "Esta questão é obrigatória",
            'formato': "Formato da resposta não é válido",
            'tentativas_esgotadas': self.mensagem_tentativa_esgotada or "Número máximo de tentativas atingido"
        }
        
        mensagem = mensagens.get(tipo_erro, "Resposta inválida")
        
        if self.instrucoes_resposta_correta:
            mensagem += f"\n\n💡 {self.instrucoes_resposta_correta}"
        
        return mensagem
    
    def deve_ser_exibida(self, respostas_anteriores):
        """
        Verifica se a questão deve ser exibida baseada em dependências
        """
        if not self.questao_dependencia:
            return True
        
        # Buscar resposta da questão de dependência
        resposta_dependencia = respostas_anteriores.get(str(self.questao_dependencia.indice))
        
        if not resposta_dependencia:
            return False
        
        # Se não há valor específico de dependência, sempre exibe
        if not self.valor_dependencia:
            return True
        
        # Verificar se a resposta corresponde ao valor esperado
        return str(resposta_dependencia) == str(self.valor_dependencia)
    
    def get_proxima_questao_inteligente(self, resposta, contexto=None):
        """
        Determina a próxima questão baseada na resposta (ROTEAMENTO INTELIGENTE)
        Retorna (questao_obj, acao_especial, dados_extras)
        """
        # 1. Verificar roteamento específico por resposta
        if self.roteamento_respostas and str(resposta) in self.roteamento_respostas:
            questao_id = self.roteamento_respostas[str(resposta)]
            try:
                proxima_questao = QuestaoFluxo.objects.get(id=questao_id, ativo=True)
                return proxima_questao, None, {'roteamento_tipo': 'especifico'}
            except QuestaoFluxo.DoesNotExist:
                pass
        
        # 2. Verificar ações especiais (ver mais planos, ver mais vencimentos, etc.)
        if self.opcoes_dinamicas_fonte:
            acao_especial = self._processar_acao_especial(resposta, contexto)
            if acao_especial:
                return None, acao_especial, {'roteamento_tipo': 'acao_especial'}
        
        # 3. Questão padrão próxima (se configurada)
        if self.questao_padrao_proxima:
            return self.questao_padrao_proxima, None, {'roteamento_tipo': 'padrao'}
        
        # 4. Próxima questão por índice (comportamento tradicional)
        proxima_por_indice = self.fluxo.get_proxima_questao(self.indice)
        if proxima_por_indice:
            return proxima_por_indice, None, {'roteamento_tipo': 'sequencial'}
        
        # 5. Fim do fluxo
        return None, 'finalizar_fluxo', {'roteamento_tipo': 'fim_fluxo'}
    
    def _processar_acao_especial(self, resposta, contexto=None):
        """Processa ações especiais como 'ver mais planos'"""
        if resposta == 'ver_mais_planos':
            # Buscar questão específica para mais planos
            questao_mais_planos = self.fluxo.questoes.filter(
                tipo_questao='planos_internet',
                titulo__icontains='mais planos'
            ).first()
            
            if questao_mais_planos:
                return {
                    'tipo': 'redirecionar_questao',
                    'questao_destino': questao_mais_planos.id,
                    'mensagem': 'Aqui estão mais opções de planos para você:'
                }
            
            return {
                'tipo': 'mostrar_opcoes_expandidas',
                'fonte': 'planos_internet_completo',
                'mensagem': 'Vou mostrar todos os planos disponíveis:'
            }
        
        elif resposta == 'ver_mais_vencimentos':
            questao_mais_vencimentos = self.fluxo.questoes.filter(
                tipo_questao='vencimentos',
                titulo__icontains='mais vencimentos'
            ).first()
            
            if questao_mais_vencimentos:
                return {
                    'tipo': 'redirecionar_questao',
                    'questao_destino': questao_mais_vencimentos.id,
                    'mensagem': 'Aqui estão mais opções de vencimento:'
                }
            
            return {
                'tipo': 'mostrar_opcoes_expandidas',
                'fonte': 'opcoes_vencimento_completo',
                'mensagem': 'Vou mostrar todas as opções de vencimento:'
            }
        
        return None
    
    def aplicar_estrategia_erro(self, tentativa_atual, contexto=None):
        """
        Aplica estratégia de erro baseada no número de tentativas
        Retorna (acao, dados_acao)
        """
        if tentativa_atual >= self.max_tentativas:
            if self.estrategia_erro == 'repetir':
                return 'repetir_questao', {
                    'mensagem': self._get_mensagem_erro_personalizada("tentativas_esgotadas"),
                    'reiniciar_tentativas': True
                }
            
            elif self.estrategia_erro == 'pular':
                proxima_questao = self.fluxo.get_proxima_questao(self.indice)
                return 'pular_questao', {
                    'questao_destino': proxima_questao.id if proxima_questao else None,
                    'mensagem': "Vamos pular esta questão e continuar."
                }
            
            elif self.estrategia_erro == 'redirecionar' and self.questao_erro_redirecionamento:
                return 'redirecionar', {
                    'questao_destino': self.questao_erro_redirecionamento.id,
                    'mensagem': "Vou te ajudar de uma forma diferente."
                }
            
            elif self.estrategia_erro == 'escalar_humano':
                return 'escalar_humano', {
                    'mensagem': "Vou transferir você para um atendente humano que pode te ajudar melhor.",
                    'motivo': f"Dificuldade na questão: {self.titulo}"
                }
            
            elif self.estrategia_erro == 'finalizar':
                return 'finalizar_fluxo', {
                    'mensagem': "Não conseguimos prosseguir. Obrigado pelo seu tempo.",
                    'motivo': 'tentativas_esgotadas'
                }
        
        # Tentativa normal - repetir questão
        return 'repetir_questao', {
            'mensagem': self._get_mensagem_erro_personalizada("formato"),
            'tentativas_restantes': self.max_tentativas - tentativa_atual
        }
    
    def executar_webhook_pos_resposta(self, resposta, contexto=None):
        """Executa webhook N8N após resposta válida"""
        if not self.webhook_n8n_pos_resposta:
            return True
        
        try:
            import requests
            
            payload = {
                'questao_id': self.id,
                'resposta': resposta,
                'contexto': contexto or {},
                'dados_questao': {
                    'titulo': self.titulo,
                    'tipo': self.tipo_questao,
                    'indice': self.indice
                },
                'timestamp': timezone.now().isoformat()
            }
            
            response = requests.post(
                self.webhook_n8n_pos_resposta,
                json=payload,
                timeout=5  # Timeout menor para não bloquear o fluxo
            )
            
            return response.status_code == 200
            
        except Exception as e:
            # Log do erro, mas não bloquear o fluxo
            print(f"Erro ao executar webhook pós-resposta: {e}")
            return False
    
    def clean(self):
        """Validação personalizada do modelo"""
        from django.core.exceptions import ValidationError
        
        # Se não tem índice, calcular automaticamente
        if not self.indice and self.fluxo:
            ultimo_indice = self.fluxo.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0
            self.indice = ultimo_indice + 1
        
        # Verificar se o índice já existe para este fluxo
        if self.pk:  # Se é uma edição
            existing = QuestaoFluxo.objects.filter(
                fluxo=self.fluxo,
                indice=self.indice
            ).exclude(pk=self.pk).exists()
        else:  # Se é uma criação
            existing = QuestaoFluxo.objects.filter(
                fluxo=self.fluxo,
                indice=self.indice
            ).exists()
        
        if existing:
            raise ValidationError({
                'indice': f'Já existe uma questão com índice {self.indice} neste fluxo.'
            })
        
        super().clean()
    
    def save(self, *args, **kwargs):
        # Garantir que o índice seja preenchido antes de salvar
        if not self.indice and self.fluxo:
            ultimo_indice = self.fluxo.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0
            self.indice = ultimo_indice + 1
        
        super().save(*args, **kwargs)

class TentativaResposta(models.Model):
    """
    Modelo para rastrear tentativas de resposta em questões
    Essencial para controle de IA e estratégias de erro
    """
    atendimento = models.ForeignKey(
        'AtendimentoFluxo',
        on_delete=models.CASCADE,
        related_name='tentativas_respostas',
        verbose_name="Atendimento"
    )
    
    questao = models.ForeignKey(
        QuestaoFluxo,
        on_delete=models.CASCADE,
        related_name='tentativas',
        verbose_name="Questão"
    )
    
    tentativa_numero = models.PositiveIntegerField(
        verbose_name="Número da Tentativa"
    )
    
    resposta_original = models.TextField(
        verbose_name="Resposta Original"
    )
    
    resposta_processada = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resposta Processada"
    )
    
    valida = models.BooleanField(
        default=False,
        verbose_name="Resposta Válida"
    )
    
    mensagem_erro = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem de Erro"
    )
    
    # Dados da validação por IA
    resultado_ia = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado da IA",
        help_text="Resultado completo da validação por IA"
    )
    
    confianca_ia = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Confiança da IA",
        help_text="Score de confiança da IA (0.0 a 1.0)"
    )
    
    # Dados do webhook N8N
    resultado_webhook = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado do Webhook N8N"
    )
    
    # Estratégia aplicada
    estrategia_aplicada = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Estratégia Aplicada"
    )
    
    # Dados de contexto
    contexto_tentativa = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Contexto da Tentativa"
    )
    
    # Timestamps
    data_tentativa = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data da Tentativa"
    )
    
    tempo_resposta_segundos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo de Resposta (segundos)"
    )
    
    # Dados de auditoria
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent"
    )
    
    class Meta:
        db_table = 'tentativas_resposta'
        verbose_name = 'Tentativa de Resposta'
        verbose_name_plural = "🔧 02. Tentativas de Resposta"
        ordering = ['-data_tentativa']
        indexes = [
            models.Index(fields=['atendimento', 'questao']),
            models.Index(fields=['tentativa_numero']),
            models.Index(fields=['valida']),
            models.Index(fields=['data_tentativa']),
        ]
        unique_together = [('atendimento', 'questao', 'tentativa_numero')]
    
    def __str__(self):
        return f"{self.atendimento} - Q{self.questao.indice} - Tentativa {self.tentativa_numero}"
    
    def get_tempo_resposta_formatado(self):
        """Retorna tempo de resposta formatado"""
        if self.tempo_resposta_segundos:
            if self.tempo_resposta_segundos < 60:
                return f"{self.tempo_resposta_segundos}s"
            else:
                minutos = self.tempo_resposta_segundos // 60
                segundos = self.tempo_resposta_segundos % 60
                return f"{minutos}m {segundos}s"
        return "N/A"
    
    def get_resultado_ia_resumido(self):
        """Retorna resumo do resultado da IA"""
        if self.resultado_ia:
            return {
                'valido': self.resultado_ia.get('valido', False),
                'confianca': self.confianca_ia,
                'sugestoes': len(self.resultado_ia.get('sugestoes', [])),
                'criterios_atendidos': len([c for c in self.resultado_ia.get('criterios', {}).values() if c])
            }
        return None

class AtendimentoFluxo(models.Model):
    """
    Modelo para controlar uma sessão de atendimento específica
    Relaciona lead/prospecto com um fluxo e controla o progresso
    """
    STATUS_CHOICES = [
        ('iniciado', 'Iniciado'),
        ('em_andamento', 'Em Andamento'),
        ('pausado', 'Pausado'),
        ('completado', 'Completado'),
        ('abandonado', 'Abandonado'),
        ('erro', 'Erro'),
        ('cancelado', 'Cancelado'),
        ('aguardando_validacao', 'Aguardando Validação'),
        ('validado', 'Validado'),
        ('rejeitado', 'Rejeitado'),
    ]
    
    # Relacionamentos principais
    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.CASCADE,
        related_name='atendimentos_fluxo',
        verbose_name="Lead/Prospecto"
    )
    
    fluxo = models.ForeignKey(
        FluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='atendimentos',
        verbose_name="Fluxo"
    )
    
    # Relacionamento opcional com histórico de contato
    historico_contato = models.ForeignKey(
        HistoricoContato,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_fluxo',
        verbose_name="Histórico de Contato"
    )
    
    # Controle de progresso
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='iniciado',
        verbose_name="Status"
    )
    
    questao_atual = models.PositiveIntegerField(
        default=1,
        verbose_name="Questão Atual",
        help_text="Índice da questão atual no fluxo"
    )
    
    total_questoes = models.PositiveIntegerField(
        verbose_name="Total de Questões",
        help_text="Total de questões no fluxo"
    )
    
    questoes_respondidas = models.PositiveIntegerField(
        default=0,
        verbose_name="Questões Respondidas"
    )
    
    # Controle de tempo
    data_inicio = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Início"
    )
    
    data_ultima_atividade = models.DateTimeField(
        auto_now=True,
        verbose_name="Data da Última Atividade"
    )
    
    data_conclusao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Conclusão"
    )
    
    tempo_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo Total (segundos)",
        help_text="Tempo total para completar o fluxo"
    )
    
    # Controle de tentativas
    tentativas_atual = models.PositiveIntegerField(
        default=0,
        verbose_name="Tentativas Atuais"
    )
    
    max_tentativas = models.PositiveIntegerField(
        default=3,
        verbose_name="Máximo de Tentativas"
    )
    
    # Dados do atendimento
    dados_respostas = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name="Dados das Respostas",
        help_text="JSON com todas as respostas do usuário"
        
        
    )
    
    observacoes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações",
        help_text="Observações sobre o atendimento"
    )
    
    # Campos de auditoria
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent"
    )
    
    dispositivo = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Dispositivo",
        help_text="Tipo de dispositivo usado"
    )
    
    # Campos para integração
    id_externo = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID Externo",
        help_text="ID em sistema externo (ex: Hubsoft)"
    )
    
    resultado_final = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado Final",
        help_text="Resultado processado do atendimento"
    )
    
    score_qualificacao = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Score de Qualificação",
        help_text="Score calculado baseado nas respostas"
    )
    
    class Meta:
        db_table = 'atendimentos_fluxo'
        verbose_name = "Atendimento de Fluxo"
        verbose_name_plural = "🤖 03. Atendimentos de Fluxo"
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['lead']),
            models.Index(fields=['fluxo']),
            models.Index(fields=['status']),
            models.Index(fields=['data_inicio']),
            models.Index(fields=['questao_atual']),
            models.Index(fields=['id_externo']),
            # Índices compostos para consultas eficientes
            models.Index(fields=['lead', 'status']),
            models.Index(fields=['fluxo', 'status']),
            models.Index(fields=['data_inicio', 'status']),
        ]
    
    def __str__(self):
        return f"{self.lead.nome_razaosocial} - {self.fluxo.nome} ({self.status})"
    
    def get_status_display(self):  # compatível com chamadas existentes
        if not self.status:
            return "Não definido"
        try:
            return StatusConfiguravel.get_label('atendimento_status', self.status)
        except Exception:
            mapping = dict(self.STATUS_CHOICES)
            return mapping.get(self.status, self.status)
    
    def get_progresso_percentual(self):
        """Retorna progresso em percentual"""
        if not self.total_questoes or self.total_questoes == 0:
            return 0
        return round((self.questoes_respondidas / self.total_questoes) * 100, 1)
    
    def get_questao_atual_obj(self):
        """Retorna objeto da questão atual"""
        return self.fluxo.get_questao_por_indice(self.questao_atual)
    
    def get_proxima_questao(self):
        """Retorna próxima questão a ser exibida"""
        return self.fluxo.get_proxima_questao(self.questao_atual)
    
    def get_questao_anterior(self):
        """Retorna questão anterior"""
        return self.fluxo.get_questao_anterior(self.questao_atual)
    
    def pode_avancar(self):
        """Verifica se pode avançar para próxima questão"""
        questao_atual = self.get_questao_atual_obj()
        if not questao_atual:
            return False
        
        # Verificar se a questão atual foi respondida
        resposta_atual = self.dados_respostas.get(str(self.questao_atual))
        if questao_atual.tipo_validacao == 'obrigatoria' and not resposta_atual:
            return False
        
        return True
    
    def pode_voltar(self):
        """Verifica se pode voltar para questão anterior"""
        questao_atual = self.get_questao_atual_obj()
        if not questao_atual:
            return False
        
        return questao_atual.permite_voltar and self.questao_atual > 1
    
    def responder_questao_inteligente(self, indice_questao, resposta, contexto=None, ip_origem=None, user_agent=None):
        """
        Registra resposta para uma questão usando sistema inteligente
        Retorna (sucesso, mensagem, proxima_acao, dados_extras)
        """
        questao = self.fluxo.get_questao_por_indice(indice_questao)
        if not questao:
            return False, "Questão não encontrada", None, {}

        # Fluxos de upgrade: enriquece o contexto a partir do próprio
        # atendimento (lead_id, id_servico_hubsoft_atual) pra que a
        # validação de opções dinâmicas e o roteamento funcionem sem o
        # canal precisar mandar esses dados manualmente.
        try:
            from .services.upgrade_plano_service import enriquecer_contexto_upgrade
            contexto = enriquecer_contexto_upgrade(self, contexto)
        except Exception:
            pass

        # Verificar número de tentativas para esta questão
        tentativa_numero = self.tentativas_respostas.filter(questao=questao).count() + 1
        
        # Criar registro da tentativa
        tentativa = TentativaResposta.objects.create(
            atendimento=self,
            questao=questao,
            tentativa_numero=tentativa_numero,
            resposta_original=resposta,
            contexto_tentativa=contexto or {},
            ip_origem=ip_origem,
            user_agent=user_agent
        )
        
        # Validação inteligente
        valido, mensagem_erro, dados_validacao = questao.validar_resposta(resposta, contexto, tentativa_numero)
        
        # Atualizar tentativa com resultado
        tentativa.valida = valido
        tentativa.mensagem_erro = mensagem_erro
        tentativa.resposta_processada = dados_validacao
        
        # Extrair dados específicos da validação
        if 'resultado_ia' in dados_validacao:
            tentativa.resultado_ia = dados_validacao['resultado_ia']
            tentativa.confianca_ia = dados_validacao['resultado_ia'].get('confianca', 0)
        
        if 'resultado_webhook' in dados_validacao:
            tentativa.resultado_webhook = dados_validacao['resultado_webhook']
        
        tentativa.save()
        
        # Se resposta é válida
        if valido:
            # Executar webhook pós-resposta
            questao.executar_webhook_pos_resposta(resposta, contexto)
            
            # Verificar se esta questão já foi respondida antes
            questao_ja_respondida = str(indice_questao) in self.dados_respostas
            
            # Registrar resposta nos dados do atendimento
            self.dados_respostas[str(indice_questao)] = {
                'resposta': resposta,
                'data_resposta': timezone.now().isoformat(),
                'valida': True,
                'tentativas': tentativa_numero,
                'dados_validacao': dados_validacao
            }
            
            # Atualizar contadores
            if not questao_ja_respondida:
                self.questoes_respondidas += 1
            
            # Determinar próxima ação usando roteamento inteligente
            proxima_questao, acao_especial, dados_roteamento = questao.get_proxima_questao_inteligente(resposta, contexto)
            
            self.save()
            
            if acao_especial:
                return True, "Resposta válida", acao_especial, {
                    'dados_roteamento': dados_roteamento,
                    'dados_validacao': dados_validacao,
                    'tentativas': tentativa_numero
                }
            elif proxima_questao:
                return True, "Resposta válida", 'proxima_questao', {
                    'proxima_questao': proxima_questao,
                    'dados_roteamento': dados_roteamento,
                    'dados_validacao': dados_validacao,
                    'tentativas': tentativa_numero
                }
            else:
                return True, "Resposta válida", 'finalizar_fluxo', {
                    'dados_roteamento': dados_roteamento,
                    'dados_validacao': dados_validacao,
                    'tentativas': tentativa_numero
                }
        
        # Se resposta é inválida, aplicar estratégia de erro
        else:
            acao_erro, dados_acao = questao.aplicar_estrategia_erro(tentativa_numero, contexto)
            tentativa.estrategia_aplicada = acao_erro
            tentativa.save()
            
            return False, mensagem_erro, acao_erro, {
                'dados_acao': dados_acao,
                'tentativas': tentativa_numero,
                'max_tentativas': questao.max_tentativas,
                'dados_validacao': dados_validacao
            }
    
    def responder_questao(self, indice_questao, resposta, validar=True):
        """
        Método legado mantido para compatibilidade
        """
        resultado = self.responder_questao_inteligente(indice_questao, resposta)
        return resultado[0], resultado[1]
    
    def avancar_questao(self):
        """
        Avança para próxima questão
        Retorna (sucesso, proxima_questao)
        """
        if not self.pode_avancar():
            return False, "Não é possível avançar"
        
        proxima_questao = self.get_proxima_questao()
        if proxima_questao:
            self.questao_atual = proxima_questao.indice
            self.save()
            return True, proxima_questao
        
        # Se não há próxima questão, finalizar
        self.finalizar_atendimento()
        return True, None
    
    def voltar_questao(self):
        """
        Volta para questão anterior
        Retorna (sucesso, questao_anterior)
        """
        if not self.pode_voltar():
            return False, "Não é possível voltar"
        
        questao_anterior = self.get_questao_anterior()
        if questao_anterior:
            self.questao_atual = questao_anterior.indice
            self.save()
            return True, questao_anterior
        
        return False, "Questão anterior não encontrada"
    
    def finalizar_atendimento(self, sucesso=True):
        """
        Finaliza o atendimento
        """
        self.status = 'completado' if sucesso else 'abandonado'
        self.data_conclusao = timezone.now()
        
        # Calcular tempo total
        if self.data_inicio and self.data_conclusao:
            tempo_delta = self.data_conclusao - self.data_inicio
            self.tempo_total = int(tempo_delta.total_seconds())
        
        # Calcular score de qualificação
        self.score_qualificacao = self.calcular_score_qualificacao()
        
        self.save()
        
        # Atualizar lead se necessário
        self.atualizar_lead_com_resultados()
    
    def calcular_score_qualificacao(self):
        """
        Calcula score de qualificação baseado nas respostas
        """
        score = 5  # Score base
        
        # Lógica de cálculo baseada no tipo de fluxo e respostas
        if self.fluxo.tipo_fluxo == 'qualificacao':
            # Score baseado em respostas específicas
            for indice, dados in self.dados_respostas.items():
                questao = self.fluxo.get_questao_por_indice(int(indice))
                if questao and dados.get('valida'):
                    # Lógica específica para cada tipo de questão
                    if questao.tipo_questao == 'escala':
                        try:
                            valor = int(dados['resposta'])
                            if valor >= 8:
                                score += 2
                            elif valor >= 6:
                                score += 1
                            elif valor <= 3:
                                score -= 1
                        except:
                            pass
        
        return max(1, min(10, score))
    
    def atualizar_lead_com_resultados(self):
        """
        Atualiza o lead com resultados do atendimento
        """
        if self.status == 'completado' and self.score_qualificacao:
            # Atualizar score do lead
            self.lead.score_qualificacao = self.score_qualificacao
            self.lead.save()
            
            # Adicionar observações sobre o fluxo
            if self.observacoes:
                if not self.lead.observacoes:
                    self.lead.observacoes = ""
                self.lead.observacoes += f"\n\nFluxo {self.fluxo.nome} ({self.data_conclusao.strftime('%d/%m/%Y %H:%M')}):\n{self.observacoes}"
                self.lead.save()
    
    def get_tempo_formatado(self):
        """Retorna tempo total formatado"""
        if self.tempo_total:
            if self.tempo_total < 60:
                return f"{self.tempo_total}s"
            elif self.tempo_total < 3600:
                minutos = self.tempo_total // 60
                segundos = self.tempo_total % 60
                return f"{minutos}m {segundos}s"
            else:
                horas = self.tempo_total // 3600
                minutos = (self.tempo_total % 3600) // 60
                return f"{horas}h {minutos}m"
        return "N/A"
    
    def get_respostas_formatadas(self):
        """Retorna respostas formatadas para exibição"""
        respostas_formatadas = []
        
        if not self.total_questoes or self.total_questoes == 0:
            return respostas_formatadas
        
        for indice in range(1, self.total_questoes + 1):
            questao = self.fluxo.get_questao_por_indice(indice)
            if questao:
                dados_resposta = self.dados_respostas.get(str(indice), {})
                resposta = dados_resposta.get('resposta', 'Não respondida')
                
                respostas_formatadas.append({
                    'indice': indice,
                    'questao': questao.titulo,
                    'resposta': resposta,
                    'respondida': bool(dados_resposta),
                    'valida': dados_resposta.get('valida', False),
                    'data_resposta': dados_resposta.get('data_resposta'),
                })
        
        return respostas_formatadas
    
    def pode_ser_reiniciado(self):
        """Verifica se o atendimento pode ser reiniciado"""
        return self.status in ['completado', 'abandonado', 'cancelado']
    
    def reiniciar_atendimento(self):
        """Reinicia o atendimento do início"""
        if not self.pode_ser_reiniciado():
            return False
        
        self.status = 'iniciado'
        self.questao_atual = 1
        self.questoes_respondidas = 0
        self.dados_respostas = {}
        self.data_inicio = timezone.now()
        self.data_conclusao = None
        self.tempo_total = None
        self.tentativas_atual += 1
        self.observacoes = None
        self.resultado_final = None
        self.score_qualificacao = None
        
        self.save()
        return True
    
    def get_estatisticas_tentativas(self):
        """Retorna estatísticas das tentativas de resposta"""
        tentativas = self.tentativas_respostas.all()
        
        if not tentativas.exists():
            return {}
        
        stats = {
            'total_tentativas': tentativas.count(),
            'tentativas_validas': tentativas.filter(valida=True).count(),
            'tentativas_invalidas': tentativas.filter(valida=False).count(),
            'questoes_com_multiplas_tentativas': tentativas.values('questao').annotate(
                total=models.Count('id')
            ).filter(total__gt=1).count(),
            'media_tentativas_por_questao': tentativas.values('questao').annotate(
                total=models.Count('id')
            ).aggregate(media=models.Avg('total'))['media'] or 0,
            'tentativas_por_ia': tentativas.filter(resultado_ia__isnull=False).count(),
            'media_confianca_ia': tentativas.filter(
                confianca_ia__isnull=False
            ).aggregate(media=models.Avg('confianca_ia'))['media'] or 0,
            'estrategias_aplicadas': list(tentativas.exclude(
                estrategia_aplicada__isnull=True
            ).values_list('estrategia_aplicada', flat=True).distinct())
        }
        
        # Taxa de sucesso
        if stats['total_tentativas'] > 0:
            stats['taxa_sucesso'] = (stats['tentativas_validas'] / stats['total_tentativas']) * 100
        else:
            stats['taxa_sucesso'] = 0
        
        return stats
    
    def get_questoes_problematicas(self):
        """Identifica questões com maior número de erros"""
        from django.db.models import Count, Avg
        
        questoes_stats = self.tentativas_respostas.values(
            'questao__id', 'questao__titulo', 'questao__indice'
        ).annotate(
            total_tentativas=Count('id'),
            tentativas_invalidas=Count('id', filter=models.Q(valida=False)),
            media_confianca_ia=Avg('confianca_ia')
        ).filter(tentativas_invalidas__gt=0).order_by('-tentativas_invalidas')
        
        problematicas = []
        for stat in questoes_stats:
            if stat['tentativas_invalidas'] >= 2:  # 2 ou mais erros
                problematicas.append({
                    'questao_id': stat['questao__id'],
                    'titulo': stat['questao__titulo'],
                    'indice': stat['questao__indice'],
                    'total_tentativas': stat['total_tentativas'],
                    'erros': stat['tentativas_invalidas'],
                    'taxa_erro': (stat['tentativas_invalidas'] / stat['total_tentativas']) * 100,
                    'media_confianca_ia': stat['media_confianca_ia'] or 0
                })
        
        return problematicas
    
    def get_contexto_dinamico(self):
        """Gera contexto dinâmico para usar em templates de questões"""
        contexto = {
            'nome_cliente': self.lead.nome_razaosocial,
            'telefone_cliente': self.lead.telefone,
            'email_cliente': self.lead.email or '',
            'progresso_percentual': self.get_progresso_percentual(),
            'questoes_respondidas': self.questoes_respondidas,
            'total_questoes': self.total_questoes,
            'tempo_atendimento': self.get_tempo_formatado(),
            'tentativas_atuais': self.tentativas_respostas.count(),
        }
        
        # Adicionar dados das respostas anteriores
        for indice, dados in self.dados_respostas.items():
            contexto[f'resposta_q{indice}'] = dados.get('resposta', '')
        
        # Adicionar dados do lead
        if self.lead.valor:
            contexto['valor_lead'] = self.lead.get_valor_formatado()
        
        if self.lead.cidade:
            contexto['cidade_cliente'] = self.lead.cidade
        
        if self.lead.estado:
            contexto['estado_cliente'] = self.lead.estado
        
        return contexto

class RespostaQuestao(models.Model):
    """
    Modelo para armazenar respostas individuais de questões
    Permite histórico detalhado e auditoria completa
    """
    atendimento = models.ForeignKey(
        AtendimentoFluxo,
        on_delete=models.CASCADE,
        related_name='respostas_detalhadas',
        verbose_name="Atendimento"
    )
    
    questao = models.ForeignKey(
        QuestaoFluxo,
        on_delete=models.CASCADE,
        related_name='respostas',
        verbose_name="Questão"
    )
    
    resposta = models.TextField(
        verbose_name="Resposta"
    )
    
    resposta_processada = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resposta Processada",
        help_text="Resposta processada/validada em formato estruturado"
    )
    
    valida = models.BooleanField(
        default=True,
        verbose_name="Válida"
    )
    
    mensagem_erro = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem de Erro"
    )
    
    tentativas = models.PositiveIntegerField(
        default=1,
        verbose_name="Tentativas"
    )
    
    data_resposta = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data da Resposta"
    )
    
    tempo_resposta = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo de Resposta (segundos)",
        help_text="Tempo para responder esta questão"
    )
    
    # Campos de auditoria
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent"
    )
    
    dados_extras = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Dados Extras",
        help_text="Dados adicionais sobre a resposta"
    )
    
    class Meta:
        db_table = 'respostas_questao'
        verbose_name = "Resposta de Questão"
        verbose_name_plural = "🔧 01. Respostas de Questões"
        ordering = ['atendimento', 'questao', '-data_resposta']
        indexes = [
            models.Index(fields=['atendimento', 'questao']),
            models.Index(fields=['data_resposta']),
            models.Index(fields=['valida']),
        ]
    
    def __str__(self):
        return f"{self.atendimento} - Q{self.questao.indice}: {self.resposta[:50]}"
    
    def get_tempo_resposta_formatado(self):
        """Retorna tempo de resposta formatado"""
        if self.tempo_resposta:
            if self.tempo_resposta < 60:
                return f"{self.tempo_resposta}s"
            else:
                minutos = self.tempo_resposta // 60
                segundos = self.tempo_resposta % 60
                return f"{minutos}m {segundos}s"
        return "N/A"

# Registrar sinais mesmo se o AppConfig não estiver referenciado diretamente em INSTALLED_APPS
from . import signals  # noqa: E402,F401

class ConfiguracaoRecontato(models.Model):
    """
    Modelo para gerenciar configurações de recontato
    """
    mensagem = models.TextField(
        verbose_name="Mensagem de Recontato"
    )
    
    tempo_recontato = models.PositiveIntegerField(
        verbose_name="Tempo para Recontato"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    class Meta:
        db_table = 'configuracoes_recontato'
        verbose_name = 'Configuração de Recontato'
        verbose_name_plural = "⚙️ 03. Configurações de Recontato"
        ordering = ['-ativo']
    
    def __str__(self):
        return f"{self.mensagem} - {self.tempo_recontato} - {self.ativo}"
    
    def get_tempo_recontato_formatado(self):
        """Retorna tempo de recontato formatado"""
        if self.tempo_recontato:
            return f"{self.tempo_recontato} dias"
        return "N/A"

class ConfiguracaoCadastro(models.Model):
    """
    Modelo para gerenciar configurações da página de cadastro
    """
    empresa = models.CharField(
        max_length=100,
        verbose_name="Nome da Empresa",
        help_text="Nome da empresa para qual esta configuração se aplica"
    )
    
    # Configurações gerais
    titulo_pagina = models.CharField(
        max_length=200,
        default="Cadastro de Cliente",
        verbose_name="Título da Página"
    )
    
    subtitulo_pagina = models.CharField(
        max_length=300,
        default="Preencha seus dados para começar",
        verbose_name="Subtítulo da Página"
    )
    
    # Configurações visuais
    logo_url = models.URLField(
        max_length=500,
        default="https://i.ibb.co/q3MyCdBZ/Ativo-33.png",
        verbose_name="URL da Logo",
        help_text="URL da imagem da logo"
    )
    
    background_type = models.CharField(
        max_length=20,
        choices=[
            ('gradient', 'Gradiente'),
            ('solid', 'Cor Sólida'),
            ('image', 'Imagem')
        ],
        default='gradient',
        verbose_name="Tipo de Background"
    )
    
    background_color_1 = models.CharField(
        max_length=7,
        default="#667eea",
        verbose_name="Cor de Background 1",
        help_text="Cor principal ou inicial do gradiente"
    )
    
    background_color_2 = models.CharField(
        max_length=7,
        default="#764ba2",
        verbose_name="Cor de Background 2",
        help_text="Cor secundária ou final do gradiente"
    )
    
    background_image_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL da Imagem de Background",
        help_text="URL da imagem de fundo (se tipo = imagem)"
    )
    
    primary_color = models.CharField(
        max_length=7,
        default="#667eea",
        verbose_name="Cor Primária",
        help_text="Cor principal para botões e destaques"
    )
    
    secondary_color = models.CharField(
        max_length=7,
        default="#764ba2",
        verbose_name="Cor Secundária",
        help_text="Cor secundária para elementos"
    )
    
    success_color = models.CharField(
        max_length=7,
        default="#2ecc71",
        verbose_name="Cor de Sucesso"
    )
    
    error_color = models.CharField(
        max_length=7,
        default="#e74c3c",
        verbose_name="Cor de Erro"
    )
    
    # Configurações de contato
    telefone_suporte = models.CharField(
        max_length=20,
        default="(89) 2221-0068",
        verbose_name="Telefone de Suporte"
    )
    
    whatsapp_suporte = models.CharField(
        max_length=20,
        default="558922210068",
        verbose_name="WhatsApp de Suporte"
    )
    
    email_suporte = models.EmailField(
        default="contato@megalinkpiaui.com.br",
        verbose_name="Email de Suporte"
    )
    
    # Configurações de planos
    mostrar_selecao_plano = models.BooleanField(
        default=True,
        verbose_name="Mostrar Seleção de Plano"
    )
    
    plano_padrao = models.ForeignKey(
        'PlanoInternet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Plano Padrão"
    )
    
    # Configurações de campos obrigatórios
    cpf_obrigatorio = models.BooleanField(
        default=True,
        verbose_name="CPF Obrigatório"
    )
    
    email_obrigatorio = models.BooleanField(
        default=True,
        verbose_name="Email Obrigatório"
    )
    
    telefone_obrigatorio = models.BooleanField(
        default=True,
        verbose_name="Telefone Obrigatório"
    )
    
    endereco_obrigatorio = models.BooleanField(
        default=True,
        verbose_name="Endereço Obrigatório"
    )
    
    # Configurações de validação
    validar_cep = models.BooleanField(
        default=True,
        verbose_name="Validar CEP"
    )
    
    validar_cpf = models.BooleanField(
        default=True,
        verbose_name="Validar CPF"
    )
    
    # Configurações de fluxo
    mostrar_progress_bar = models.BooleanField(
        default=True,
        verbose_name="Mostrar Barra de Progresso"
    )
    
    numero_etapas = models.PositiveIntegerField(
        default=4,
        verbose_name="Número de Etapas"
    )
    
    # Configurações de sucesso
    mensagem_sucesso = models.TextField(
        default="Parabéns! Seu cadastro foi realizado com sucesso.",
        verbose_name="Mensagem de Sucesso"
    )
    
    instrucoes_pos_cadastro = models.TextField(
        default="Em breve nossa equipe entrará em contato para agendar a instalação.",
        verbose_name="Instruções Pós-Cadastro"
    )
    
    # Configurações de integração
    criar_lead_automatico = models.BooleanField(
        default=True,
        verbose_name="Criar Lead Automático"
    )
    
    id_origem = models.PositiveIntegerField(
        default=148,
        verbose_name="ID Origem do Lead",
        help_text="Identificador único do lead no sistema de origem (Facebook Ads, Google Ads, etc.)"
    )
    
    id_origem_servico = models.PositiveIntegerField(
        default=63,
        verbose_name="ID Origem do Serviço",
        help_text="Identificador do serviço específico de origem do lead"
    )
    
    id_vendedor = models.PositiveIntegerField(
        default=901,
        verbose_name="ID Vendedor (RP)",
        help_text="Identificador do vendedor responsável pelo lead"
    )
    
    origem_lead_padrao = models.CharField(
        max_length=50,
        choices=LeadProspecto.ORIGEM_CHOICES,
        default='site',
        verbose_name="Origem Padrão do Lead"
    )
    
    # Configurações de notificação
    enviar_email_confirmacao = models.BooleanField(
        default=False,
        verbose_name="Enviar Email de Confirmação"
    )
    
    enviar_whatsapp_confirmacao = models.BooleanField(
        default=False,
        verbose_name="Enviar WhatsApp de Confirmação"
    )
    
    # Configurações de segurança
    captcha_obrigatorio = models.BooleanField(
        default=False,
        verbose_name="Captcha Obrigatório"
    )
    
    limite_tentativas_dia = models.PositiveIntegerField(
        default=5,
        verbose_name="Limite de Tentativas por Dia"
    )
    
    # Configurações de documentação
    solicitar_documentacao = models.BooleanField(
        default=True,
        verbose_name="Solicitar Documentação",
        help_text="Habilita etapa de envio de documentos"
    )
    
    texto_instrucao_selfie = models.TextField(
        default="Por favor, tire uma selfie segurando seu documento de identificação próximo ao rosto",
        verbose_name="Instrução para Selfie"
    )
    
    texto_instrucao_doc_frente = models.TextField(
        default="Tire uma foto nítida da frente do seu documento",
        verbose_name="Instrução para Documento Frente"
    )
    
    texto_instrucao_doc_verso = models.TextField(
        default="Tire uma foto nítida do verso do seu documento",
        verbose_name="Instrução para Documento Verso"
    )
    
    tamanho_max_arquivo_mb = models.PositiveIntegerField(
        default=5,
        verbose_name="Tamanho Máximo de Arquivo (MB)"
    )
    
    formatos_aceitos = models.CharField(
        max_length=100,
        default="jpg,jpeg,png,webp",
        verbose_name="Formatos de Arquivo Aceitos",
        help_text="Separados por vírgula"
    )
    
    # Configurações de contrato
    exibir_contrato = models.BooleanField(
        default=True,
        verbose_name="Exibir Contrato",
        help_text="Mostra contrato antes da finalização"
    )
    
    titulo_contrato = models.CharField(
        max_length=200,
        default="Termos de Serviço e Contrato",
        verbose_name="Título do Contrato"
    )
    
    texto_contrato = models.TextField(
        default="Ao assinar este contrato, você concorda com os termos e condições de prestação de serviços...",
        verbose_name="Texto do Contrato",
        help_text="Texto completo do contrato a ser exibido"
    )
    
    tempo_minimo_leitura_segundos = models.PositiveIntegerField(
        default=30,
        verbose_name="Tempo Mínimo de Leitura (segundos)",
        help_text="Tempo mínimo antes de permitir aceite"
    )
    
    texto_aceite_contrato = models.CharField(
        max_length=200,
        default="Li e concordo com os termos do contrato",
        verbose_name="Texto de Aceite do Contrato"
    )
    
    # Metadados
    ativo = models.BooleanField(
        default=True,
        verbose_name="Configuração Ativa"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    class Meta:
        db_table = 'configuracoes_cadastro'
        verbose_name = 'Configuração de Cadastro'
        verbose_name_plural = "⚙️ 02. Configurações de Cadastro"
        ordering = ['-ativo', '-data_atualizacao']
    
    def __str__(self):
        return f"Configuração - {self.empresa}"
    
    def get_configuracao_ativa(self):
        """Retorna a configuração ativa para a empresa"""
        return ConfiguracaoCadastro.objects.filter(
            empresa=self.empresa,
            ativo=True
        ).first()

class PlanoInternet(models.Model):
    """
    Modelo para gerenciar planos de internet
    """
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome do Plano"
    )
    
    descricao = models.TextField(
        verbose_name="Descrição do Plano"
    )
    
    velocidade_download = models.PositiveIntegerField(
        verbose_name="Velocidade de Download (Mbps)"
    )
    
    velocidade_upload = models.PositiveIntegerField(
        verbose_name="Velocidade de Upload (Mbps)"
    )
    
    valor_mensal = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Valor Mensal (R$)"
    )
    
    # IDs externos
    id_sistema_externo = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="ID no Sistema Externo"
    )
    
    # Características do plano
    wifi_6 = models.BooleanField(
        default=False,
        verbose_name="Wi-Fi 6"
    )
    
    suporte_prioritario = models.BooleanField(
        default=False,
        verbose_name="Suporte Prioritário"
    )
    
    suporte_24h = models.BooleanField(
        default=True,
        verbose_name="Suporte 24h"
    )
    
    upload_simetrico = models.BooleanField(
        default=True,
        verbose_name="Upload Simétrico"
    )
    
    # Configurações de exibição
    ordem_exibicao = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordem de Exibição"
    )
    
    destaque = models.CharField(
        max_length=50,
        choices=[
            ('', 'Sem Destaque'),
            ('popular', 'Mais Popular'),
            ('premium', 'Premium'),
            ('economico', 'Mais Econômico'),
            ('recomendado', 'Recomendado')
        ],
        default='',
        verbose_name="Tipo de Destaque"
    )
    
    # Status
    ativo = models.BooleanField(
        default=True,
        verbose_name="Plano Ativo"
    )
    
    # Metadados
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    class Meta:
        db_table = 'planos_internet'
        verbose_name = 'Plano de Internet'
        verbose_name_plural = "⚙️ 03. Planos de Internet"
        ordering = ['ordem_exibicao', 'valor_mensal']
    
    def __str__(self):
        return f"{self.nome} - {self.velocidade_download}MB"
    
    def get_valor_formatado(self):
        """Retorna o valor formatado em reais"""
        return f"R$ {self.valor_mensal:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    def get_velocidade_formatada(self):
        """Retorna a velocidade formatada em Mega/Giga"""
        if self.velocidade_download >= 1000:
            gb = self.velocidade_download / 1000
            return f"{gb:.0f} Giga" if gb == int(gb) else f"{gb:.1f} Giga"
        return f"{self.velocidade_download} Mega"

    @property
    def velocidade_formatada(self):
        """Alias de propriedade usado nos templates (ex.: card do /cadastro/)."""
        return self.get_velocidade_formatada()

class OpcaoVencimento(models.Model):
    """
    Modelo para gerenciar opções de vencimento de fatura
    """
    dia_vencimento = models.PositiveIntegerField(
        verbose_name="Dia do Vencimento"
    )
    
    descricao = models.CharField(
        max_length=50,
        verbose_name="Descrição"
    )
    
    ordem_exibicao = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordem de Exibição"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Opção Ativa"
    )
    
    class Meta:
        db_table = 'opcoes_vencimento'
        verbose_name = 'Opção de Vencimento'
        verbose_name_plural = "⚙️ 04. Opções de Vencimento"
        ordering = ['ordem_exibicao', 'dia_vencimento']
    
    def __str__(self):
        return f"Dia {self.dia_vencimento} - {self.descricao}"

class DocumentoLead(models.Model):
    """
    Modelo para armazenar documentos do lead/prospecto
    """
    TIPO_DOCUMENTO_CHOICES = [
        ('selfie', 'Selfie com Documento'),
        ('doc_frente', 'Documento Frente'),
        ('doc_verso', 'Documento Verso'),
        ('comprovante_residencia', 'Comprovante de Residência'),
        ('contrato_assinado', 'Contrato Assinado'),
        ('outro', 'Outro')
    ]
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('rejeitado', 'Rejeitado'),
        ('em_analise', 'Em Análise')
    ]
    
    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name="Lead/Prospecto"
    )
    
    tipo_documento = models.CharField(
        max_length=30,
        choices=TIPO_DOCUMENTO_CHOICES,
        verbose_name="Tipo de Documento"
    )
    
    arquivo_base64 = models.TextField(
        verbose_name="Arquivo em Base64",
        help_text="Imagem codificada em base64"
    )
    
    nome_arquivo = models.CharField(
        max_length=255,
        verbose_name="Nome do Arquivo"
    )
    
    tamanho_arquivo = models.PositiveIntegerField(
        verbose_name="Tamanho do Arquivo (bytes)"
    )
    
    formato_arquivo = models.CharField(
        max_length=10,
        verbose_name="Formato do Arquivo"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name="Status"
    )
    
    observacoes_validacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações da Validação"
    )
    
    data_upload = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Upload"
    )
    
    data_validacao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Validação"
    )
    
    validado_por = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Validado Por"
    )
    
    class Meta:
        db_table = 'documentos_lead'
        verbose_name = 'Documento do Lead'
        verbose_name_plural = "📈 02. Documentos do Lead"
        ordering = ['-data_upload']
        indexes = [
            models.Index(fields=['lead', 'tipo_documento']),
            models.Index(fields=['status']),
            models.Index(fields=['data_upload']),
        ]
    
    def __str__(self):
        return f"{self.lead.nome_razaosocial} - {self.get_tipo_documento_display()}"
    
    def get_imagem_url_data(self):
        """Retorna a URL data da imagem para exibição"""
        if self.arquivo_base64:
            return f"data:image/{self.formato_arquivo};base64,{self.arquivo_base64}"
        return None
    
    def validar_documento(self, status, observacoes=None, usuario=None):
        """Valida o documento"""
        self.status = status
        self.observacoes_validacao = observacoes
        self.data_validacao = timezone.now()
        self.validado_por = usuario
        self.save()

class CadastroCliente(models.Model):
    """
    Modelo para armazenar cadastros de clientes via site
    """
    # Dados pessoais
    nome_completo = models.CharField(
        max_length=255,
        verbose_name="Nome Completo"
    )
    
    cpf = models.CharField(
        max_length=14,
        verbose_name="CPF"
    )
    
    rg = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="RG"
    )
    
    email = models.EmailField(
        verbose_name="E-mail"
    )
    
    telefone = models.CharField(
        max_length=20,
        verbose_name="Telefone/WhatsApp"
    )
    
    data_nascimento = models.DateField(
        verbose_name="Data de Nascimento"
    )
    
    # Endereço
    cep = models.CharField(
        max_length=9,
        verbose_name="CEP"
    )
    
    endereco = models.CharField(
        max_length=255,
        verbose_name="Endereço"
    )
    
    numero = models.CharField(
        max_length=20,
        verbose_name="Número"
    )
    
    bairro = models.CharField(
        max_length=100,
        verbose_name="Bairro"
    )
    
    cidade = models.CharField(
        max_length=100,
        verbose_name="Cidade"
    )
    
    estado = models.CharField(
        max_length=2,
        verbose_name="Estado"
    )
    
    # Plano e vencimento
    plano_selecionado = models.ForeignKey(
        PlanoInternet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Plano Selecionado"
    )
    
    vencimento_selecionado = models.ForeignKey(
        OpcaoVencimento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Vencimento Selecionado"
    )
    
    # Status do cadastro
    STATUS_CHOICES = [
        ('iniciado', 'Iniciado'),
        ('dados_pessoais', 'Dados Pessoais Preenchidos'),
        ('endereco', 'Endereço Preenchido'),
        ('documentacao', 'Documentação Enviada'),
        ('contrato', 'Contrato Aceito'),
        ('finalizado', 'Finalizado'),
        ('erro', 'Erro'),
        ('cancelado', 'Cancelado')
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='iniciado',
        verbose_name="Status do Cadastro"
    )
    
    # Integração com Lead
    lead_gerado = models.ForeignKey(
        LeadProspecto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Lead Gerado"
    )
    
    # Metadados
    ip_cliente = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP do Cliente"
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent"
    )
    
    origem_cadastro = models.CharField(
        max_length=50,
        default='site',
        verbose_name="Origem do Cadastro"
    )
    
    data_inicio = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Início"
    )
    
    data_finalizacao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Finalização"
    )
    
    tempo_total_cadastro = models.DurationField(
        null=True,
        blank=True,
        verbose_name="Tempo Total de Cadastro"
    )
    
    # Campos de auditoria
    tentativas_etapa = models.JSONField(
        default=dict,
        verbose_name="Tentativas por Etapa"
    )
    
    campos_preenchidos = models.JSONField(
        default=dict,
        verbose_name="Campos Preenchidos"
    )
    
    erros_validacao = models.JSONField(
        default=list,
        verbose_name="Erros de Validação"
    )
    
    # Campos de documentação
    documentos_enviados = models.BooleanField(
        default=False,
        verbose_name="Documentos Enviados"
    )
    
    data_envio_documentos = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Envio dos Documentos"
    )
    
    # Campos de contrato
    contrato_aceito = models.BooleanField(
        default=False,
        verbose_name="Contrato Aceito"
    )
    
    data_aceite_contrato = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Aceite do Contrato"
    )
    
    tempo_leitura_contrato = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo de Leitura do Contrato (segundos)"
    )
    
    ip_aceite_contrato = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Aceite do Contrato"
    )
    
    class Meta:
        db_table = 'cadastros_clientes'
        verbose_name = 'Cadastro de Cliente'
        verbose_name_plural = "📈 01. Cadastros de Clientes"
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['cpf']),
            models.Index(fields=['email']),
            models.Index(fields=['telefone']),
            models.Index(fields=['status']),
            models.Index(fields=['data_inicio']),
        ]
    
    def __str__(self):
        return f"{self.nome_completo} - {self.get_status_display()}"
    
    def finalizar_cadastro(self):
        """Finaliza o cadastro e gera o lead"""
        try:
            # Calcular tempo total
            if self.data_finalizacao:
                self.tempo_total_cadastro = self.data_finalizacao - self.data_inicio
            
            # Atualizar status
            self.status = 'finalizado'
            self.save()
            
            # Gerar lead automaticamente
            if not self.lead_gerado:
                self.gerar_lead()
            
            return True
        except Exception as e:
            self.status = 'erro'
            self.erros_validacao.append(str(e))
            self.save()
            return False
    
    def gerar_lead(self):
        """Gera um lead baseado no cadastro"""
        try:
            # Buscar configuração para IDs de integração
            from vendas_web.models import ConfiguracaoCadastro
            config = ConfiguracaoCadastro.objects.filter(ativo=True).first()

            lead = LeadProspecto.objects.create(
                nome_razaosocial=self.nome_completo,
                email=self.email,
                telefone=self.telefone,
                valor=self.plano_selecionado.valor_mensal if self.plano_selecionado else None,
                origem=self.origem_cadastro or 'site',
                status_api='pendente',
                cpf_cnpj=self.cpf,
                rg=self.rg,
                data_nascimento=self.data_nascimento,
                # Endereço separado corretamente
                endereco=f"{self.endereco}, {self.numero}",
                rua=self.endereco,
                numero_residencia=self.numero,
                bairro=self.bairro,
                cidade=self.cidade,
                estado=self.estado,
                cep=self.cep,
                observacoes=f"Cadastro via site - Plano: {self.plano_selecionado.nome if self.plano_selecionado else 'Nao selecionado'}",
                # IDs de integração da configuração
                id_vendedor_rp=config.id_vendedor if config else 901,
                id_origem=str(config.id_origem) if config else '148',
                id_origem_servico=str(config.id_origem_servico) if config else '63',
                # Plano e vencimento
                id_plano_rp=self.plano_selecionado.id_sistema_externo if self.plano_selecionado else None,
                id_dia_vencimento=self.vencimento_selecionado.descricao if self.vencimento_selecionado else None,
            )
            
            # Atualizar referência
            self.lead_gerado = lead
            self.save()
            
            # Criar histórico de contato
            self.criar_historico_contato(lead)
            
            return lead
        except Exception as e:
            self.erros_validacao.append(f"Erro ao gerar lead: {str(e)}")
            self.save()
            return None
    
    def criar_historico_contato(self, lead):
        """Cria histórico de contato para o lead"""
        try:
            HistoricoContato.objects.create(
                lead=lead,
                nome_contato=self.nome_completo,
                telefone=self.telefone,
                status='fluxo_finalizado',
                observacoes=f"Cadastro finalizado via site - Plano: {self.plano_selecionado.nome if self.plano_selecionado else 'Não selecionado'}",
                data_hora_contato=self.data_finalizacao or timezone.now(),
                duracao=self.tempo_total_cadastro or timedelta(seconds=0),
                convertido_lead=True,
                data_conversao_lead=self.data_finalizacao or timezone.now(),
                origem_contato='site_cadastro',
                ip_contato=self.ip_cliente,
                user_agent=self.user_agent
            )
            return True
        except Exception as e:
            self.erros_validacao.append(f"Erro ao criar histórico: {str(e)}")
            self.save()
            return False
    
    def get_progresso_percentual(self):
        """Retorna o progresso do cadastro em percentual"""
        progresso_map = {
            'iniciado': 25,
            'dados_pessoais': 50,
            'endereco': 75,
            'finalizado': 100
        }
        return progresso_map.get(self.status, 0)
    
    def get_etapa_atual(self):
        """Retorna a etapa atual do cadastro"""
        etapas = {
            'iniciado': 1,
            'dados_pessoais': 2,
            'endereco': 3,
            'documentacao': 4,
            'contrato': 5,
            'finalizado': 6
        }
        return etapas.get(self.status, 1)
    
    def validar_dados_pessoais(self):
        """Valida os dados pessoais preenchidos"""
        erros = []
        
        if not self.nome_completo or len(self.nome_completo.strip()) < 3:
            erros.append("Nome completo deve ter pelo menos 3 caracteres")
        
        if not self.cpf or len(self.cpf.replace('.', '').replace('-', '')) != 11:
            erros.append("CPF inválido")
        
        if not self.email or '@' not in self.email:
            erros.append("Email inválido")
        
        if not self.telefone or len(self.telefone.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')) < 10:
            erros.append("Telefone inválido")
        
        if not self.data_nascimento:
            erros.append("Data de nascimento obrigatória")
        
        return erros
    
    def validar_endereco(self):
        """Valida os dados de endereço"""
        erros = []
        
        if not self.cep or len(self.cep.replace('-', '')) != 8:
            erros.append("CEP inválido")
        
        if not self.endereco or len(self.endereco.strip()) < 5:
            erros.append("Endereço deve ter pelo menos 5 caracteres")
        
        if not self.numero:
            erros.append("Número obrigatório")
        
        if not self.bairro or len(self.bairro.strip()) < 2:
            erros.append("Bairro deve ter pelo menos 2 caracteres")
        
        if not self.cidade or len(self.cidade.strip()) < 2:
            erros.append("Cidade deve ter pelo menos 2 caracteres")
        
        if not self.estado or len(self.estado) != 2:
            erros.append("Estado deve ter 2 caracteres")
        
        return erros

class AgendamentoInstalacao(models.Model):
    """Registro de agendamento de instalacao feito pelo cliente na pagina de acompanhamento."""
    TURNO_CHOICES = [('manha', 'Manha'), ('tarde', 'Tarde')]
    STATUS_CHOICES = [('pendente', 'Pendente'), ('agendado', 'Agendado'), ('erro', 'Erro')]

    lead = models.ForeignKey(LeadProspecto, on_delete=models.CASCADE, related_name='agendamentos_instalacao')
    cadastro = models.ForeignKey('CadastroCliente', on_delete=models.CASCADE, related_name='agendamentos_instalacao')
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES)
    data_instalacao = models.DateField()
    horario = models.TimeField()
    id_tecnico = models.IntegerField()
    nome_tecnico = models.CharField(max_length=255)
    id_agenda_os = models.IntegerField()
    id_cliente_servico = models.IntegerField()
    id_atendimento_matrix = models.IntegerField(null=True, blank=True)
    id_os_matrix = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    dados_resposta_atendimento = models.JSONField(default=dict, blank=True)
    dados_resposta_os = models.JSONField(default=dict, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agendamentos_instalacao'
        verbose_name = 'Agendamento de Instalacao'
        verbose_name_plural = 'Agendamentos de Instalacao'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Agendamento {self.pk} - {self.lead.nome_razaosocial} - {self.data_instalacao}"


class ConfiguracaoEmpresa(models.Model):
    """
    Modelo para configurações da empresa (nome, logo, etc.)
    """
    nome_empresa = models.CharField(
        max_length=100,
        verbose_name="Nome da Empresa",
        help_text="Nome da empresa que aparecerá no sistema",
        default="Megalink"
    )
    
    logo_empresa = models.ImageField(
        upload_to='logos/',
        verbose_name="Logo da Empresa",
        help_text="Logo da empresa (recomendado: 200x200px)",
        blank=True,
        null=True
    )
    
    cor_primaria = models.CharField(
        max_length=7,
        verbose_name="Cor Primária",
        help_text="Cor primária da empresa (formato HEX, ex: #1F3D59)",
        default="#1F3D59",
        validators=[RegexValidator(
            regex='^#[0-9A-Fa-f]{6}$',
            message='Formato inválido. Use #RRGGBB'
        )]
    )
    
    cor_secundaria = models.CharField(
        max_length=7,
        verbose_name="Cor Secundária",
        help_text="Cor secundária da empresa (formato HEX, ex: #2c5aa0)",
        default="#2c5aa0",
        validators=[RegexValidator(
            regex='^#[0-9A-Fa-f]{6}$',
            message='Formato inválido. Use #RRGGBB'
        )]
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Configuração Ativa",
        help_text="Se esta configuração está ativa"
    )
    
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "🏢 Configuração da Empresa"
        verbose_name_plural = "⚙️ 01. Configurações da Empresa"
        ordering = ['-ativo', '-data_criacao']
        app_label = 'vendas_web'
    
    def __str__(self):
        return f"{self.nome_empresa} ({'Ativo' if self.ativo else 'Inativo'})"
    
    def save(self, *args, **kwargs):
        # Se esta configuração está sendo ativada, desativar as outras
        if self.ativo:
            ConfiguracaoEmpresa.objects.filter(ativo=True).exclude(id=self.id).update(ativo=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_configuracao_ativa(cls):
        """Retorna a configuração ativa da empresa"""
        try:
            return cls.objects.filter(ativo=True).first()
        except:
            return None


# ============================================================================
# MODELOS DO SISTEMA DE NOTIFICAÇÕES
# ============================================================================

class TipoNotificacao(models.Model):
    """Tipos de notificações disponíveis no sistema"""
    TIPOS = [
        ('lead_novo', 'Novo Lead'),
        ('lead_convertido', 'Lead Convertido'),
        ('venda_aprovada', 'Venda Aprovada'),
        ('venda_rejeitada', 'Venda Rejeitada'),
        ('prospecto_aguardando', 'Prospecto Aguardando Validação'),
    ]
    
    codigo = models.CharField(
        max_length=50, 
        choices=TIPOS, 
        unique=True,
        verbose_name="Código"
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome"
    )
    descricao = models.TextField(
        verbose_name="Descrição"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    template_padrao = models.TextField(
        verbose_name="Template Padrão",
        help_text="Template padrão da mensagem"
    )
    prioridade_padrao = models.CharField(
        max_length=20,
        choices=[
            ('baixa', 'Baixa'),
            ('normal', 'Normal'),
            ('alta', 'Alta'),
            ('urgente', 'Urgente'),
        ],
        default='normal',
        verbose_name="Prioridade Padrão"
    )
    whatsapp_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuração WhatsApp",
        help_text="Configurações específicas para o canal WhatsApp"
    )
    
    class Meta:
        verbose_name = "Tipo de Notificação"
        verbose_name_plural = "📢 01. Tipos de Notificação"
        ordering = ['nome']
    
    def __str__(self):
        return self.nome

class CanalNotificacao(models.Model):
    """Canais de notificação disponíveis"""
    CANAIS = [
        ('whatsapp', 'WhatsApp'),
        ('webhook', 'Webhook'),
        ('painel', 'Painel (in-app)'),  # v2: sino/central do Megalink One
    ]
    
    codigo = models.CharField(
        max_length=20, 
        choices=CANAIS, 
        unique=True,
        verbose_name="Código"
    )
    nome = models.CharField(
        max_length=50,
        verbose_name="Nome"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    configuracao = models.JSONField(
        default=dict, 
        verbose_name="Configuração",
        help_text="Configurações específicas do canal"
    )
    icone = models.CharField(
        max_length=50,
        default="fas fa-envelope",
        verbose_name="Ícone",
        help_text="Classe do ícone FontAwesome"
    )
    
    class Meta:
        verbose_name = "Canal de Notificação"
        verbose_name_plural = "📱 02. Canais de Notificação"
        ordering = ['nome']
    
    def __str__(self):
        return self.nome

class PreferenciaNotificacao(models.Model):
    """Preferências de notificação por usuário"""
    usuario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='preferencias_notificacao'
    )
    tipo_notificacao = models.ForeignKey(
        TipoNotificacao, 
        on_delete=models.CASCADE
    )
    canal_preferido = models.ForeignKey(
        CanalNotificacao, 
        on_delete=models.CASCADE
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    horario_inicio = models.TimeField(
        default=time(8, 0), 
        verbose_name="Horário Início",
        help_text="Horário início para receber notificações"
    )
    horario_fim = models.TimeField(
        default=time(18, 0), 
        verbose_name="Horário Fim",
        help_text="Horário fim para receber notificações"
    )
    dias_semana = models.JSONField(
        default=list, 
        verbose_name="Dias da Semana",
        help_text="Dias da semana [0=segunda, 6=domingo]"
    )
    
    class Meta:
        unique_together = ['usuario', 'tipo_notificacao', 'canal_preferido']
        verbose_name = "Preferência de Notificação"
        verbose_name_plural = "⚙️ 03. Preferências de Notificação"
        ordering = ['usuario__username', 'tipo_notificacao__nome']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.tipo_notificacao.nome}"

class Notificacao(models.Model):
    """Registro de notificações enviadas"""
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviando', 'Enviando'),
        ('enviada', 'Enviada'),
        ('falhou', 'Falhou'),
        ('cancelada', 'Cancelada'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    # Dados básicos
    tipo = models.ForeignKey(
        TipoNotificacao, 
        on_delete=models.CASCADE
    )
    canal = models.ForeignKey(
        CanalNotificacao, 
        on_delete=models.CASCADE
    )
    destinatario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    destinatario_email = models.EmailField(
        null=True, 
        blank=True
    )
    destinatario_telefone = models.CharField(
        max_length=20, 
        null=True, 
        blank=True
    )
    
    # Conteúdo
    titulo = models.CharField(
        max_length=200,
        verbose_name="Título"
    )
    mensagem = models.TextField(
        verbose_name="Mensagem"
    )
    dados_contexto = models.JSONField(
        default=dict, 
        verbose_name="Dados de Contexto",
        help_text="Dados para personalização"
    )
    
    # Controle
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pendente'
    )
    prioridade = models.CharField(
        max_length=20, 
        choices=PRIORIDADE_CHOICES, 
        default='normal'
    )
    tentativas = models.PositiveIntegerField(
        default=0
    )
    max_tentativas = models.PositiveIntegerField(
        default=3
    )
    # NOTA (v2): a leitura no painel é registrada em
    # dados_contexto['lida_em'] (ISO datetime) — sem schema change, pois o
    # banco é compartilhado com o v1. Ver vendas_web/views_notificacoes_v2.py.

    # Timestamps
    data_criacao = models.DateTimeField(
        default=timezone.now
    )
    data_envio = models.DateTimeField(
        null=True, 
        blank=True
    )
    data_agendamento = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Para envio agendado"
    )
    
    # N8N Integration
    n8n_webhook_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True
    )
    n8n_execution_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True
    )
    n8n_response = models.JSONField(
        null=True, 
        blank=True
    )
    
    # Logs
    erro_detalhes = models.TextField(
        null=True, 
        blank=True
    )
    
    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "📨 04. Notificações"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['data_criacao']),
            models.Index(fields=['tipo']),
            models.Index(fields=['canal']),
        ]
    
    def __str__(self):
        return f"{self.tipo.nome} - {self.destinatario or self.destinatario_email}"

class TemplateNotificacao(models.Model):
    """Templates de notificação por canal"""
    tipo_notificacao = models.ForeignKey(
        TipoNotificacao, 
        on_delete=models.CASCADE
    )
    canal = models.ForeignKey(
        CanalNotificacao, 
        on_delete=models.CASCADE
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome do Template"
    )
    assunto = models.CharField(
        max_length=200, 
        verbose_name="Assunto",
        help_text="Assunto para email"
    )
    corpo_html = models.TextField(
        verbose_name="Corpo HTML",
        help_text="Template HTML"
    )
    corpo_texto = models.TextField(
        verbose_name="Corpo Texto",
        help_text="Template texto simples"
    )
    variaveis = models.JSONField(
        default=list, 
        verbose_name="Variáveis",
        help_text="Lista de variáveis disponíveis"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    class Meta:
        unique_together = ['tipo_notificacao', 'canal']
        verbose_name = "Template de Notificação"
        verbose_name_plural = "📝 05. Templates de Notificação"
        ordering = ['tipo_notificacao__nome', 'canal__nome']
    
    def __str__(self):
        return f"{self.tipo_notificacao.nome} - {self.canal.nome}"

# ============================================================================
# GESTÃO DE CAMPANHAS DE TRÁFEGO PAGO
# ============================================================================

class CampanhaTrafego(models.Model):
    """
    Modelo para gerenciar campanhas de tráfego pago com detecção por palavra-chave
    """
    PLATAFORMA_CHOICES = [
        ('google_ads', 'Google Ads'),
        ('facebook_ads', 'Facebook Ads'),
        ('instagram_ads', 'Instagram Ads'),
        ('tiktok_ads', 'TikTok Ads'),
        ('linkedin_ads', 'LinkedIn Ads'),
        ('email', 'Email Marketing'),
        ('sms', 'SMS Marketing'),
        ('whatsapp', 'WhatsApp Business'),
        ('outro', 'Outro'),
    ]
    
    TIPO_TRAFEGO_CHOICES = [
        ('pago', 'Tráfego Pago'),
        ('organico', 'Tráfego Orgânico'),
        ('hibrido', 'Híbrido'),
    ]
    
    TIPO_MATCH_CHOICES = [
        ('exato', 'Match Exato'),
        ('parcial', 'Match Parcial'),
        ('regex', 'Expressão Regular'),
    ]
    
    # Identificação
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome da Campanha",
        help_text="Nome descritivo da campanha"
    )
    
    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código Único",
        help_text="Código identificador único (ex: BF2024, CUPOM50)"
    )
    
    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da campanha"
    )
    
    # Palavra-chave (integrada)
    palavra_chave = models.CharField(
        max_length=200,
        verbose_name="Palavra-chave",
        help_text="Palavra ou termo que identifica esta campanha"
    )
    
    tipo_match = models.CharField(
        max_length=20,
        choices=TIPO_MATCH_CHOICES,
        default='parcial',
        verbose_name="Tipo de Detecção",
        help_text="Como a palavra-chave será detectada na mensagem"
    )
    
    case_sensitive = models.BooleanField(
        default=False,
        verbose_name="Case Sensitive",
        help_text="Diferenciar maiúsculas de minúsculas"
    )
    
    # Classificação
    plataforma = models.CharField(
        max_length=50,
        choices=PLATAFORMA_CHOICES,
        verbose_name="Plataforma",
        help_text="Plataforma de origem do tráfego"
    )
    
    tipo_trafego = models.CharField(
        max_length=50,
        choices=TIPO_TRAFEGO_CHOICES,
        blank=True,
        verbose_name="Tipo de Tráfego"
    )
    
    # Configurações
    prioridade = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Prioridade",
        help_text="Prioridade para desempate (1-10)"
    )
    
    ativa = models.BooleanField(
        default=True,
        verbose_name="Ativa",
        help_text="Se a campanha está ativa para detecção"
    )
    
    # Período
    data_inicio = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Início"
    )
    
    data_fim = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Término"
    )
    
    # Comercial
    url_destino = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL de Destino",
        help_text="URL da landing page ou destino da campanha"
    )
    
    orcamento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Orçamento",
        help_text="Orçamento total da campanha em R$"
    )
    
    meta_leads = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Meta de Leads",
        help_text="Quantidade de leads esperada"
    )
    
    # Estatísticas (auto-calculadas)
    contador_deteccoes = models.IntegerField(
        default=0,
        verbose_name="Total de Detecções",
        help_text="Contador automático de detecções"
    )
    
    ultima_deteccao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última Detecção"
    )
    
    # UI/Visual
    cor_identificacao = models.CharField(
        max_length=7,
        default='#667eea',
        verbose_name="Cor de Identificação",
        help_text="Cor hexadecimal para identificação visual"
    )
    
    ordem_exibicao = models.IntegerField(
        default=0,
        verbose_name="Ordem de Exibição"
    )
    
    # Metadados
    observacoes = models.TextField(
        blank=True,
        verbose_name="Observações"
    )
    
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por"
    )
    
    class Meta:
        db_table = 'campanha_trafego'
        verbose_name = "Campanha de Tráfego"
        verbose_name_plural = "📢 Campanhas de Tráfego"
        ordering = ['-ativa', 'ordem_exibicao', 'nome']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['ativa']),
            models.Index(fields=['palavra_chave']),
            models.Index(fields=['plataforma']),
        ]
    
    def __str__(self):
        return f"{self.nome} ({self.codigo})"
    
    @property
    def esta_no_periodo(self):
        """Verifica se a campanha está dentro do período ativo"""
        from datetime import date
        hoje = date.today()
        
        if self.data_inicio and hoje < self.data_inicio:
            return False
        if self.data_fim and hoje > self.data_fim:
            return False
        return True
    
    @property
    def esta_ativa(self):
        """Verifica se a campanha está ativa E dentro do período"""
        return self.ativa and self.esta_no_periodo
    
    @property
    def total_leads(self):
        """Total de leads gerados por esta campanha"""
        return LeadProspecto.objects.filter(campanha_origem=self).count()
    
    @property
    def total_conversoes(self):
        """Total de vendas convertidas"""
        return self.deteccoes.filter(converteu_venda=True).count()
    
    @property
    def taxa_conversao(self):
        """Taxa de conversão percentual"""
        if self.contador_deteccoes == 0:
            return 0
        return round((self.total_conversoes / self.contador_deteccoes) * 100, 2)
    
    @property
    def receita_total(self):
        """Receita total gerada pela campanha"""
        from django.db.models import Sum
        total = self.deteccoes.filter(converteu_venda=True).aggregate(
            total=Sum('valor_venda')
        )['total']
        return total or Decimal('0.00')
    
    @property
    def roi(self):
        """Retorno sobre investimento"""
        if not self.orcamento or self.orcamento == 0:
            return None
        return round(((self.receita_total - self.orcamento) / self.orcamento) * 100, 2)

class DeteccaoCampanha(models.Model):
    """
    Modelo para registrar detecções de campanhas em mensagens de clientes
    """
    ORIGEM_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('chat', 'Chat Web'),
        ('telefone', 'Telefone'),
    ]
    
    METODO_DETECCAO_CHOICES = [
        ('exato', 'Match Exato'),
        ('parcial', 'Match Parcial'),
        ('regex', 'Expressão Regular'),
    ]
    
    # Relacionamentos
    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deteccoes_campanha',
        verbose_name="Lead"
    )
    
    campanha = models.ForeignKey(
        CampanhaTrafego,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deteccoes',
        verbose_name="Campanha"
    )
    
    # Dados da Mensagem
    telefone = models.CharField(
        max_length=20,
        verbose_name="Telefone"
    )
    
    mensagem_original = models.TextField(
        verbose_name="Mensagem Original"
    )
    
    mensagem_normalizada = models.TextField(
        blank=True,
        verbose_name="Mensagem Normalizada",
        help_text="Versão normalizada para processamento"
    )
    
    tamanho_mensagem = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tamanho da Mensagem"
    )
    
    # Detecção
    trecho_detectado = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Trecho Detectado",
        help_text="Parte da mensagem que deu match"
    )
    
    posicao_inicio = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Posição Inicial"
    )
    
    posicao_fim = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Posição Final"
    )
    
    metodo_deteccao = models.CharField(
        max_length=20,
        choices=METODO_DETECCAO_CHOICES,
        blank=True,
        verbose_name="Método de Detecção"
    )
    
    score_confianca = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Score de Confiança",
        help_text="Percentual de confiança (0-100%)"
    )
    
    # Contexto
    eh_primeira_mensagem = models.BooleanField(
        default=False,
        verbose_name="É Primeira Mensagem",
        help_text="Se é a primeira mensagem do cliente"
    )
    
    origem = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default='whatsapp',
        verbose_name="Origem"
    )
    
    timestamp_mensagem = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Timestamp da Mensagem"
    )
    
    # Dados Técnicos
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )
    
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="User Agent"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadata",
        help_text="Dados adicionais em formato JSON"
    )
    
    # Validação Manual
    aceita = models.BooleanField(
        default=True,
        verbose_name="Detecção Aceita",
        help_text="Se a detecção foi validada como correta"
    )
    
    motivo_rejeicao = models.TextField(
        blank=True,
        verbose_name="Motivo da Rejeição"
    )
    
    rejeitada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deteccoes_rejeitadas',
        verbose_name="Rejeitada por"
    )
    
    data_rejeicao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Rejeição"
    )
    
    # Integração N8N
    processado_n8n = models.BooleanField(
        default=False,
        verbose_name="Processado pelo N8N"
    )
    
    data_processamento_n8n = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Processamento N8N"
    )
    
    resposta_n8n = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Resposta do N8N"
    )
    
    # Conversão
    converteu_venda = models.BooleanField(
        default=False,
        verbose_name="Converteu em Venda"
    )
    
    data_conversao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Conversão"
    )
    
    valor_venda = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor da Venda"
    )
    
    # Auditoria
    detectado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Detectado em"
    )
    
    class Meta:
        db_table = 'deteccao_campanha'
        verbose_name = "Detecção de Campanha"
        verbose_name_plural = "📊 Detecções de Campanhas"
        ordering = ['-detectado_em']
        indexes = [
            models.Index(fields=['telefone']),
            models.Index(fields=['lead']),
            models.Index(fields=['campanha']),
            models.Index(fields=['-detectado_em']),
            models.Index(fields=['aceita']),
            models.Index(fields=['converteu_venda']),
        ]
    
    def __str__(self):
        campanha_nome = self.campanha.nome if self.campanha else "Sem campanha"
        return f"{campanha_nome} - {self.telefone} - {self.detectado_em.strftime('%d/%m/%Y %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Normalizar mensagem automaticamente
        if self.mensagem_original and not self.mensagem_normalizada:
            import unicodedata
            self.mensagem_normalizada = unicodedata.normalize('NFKD', self.mensagem_original.lower())
            self.mensagem_normalizada = self.mensagem_normalizada.encode('ASCII', 'ignore').decode('ASCII')
        
        # Calcular tamanho
        if self.mensagem_original:
            self.tamanho_mensagem = len(self.mensagem_original)
        
        super().save(*args, **kwargs)
        
        # Atualizar contador da campanha
        if self.campanha and self.aceita:
            self.campanha.contador_deteccoes = self.campanha.deteccoes.filter(aceita=True).count()
            self.campanha.ultima_deteccao = timezone.now()
            self.campanha.save()

# ============================================================================
# VIABILIDADE TÉCNICA — CIDADES / CEPs ATENDIDOS
# ============================================================================

class CidadeViabilidade(models.Model):
    """
    Regiões onde há viabilidade técnica de atendimento.
    Pode-se cadastrar por cidade (com UF) e/ou por CEP específico.
    Na consulta, se o CEP informado não estiver cadastrado diretamente mas
    a cidade já constar na lista, o sistema sinaliza viabilidade pela cidade.
    """

    ESTADO_CHOICES = [
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'),
        ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'),
        ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'), ('MG', 'Minas Gerais'),
        ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'), ('PE', 'Pernambuco'),
        ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'),
        ('SC', 'Santa Catarina'), ('SP', 'São Paulo'), ('SE', 'Sergipe'),
        ('TO', 'Tocantins'),
    ]

    cidade = models.CharField(
        max_length=120,
        verbose_name="Cidade",
        help_text="Nome da cidade com viabilidade técnica",
        db_index=True,
    )
    estado = models.CharField(
        max_length=2,
        choices=ESTADO_CHOICES,
        verbose_name="Estado (UF)",
        db_index=True,
    )
    regional = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="Regional",
        help_text="Regional responsável pelo atendimento desta cidade (ex: REGIONAL - 01)",
        db_index=True,
    )
    cep = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="CEP Específico",
        help_text="CEP exato com viabilidade (opcional, formato: 00000-000). "
                  "Se não informado, toda a cidade é considerada viável.",
        validators=[RegexValidator(
            regex=r'^\d{5}-?\d{3}$',
            message='CEP deve estar no formato 00000-000 ou 00000000',
        )],
        db_index=True,
    )
    atende_cidade_inteira = models.BooleanField(
        default=False,
        verbose_name="Atende a cidade inteira",
        help_text="Marque se temos viabilidade em TODA a cidade, independente do bairro. "
                  "Nesse caso a lista de bairros abaixo é só informativa (não restringe a venda). "
                  "Deixe desmarcado se a viabilidade é restrita aos bairros cadastrados.",
        db_index=True,
    )
    observacao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observação",
        help_text="Informações adicionais sobre esta região (tecnologia disponível, restrições, etc.)",
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Desative para suspender temporariamente sem excluir o registro",
        db_index=True,
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Cidade com Viabilidade"
        verbose_name_plural = "📡 Viabilidade Técnica — Cidades"
        ordering = ['estado', 'cidade', 'cep']
        app_label = 'vendas_web'
        indexes = [
            models.Index(fields=['cidade', 'estado']),
            models.Index(fields=['regional']),
        ]

    def __str__(self):
        base = f"{self.cidade}/{self.estado}"
        if self.cep:
            base += f" — CEP {self.cep}"
        if self.regional:
            base += f" [{self.regional}]"
        if self.atende_cidade_inteira:
            base += " (cidade inteira)"
        return base

    def cep_normalizado(self):
        """Retorna CEP sem traço (somente dígitos)."""
        return (self.cep or '').replace('-', '')

    def save(self, *args, **kwargs):
        # Normaliza CEP: insere traço se vier somente com 8 dígitos
        if self.cep:
            digits = self.cep.replace('-', '')
            if len(digits) == 8:
                self.cep = f"{digits[:5]}-{digits[5:]}"
        # Normaliza capitalização da cidade
        if self.cidade:
            self.cidade = self.cidade.strip().title()
        super().save(*args, **kwargs)


class BairroViabilidade(models.Model):
    """
    Bairro específico com viabilidade técnica dentro de uma cidade.
    Uma CidadeViabilidade pode ter vários bairros atendidos — cada um
    opcionalmente com o próprio CEP. Se a cidade não tiver nenhum bairro
    cadastrado, considera-se toda a cidade viável (comportamento anterior).
    """

    cidade = models.ForeignKey(
        CidadeViabilidade,
        on_delete=models.CASCADE,
        related_name='bairros',
        verbose_name="Cidade",
    )
    nome = models.CharField(
        max_length=120,
        verbose_name="Bairro",
        help_text="Nome do bairro atendido",
        db_index=True,
    )
    cep = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="CEP do bairro",
        help_text="CEP específico do bairro (opcional, formato: 00000-000).",
        validators=[RegexValidator(
            regex=r'^\d{5}-?\d{3}$',
            message='CEP deve estar no formato 00000-000 ou 00000000',
        )],
        db_index=True,
    )
    observacao = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Observação",
        help_text="Informação adicional sobre este bairro (opcional)",
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Desative para suspender este bairro sem excluir",
        db_index=True,
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Bairro com Viabilidade"
        verbose_name_plural = "Bairros com Viabilidade"
        ordering = ['nome']
        app_label = 'vendas_web'
        constraints = [
            models.UniqueConstraint(
                fields=['cidade', 'nome'],
                name='uniq_bairro_por_cidade',
            ),
        ]
        indexes = [
            models.Index(fields=['nome']),
        ]

    def __str__(self):
        base = self.nome
        if self.cep:
            base += f" — {self.cep}"
        return f"{base} ({self.cidade.cidade}/{self.cidade.estado})"

    def cep_normalizado(self):
        """Retorna CEP sem traço (somente dígitos)."""
        return (self.cep or '').replace('-', '')

    def save(self, *args, **kwargs):
        # Normaliza CEP: insere traço se vier somente com 8 dígitos
        if self.cep:
            digits = self.cep.replace('-', '')
            if len(digits) == 8:
                self.cep = f"{digits[:5]}-{digits[5:]}"
        # Normaliza capitalização do bairro
        if self.nome:
            self.nome = self.nome.strip().title()
        super().save(*args, **kwargs)


# ════════════════════════════════════════════════════════════════════
#  NEW SERVICE — contratação de novo serviço pra cliente Hubsoft existente
# ════════════════════════════════════════════════════════════════════
class NewService(models.Model):
    """Contratação de um NOVO serviço por um cliente que já existe no Hubsoft.

    O fluxo de coleta é o mesmo do cadastro inicial (endereço, plano,
    docs, agendamento), mas os dados são gravados aqui ao invés de
    sobrescreverem o `LeadProspecto` (que reflete o cadastro original).

    Por enquanto NÃO há integração com Hubsoft: o registro fica aqui
    aguardando ação humana pra concretizar a contratação.
    """

    STATUS_CHOICES = [
        ('em_coleta',            'Em coleta (conversando com cliente)'),
        ('aguardando_validacao', 'Aguardando validação dos documentos'),
        ('documentos_validos',   'Documentos validados'),
        ('finalizado',           'Finalizado'),
        ('cancelado',            'Cancelado'),
    ]

    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.CASCADE,
        related_name='novos_servicos',
        verbose_name='Lead (cliente Hubsoft)',
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='em_coleta',
        db_index=True,
    )

    # ─── Tipo de imóvel ────────────────────────────────────────────
    tipo_imovel = models.CharField(
        max_length=20, blank=True,
        choices=[('casa', 'Casa / Residencial'), ('empresa', 'Empresa / Comercial')],
    )
    tipo_residencia = models.CharField(
        max_length=20, blank=True, default='',
        choices=[
            ('casa_terrea', 'Casa térrea / Sobrado'),
            ('apartamento', 'Apartamento'),
            ('condominio',  'Condomínio fechado'),
        ],
    )

    # ─── Endereço de instalação (pode ser diferente do cadastro) ───
    cep = models.CharField(max_length=10, blank=True, default='')
    rua = models.CharField(max_length=255, blank=True, default='')
    numero_residencia = models.CharField(max_length=20, blank=True, default='')
    bairro = models.CharField(max_length=120, blank=True, default='')
    cidade = models.CharField(max_length=100, blank=True, default='')
    estado = models.CharField(max_length=2, blank=True, default='')
    endereco_confirmado = models.BooleanField(null=True, blank=True)
    ponto_referencia = models.CharField(max_length=255, blank=True, default='')

    # ─── Plano ──────────────────────────────────────────────────────
    id_plano_rp = models.IntegerField(null=True, blank=True)
    plano_confirmado = models.BooleanField(null=True, blank=True)
    id_dia_vencimento = models.IntegerField(null=True, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # ─── Confirmação final + ajustes ────────────────────────────────
    dados_confirmados = models.BooleanField(null=True, blank=True)
    tipo_ajuste = models.CharField(
        max_length=20, blank=True, default='',
        choices=[
            ('endereco', 'Endereço'),
            ('plano', 'Plano selecionado'),
        ],
    )

    # ─── Documentação (estado de coleta — fotos em ImagemNewService) ─
    doc_selfie_recebida = models.BooleanField(null=True, blank=True, default=None)
    doc_frente_recebida = models.BooleanField(null=True, blank=True, default=None)
    doc_verso_recebida  = models.BooleanField(null=True, blank=True, default=None)

    # ─── Agendamento ────────────────────────────────────────────────
    turno_instalacao = models.CharField(
        max_length=10, blank=True, default='',
        choices=[('manha', 'Manhã'), ('tarde', 'Tarde')],
    )
    data_instalacao = models.DateField(null=True, blank=True)

    # ─── Auditoria ──────────────────────────────────────────────────
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True, default='')

    # ─── Integração HubSoft (preenchido pelo webdriver) ─────────────
    HUBSOFT_STATUS_CHOICES = [
        ('sucesso',  'Contratação criada no HubSoft'),
        ('falha',    'Falha ao criar no HubSoft'),
        ('dry_run',  'Dry-run (sem clicar Salvar)'),
    ]
    hubsoft_processado_em = models.DateTimeField(
        null=True, blank=True, db_index=True,
        verbose_name='Processado no HubSoft em',
        help_text='Quando o webdriver concluiu (ou tentou concluir) a contratação no HubSoft',
    )
    hubsoft_processado_status = models.CharField(
        max_length=20, choices=HUBSOFT_STATUS_CHOICES,
        blank=True, default='',
        verbose_name='Resultado HubSoft',
    )
    hubsoft_erro = models.TextField(
        blank=True, default='',
        verbose_name='Mensagem de erro HubSoft',
        help_text='Última mensagem de erro do webdriver (vazio = sem erro)',
    )

    # ─── Sync Matrix (worker abre Atendimento + OS de Instalação) ───
    # Worker `processar_newservice_finalizados` processa NewServices que
    # estão com status='finalizado' e este campo='pendente'. Chama Matrix
    # API (mesma infra do agendamento normal de instalação).
    MATRIX_SYNC_CHOICES = [
        ('pendente',     'Pendente — aguardando processamento'),
        ('processando',  'Processando'),
        ('sincronizado', 'Sincronizado (Atendimento + OS abertos)'),
        ('erro',         'Erro na sincronização'),
        ('cancelado',    'Cancelado / ignorado (não abrir Atendimento+OS)'),
    ]
    matrix_sync_status = models.CharField(
        max_length=20, choices=MATRIX_SYNC_CHOICES,
        default='pendente', db_index=True,
        verbose_name='Status sync Matrix',
    )
    id_atendimento_matrix = models.BigIntegerField(null=True, blank=True)
    id_os_matrix = models.BigIntegerField(null=True, blank=True)
    id_cliente_servico_origem = models.IntegerField(
        null=True, blank=True,
        help_text='id_cliente_servico do Hubsoft usado para abrir Atendimento+OS',
    )
    data_sync_matrix = models.DateTimeField(null=True, blank=True)
    tentativas_sync_matrix = models.PositiveIntegerField(default=0)
    ultimo_erro_sync_matrix = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'new_service'
        verbose_name = 'Novo Serviço'
        verbose_name_plural = 'Novos Serviços'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['lead', 'status']),
            models.Index(fields=['status', 'hubsoft_processado_em']),
            models.Index(fields=['status', 'matrix_sync_status']),
        ]

    def __str__(self):
        return f'NewService #{self.pk} — Lead {self.lead_id} [{self.status}]'

    def save(self, *args, **kwargs):
        # Normaliza CEP (mesmo padrão do LeadProspecto)
        if self.cep:
            digits = self.cep.replace('-', '')
            if len(digits) == 8:
                self.cep = f'{digits[:5]}-{digits[5:]}'
        if self.cidade:
            self.cidade = self.cidade.strip().title()
        if self.bairro:
            self.bairro = self.bairro.strip().title()
        super().save(*args, **kwargs)


# ════════════════════════════════════════════════════════════════════
#  UPGRADE DE PLANO — migração de um cliente_servico existente
#  pra um novo plano (id_servico) no HubSoft.
# ════════════════════════════════════════════════════════════════════
class UpgradePlano(models.Model):
    """Solicitação de upgrade de plano pra um serviço já ativo no HubSoft.

    O webdriver pega rows com `status='finalizado'` e
    `hubsoft_processado_em IS NULL`, abre o wizard "Migrar para Outro
    Serviço" no HubSoft pra o `id_cliente_servico` informado, escolhe o
    `id_plano_novo` e finaliza com migração imediata ativada.

    Não precisa de endereço, vencimento ou forma de cobrança — esses
    são herdados do cliente_servico atual durante a migração.
    """

    STATUS_CHOICES = [
        ('em_coleta',  'Em coleta (montagem do pedido)'),
        ('finalizado', 'Finalizado — pronto pra processar'),
        ('cancelado',  'Cancelado'),
    ]

    HUBSOFT_STATUS_CHOICES = [
        ('sucesso',  'Upgrade aplicado no HubSoft'),
        ('falha',    'Falha ao aplicar upgrade'),
        ('dry_run',  'Dry-run (sem clicar Salvar)'),
    ]

    lead = models.ForeignKey(
        LeadProspecto,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='upgrades_plano',
        verbose_name='Lead (origem da solicitação)',
        help_text='Opcional — solicitações também podem vir de fonte sem lead vinculado',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='em_coleta', db_index=True,
    )

    # ─── Identificadores HubSoft (alvo do upgrade) ─────────────────
    id_cliente_servico = models.IntegerField(
        db_index=True,
        verbose_name='ID Cliente Serviço (HubSoft)',
        help_text='id_cliente_servico do serviço a ser migrado',
    )
    id_plano_novo = models.IntegerField(
        verbose_name='ID Plano novo (HubSoft id_servico)',
        help_text='id_servico do plano de destino no HubSoft',
    )

    # ─── Auditoria ──────────────────────────────────────────────────
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True, default='')

    # ─── Integração HubSoft (preenchido pelo webdriver) ─────────────
    hubsoft_processado_em = models.DateTimeField(
        null=True, blank=True, db_index=True,
        verbose_name='Processado no HubSoft em',
    )
    hubsoft_processado_status = models.CharField(
        max_length=20, choices=HUBSOFT_STATUS_CHOICES,
        blank=True, default='',
        verbose_name='Resultado HubSoft',
    )
    hubsoft_erro = models.TextField(
        blank=True, default='',
        verbose_name='Mensagem de erro HubSoft',
    )

    class Meta:
        db_table = 'upgrade_plano'
        verbose_name = 'Upgrade de Plano'
        verbose_name_plural = 'Upgrades de Plano'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['status', 'hubsoft_processado_em']),
            models.Index(fields=['id_cliente_servico']),
        ]

    def __str__(self):
        return (
            f'UpgradePlano #{self.pk} — cs={self.id_cliente_servico} '
            f'→ plano {self.id_plano_novo} [{self.status}]'
        )


class ImagemNewService(models.Model):
    """Imagens de documentação do fluxo de contratação de novo serviço.

    Estrutura espelhada da `ImagemLeadProspecto` — mesmo ciclo de
    aprovação (pendente → aprovado_ia → documentos_validos).
    """

    STATUS_PENDENTE    = 'pendente'
    STATUS_APROVADO_IA = 'aprovado_ia'
    STATUS_VALIDO      = 'documentos_validos'
    STATUS_REJEITADO   = 'documentos_rejeitados'

    STATUS_VALIDACAO_CHOICES = [
        (STATUS_PENDENTE,    'Pendente'),
        (STATUS_APROVADO_IA, 'Aprovado pela IA (aguardando validação humana)'),
        (STATUS_VALIDO,      'Documentos Válidos'),
        (STATUS_REJEITADO,   'Documentos Rejeitados'),
    ]

    new_service = models.ForeignKey(
        NewService,
        on_delete=models.CASCADE,
        related_name='imagens',
    )
    link_url = models.URLField(max_length=1024)
    descricao = models.CharField(max_length=255, blank=True, default='')
    status_validacao = models.CharField(
        max_length=30,
        choices=STATUS_VALIDACAO_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    observacao_validacao = models.TextField(blank=True, default='')
    data_validacao = models.DateTimeField(null=True, blank=True)
    validado_por = models.CharField(max_length=150, blank=True, default='')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'imagens_new_service'
        verbose_name = 'Imagem do Novo Serviço'
        verbose_name_plural = 'Imagens do Novo Serviço'
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['new_service']),
        ]

    def __str__(self):
        return f'Imagem #{self.pk} — NewService {self.new_service_id} [{self.status_validacao}]'


class PerfilAcesso(models.Model):
    """Perfil de acesso (RBAC) — define o que um TIPO de usuário pode VER e OPERAR.

    Configurável por uma tela de matriz. As capacidades concedidas ficam em
    `capacidades` (lista de códigos do catálogo em vendas_web/rbac.py). Um usuário
    pode ter 1+ perfis (capacidades = união). Superusuário tem tudo.
    """
    ESCOPO_CHOICES = [
        ('todos',    'Todos os registros'),
        ('pipeline', 'Registros dos pipelines que pode ver'),
        ('proprios', 'Apenas os atribuídos a ele'),
    ]

    nome = models.CharField(max_length=80, unique=True, verbose_name='Nome do Perfil')
    slug = models.SlugField(max_length=80, unique=True)
    descricao = models.CharField(max_length=255, blank=True, default='')
    cor_hex = models.CharField(max_length=7, default='#0022fa')
    ativo = models.BooleanField(default=True)
    # Lista de códigos de capacidade concedidos (catálogo em rbac.CAPACIDADES).
    capacidades = models.JSONField(default=list, blank=True)
    escopo_dados = models.CharField(max_length=12, choices=ESCOPO_CHOICES, default='proprios')
    usuarios = models.ManyToManyField(User, blank=True, related_name='perfis_acesso',
                                      verbose_name='Usuários')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'perfil_acesso'
        verbose_name = 'Perfil de Acesso'
        verbose_name_plural = 'Perfis de Acesso'
        ordering = ['nome']

    def __str__(self):
        return self.nome