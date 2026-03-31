from django.contrib import admin
from .models import PremioRoleta, ParticipanteRoleta, MembroClube, RegraPontuacao, ExtratoPontuacao, Cidade


# Customizing Admin Site
admin.site.site_header = "Administração Roleta Digital"
admin.site.site_title = "Roleta Digital"
admin.site.index_title = "Gestão de Prêmios e Participantes"

@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo')
    search_fields = ('nome',)
    list_filter = ('ativo',)

@admin.register(PremioRoleta)
class PremioRoletaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'quantidade', 'probabilidade', 'mensagem_vitoria')
    filter_horizontal = ('cidades_permitidas',)
    search_fields = ('nome',)
    list_editable = ('quantidade',)

@admin.register(ParticipanteRoleta)
class ParticipanteRoletaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'cidade', 'premio', 'status', 'data_criacao')
    list_filter = ('status', 'cidade', 'data_criacao')
    search_fields = ('nome', 'cpf', 'email')
    readonly_fields = ('data_criacao',)
    ordering = ('-data_criacao',)

class ExtratoPontuacaoInline(admin.TabularInline):
    model = ExtratoPontuacao
    extra = 0
    readonly_fields = ('data_recebimento',)

@admin.register(MembroClube)
class MembroClubeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'telefone', 'validado', 'saldo', 'nivel_atual')
    list_filter = ('validado',)
    search_fields = ('nome', 'cpf', 'telefone')
    inlines = [ExtratoPontuacaoInline]

@admin.register(RegraPontuacao)
class RegraPontuacaoAdmin(admin.ModelAdmin):
    list_display = ('nome_exibicao', 'gatilho', 'pontos_saldo', 'pontos_xp', 'ativo', 'visivel_na_roleta')
    list_filter = ('ativo', 'visivel_na_roleta')
    search_fields = ('nome_exibicao', 'gatilho')
    list_editable = ('ativo', 'visivel_na_roleta', 'pontos_saldo', 'pontos_xp')

@admin.register(ExtratoPontuacao)
class ExtratoPontuacaoAdmin(admin.ModelAdmin):
    list_display = ('membro', 'regra', 'pontos_saldo_ganhos', 'data_recebimento')
    list_filter = ('regra', 'data_recebimento')
    search_fields = ('membro__nome', 'membro__cpf', 'descricao_extra')
    readonly_fields = ('data_recebimento',)
