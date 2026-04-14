from django.contrib import admin
from .models import ConversaAssistente, MensagemAssistente


class MensagemInline(admin.TabularInline):
    model = MensagemAssistente
    extra = 0
    readonly_fields = ['role', 'conteudo', 'tool_chamada', 'tool_resultado', 'data']


@admin.register(ConversaAssistente)
class ConversaAssistenteAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'telefone', 'modelo', 'ativa', 'data_ultima_mensagem']
    list_filter = ['ativa', 'modelo']
    inlines = [MensagemInline]


@admin.register(MensagemAssistente)
class MensagemAssistenteAdmin(admin.ModelAdmin):
    list_display = ['conversa', 'role', 'conteudo_curto', 'tool_chamada', 'data']
    list_filter = ['role']

    def conteudo_curto(self, obj):
        return obj.conteudo[:80]
    conteudo_curto.short_description = 'Conteudo'
