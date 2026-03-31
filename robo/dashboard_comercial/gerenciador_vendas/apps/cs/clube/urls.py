from django.urls import path

app_name = 'clube'

from apps.cs.clube.views.core_views import roleta_index, landing_clube, roleta_logout
from apps.cs.clube.views.api_views import (
    cadastrar_participante, roleta_init_dados, verificar_cliente,
    solicitar_otp, validar_otp, pre_cadastrar, api_resgatar_cupom, api_criar_indicacao,
)
from apps.cs.clube.views.dashboard_views import (
    dashboard_home, admin_login, dashboard_premios, dashboard_participantes,
    dashboard_extrato_membro, dashboard_giros, dashboard_cidades, exportar_csv,
    dashboard_assets, dashboard_config, dashboard_gamificacao,
    dashboard_landing_config, dashboard_banners, dashboard_categorias,
    dashboard_relatorios, dashboard_relatorios_indicacoes, dashboard_relatorios_parceiros,
)
from apps.cs.clube.views.membro_views import (
    membro_hub, membro_jogar, membro_missoes, membro_cupons,
    membro_indicar, membro_perfil, membro_faq,
)
from apps.cs.clube.views.docs_views import documentacao

urlpatterns = [
    path('', roleta_index, name='roleta_index'),
    path('clube/', landing_clube, name='landing_clube'),
    path('cadastrar/', cadastrar_participante, name='cadastrar_participante'),

    # Custom Admin Dashboard
    path('dashboard/', dashboard_home, name='dashboard_home'),
    path('dashboard/login/', admin_login, name='admin_login'),
    path('dashboard/premios/', dashboard_premios, name='dashboard_premios'),
    path('dashboard/participantes/', dashboard_participantes, name='dashboard_participantes'),
    path('dashboard/participantes/<int:membro_id>/extrato/', dashboard_extrato_membro, name='dashboard_extrato_membro'),
    path('dashboard/giros/', dashboard_giros, name='dashboard_giros'),
    path('dashboard/cidades/', dashboard_cidades, name='dashboard_cidades'),
    path('dashboard/exportar/', exportar_csv, name='exportar_csv'),
    path('dashboard/assets/', dashboard_assets, name='dashboard_assets'),
    path('dashboard/config/', dashboard_config, name='dashboard_config'),
    path('dashboard/gamificacao/', dashboard_gamificacao, name='dashboard_gamificacao'),
    path('dashboard/landing/', dashboard_landing_config, name='dashboard_landing_config'),
    path('dashboard/banners/', dashboard_banners, name='dashboard_banners'),
    path('dashboard/categorias/', dashboard_categorias, name='dashboard_categorias'),
    path('dashboard/relatorios/', dashboard_relatorios, name='dashboard_relatorios'),
    path('dashboard/relatorios/indicacoes/', dashboard_relatorios_indicacoes, name='dashboard_relatorios_indicacoes'),
    path('dashboard/relatorios/parceiros/', dashboard_relatorios_parceiros, name='dashboard_relatorios_parceiros'),
    path('verificar-cliente/', verificar_cliente, name='verificar_cliente'),
    path('solicitar-otp/', solicitar_otp, name='solicitar_otp'),
    path('validar-otp/', validar_otp, name='validar_otp'),
    path('pre-cadastrar/', pre_cadastrar, name='pre_cadastrar'),
    # Área do Membro
    path('membro/', membro_hub, name='membro_hub'),
    path('membro/jogar/', membro_jogar, name='membro_jogar'),
    path('membro/missoes/', membro_missoes, name='membro_missoes'),
    path('membro/cupons/', membro_cupons, name='membro_cupons'),
    path('membro/indicar/', membro_indicar, name='membro_indicar'),
    path('membro/perfil/', membro_perfil, name='membro_perfil'),
    path('membro/faq/', membro_faq, name='membro_faq'),

    path('api/init-dados/', roleta_init_dados, name='roleta_init_dados'),
    path('api/cupons/resgatar/', api_resgatar_cupom, name='api_resgatar_cupom'),
    path('api/indicacao/criar/', api_criar_indicacao, name='api_criar_indicacao'),
    path('logout/', roleta_logout, name='roleta_logout'),
    path('dashboard/docs/', documentacao, name='documentacao'),
]
