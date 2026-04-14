from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


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
