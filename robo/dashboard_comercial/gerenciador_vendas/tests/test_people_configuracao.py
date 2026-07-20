"""
Testes da configuracao do modulo: fluxo, mensagem por etapa e template de
formulario.

O que importa aqui: a tela de fluxo precisa mostrar as SETE etapas do produto
real (nao as seis que a spec descrevia), o campo travado do formulario nao pode
ser desligado pela tela, e a mensagem por etapa nao pode virar envio automatico.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.people import estados
from apps.people.campos_formulario import CAMPOS_TRAVADOS, config_padrao, normalizar_config
from apps.people.models import (
    ConfiguracaoPeople, MensagemEtapa, TemplateFormulario, Unidade,
)
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


TODAS = ['people.ver', 'people.gerir_unidades', 'people.gerir_links']


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant, nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro', codigo='loja-centro')
    return {'tenant': tenant, 'unidade': unidade}


def _cliente(tenant, username='gestora', funcionalidades=TODAS):
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=tenant)
    perfil = PerfilPermissao.objects.create(tenant=tenant, nome=f'Perfil {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil)
    cliente = Client()
    cliente.force_login(user)
    return cliente


# ──────────────────────────────────────────────
# Fluxo: as sete etapas
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_fluxo_mostra_as_sete_etapas(cenario):
    """
    Sete, nao seis. Ferias e Afastamentos so apareceram quando os prints do
    produto real chegaram, e a spec listava Afastamentos como uma aba que
    "nenhuma fonte descreve o que faz".
    """
    resposta = _cliente(cenario['tenant']).get('/people/config/fluxo/')

    assert resposta.status_code == 200
    nomes = [e['nome'] for e in resposta.context['etapas']]
    # Acentuados: sao rotulo de tela, nao identificador. O identificador e o
    # 'situacao' de cada etapa, que continua sem acento.
    assert nomes == [
        'Cadastro Inicial', 'Admissão', 'Período de Experiência',
        'Ativos', 'Férias', 'Afastamentos', 'Desligamento',
    ]


@pytest.mark.django_db
def test_etapa_lista_os_recursos_configuraveis(cenario):
    resposta = _cliente(cenario['tenant']).get(
        f'/people/config/fluxo/{estados.SITUACAO_EM_EXPERIENCIA}/')

    chaves = [r['chave'] for r in resposta.context['recursos']]
    assert chaves == ['comunicacao', 'periodo_experiencia', 'checklist']


@pytest.mark.django_db
def test_recurso_ainda_nao_construido_aparece_marcado(cenario):
    """
    Esconder faria a tela mentir sobre o tamanho do modulo. O mapa precisa ficar
    visivel desde o inicio.
    """
    resposta = _cliente(cenario['tenant']).get(
        f'/people/config/fluxo/{estados.SITUACAO_EM_ADMISSAO}/')

    por_chave = {r['chave']: r for r in resposta.context['recursos']}
    assert por_chave['comunicacao']['disponivel'] is True
    assert por_chave['checklist']['disponivel'] is False
    assert 'Em construção' in resposta.content.decode()


@pytest.mark.django_db
def test_etapa_inexistente_da_404(cenario):
    assert _cliente(cenario['tenant']).get('/people/config/fluxo/inventada/').status_code == 404


# ──────────────────────────────────────────────
# Mensagem por etapa
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_salva_mensagem_da_etapa(cenario):
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/config/fluxo/{estados.SITUACAO_EM_ADMISSAO}/mensagem/', {
        'texto': 'Ola, {{nome}}! Sua admissao comecou.',
        'escopo': 'tenant', 'ativo': 'on',
    })

    mensagem = MensagemEtapa.all_tenants.get(
        tenant=cenario['tenant'], etapa=estados.SITUACAO_EM_ADMISSAO)
    assert '{{nome}}' in mensagem.texto


@pytest.mark.django_db
def test_mensagem_e_sugestao_e_nao_envio(cenario):
    """
    O produto de origem diz em dois lugares que nada e enviado automaticamente.
    O modelo nao tem canal, destinatario nem agendamento: e texto pro RH usar.
    """
    campos = {f.name for f in MensagemEtapa._meta.get_fields()}
    for proibido in ('canal', 'enviado_em', 'agendado_para', 'destinatario'):
        assert proibido not in campos, (
            f'MensagemEtapa ganhou "{proibido}": isso a transforma em envio '
            f'automatico, que e o oposto da decisao de produto.')


@pytest.mark.django_db
def test_mensagem_renderiza_as_variaveis(cenario):
    from apps.people.services import registrar_colaborador

    resultado = registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': 'Maria Souza'}, origem='rh')
    mensagem = MensagemEtapa.all_tenants.create(
        tenant=cenario['tenant'], etapa=estados.SITUACAO_CADASTRO,
        texto='Ola, {{primeiro_nome}}! Voce esta na {{unidade}}.')

    texto = mensagem.render(resultado.colaborador)
    assert texto == 'Ola, Maria! Voce esta na Loja Centro.'


@pytest.mark.django_db
def test_mensagem_por_unidade_so_vale_naquela_unidade(cenario):
    outra = Unidade.all_tenants.create(
        tenant=cenario['tenant'], nome='Loja Norte', codigo='loja-norte')
    mensagem = MensagemEtapa.all_tenants.create(
        tenant=cenario['tenant'], etapa=estados.SITUACAO_CADASTRO,
        texto='So do centro', escopo='unidades')
    mensagem.unidades.add(cenario['unidade'])

    assert mensagem.vale_para(cenario['unidade']) is True
    assert mensagem.vale_para(outra) is False


# ──────────────────────────────────────────────
# Template de formulario
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cria_template_pela_tela(cenario):
    cliente = _cliente(cenario['tenant'])

    cliente.post('/people/config/formularios/novo/', {
        'nome': 'Cadastro operacional', 'ativo': 'on',
        'solicitar_nome_completo': 'on', 'obrigatorio_nome_completo': 'on',
        'rotulo_nome_completo': 'Seu nome',
        'solicitar_telefone': 'on', 'rotulo_telefone': 'WhatsApp',
    })

    template = TemplateFormulario.all_tenants.get(nome='Cadastro operacional')
    config = template.config()
    assert config['nome_completo']['rotulo'] == 'Seu nome'
    assert config['telefone']['solicitar'] is True
    assert config['telefone']['obrigatorio'] is False
    assert config['email']['solicitar'] is False  # nao marcado no POST


@pytest.mark.django_db
def test_campo_travado_nao_pode_ser_desligado(cenario):
    """
    Nome e o unico campo travado: sem ele nao ha cadastro, e o dedup precisa de
    algo pra comparar quando nao ha documento.
    """
    cliente = _cliente(cenario['tenant'])

    cliente.post('/people/config/formularios/novo/', {
        'nome': 'Tentativa', 'ativo': 'on',
        # nome_completo deliberadamente ausente do POST
        'solicitar_telefone': 'on',
    })

    template = TemplateFormulario.all_tenants.get(nome='Tentativa')
    config = template.config()
    assert 'nome_completo' in CAMPOS_TRAVADOS
    assert config['nome_completo']['solicitar'] is True
    assert config['nome_completo']['obrigatorio'] is True


@pytest.mark.django_db
def test_campo_nao_solicitado_nunca_fica_obrigatorio(cenario):
    """Formulario impossivel de enviar: campo obrigatorio que nao aparece."""
    config = normalizar_config({
        'email': {'solicitar': False, 'obrigatorio': True, 'rotulo': 'Email'},
    })
    assert config['email']['obrigatorio'] is False


@pytest.mark.django_db
def test_template_novo_no_catalogo_nao_some_de_template_antigo(cenario):
    """
    Config gravada antes de um campo entrar no catalogo continua valendo, e o
    campo novo aparece com o padrao em vez de sumir da tela.
    """
    config = normalizar_config({'nome_completo': {'solicitar': True, 'obrigatorio': True}})
    assert 'cep' in config
    assert config['cep']['rotulo'] == 'CEP'


@pytest.mark.django_db
def test_um_padrao_por_tenant(cenario):
    from django.db import IntegrityError, transaction

    TemplateFormulario.all_tenants.create(
        tenant=cenario['tenant'], nome='Um', campos=config_padrao(), padrao=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TemplateFormulario.all_tenants.create(
                tenant=cenario['tenant'], nome='Dois', campos=config_padrao(), padrao=True)


# ──────────────────────────────────────────────
# Configuracao geral
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_salva_configuracao_geral(cenario):
    cliente = _cliente(cenario['tenant'])

    cliente.post('/people/config/geral/', {
        'dias_experiencia_padrao': '60',
        'dias_primeiro_periodo_experiencia': '30',
        'texto_consentimento_lgpd': 'Autorizo o uso dos meus dados.',
        'versao_consentimento_lgpd': '2.0',
        'link_expira_em_dias': '30',
        'exige_cpf_no_autocadastro': 'on',
    })

    config = ConfiguracaoPeople.all_tenants.get(tenant=cenario['tenant'])
    assert config.dias_experiencia_padrao == 60
    assert config.versao_consentimento_lgpd == '2.0'


@pytest.mark.django_db
def test_quem_so_ve_nao_configura(cenario):
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])

    assert cliente.get('/people/config/geral/').status_code == 403
    assert cliente.post(
        f'/people/config/fluxo/{estados.SITUACAO_CADASTRO}/mensagem/',
        {'texto': 'x', 'escopo': 'tenant'}).status_code == 403


@pytest.mark.django_db
def test_quem_so_ve_consegue_ler_o_fluxo(cenario):
    """Ver o mapa do modulo nao e privilegio de quem configura."""
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])
    assert cliente.get('/people/config/fluxo/').status_code == 200


@pytest.mark.django_db
def test_nao_edita_template_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheio = TemplateFormulario.all_tenants.create(
        tenant=outro, nome='Alheio', campos=config_padrao())
    cliente = _cliente(cenario['tenant'])

    assert cliente.get(f'/people/config/formularios/{alheio.pk}/').status_code == 404


# ──────────────────────────────────────────────
# Render: erro de sintaxe de template so aparece ao renderizar
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_todas_as_telas_de_configuracao_renderizam(cenario):
    """
    Varredura de render.

    Existe porque `manage.py check` NAO compila template: um erro de sintaxe
    (como usar chaves literais sem verbatim) so aparece quando a pagina e
    pedida. Sem este teste, uma tela quebrada passaria pela suite inteira.
    """
    cliente = _cliente(cenario['tenant'])
    template = TemplateFormulario.padrao_do_tenant(cenario['tenant'])

    urls = [
        '/people/config/',
        '/people/config/fluxo/',
        '/people/config/geral/',
        '/people/config/formularios/',
        '/people/config/formularios/novo/',
        f'/people/config/formularios/{template.pk}/',
        '/people/analises/',
    ]
    urls += [f'/people/config/fluxo/{e["situacao"]}/' for e in estados.ETAPAS_FLUXO]
    urls += [f'/people/config/fluxo/{e["situacao"]}/mensagem/' for e in estados.ETAPAS_FLUXO]

    for url in urls:
        assert cliente.get(url).status_code == 200, f'{url} nao renderizou'
