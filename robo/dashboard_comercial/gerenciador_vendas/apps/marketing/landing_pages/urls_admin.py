"""URLs admin de Landing Pages. Montadas em /marketing/landing-pages/."""
from django.urls import path

from . import views

app_name = 'landing_pages_admin'

urlpatterns = [
    # Landing Pages
    path('', views.admin_lista_lps, name='lista_lps'),
    path('nova/', views.admin_criar_lp, name='criar_lp'),
    path('<int:pk>/editar/', views.admin_editar_lp, name='editar_lp'),
    path('<int:pk>/salvar/', views.admin_salvar_lp, name='salvar_lp'),
    path('<int:pk>/excluir/', views.admin_excluir_lp, name='excluir_lp'),
    path('<int:pk>/preview/', views.admin_preview_lp, name='preview_lp'),
    path('render-blocos/', views.admin_render_blocos_html, name='render_blocos'),

    # Formularios
    path('formularios/', views.admin_lista_forms, name='lista_forms'),
    path('formularios/novo/', views.admin_criar_form, name='criar_form'),
    path('formularios/<int:pk>/editar/', views.admin_editar_form, name='editar_form'),
    path('formularios/<int:pk>/salvar/', views.admin_salvar_form, name='salvar_form'),
    path('formularios/<int:pk>/excluir/', views.admin_excluir_form, name='excluir_form'),
]
