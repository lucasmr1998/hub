from django.contrib import admin
from .models import ConfiguracaoAssistenteGlobal, ConfiguracaoAssistenteTenant, ConversaAssistente, MensagemAssistente


@admin.register(ConfiguracaoAssistenteGlobal)
class ConfiguracaoAssistenteGlobalAdmin(admin.ModelAdmin):
    list_display = ['ativo', 'integracao_whatsapp', 'data_atualizacao']

    def has_add_permission(self, request):
        return not ConfiguracaoAssistenteGlobal.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConfiguracaoAssistenteTenant)
class ConfiguracaoAssistenteTenantAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'ativo', 'integracao_ia', 'modelo_ia']
    list_filter = ['ativo']


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
