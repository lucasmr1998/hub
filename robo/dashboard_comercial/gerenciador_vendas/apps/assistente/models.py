from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


class ConfiguracaoAssistenteGlobal(models.Model):
    """Configuracao global do assistente CRM (numero WhatsApp da Hubtrix). Singleton."""
    integracao_whatsapp = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assistente_whatsapp',
        verbose_name="Integracao WhatsApp (Uazapi)",
        help_text="Numero da Hubtrix usado pelo assistente"
    )
    ativo = models.BooleanField(default=False, verbose_name="Assistente ativo globalmente")
    mensagem_boas_vindas = models.TextField(
        blank=True, default='Ola {nome}! Sou o assistente Hubtrix. Como posso ajudar?',
        verbose_name="Mensagem de boas-vindas",
        help_text="Use {nome} para o nome do usuario"
    )
    mensagem_acesso_restrito = models.TextField(
        blank=True, default='Este numero e de uso exclusivo para usuarios do sistema Hubtrix.',
        verbose_name="Mensagem de acesso restrito"
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assistente_configuracao_global'
        verbose_name = "Configuracao Global do Assistente"
        verbose_name_plural = "Configuracao Global do Assistente"

    def __str__(self):
        return f"Assistente Hubtrix ({'Ativo' if self.ativo else 'Inativo'})"

    @property
    def webhook_url(self):
        if self.integracao_whatsapp and self.integracao_whatsapp.api_token:
            return f"/assistente/webhook/{self.integracao_whatsapp.api_token}/"
        return None

    @classmethod
    def get_config(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


class ConfiguracaoAssistenteTenant(models.Model):
    """Configuracao do assistente por tenant (IA, modelo). Gerenciado pelo aurora-admin."""
    tenant = models.OneToOneField(
        'sistema.Tenant', on_delete=models.CASCADE,
        related_name='config_assistente', verbose_name="Tenant"
    )
    ativo = models.BooleanField(default=False, verbose_name="Ativo para este tenant")
    integracao_ia = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assistente_ia',
        verbose_name="Integracao IA (OpenAI, etc.)"
    )
    modelo_ia = models.CharField(
        max_length=50, default='gpt-4o-mini',
        verbose_name="Modelo IA"
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assistente_configuracao_tenant'
        verbose_name = "Configuracao Assistente (Tenant)"
        verbose_name_plural = "Configuracoes Assistente (Tenant)"

    def __str__(self):
        return f"Assistente {self.tenant.nome} ({'Ativo' if self.ativo else 'Inativo'})"

    @classmethod
    def get_config(cls, tenant):
        obj, _ = cls.objects.get_or_create(tenant=tenant)
        return obj


class ConversaAssistente(TenantMixin):
    """Sessao de conversa entre um usuario e o assistente IA."""
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='conversas_assistente', verbose_name="Usuario"
    )
    telefone = models.CharField(max_length=20, verbose_name="Telefone")
    integracao = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Integracao IA"
    )
    modelo = models.CharField(max_length=50, default='gpt-4o-mini', verbose_name="Modelo IA")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")
    data_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Inicio")
    data_ultima_mensagem = models.DateTimeField(auto_now=True, verbose_name="Ultima mensagem")

    class Meta:
        db_table = 'assistente_conversas'
        verbose_name = "Conversa do Assistente"
        verbose_name_plural = "Conversas do Assistente"
        ordering = ['-data_ultima_mensagem']

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} - {self.telefone}"


class MensagemAssistente(TenantMixin):
    """Mensagem individual na conversa do assistente."""
    ROLE_CHOICES = [
        ('user', 'Usuario'),
        ('assistant', 'Assistente'),
        ('system', 'Sistema'),
    ]

    conversa = models.ForeignKey(
        ConversaAssistente, on_delete=models.CASCADE,
        related_name='mensagens', verbose_name="Conversa"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, verbose_name="Tipo")
    conteudo = models.TextField(verbose_name="Conteudo")
    tool_chamada = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name="Tool chamada",
        help_text="Nome da tool executada (se houver)"
    )
    tool_resultado = models.TextField(
        blank=True, default='',
        verbose_name="Resultado da tool"
    )
    data = models.DateTimeField(auto_now_add=True, verbose_name="Data")

    class Meta:
        db_table = 'assistente_mensagens'
        verbose_name = "Mensagem do Assistente"
        verbose_name_plural = "Mensagens do Assistente"
        ordering = ['data']

    def __str__(self):
        return f"[{self.role}] {self.conteudo[:50]}"
