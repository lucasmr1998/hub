"""
Serializers para endpoints N8N / integracao externa.

Regras:
- Nao expor campos internos (tenant, ip_aceite_contrato, dados_extras etc.)
- Nao expor campos sensiveis (senha, mac_addr, ipv4, ipv6 etc.)
- Input serializers: apenas campos que o N8N precisa enviar
- Output serializers: campos de leitura uteis para o N8N consumir
"""

from rest_framework import serializers

from apps.comercial.leads.models import (
    LeadProspecto,
    ImagemLeadProspecto,
    Prospecto,
    HistoricoContato,
)
from apps.comercial.atendimento.models import (
    FluxoAtendimento,
    QuestaoFluxo,
    AtendimentoFluxo,
    RespostaQuestao,
)


# =====================================================================
# LeadProspecto
# =====================================================================

class LeadInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadProspecto
        fields = [
            'nome_razaosocial',
            'email',
            'telefone',
            'cpf_cnpj',
            'valor',
            'origem',
            'endereco',
            'cidade',
            'estado',
            'cep',
            'bairro',
            'status_api',
            'id_hubsoft',
            'score_qualificacao',
            'observacoes',
            'dados_custom',
        ]
        extra_kwargs = {
            'nome_razaosocial': {'required': True},
            'telefone': {'required': True},
        }


class LeadOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadProspecto
        fields = [
            'id',
            'nome_razaosocial',
            'email',
            'telefone',
            'cpf_cnpj',
            'valor',
            'origem',
            'endereco',
            'cidade',
            'estado',
            'cep',
            'bairro',
            'status_api',
            'id_hubsoft',
            'score_qualificacao',
            'data_cadastro',
            'documentacao_completa',
            'contrato_aceito',
        ]
        read_only_fields = fields


# =====================================================================
# ImagemLeadProspecto
# =====================================================================

class ImagemLeadInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagemLeadProspecto
        fields = [
            'lead',
            'link_url',
            'descricao',
        ]


class ImagemLeadOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagemLeadProspecto
        fields = [
            'id',
            'lead',
            'link_url',
            'descricao',
            'status_validacao',
            'data_criacao',
        ]
        read_only_fields = fields


# =====================================================================
# Prospecto
# =====================================================================

class ProspectoInputSerializer(serializers.ModelSerializer):
    observacao = serializers.CharField(
        required=False,
        allow_blank=True,
        source='erro_processamento',
    )

    class Meta:
        model = Prospecto
        fields = [
            'lead',
            'status',
            'observacao',
        ]

    def create(self, validated_data):
        lead = validated_data.get('lead')
        if lead:
            validated_data.setdefault(
                'nome_prospecto', lead.nome_razaosocial
            )
        else:
            validated_data.setdefault('nome_prospecto', 'Sem nome')
        return super().create(validated_data)


class ProspectoOutputSerializer(serializers.ModelSerializer):
    observacao = serializers.CharField(source='erro_processamento', default='')

    class Meta:
        model = Prospecto
        fields = [
            'id',
            'lead',
            'status',
            'observacao',
            'data_criacao',
        ]
        read_only_fields = fields


# =====================================================================
# HistoricoContato
# =====================================================================

class HistoricoContatoInputSerializer(serializers.ModelSerializer):
    descricao = serializers.CharField(
        required=False,
        allow_blank=True,
        source='observacoes',
    )

    class Meta:
        model = HistoricoContato
        fields = [
            'lead',
            'descricao',
            'telefone',
            'status',
            'converteu_venda',
            'valor_venda',
        ]
        extra_kwargs = {
            'telefone': {'required': True},
            'status': {'required': True},
        }


class HistoricoContatoOutputSerializer(serializers.ModelSerializer):
    descricao = serializers.CharField(source='observacoes', default='')

    class Meta:
        model = HistoricoContato
        fields = [
            'id',
            'lead',
            'descricao',
            'telefone',
            'status',
            'converteu_venda',
            'valor_venda',
            'data_hora_contato',
        ]
        read_only_fields = fields


# =====================================================================
# FluxoAtendimento (read-only)
# =====================================================================

class FluxoAtendimentoOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = FluxoAtendimento
        fields = [
            'id',
            'nome',
            'tipo_fluxo',
            'status',
            'max_tentativas',
        ]
        read_only_fields = fields


# =====================================================================
# QuestaoFluxo (read-only)
# =====================================================================

class QuestaoFluxoOutputSerializer(serializers.ModelSerializer):
    obrigatoria = serializers.SerializerMethodField()

    class Meta:
        model = QuestaoFluxo
        fields = [
            'id',
            'fluxo',
            'titulo',
            'tipo_questao',
            'indice',
            'opcoes_resposta',
            'obrigatoria',
        ]
        read_only_fields = fields

    def get_obrigatoria(self, obj):
        return obj.tipo_validacao == 'obrigatoria'


# =====================================================================
# AtendimentoFluxo
# =====================================================================

class AtendimentoFluxoInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = AtendimentoFluxo
        fields = [
            'lead',
            'fluxo',
        ]


class AtendimentoFluxoOutputSerializer(serializers.ModelSerializer):
    questao_atual_indice = serializers.IntegerField(source='questao_atual')

    class Meta:
        model = AtendimentoFluxo
        fields = [
            'id',
            'lead',
            'fluxo',
            'status',
            'data_inicio',
            'questao_atual_indice',
            'total_questoes',
            'questoes_respondidas',
        ]
        read_only_fields = fields


# =====================================================================
# RespostaQuestao
# =====================================================================

class RespostaQuestaoInputSerializer(serializers.ModelSerializer):
    resposta_texto = serializers.CharField(source='resposta')

    class Meta:
        model = RespostaQuestao
        fields = [
            'atendimento',
            'questao',
            'resposta_texto',
        ]


class RespostaQuestaoOutputSerializer(serializers.ModelSerializer):
    resposta_texto = serializers.CharField(source='resposta')
    validada = serializers.BooleanField(source='valida')

    class Meta:
        model = RespostaQuestao
        fields = [
            'id',
            'atendimento',
            'questao',
            'resposta_texto',
            'data_resposta',
            'validada',
        ]
        read_only_fields = fields
