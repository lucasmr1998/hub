"""
URLs do Workspace.

Estrutura (algumas views são stubs na fase 1, completam nas próximas PRs):
- /workspace/                   — Home
- /workspace/projetos/...       — CRUD projetos + kanban (PR 3 + 5)
- /workspace/tarefas/...        — Visão minhas tarefas + CRUD (PR 4)
- /workspace/documentos/...     — CRUD documentos + render markdown (PR 2)
- /workspace/pastas/...         — CRUD pastas (PR 2)
- /workspace/api/...            — Endpoints AJAX (PR 5)
"""
from django.urls import path

from apps.workspace.views import dashboard, documentos, projetos, tarefas, api as api_views

app_name = 'workspace'

urlpatterns = [
    # Home
    path('', dashboard.home, name='home'),

    # Drive — vista unificada de pastas + documentos
    path('documentos/', documentos.drive, name='documentos_lista'),
    path('documentos/pasta/<slug:slug>/', documentos.drive_pasta, name='pasta_detalhe'),

    # Documentos — CRUD
    path('documentos/criar/', documentos.criar, name='documento_criar'),
    path('documentos/<int:pk>/', documentos.detalhe, name='documento_detalhe'),
    path('documentos/<int:pk>/editar/', documentos.editar, name='documento_editar'),
    path('documentos/<int:pk>/excluir/', documentos.excluir, name='documento_excluir'),

    # Pastas — CRUD (acesso dentro do contexto do Drive)
    path('pastas/criar/', documentos.pasta_criar, name='pasta_criar'),
    path('pastas/<int:pk>/editar/', documentos.pasta_editar, name='pasta_editar'),
    path('pastas/<int:pk>/excluir/', documentos.pasta_excluir, name='pasta_excluir'),

    # Anexos — upload manual + geracao IA + excluir (AJAX)
    path('documentos/<int:doc_pk>/anexos/upload/', documentos.anexo_upload, name='anexo_upload'),
    path('documentos/<int:doc_pk>/anexos/gerar-ia/', documentos.anexo_gerar_ia, name='anexo_gerar_ia'),
    path('anexos/<int:pk>/excluir/', documentos.anexo_excluir, name='anexo_excluir'),

    # Projetos
    path('projetos/', projetos.lista, name='projetos_lista'),
    path('projetos/criar/', projetos.criar, name='projeto_criar'),
    path('projetos/<int:pk>/', projetos.detalhe, name='projeto_detalhe'),
    path('projetos/<int:pk>/editar/', projetos.editar, name='projeto_editar'),
    path('projetos/<int:pk>/excluir/', projetos.excluir, name='projeto_excluir'),
    path('projetos/<int:pk>/kanban/', projetos.kanban, name='projeto_kanban'),

    # Etapas
    path('projetos/<int:projeto_pk>/etapas/criar/', projetos.etapa_criar, name='etapa_criar'),
    path('etapas/<int:pk>/editar/', projetos.etapa_editar, name='etapa_editar'),
    path('etapas/<int:pk>/excluir/', projetos.etapa_excluir, name='etapa_excluir'),

    # Tarefas
    path('tarefas/', tarefas.minhas, name='minhas_tarefas'),
    path('projetos/<int:projeto_pk>/tarefas/criar/', tarefas.criar, name='tarefa_criar'),
    path('tarefas/<int:pk>/', tarefas.detalhe, name='tarefa_detalhe'),
    path('tarefas/<int:pk>/editar/', tarefas.editar, name='tarefa_editar'),
    path('tarefas/<int:pk>/excluir/', tarefas.excluir, name='tarefa_excluir'),

    # Notas em tarefa
    path('tarefas/<int:tarefa_pk>/notas/criar/', tarefas.nota_criar, name='nota_criar'),
    path('notas/<int:pk>/excluir/', tarefas.nota_excluir, name='nota_excluir'),

    # APIs AJAX
    path('api/kanban/mover/', api_views.kanban_mover, name='api_kanban_mover'),
    path('api/tarefa/<int:pk>/status/', api_views.tarefa_status, name='api_tarefa_status'),
]
