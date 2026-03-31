from django.db import models
from django.core.validators import RegexValidator
from apps.sistema.mixins import TenantMixin


class CidadeViabilidade(TenantMixin):
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
    bairro = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name="Bairro",
        help_text="Bairro específico (opcional)",
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
        indexes = [
            models.Index(fields=['cidade', 'estado']),
        ]

    def __str__(self):
        base = f"{self.cidade}/{self.estado}"
        if self.cep:
            base += f" — CEP {self.cep}"
        if self.bairro:
            base += f" ({self.bairro})"
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
        if self.bairro:
            self.bairro = self.bairro.strip().title()
        super().save(*args, **kwargs)
