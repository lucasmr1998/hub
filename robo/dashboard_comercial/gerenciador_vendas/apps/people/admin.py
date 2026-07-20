from django.contrib import admin

from apps.people.models import ConfiguracaoPeople, Unidade


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'cidade', 'estado', 'ativo', 'tenant')
    list_filter = ('ativo', 'tenant', 'estado')
    search_fields = ('nome', 'codigo', 'cnpj')
    ordering = ('tenant', 'nome')

    def get_queryset(self, request):
        return Unidade.all_tenants.select_related('tenant', 'responsavel')


@admin.register(ConfiguracaoPeople)
class ConfiguracaoPeopleAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'dias_experiencia_padrao', 'exige_cpf_no_autocadastro',
                    'versao_consentimento_lgpd')
    list_filter = ('exige_cpf_no_autocadastro',)

    def get_queryset(self, request):
        return ConfiguracaoPeople.all_tenants.select_related('tenant')
