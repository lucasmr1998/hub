from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

app_name = 'api'

urlpatterns = [
    # Versioned APIs
    path('v1/', include('apps.api.urls_panel')),
    path('v1/n8n/', include('apps.api.urls_n8n')),

    # OpenAPI documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='swagger-ui'),
]
