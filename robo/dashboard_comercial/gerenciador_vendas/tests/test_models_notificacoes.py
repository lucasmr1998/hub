"""
Testes de modelo para o modulo Notificacoes (TipoNotificacao, CanalNotificacao, Notificacao, TemplateNotificacao).
"""
import pytest

from apps.notificacoes.models import (
    TipoNotificacao,
    CanalNotificacao,
    Notificacao,
    TemplateNotificacao,
)

from tests.factories import (
    TipoNotificacaoFactory,
    CanalNotificacaoFactory,
    NotificacaoFactory,
    TemplateNotificacaoFactory,
)


@pytest.mark.django_db
class TestTipoNotificacao:

    def test_criar_tipo_notificacao(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        tipo = TipoNotificacaoFactory(tenant=tenant_a, codigo='lead_novo')
        assert tipo.pk is not None
        assert tipo.ativo is True
        assert str(tipo) == tipo.nome

    def test_tipo_prioridade_padrao(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        tipo = TipoNotificacaoFactory(tenant=tenant_a, codigo='lead_convertido')
        assert tipo.prioridade_padrao == 'normal'


@pytest.mark.django_db
class TestCanalNotificacao:

    def test_criar_canal_notificacao(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        canal = CanalNotificacaoFactory(tenant=tenant_a, codigo='whatsapp')
        assert canal.pk is not None
        assert canal.ativo is True
        assert str(canal) == canal.nome

    def test_canal_icone_default(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        canal = CanalNotificacaoFactory(tenant=tenant_a, codigo='webhook')
        assert canal.icone == 'fas fa-envelope'


@pytest.mark.django_db
class TestNotificacao:

    def test_criar_notificacao(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        tipo = TipoNotificacaoFactory(tenant=tenant_a, codigo='lead_novo')
        canal = CanalNotificacaoFactory(tenant=tenant_a, codigo='whatsapp')
        notif = NotificacaoFactory(tenant=tenant_a, tipo=tipo, canal=canal)
        assert notif.pk is not None
        assert notif.tipo == tipo
        assert notif.canal == canal

    def test_notificacao_status_default_pendente(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        tipo = TipoNotificacaoFactory(tenant=tenant_a, codigo='venda_aprovada')
        canal = CanalNotificacaoFactory(tenant=tenant_a, codigo='webhook')
        notif = NotificacaoFactory(tenant=tenant_a, tipo=tipo, canal=canal)
        assert notif.status == 'pendente'

    def test_notificacao_prioridade_default_normal(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        tipo = TipoNotificacaoFactory(tenant=tenant_a, codigo='venda_rejeitada')
        canal = CanalNotificacaoFactory(tenant=tenant_a, codigo='whatsapp')
        notif = NotificacaoFactory(tenant=tenant_a, tipo=tipo, canal=canal)
        assert notif.prioridade == 'normal'

    def test_notificacao_tentativas_default(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        tipo = TipoNotificacaoFactory(tenant=tenant_a, codigo='prospecto_aguardando')
        canal = CanalNotificacaoFactory(tenant=tenant_a, codigo='webhook')
        notif = NotificacaoFactory(tenant=tenant_a, tipo=tipo, canal=canal)
        assert notif.tentativas == 0
        assert notif.max_tentativas == 3


@pytest.mark.django_db
class TestTemplateNotificacao:

    def test_criar_template_notificacao(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        tipo = TipoNotificacaoFactory(tenant=tenant_a, codigo='lead_novo')
        canal = CanalNotificacaoFactory(tenant=tenant_a, codigo='whatsapp')
        tmpl = TemplateNotificacaoFactory(
            tenant=tenant_a,
            tipo_notificacao=tipo,
            canal=canal,
        )
        assert tmpl.pk is not None
        assert tmpl.ativo is True
        assert str(tmpl) == f"{tipo.nome} - {canal.nome}"
