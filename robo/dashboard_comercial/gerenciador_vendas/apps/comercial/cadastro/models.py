from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
from apps.sistema.mixins import TenantMixin


class ConfiguracaoCadastro(TenantMixin):
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

    ORIGEM_LEAD_CHOICES = [
        ('site', 'Site'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('google', 'Google Ads'),
        ('whatsapp', 'WhatsApp'),
        ('indicacao', 'Indicação'),
        ('telefone', 'Telefone'),
        ('email', 'Email'),
        ('outros', 'Outros'),
    ]

    origem_lead_padrao = models.CharField(
        max_length=50,
        choices=ORIGEM_LEAD_CHOICES,
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


class PlanoInternet(TenantMixin):
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
        """Retorna a velocidade formatada"""
        if self.velocidade_download >= 1000:
            return f"{self.velocidade_download/1000:.1f} GB"
        return f"{self.velocidade_download} MB"


class OpcaoVencimento(TenantMixin):
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


class DocumentoLead(TenantMixin):
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
        'leads.LeadProspecto',
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


class CadastroCliente(TenantMixin):
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
        'leads.LeadProspecto',
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
        from apps.comercial.leads.models import LeadProspecto
        try:
            # Criar lead
            lead = LeadProspecto.objects.create(
                nome_razaosocial=self.nome_completo,
                email=self.email,
                telefone=self.telefone,
                valor=self.plano_selecionado.valor_mensal if self.plano_selecionado else None,
                origem=self.origem_cadastro,
                status_api='pendente',
                cpf_cnpj=self.cpf,
                rg=self.rg,
                endereco=f"{self.endereco}, {self.numero} - {self.bairro}",
                cidade=self.cidade,
                estado=self.estado,
                cep=self.cep,
                observacoes=f"Cadastro via site - Plano: {self.plano_selecionado.nome if self.plano_selecionado else 'Não selecionado'}",
                # Definir vendedor padrão para cadastros do site (ID 538)
                id_vendedor_rp=150,
                # Definir plano e vencimento
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
        from datetime import timedelta
        from apps.comercial.leads.models import HistoricoContato
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
