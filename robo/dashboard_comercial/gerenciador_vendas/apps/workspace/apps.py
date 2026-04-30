from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    """
    Workspace — gestão de projetos, tarefas e documentos por tenant.

    Multi-tenant. Feature ativável no aurora-admin via toggle no Tenant.
    Validação interna pelo tenant Hubtrix → futuramente vira feature comercial.

    6 models: Projeto, Etapa, Tarefa, Nota, Documento, PastaDocumento.
    Permissões granulares: workspace.ver, workspace.criar_projeto,
    workspace.editar_proprios, workspace.editar_todos.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.workspace'
    verbose_name = 'Workspace (projetos e documentos)'
