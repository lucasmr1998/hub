"""Tool `listar_motivos_perda` — registry/catálogo + despachar (com DB, tenant-safe)."""
from types import SimpleNamespace

import pytest

from apps.automacao.services import ia_tools
from apps.comercial.crm.models import MotivoPerda
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db


def test_tool_registrada_no_catalogo_tipo_conhecimento_categoria_crm():
    tools = {t['chave']: t for t in ia_tools.catalogo_tools()}
    assert 'listar_motivos_perda' in tools
    assert tools['listar_motivos_perda']['tipo'] == 'conhecimento'
    assert tools['listar_motivos_perda']['categoria'] == 'crm'


def test_despachar_devolve_nomes_ativos_ordenados():
    tenant = TenantFactory()
    MotivoPerda.objects.create(tenant=tenant, nome='Preço', ativo=True, ordem=2)
    MotivoPerda.objects.create(tenant=tenant, nome='Timing', ativo=True, ordem=1)
    MotivoPerda.objects.create(tenant=tenant, nome='Descontinuado', ativo=False, ordem=0)

    out = ia_tools.despachar('listar_motivos_perda', {}, SimpleNamespace(tenant=tenant))

    assert out.splitlines() == ['Timing', 'Preço']
    assert 'Descontinuado' not in out


def test_despachar_tenant_sem_motivos_mensagem_padrao():
    tenant = TenantFactory()
    out = ia_tools.despachar('listar_motivos_perda', {}, SimpleNamespace(tenant=tenant))
    assert out == 'nenhum motivo de perda cadastrado para este tenant.'


def test_despachar_e_tenant_safe_nao_vaza_entre_tenants():
    tenant_a = TenantFactory()
    tenant_b = TenantFactory()
    MotivoPerda.objects.create(tenant=tenant_a, nome='Preço', ativo=True)

    out_b = ia_tools.despachar('listar_motivos_perda', {}, SimpleNamespace(tenant=tenant_b))

    assert out_b == 'nenhum motivo de perda cadastrado para este tenant.'
