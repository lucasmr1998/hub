from rest_framework import serializers


class MensagemRecebidaSerializer(serializers.Serializer):
    """Payload de mensagem recebida via webhook (N8N, widget, etc)."""
    telefone = serializers.CharField(max_length=20)
    nome = serializers.CharField(max_length=255, required=False, default='')
    conteudo = serializers.CharField(required=False, default='')
    tipo_conteudo = serializers.ChoiceField(
        choices=['texto', 'imagem', 'arquivo', 'audio', 'video', 'localizacao'],
        default='texto',
    )
    canal_tipo = serializers.ChoiceField(
        choices=['whatsapp', 'widget', 'email', 'interno'],
        default='whatsapp',
    )
    identificador_externo = serializers.CharField(max_length=100, required=False, default='')
    arquivo_url = serializers.URLField(required=False, default='')
    arquivo_nome = serializers.CharField(max_length=255, required=False, default='')
    metadata = serializers.DictField(required=False, default=dict)
    tenant_slug = serializers.SlugField(max_length=100, required=False)


class StatusMensagemSerializer(serializers.Serializer):
    """Payload de callback de status (entrega/leitura)."""
    identificador_externo = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=['enviada', 'entregue', 'lida', 'erro'])
    tenant_slug = serializers.SlugField(max_length=100, required=False)
    erro = serializers.CharField(required=False, default='')


class ConversaOutputSerializer(serializers.Serializer):
    """Serializer de saída para Conversa."""
    id = serializers.IntegerField()
    numero = serializers.IntegerField()
    canal_tipo = serializers.CharField(source='canal.tipo')
    canal_nome = serializers.CharField(source='canal.nome')
    contato_nome = serializers.CharField()
    contato_telefone = serializers.CharField()
    contato_email = serializers.CharField()
    status = serializers.CharField()
    prioridade = serializers.CharField()
    agente_id = serializers.IntegerField(source='agente.id', default=None)
    agente_nome = serializers.SerializerMethodField()
    equipe_id = serializers.IntegerField(source='equipe.id', default=None)
    equipe_nome = serializers.CharField(source='equipe.nome', default=None)
    fila_id = serializers.IntegerField(source='fila.id', default=None)
    fila_nome = serializers.CharField(source='fila.nome', default=None)
    lead_id = serializers.IntegerField(source='lead.id', default=None)
    ticket_id = serializers.IntegerField(source='ticket.id', default=None)
    ticket_numero = serializers.IntegerField(source='ticket.numero', default=None)
    ultima_mensagem_em = serializers.DateTimeField()
    ultima_mensagem_preview = serializers.CharField()
    mensagens_nao_lidas = serializers.IntegerField()
    tempo_primeira_resposta_seg = serializers.IntegerField()
    data_abertura = serializers.DateTimeField()
    data_resolucao = serializers.DateTimeField()
    modo_atendimento = serializers.CharField()
    etiquetas = serializers.SerializerMethodField()

    def get_agente_nome(self, obj):
        if obj.agente:
            return obj.agente.get_full_name() or obj.agente.username
        return None

    def get_etiquetas(self, obj):
        return list(obj.etiquetas.values('id', 'nome', 'cor_hex'))


class MensagemOutputSerializer(serializers.Serializer):
    """Serializer de saída para Mensagem."""
    id = serializers.IntegerField()
    conversa_id = serializers.IntegerField()
    remetente_tipo = serializers.CharField()
    remetente_nome = serializers.CharField()
    remetente_user_id = serializers.IntegerField(source='remetente_user.id', default=None)
    tipo_conteudo = serializers.CharField()
    conteudo = serializers.CharField()
    arquivo_url = serializers.CharField()
    arquivo_nome = serializers.CharField()
    lida = serializers.BooleanField()
    data_envio = serializers.DateTimeField()
    data_entrega = serializers.DateTimeField()
    data_leitura = serializers.DateTimeField()
    identificador_externo = serializers.CharField()
    erro_envio = serializers.CharField()
