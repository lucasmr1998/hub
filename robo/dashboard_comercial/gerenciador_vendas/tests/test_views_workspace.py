"""
Testes de views do Workspace.

Foco:
- Permissoes granulares (workspace.ver / criar_projeto / editar_proprios / editar_todos)
  e os 3 fixes de permissao (projeto por tarefa, pasta_editar, escopo=todas).
- Isolamento de tenant (TenantManager auto-filtra por thread-local).
- CRUD basico de projeto/tarefa/documento.
- API do kanban (mover + gate de edicao).

Como rodar:
    pytest tests/test_views_workspace.py -v
"""
import json

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.sistema.middleware import set_current_tenant
from apps.sistema.models import Funcionalidade, PerfilPermissao, PermissaoUsuario
from apps.workspace.models import Documento, Projeto, Tarefa
from tests.factories import (
    ConfigEmpresaFactory,
    DocumentoFactory,
    PastaDocumentoFactory,
    PerfilFactory,
    ProjetoFactory,
    TarefaFactory,
    TenantFactory,
    UserFactory,
)


# ── Helpers ────────────────────────────────────────────────────────────────

WS_FUNCS = {
    'workspace.ver': 'Ver Workspace',
    'workspace.criar_projeto': 'Criar projeto',
    'workspace.editar_proprios': 'Editar proprios',
    'workspace.editar_todos': 'Editar todos',
}


def _funcs(*codigos):
    objs = []
    for c in codigos:
        f, _ = Funcionalidade.objects.get_or_create(
            codigo=c, defaults={'modulo': 'workspace', 'nome': WS_FUNCS.get(c, c)},
        )
        objs.append(f)
    return objs


def mk_user(tenant, *codigos, is_superuser=False):
    """Cria user com PerfilUsuario (tenant) + PerfilPermissao com as funcs dadas."""
    user = UserFactory(is_staff=True, is_superuser=is_superuser)
    PerfilFactory(user=user, tenant=tenant)
    if not is_superuser:
        perfil = PerfilPermissao.objects.create(
            tenant=tenant, nome=f'Perfil {user.username}',
        )
        if codigos:
            perfil.funcionalidades.add(*_funcs(*codigos))
        PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil)
    return user


@pytest.fixture
def tenant(db):
    t = TenantFactory(nome='Aurora HQ Teste', slug='aurora-hq-teste')
    ConfigEmpresaFactory(tenant=t)
    set_current_tenant(t)
    yield t
    set_current_tenant(None)


# ── Fix 1: edicao de projeto por responsavel de QUALQUER tarefa ─────────────

class TestPermissaoProjeto:
    def test_responsavel_de_tarefa_nao_primeira_edita_projeto(self, client, tenant):
        """
        Fix do slice [:1]: ser responsavel de uma tarefa que NAO e a primeira
        (por ordering ordem,-criado_em) deve permitir editar o projeto.
        """
        dono = mk_user(tenant, 'workspace.ver')
        editor = mk_user(tenant, 'workspace.ver', 'workspace.editar_proprios')

        projeto = ProjetoFactory(tenant=tenant, responsavel=dono)
        # tarefa 1 (ordem 0) de outro; tarefa 2 (ordem 1) do editor
        TarefaFactory(tenant=tenant, projeto=projeto, responsavel=dono, ordem=0)
        TarefaFactory(tenant=tenant, projeto=projeto, responsavel=editor, ordem=1)

        client.force_login(editor)
        resp = client.get(reverse('workspace:projeto_editar', args=[projeto.pk]))
        assert resp.status_code == 200

    def test_sem_vinculo_nao_edita_projeto(self, client, tenant):
        estranho = mk_user(tenant, 'workspace.ver', 'workspace.editar_proprios')
        projeto = ProjetoFactory(tenant=tenant, responsavel=mk_user(tenant, 'workspace.ver'))

        client.force_login(estranho)
        resp = client.get(reverse('workspace:projeto_editar', args=[projeto.pk]))
        assert resp.status_code == 403

    def test_editar_todos_edita_qualquer_projeto(self, client, tenant):
        admin = mk_user(tenant, 'workspace.ver', 'workspace.editar_todos')
        projeto = ProjetoFactory(tenant=tenant, responsavel=mk_user(tenant, 'workspace.ver'))

        client.force_login(admin)
        resp = client.get(reverse('workspace:projeto_editar', args=[projeto.pk]))
        assert resp.status_code == 200


