from rest_framework import serializers

from apps.comercial.cadastro.models import (
    ConfiguracaoCadastro,
    PlanoInternet,
    OpcaoVencimento,
)
from apps.comercial.viabilidade.models import CidadeViabilidade
from apps.marketing.campanhas.models import CampanhaTrafego
from apps.notificacoes.models import (
    TipoNotificacao,
    CanalNotificacao,
    TemplateNotificacao,
)


# ============================================================================
# COMERCIAL — CADASTRO
# ============================================================================

class PlanoInternetSerializer(serializers.ModelSerializer):
    valor_formatado = serializers.CharField(
        source='get_valor_formatado', read_only=True
    )
    velocidade_formatada = serializers.CharField(
        source='get_velocidade_formatada', read_only=True
    )

    class Meta:
        model = PlanoInternet
        fields = '__all__'
        read_only_fields = ['tenant', 'data_criacao', 'data_atualizacao']


class OpcaoVencimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpcaoVencimento
        fields = '__all__'
        read_only_fields = ['tenant']


class ConfiguracaoCadastroSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoCadastro
        fields = '__all__'
        read_only_fields = ['tenant', 'data_criacao', 'data_atualizacao']


# ============================================================================
# COMERCIAL — VIABILIDADE
# ============================================================================

class CidadeViabilidadeSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(
        source='get_estado_display', read_only=True
    )

    class Meta:
        model = CidadeViabilidade
        fields = '__all__'
        read_only_fields = ['tenant', 'data_criacao', 'data_atualizacao']


# ============================================================================
# MARKETING — CAMPANHAS
# ============================================================================

class CampanhaTrafegoSerializer(serializers.ModelSerializer):
    esta_ativa = serializers.BooleanField(read_only=True)
    esta_no_periodo = serializers.BooleanField(read_only=True)
    total_leads = serializers.IntegerField(read_only=True)
    total_conversoes = serializers.IntegerField(read_only=True)
    taxa_conversao = serializers.FloatField(read_only=True)

    class Meta:
        model = CampanhaTrafego
        fields = '__all__'
        read_only_fields = [
            'tenant',
            'contador_deteccoes',
            'ultima_deteccao',
            'criado_em',
            'atualizado_em',
        ]


# ============================================================================
# NOTIFICACOES
# ============================================================================

class TipoNotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoNotificacao
        fields = [
            'id', 'tenant', 'codigo', 'nome', 'descricao', 'ativo',
            'template_padrao', 'prioridade_padrao', 'whatsapp_config',
        ]
        read_only_fields = fields


class CanalNotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CanalNotificacao
        fields = [
            'id', 'tenant', 'codigo', 'nome', 'ativo',
            'configuracao', 'icone',
        ]
        read_only_fields = fields


class TemplateNotificacaoSerializer(serializers.ModelSerializer):
    tipo_notificacao_nome = serializers.CharField(
        source='tipo_notificacao.nome', read_only=True
    )
    canal_nome = serializers.CharField(
        source='canal.nome', read_only=True
    )

    class Meta:
        model = TemplateNotificacao
        fields = '__all__'
        read_only_fields = ['tenant']
