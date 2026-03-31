"""
Factories para gerar dados de teste com Factory Boy.
"""
import factory
from django.contrib.auth.models import User
from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant

    nome = factory.Sequence(lambda n: f'Provedor {n}')
    slug = factory.Sequence(lambda n: f'provedor-{n}')
    modulo_comercial = True
    modulo_marketing = False
    modulo_cs = False
    plano_comercial = 'start'
    ativo = True


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@teste.com')
    password = factory.PostGenerationMethodCall('set_password', 'senha123')


class PerfilFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PerfilUsuario

    user = factory.SubFactory(UserFactory)
    tenant = factory.SubFactory(TenantFactory)


class ConfigEmpresaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConfiguracaoEmpresa

    tenant = factory.SubFactory(TenantFactory)
    nome_empresa = factory.LazyAttribute(lambda o: o.tenant.nome)
    ativo = True
