"""
Factories para gerar dados de teste com Factory Boy.
"""
import factory
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
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


# ──────────────────────────────────────────────
# Factories — Comercial
# ──────────────────────────────────────────────

from apps.comercial.leads.models import LeadProspecto, HistoricoContato
from apps.comercial.cadastro.models import PlanoInternet
from apps.comercial.atendimento.models import FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo
from apps.comercial.crm.models import (
    PipelineEstagio,
    OportunidadeVenda,
    ConfiguracaoCRM,
)


class LeadProspectoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LeadProspecto

    tenant = factory.SubFactory(TenantFactory)
    nome_razaosocial = factory.Sequence(lambda n: f'Lead Teste {n}')
    telefone = factory.Sequence(lambda n: f'+5589999{n:04d}')
    email = factory.LazyAttribute(lambda o: f'{o.nome_razaosocial.lower().replace(" ", "_")}@teste.com')
    origem = 'site'
    status_api = 'pendente'


class HistoricoContatoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HistoricoContato

    tenant = factory.SubFactory(TenantFactory)
    lead = factory.SubFactory(LeadProspectoFactory)
    telefone = factory.LazyAttribute(lambda o: o.lead.telefone)
    status = 'fluxo_inicializado'
    converteu_venda = False


class PlanoInternetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PlanoInternet

    tenant = factory.SubFactory(TenantFactory)
    nome = factory.Sequence(lambda n: f'Plano {n}')
    descricao = 'Plano de teste'
    velocidade_download = 300
    velocidade_upload = 150
    valor_mensal = factory.LazyFunction(lambda: Decimal('99.90'))


class FluxoAtendimentoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FluxoAtendimento

    tenant = factory.SubFactory(TenantFactory)
    nome = factory.Sequence(lambda n: f'Fluxo Teste {n}')
    tipo_fluxo = 'qualificacao'
    status = 'ativo'


class QuestaoFluxoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuestaoFluxo

    tenant = factory.SubFactory(TenantFactory)
    fluxo = factory.SubFactory(FluxoAtendimentoFactory)
    indice = factory.Sequence(lambda n: n + 1)
    titulo = factory.Sequence(lambda n: f'Pergunta {n}')
    tipo_questao = 'texto'


class PipelineEstagioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PipelineEstagio

    tenant = factory.SubFactory(TenantFactory)
    nome = factory.Sequence(lambda n: f'Estagio {n}')
    slug = factory.Sequence(lambda n: f'estagio-{n}')
    ordem = factory.Sequence(lambda n: n)
    tipo = 'novo'


class OportunidadeVendaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OportunidadeVenda

    tenant = factory.SubFactory(TenantFactory)
    lead = factory.SubFactory(LeadProspectoFactory)
    estagio = factory.SubFactory(PipelineEstagioFactory)
    origem_crm = 'manual'


class ConfiguracaoCRMFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConfiguracaoCRM

    tenant = factory.SubFactory(TenantFactory)
    criar_oportunidade_automatico = True
    score_minimo_auto_criacao = 7
    estagio_inicial_padrao = factory.SubFactory(PipelineEstagioFactory)


# ──────────────────────────────────────────────
# Factories — CS (Clube, Parceiros, Indicacoes, Carteirinha)
# ──────────────────────────────────────────────

from apps.cs.clube.models import MembroClube, NivelClube, RegraPontuacao
from apps.cs.parceiros.models import CategoriaParceiro, Parceiro, CupomDesconto
from apps.cs.indicacoes.models import Indicacao, IndicacaoConfig
from apps.cs.carteirinha.models import ModeloCarteirinha, RegraAtribuicao


class NivelClubeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NivelClube

    nome = factory.Sequence(lambda n: f'Nivel {n}')
    xp_necessario = factory.Sequence(lambda n: n * 100)
    ordem = factory.Sequence(lambda n: n)
    tenant = factory.SubFactory(TenantFactory)


class MembroClubeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MembroClube

    nome = factory.Sequence(lambda n: f'Membro {n}')
    cpf = factory.Sequence(lambda n: f'{n:011d}')
    email = factory.LazyAttribute(lambda o: f'{o.nome.lower().replace(" ", "")}@teste.com')
    telefone = '86999990000'
    tenant = factory.SubFactory(TenantFactory)


class RegraPontuacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegraPontuacao

    gatilho = factory.Sequence(lambda n: f'gatilho_{n}')
    nome_exibicao = factory.Sequence(lambda n: f'Regra {n}')
    pontos_saldo = 10
    pontos_xp = 5
    tenant = factory.SubFactory(TenantFactory)


class CategoriaParceiroFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CategoriaParceiro

    nome = factory.Sequence(lambda n: f'Categoria {n}')
    slug = factory.Sequence(lambda n: f'categoria-{n}')
    tenant = factory.SubFactory(TenantFactory)


class ParceiroFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Parceiro

    nome = factory.Sequence(lambda n: f'Parceiro {n}')
    descricao = 'Descricao do parceiro'
    categoria = factory.SubFactory(CategoriaParceiroFactory)
    tenant = factory.SubFactory(TenantFactory)


class CupomDescontoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CupomDesconto

    parceiro = factory.SubFactory(ParceiroFactory)
    titulo = factory.Sequence(lambda n: f'Cupom {n}')
    codigo = factory.Sequence(lambda n: f'CUP{n:05d}')
    tipo_desconto = 'percentual'
    valor_desconto = Decimal('10.00')
    data_inicio = factory.LazyFunction(timezone.now)
    data_fim = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    tenant = factory.SubFactory(TenantFactory)


class IndicacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Indicacao

    membro_indicador = factory.SubFactory(MembroClubeFactory)
    nome_indicado = factory.Sequence(lambda n: f'Indicado {n}')
    telefone_indicado = factory.Sequence(lambda n: f'8699998{n:04d}')
    tenant = factory.SubFactory(TenantFactory)


class ModeloCarteirinhaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ModeloCarteirinha

    nome = factory.Sequence(lambda n: f'Modelo Carteirinha {n}')
    tenant = factory.SubFactory(TenantFactory)


class RegraAtribuicaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegraAtribuicao

    modelo = factory.SubFactory(ModeloCarteirinhaFactory)
    tipo = 'todos'
    tenant = factory.SubFactory(TenantFactory)


# ──────────────────────────────────────────────
# Factories — Integracoes
# ──────────────────────────────────────────────

from apps.integracoes.models import IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft


class IntegracaoAPIFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IntegracaoAPI

    nome = factory.Sequence(lambda n: f'Integracao {n}')
    tipo = 'hubsoft'
    base_url = 'https://api.teste.hubsoft.com.br'
    client_id = 'test_client_id'
    client_secret = 'test_client_secret'
    username = 'test_user'
    password = 'test_pass'
    ativa = True


class LogIntegracaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LogIntegracao

    integracao = factory.SubFactory(IntegracaoAPIFactory)
    endpoint = '/api/v1/integracao/prospecto'
    metodo = 'POST'
    sucesso = True
    status_code = 200


class ClienteHubsoftFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClienteHubsoft

    id_cliente = factory.Sequence(lambda n: 1000 + n)
    nome_razaosocial = factory.Sequence(lambda n: f'Cliente Hubsoft {n}')
    cpf_cnpj = factory.Sequence(lambda n: f'{n:011d}')


class ServicoClienteHubsoftFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ServicoClienteHubsoft

    cliente = factory.SubFactory(ClienteHubsoftFactory)
    id_cliente_servico = factory.Sequence(lambda n: 5000 + n)
    nome = factory.Sequence(lambda n: f'Plano Fibra {n}')
    valor = Decimal('99.90')
    status = 'Ativo'


# ──────────────────────────────────────────────
# Factories — Marketing (Campanhas)
# ──────────────────────────────────────────────

from apps.marketing.campanhas.models import CampanhaTrafego, DeteccaoCampanha


class CampanhaTrafegoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CampanhaTrafego

    nome = factory.Sequence(lambda n: f'Campanha {n}')
    codigo = factory.Sequence(lambda n: f'CAMP{n:04d}')
    palavra_chave = factory.Sequence(lambda n: f'promo{n}')
    plataforma = 'google_ads'
    ativa = True
    tenant = factory.SubFactory(TenantFactory)


class DeteccaoCampanhaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeteccaoCampanha

    campanha = factory.SubFactory(CampanhaTrafegoFactory)
    telefone = factory.Sequence(lambda n: f'8699997{n:04d}')
    mensagem_original = 'Mensagem de teste promo'
    tenant = factory.SubFactory(TenantFactory)


# ──────────────────────────────────────────────
# Factories — Notificacoes
# ──────────────────────────────────────────────

from apps.notificacoes.models import (
    TipoNotificacao, CanalNotificacao, Notificacao, TemplateNotificacao,
)


class TipoNotificacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TipoNotificacao
        django_get_or_create = ('codigo',)

    codigo = factory.Sequence(lambda n: ['lead_novo', 'lead_convertido', 'venda_aprovada',
                                          'venda_rejeitada', 'prospecto_aguardando'][n % 5])
    nome = factory.LazyAttribute(lambda o: o.codigo.replace('_', ' ').title())
    descricao = 'Descricao do tipo de notificacao'
    template_padrao = 'Template padrao {{nome}}'
    tenant = factory.SubFactory(TenantFactory)


class CanalNotificacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CanalNotificacao
        django_get_or_create = ('codigo',)

    codigo = factory.Sequence(lambda n: ['whatsapp', 'webhook'][n % 2])
    nome = factory.LazyAttribute(lambda o: o.codigo.title())
    ativo = True
    tenant = factory.SubFactory(TenantFactory)


class NotificacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notificacao

    tipo = factory.SubFactory(TipoNotificacaoFactory)
    canal = factory.SubFactory(CanalNotificacaoFactory)
    titulo = factory.Sequence(lambda n: f'Notificacao {n}')
    mensagem = 'Mensagem de teste'
    tenant = factory.SubFactory(TenantFactory)


class TemplateNotificacaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TemplateNotificacao

    tipo_notificacao = factory.SubFactory(TipoNotificacaoFactory)
    canal = factory.SubFactory(CanalNotificacaoFactory)
    nome = factory.Sequence(lambda n: f'Template {n}')
    assunto = 'Assunto teste'
    corpo_html = '<p>Corpo HTML</p>'
    corpo_texto = 'Corpo texto'
    tenant = factory.SubFactory(TenantFactory)
