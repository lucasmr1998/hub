from django.contrib import admin
from .models import (
    CanalInbox, EtiquetaConversa, Conversa, Mensagem,
    RespostaRapida, NotaInternaConversa,
    EquipeInbox, MembroEquipeInbox, PerfilAgenteInbox,
    FilaInbox, RegraRoteamento, HistoricoTransferencia,
    HorarioAtendimento, ConfiguracaoInbox,
    CategoriaFAQ, ArtigoFAQ, WidgetConfig,
)


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    readonly_fields = ['data_envio', 'remetente_tipo', 'remetente_user', 'remetente_nome',
                       'tipo_conteudo', 'conteudo', 'lida']
    fields = ['remetente_tipo', 'remetente_nome', 'tipo_conteudo', 'conteudo', 'lida', 'data_envio']


class NotaInternaInline(admin.TabularInline):
    model = NotaInternaConversa
    extra = 0
    readonly_fields = ['data_criacao']


class MembroEquipeInline(admin.TabularInline):
    model = MembroEquipeInbox
    extra = 0


class RegraRoteamentoInline(admin.TabularInline):
    model = RegraRoteamento
    extra = 0


@admin.register(CanalInbox)
class CanalInboxAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo', 'ativo', 'criado_em']
    list_filter = ['tipo', 'ativo']
    list_editable = ['ativo']


@admin.register(EtiquetaConversa)
class EtiquetaConversaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cor_hex', 'criado_por', 'criado_em']


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = ['numero', 'contato_nome', 'contato_telefone', 'canal', 'status',
                    'prioridade', 'agente', 'equipe', 'fila', 'mensagens_nao_lidas', 'ultima_mensagem_em']
    list_filter = ['status', 'prioridade', 'canal', 'equipe', 'fila']
    search_fields = ['contato_nome', 'contato_telefone', 'numero']
    readonly_fields = ['numero', 'data_abertura', 'data_resolucao', 'data_arquivamento',
                       'tempo_primeira_resposta_seg', 'ultima_mensagem_em',
                       'ultima_mensagem_preview', 'mensagens_nao_lidas']
    raw_id_fields = ['lead', 'ticket', 'oportunidade']
    inlines = [MensagemInline, NotaInternaInline]


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ['conversa', 'remetente_tipo', 'remetente_nome', 'tipo_conteudo',
                    'lida', 'data_envio']
    list_filter = ['remetente_tipo', 'tipo_conteudo', 'lida']
    search_fields = ['conteudo', 'identificador_externo']
    readonly_fields = ['data_envio', 'data_entrega', 'data_leitura']


@admin.register(RespostaRapida)
class RespostaRapidaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'atalho', 'categoria', 'uso_count', 'ativo']
    list_filter = ['categoria', 'ativo']
    search_fields = ['titulo', 'atalho', 'conteudo']
    list_editable = ['ativo']


@admin.register(NotaInternaConversa)
class NotaInternaConversaAdmin(admin.ModelAdmin):
    list_display = ['conversa', 'autor', 'data_criacao']
    readonly_fields = ['data_criacao']


@admin.register(EquipeInbox)
class EquipeInboxAdmin(admin.ModelAdmin):
    list_display = ['nome', 'lider', 'cor_hex', 'ativo', 'criado_em']
    list_filter = ['ativo']
    search_fields = ['nome']
    inlines = [MembroEquipeInline]


@admin.register(MembroEquipeInbox)
class MembroEquipeInboxAdmin(admin.ModelAdmin):
    list_display = ['user', 'equipe', 'cargo', 'adicionado_em']
    list_filter = ['equipe', 'cargo']


@admin.register(PerfilAgenteInbox)
class PerfilAgenteInboxAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'capacidade_maxima', 'ultimo_status_em']
    list_filter = ['status']
    list_editable = ['status', 'capacidade_maxima']


@admin.register(FilaInbox)
class FilaInboxAdmin(admin.ModelAdmin):
    list_display = ['nome', 'equipe', 'modo_distribuicao', 'prioridade', 'ativo']
    list_filter = ['equipe', 'modo_distribuicao', 'ativo']
    list_editable = ['prioridade', 'ativo']
    inlines = [RegraRoteamentoInline]


@admin.register(RegraRoteamento)
class RegraRoteamentoAdmin(admin.ModelAdmin):
    list_display = ['fila', 'tipo', 'canal', 'etiqueta', 'prioridade', 'ativo']
    list_filter = ['tipo', 'fila', 'ativo']


@admin.register(HistoricoTransferencia)
class HistoricoTransferenciaAdmin(admin.ModelAdmin):
    list_display = ['conversa', 'de_agente', 'para_agente', 'de_equipe', 'para_equipe', 'transferido_por', 'data']
    list_filter = ['data']
    readonly_fields = ['data']


@admin.register(HorarioAtendimento)
class HorarioAtendimentoAdmin(admin.ModelAdmin):
    list_display = ['dia_semana', 'hora_inicio', 'hora_fim', 'ativo']
    list_editable = ['hora_inicio', 'hora_fim', 'ativo']


@admin.register(ConfiguracaoInbox)
class ConfiguracaoInboxAdmin(admin.ModelAdmin):
    list_display = ['distribuicao_padrao', 'atribuir_ao_responder', 'data_atualizacao']


class ArtigoFAQInline(admin.TabularInline):
    model = ArtigoFAQ
    extra = 0
    fields = ['titulo', 'ordem', 'ativo', 'visualizacoes']
    readonly_fields = ['visualizacoes']


@admin.register(CategoriaFAQ)
class CategoriaFAQAdmin(admin.ModelAdmin):
    list_display = ['nome', 'slug', 'icone', 'cor', 'ordem', 'ativo']
    list_editable = ['ordem', 'ativo']
    prepopulated_fields = {'slug': ('nome',)}
    inlines = [ArtigoFAQInline]


@admin.register(ArtigoFAQ)
class ArtigoFAQAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'ordem', 'ativo', 'visualizacoes']
    list_filter = ['categoria', 'ativo']
    search_fields = ['titulo', 'conteudo']
    readonly_fields = ['visualizacoes', 'criado_em', 'atualizado_em']


@admin.register(WidgetConfig)
class WidgetConfigAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'token_publico', 'ativo', 'posicao', 'atualizado_em']
    readonly_fields = ['token_publico', 'criado_em', 'atualizado_em']