# ── Fix 2: pasta_editar exige editar_todos ──────────────────────────────────

class TestPermissaoPasta:
    def test_editar_proprios_nao_edita_pasta(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver', 'workspace.editar_proprios')
        pasta = PastaDocumentoFactory(tenant=tenant)

        client.force_login(user)
        resp = client.get(reverse('workspace:pasta_editar', args=[pasta.pk]))
        assert resp.status_code == 403

    def test_editar_todos_edita_pasta(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver', 'workspace.editar_todos')
        pasta = PastaDocumentoFactory(tenant=tenant)

        client.force_login(user)
        resp = client.get(reverse('workspace:pasta_editar', args=[pasta.pk]))
        assert resp.status_code == 200


# ── Fix 3: ?escopo=todas exige editar_todos ─────────────────────────────────

class TestEscopoTodas:
    def test_escopo_todas_sem_permissao_degrada_pra_minhas(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver')
        outro = mk_user(tenant, 'workspace.ver')
        projeto = ProjetoFactory(tenant=tenant, responsavel=outro)
        TarefaFactory(tenant=tenant, projeto=projeto, responsavel=outro, titulo='Tarefa do outro')

        client.force_login(user)
        resp = client.get(reverse('workspace:minhas_tarefas'), {'escopo': 'todas'})
        assert resp.status_code == 200
        assert resp.context['escopo'] == 'minhas'

    def test_escopo_todas_com_permissao_mantem(self, client, tenant):
        admin = mk_user(tenant, 'workspace.ver', 'workspace.editar_todos')
        outro = mk_user(tenant, 'workspace.ver')
        projeto = ProjetoFactory(tenant=tenant, responsavel=outro)
        TarefaFactory(tenant=tenant, projeto=projeto, responsavel=outro)

        client.force_login(admin)
        resp = client.get(reverse('workspace:minhas_tarefas'), {'escopo': 'todas'})
        assert resp.status_code == 200
        assert resp.context['escopo'] == 'todas'


# ── Isolamento de tenant ─────────────────────────────────────────────────────

class TestIsolamentoTenant:
    def test_projeto_nao_vaza_entre_tenants(self, db, set_tenant):
        ta = TenantFactory(slug='ws-iso-a')
        tb = TenantFactory(slug='ws-iso-b')
        ProjetoFactory(tenant=ta, nome='Projeto A')
        ProjetoFactory(tenant=tb, nome='Projeto B')

        set_tenant(ta)
        nomes = set(Projeto.objects.values_list('nome', flat=True))
        assert nomes == {'Projeto A'}

    def test_documento_nao_vaza_entre_tenants(self, db, set_tenant):
        ta = TenantFactory(slug='ws-iso-c')
        tb = TenantFactory(slug='ws-iso-d')
        DocumentoFactory(tenant=ta, titulo='Doc A', slug='doc-a')
        DocumentoFactory(tenant=tb, titulo='Doc B', slug='doc-b')

        set_tenant(tb)
        titulos = set(Documento.objects.values_list('titulo', flat=True))
        assert titulos == {'Doc B'}


# ── CRUD basico ──────────────────────────────────────────────────────────────

class TestCRUD:
    def test_criar_projeto(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver', 'workspace.criar_projeto')
        client.force_login(user)
        resp = client.post(reverse('workspace:projeto_criar'), {
            'nome': 'Novo Projeto', 'status': 'planejamento', 'prioridade': 'media',
        })
        assert resp.status_code == 302
        assert Projeto.objects.filter(nome='Novo Projeto', tenant=tenant).exists()

    def test_criar_projeto_sem_permissao_403(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver')
        client.force_login(user)
        resp = client.post(reverse('workspace:projeto_criar'), {
            'nome': 'Bloqueado', 'status': 'planejamento', 'prioridade': 'media',
        })
        assert resp.status_code == 403
        assert not Projeto.objects.filter(nome='Bloqueado').exists()

    def test_excluir_tarefa_owner(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver', 'workspace.editar_proprios')
        projeto = ProjetoFactory(tenant=tenant, responsavel=user)
        tarefa = TarefaFactory(tenant=tenant, projeto=projeto, responsavel=user)
        client.force_login(user)
        resp = client.post(reverse('workspace:tarefa_excluir', args=[tarefa.pk]))
        assert resp.status_code == 302
        assert not Tarefa.objects.filter(pk=tarefa.pk).exists()


# ── API kanban ───────────────────────────────────────────────────────────────

class TestKanbanAPI:
    def test_mover_tarefa_owner(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver', 'workspace.editar_proprios')
        projeto = ProjetoFactory(tenant=tenant, responsavel=user)
        tarefa = TarefaFactory(tenant=tenant, projeto=projeto, responsavel=user, status='pendente')

        client.force_login(user)
        resp = client.post(
            reverse('workspace:api_kanban_mover'),
            data=json.dumps({'tarefa_id': tarefa.pk, 'novo_status': 'em_andamento', 'ordem': 0}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True
        tarefa.refresh_from_db()
        assert tarefa.status == 'em_andamento'

    def test_mover_tarefa_sem_permissao_403(self, client, tenant):
        dono = mk_user(tenant, 'workspace.ver')
        estranho = mk_user(tenant, 'workspace.ver', 'workspace.editar_proprios')
        projeto = ProjetoFactory(tenant=tenant, responsavel=dono)
        tarefa = TarefaFactory(tenant=tenant, projeto=projeto, responsavel=dono, status='pendente')

        client.force_login(estranho)
        resp = client.post(
            reverse('workspace:api_kanban_mover'),
            data=json.dumps({'tarefa_id': tarefa.pk, 'novo_status': 'concluida'}),
            content_type='application/json',
        )
        assert resp.status_code == 403
        tarefa.refresh_from_db()
        assert tarefa.status == 'pendente'

    def test_concluida_marca_data_conclusao(self, client, tenant):
        user = mk_user(tenant, 'workspace.ver', 'workspace.editar_todos')
        projeto = ProjetoFactory(tenant=tenant, responsavel=user)
        tarefa = TarefaFactory(tenant=tenant, projeto=projeto, status='pendente')

        client.force_login(user)
        resp = client.post(
            reverse('workspace:api_kanban_mover'),
            data=json.dumps({'tarefa_id': tarefa.pk, 'novo_status': 'concluida'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        tarefa.refresh_from_db()
        assert tarefa.status == 'concluida'
        assert tarefa.data_conclusao is not None


# ── Smoke: detalhe renderiza cada formato ────────────────────────────────────

class TestDetalheFormatos:
    """Cada formato de documento abre (200) e mostra os marcadores certos."""

    def _abrir(self, client, tenant, doc):
        user = mk_user(tenant, 'workspace.ver')
        client.force_login(user)
        return client.get(reverse('workspace:documento_detalhe', args=[doc.pk]))

    def test_pdf_embed_e_download(self, client, tenant):
        doc = DocumentoFactory(tenant=tenant, formato='pdf', slug='smoke-pdf', conteudo='')
        doc.arquivo.save('smoke.pdf', ContentFile(b'%PDF-1.4 teste'), save=True)
        resp = self._abrir(client, tenant, doc)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert '<iframe' in html and 'Baixar PDF' in html

    def test_pptx_como_link_tem_download(self, client, tenant):
        doc = DocumentoFactory(tenant=tenant, formato='link', slug='smoke-pptx', conteudo='')
        doc.arquivo.save('smoke.pptx', ContentFile(b'PK fake pptx'), save=True)
        resp = self._abrir(client, tenant, doc)
        assert resp.status_code == 200
        # formato=link sem url_externa: cai no botao generico de download (template linha ~118)
        assert 'Baixar arquivo anexo' in resp.content.decode()

    def test_json_renderiza_bloco_codigo(self, client, tenant):
        doc = DocumentoFactory(
            tenant=tenant, formato='markdown', slug='smoke-json',
            conteudo='```json\n{"flow": "nuvyon", "ativo": true}\n```',
        )
        resp = self._abrir(client, tenant, doc)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert '<pre' in html and 'nuvyon' in html

    def test_sql_renderiza_bloco_codigo(self, client, tenant):
        doc = DocumentoFactory(
            tenant=tenant, formato='markdown', slug='smoke-sql',
            conteudo='```sql\nSELECT * FROM clientes WHERE tenant_id = 3;\n```',
        )
        resp = self._abrir(client, tenant, doc)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert '<pre' in html and 'SELECT' in html

    def test_markdown_renderiza_conteudo(self, client, tenant):
        doc = DocumentoFactory(
            tenant=tenant, formato='markdown', slug='smoke-md',
            conteudo='# Titulo Smoke\n\nParagrafo de teste do markdown.',
        )
        resp = self._abrir(client, tenant, doc)
        assert resp.status_code == 200
        assert 'Paragrafo de teste do markdown.' in resp.content.decode()
