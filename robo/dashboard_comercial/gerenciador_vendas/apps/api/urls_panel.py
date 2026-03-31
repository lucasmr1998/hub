from rest_framework.routers import DefaultRouter

from . import views_panel

router = DefaultRouter()
router.register('planos', views_panel.PlanoInternetViewSet, basename='planos')
router.register('opcoes-vencimento', views_panel.OpcaoVencimentoViewSet, basename='opcoes-vencimento')
router.register('configuracoes-cadastro', views_panel.ConfiguracaoCadastroViewSet, basename='configuracoes-cadastro')
router.register('cidades-viabilidade', views_panel.CidadeViabilidadeViewSet, basename='cidades-viabilidade')
router.register('campanhas', views_panel.CampanhaTrafegoViewSet, basename='campanhas')
router.register('tipos-notificacao', views_panel.TipoNotificacaoViewSet, basename='tipos-notificacao')
router.register('canais-notificacao', views_panel.CanalNotificacaoViewSet, basename='canais-notificacao')
router.register('templates-notificacao', views_panel.TemplateNotificacaoViewSet, basename='templates-notificacao')

app_name = 'api_panel'
urlpatterns = router.urls
