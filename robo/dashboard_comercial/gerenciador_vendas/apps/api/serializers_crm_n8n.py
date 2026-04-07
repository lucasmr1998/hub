"""
Serializers DRF para endpoints CRM via N8N / agentes externos.
"""
from rest_framework import serializers
from django.contrib.auth.models import User

from apps.comercial.crm.models import (
    Pipeline, PipelineEstagio, OportunidadeVenda, TarefaCRM,
)


# =====================================================================
# Pipeline / Estagios (read-only)
# =====================================================================

class PipelineEstagioOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineEstagio
        fields = ['id', 'nome', 'slug', 'ordem', 'tipo', 'cor_hex']


class PipelineOutputSerializer(serializers.ModelSerializer):
    estagios = PipelineEstagioOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Pipeline
        fields = ['id', 'nome', 'slug', 'tipo', 'padrao', 'estagios']


# =====================================================================
# Oportunidade
# =====================================================================

class OportunidadeInputSerializer(serializers.Serializer):
    lead_id = serializers.IntegerField(help_text="ID do lead")
    pipeline_slug = serializers.CharField(required=False, default='', help_text="Slug do pipeline (vazio = padrao)")
    estagio_slug = serializers.CharField(required=False, default='', help_text="Slug do estagio (vazio = primeiro)")
    titulo = serializers.CharField(required=False, default='', help_text="Titulo da oportunidade")
    valor_estimado = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=None)
    prioridade = serializers.ChoiceField(choices=['baixa', 'normal', 'alta', 'urgente'], default='normal')
    responsavel_username = serializers.CharField(required=False, default='', help_text="Username do responsavel")


class OportunidadeUpdateSerializer(serializers.Serializer):
    estagio_slug = serializers.CharField(required=False, help_text="Mover para este estagio")
    responsavel_username = serializers.CharField(required=False, help_text="Atribuir responsavel")
    titulo = serializers.CharField(required=False)
    valor_estimado = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    prioridade = serializers.ChoiceField(choices=['baixa', 'normal', 'alta', 'urgente'], required=False)
    motivo_perda = serializers.CharField(required=False)


class OportunidadeOutputSerializer(serializers.ModelSerializer):
    lead_nome = serializers.CharField(source='lead.nome_razaosocial', read_only=True)
    lead_telefone = serializers.CharField(source='lead.telefone', read_only=True)
    estagio_nome = serializers.CharField(source='estagio.nome', read_only=True)
    estagio_slug = serializers.CharField(source='estagio.slug', read_only=True)
    pipeline_nome = serializers.CharField(source='pipeline.nome', read_only=True, default='')
    responsavel_nome = serializers.SerializerMethodField()

    class Meta:
        model = OportunidadeVenda
        fields = [
            'id', 'titulo', 'lead_nome', 'lead_telefone',
            'estagio_nome', 'estagio_slug', 'pipeline_nome',
            'valor_estimado', 'prioridade', 'probabilidade',
            'responsavel_nome', 'origem_crm',
            'data_criacao', 'data_entrada_estagio', 'ativo',
        ]

    def get_responsavel_nome(self, obj):
        if obj.responsavel:
            return obj.responsavel.get_full_name() or obj.responsavel.username
        return None


# =====================================================================
# Tarefa
# =====================================================================

class TarefaInputSerializer(serializers.Serializer):
    lead_id = serializers.IntegerField(required=False, help_text="ID do lead")
    oportunidade_id = serializers.IntegerField(required=False, help_text="ID da oportunidade")
    titulo = serializers.CharField(help_text="Titulo da tarefa")
    descricao = serializers.CharField(required=False, default='')
    tipo = serializers.ChoiceField(
        choices=['ligacao', 'whatsapp', 'email', 'visita', 'followup', 'proposta', 'instalacao', 'suporte', 'outro'],
        default='followup'
    )
    prioridade = serializers.ChoiceField(choices=['baixa', 'normal', 'alta', 'urgente'], default='normal')
    responsavel_username = serializers.CharField(required=False, default='', help_text="Username (vazio = primeiro staff)")
    data_vencimento = serializers.DateTimeField(required=False, default=None)


class TarefaUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['pendente', 'em_andamento', 'concluida', 'cancelada'],
        required=False
    )
    resultado = serializers.CharField(required=False)
    prioridade = serializers.ChoiceField(choices=['baixa', 'normal', 'alta', 'urgente'], required=False)
    responsavel_username = serializers.CharField(required=False)


class TarefaOutputSerializer(serializers.ModelSerializer):
    lead_nome = serializers.SerializerMethodField()
    responsavel_nome = serializers.SerializerMethodField()

    class Meta:
        model = TarefaCRM
        fields = [
            'id', 'titulo', 'descricao', 'tipo', 'status', 'prioridade',
            'lead_nome', 'responsavel_nome',
            'data_vencimento', 'data_conclusao', 'resultado',
            'data_criacao',
        ]

    def get_lead_nome(self, obj):
        return obj.lead.nome_razaosocial if obj.lead else None

    def get_responsavel_nome(self, obj):
        if obj.responsavel:
            return obj.responsavel.get_full_name() or obj.responsavel.username
        return None


# =====================================================================
# Inbox (enviar mensagem)
# =====================================================================

class InboxEnviarMensagemSerializer(serializers.Serializer):
    telefone = serializers.CharField(help_text="Telefone do contato (busca conversa ativa)")
    conteudo = serializers.CharField(help_text="Texto da mensagem")
    remetente_nome = serializers.CharField(required=False, default='Bot', help_text="Nome do remetente")
