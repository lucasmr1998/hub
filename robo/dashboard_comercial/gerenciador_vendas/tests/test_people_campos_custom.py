"""
Campos de candidatura que o tenant inventa.

O catalogo de sistema e fixo porque cada campo tem coluna no Candidato. Este
model e a saida pro que nao tem coluna, e o valor vai pra `dados_custom`.

O que estes testes defendem, em ordem de gravidade:

1. O EXPURGO LGPD limpa o JSON. E o unico ponto onde falhar quebra uma promessa
   legal em silencio: o tenant cria um campo "CPF" e o dado sobrevive a
   retencao.
2. Campo custom NAO COLIDE com campo de sistema, nem mesmo quando o tenant
   escolhe um rotulo que gera o mesmo slug.
3. Campo novo nao liga sozinho em vaga que ja esta publicada e recebendo gente.
4. As duas guardas da tela: nao apaga campo respondido, e nao troca o slug na
   edicao (as respostas antigas ficariam orfas).
"""
import datetime

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people import campos_candidatura as catalogo
from apps.people.models import (
    CampoCandidatura, Candidato, Cargo, LinkCandidatura, Unidade, Vaga,
)
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   status='publicada')
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo, 'vaga': vaga}


def _cliente(cenario, username='rh_campos',
             funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome=f'P {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


def _campo(cenario, nome='Tem CNH?', slug='cnh', tipo='text', **kwargs):
    return CampoCandidatura.all_tenants.create(
        tenant=cenario['tenant'], nome=nome, slug=slug, tipo=tipo, **kwargs)


def _link(cenario, canal='instagram'):
    import secrets
    return LinkCandidatura.all_tenants.create(
        tenant=cenario['tenant'], vaga=cenario['vaga'],
        unidade=cenario['unidade'], canal=canal,
        token=secrets.token_urlsafe(16))


def _ligar_na_vaga(vaga, campo, obrigatorio=False):
    config = dict(vaga.config_campos or {})
    config[campo.chave] = {'solicitar': True, 'obrigatorio': obrigatorio}
    vaga.config_campos = catalogo.normalizar_config(config, vaga.campos_extras())
    vaga.save(update_fields=['config_campos'])


# ── 1. O expurgo LGPD, que e o que nao pode falhar ───────────────────────────

@pytest.mark.django_db
def test_anonimizar_zera_os_campos_custom(cenario):
    """
    O tenant inventa o campo, entao nao da pra limpar por chave conhecida. Um
    cliente cria "Nome da mae" e esse dado tem que sumir junto com o resto.
    """
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Ana Souza', whatsapp='5586999990000',
        dados_custom={'nome_da_mae': 'Maria Souza', 'cnh': 'sim'})

    candidato.anonimizar()

    candidato.refresh_from_db()
    assert candidato.dados_custom == {}
    assert candidato.nome_completo == 'Candidato anonimizado'


@pytest.mark.django_db
def test_expurgo_pelo_comando_tambem_limpa_o_json(cenario):
    """A limpeza tem que valer pelo caminho real, o cron, e nao so no metodo."""
    from django.core.management import call_command

    Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Bruno Lima', whatsapp='5586999990001',
        retencao_ate=datetime.date.today() - datetime.timedelta(days=1),
        dados_custom={'cnh': 'sim'})

    call_command('expurgar_candidatos')

    candidato = Candidato.all_tenants.get(nome_completo='Candidato anonimizado')
    assert candidato.dados_custom == {}


# ── 2. Colisao com campo de sistema ──────────────────────────────────────────

@pytest.mark.django_db
def test_campo_custom_nao_colide_com_campo_de_sistema(cenario):
    """
    Um tenant que cria um campo "Email" nao pode sequestrar o campo de sistema
    de mesmo nome. O prefixo da chave e o que torna a colisao impossivel.
    """
    campo = _campo(cenario, nome='Email', slug='email')

    assert campo.chave == 'custom__email'
    assert campo.chave not in catalogo.NOMES_DE_CAMPO

    nomes = [c['nome'] for c in catalogo.catalogo([campo.como_campo()])]
    assert nomes.count('email') == 1          # o de sistema segue unico
    assert 'custom__email' in nomes           # e o do tenant convive


@pytest.mark.django_db
def test_slug_repetido_ganha_sufixo_em_vez_de_erro(cenario):
    _campo(cenario, nome='Turno', slug='turno')

    _cliente(cenario).post(reverse('people:campo_salvar'),
                           {'nome': 'Turno', 'tipo': 'text'})

    slugs = sorted(CampoCandidatura.all_tenants.filter(
        tenant=cenario['tenant']).values_list('slug', flat=True))
    assert slugs == ['turno', 'turno_2']


# ── 3. Campo novo nao mexe em vaga publicada ─────────────────────────────────

@pytest.mark.django_db
def test_campo_novo_nasce_desligado_nas_vagas(cenario):
    """
    Criar um campo no nivel do tenant nao pode, sozinho, mudar o formulario de
    uma vaga que ja esta no ar recebendo candidato.
    """
    campo = _campo(cenario)

    config = catalogo.normalizar_config(cenario['vaga'].config_campos,
                                        [campo.como_campo()])

    assert config[campo.chave]['solicitar'] is False
    assert campo.chave not in {
        c['nome'] for c in cenario['vaga'].secoes_do_formulario()[0]['itens']}


@pytest.mark.django_db
def test_campo_desativado_some_do_formulario_sem_apagar_resposta(cenario):
    campo = _campo(cenario)
    _ligar_na_vaga(cenario['vaga'], campo)
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Carla', whatsapp='5586999990002',
        dados_custom={'cnh': 'sim'})

    campo.ativo = False
    campo.save()

    cenario['vaga'].refresh_from_db()
    solicitados = {c['nome'] for secao in cenario['vaga'].secoes_do_formulario()
                   for c in secao['itens']}
    candidato.refresh_from_db()
    assert campo.chave not in solicitados
    assert candidato.dados_custom == {'cnh': 'sim'}


# ── 4. O formulario publico ponta a ponta ────────────────────────────────────

@pytest.mark.django_db
def test_resposta_do_campo_custom_chega_no_candidato(cenario):
    campo = _campo(cenario, nome='Tem CNH?', slug='cnh', tipo='select',
                   opcoes=['Sim', 'Não'])
    _ligar_na_vaga(cenario['vaga'], campo)
    link = _link(cenario)

    Client().post(f'/people/candidatura/{link.token}/enviar/', {
        'nome_completo': 'Diego Alves', 'whatsapp': '86999990003',
        'custom__cnh': 'Sim', 'consentimento_lgpd': 'on'})

    candidato = Candidato.all_tenants.get(nome_completo='Diego Alves')
    assert candidato.dados_custom == {'cnh': 'Sim'}


@pytest.mark.django_db
def test_opcao_fora_da_lista_e_descartada(cenario):
    """POST com opcao inexistente e forjado, nao erro de digitacao."""
    campo = _campo(cenario, tipo='select', opcoes=['Sim', 'Não'])
    _ligar_na_vaga(cenario['vaga'], campo)
    link = _link(cenario)

    Client().post(f'/people/candidatura/{link.token}/enviar/', {
        'nome_completo': 'Elisa Rocha', 'whatsapp': '86999990004',
        'custom__cnh': 'Talvez', 'consentimento_lgpd': 'on'})

    candidato = Candidato.all_tenants.get(nome_completo='Elisa Rocha')
    assert candidato.dados_custom == {}


@pytest.mark.django_db
def test_campo_custom_obrigatorio_barra_o_envio(cenario):
    campo = _campo(cenario)
    _ligar_na_vaga(cenario['vaga'], campo, obrigatorio=True)
    link = _link(cenario)

    resposta = Client().post(f'/people/candidatura/{link.token}/enviar/', {
        'nome_completo': 'Fabio Melo', 'whatsapp': '86999990005',
        'consentimento_lgpd': 'on'})

    assert resposta.status_code == 400
    assert not Candidato.all_tenants.filter(nome_completo='Fabio Melo').exists()


@pytest.mark.django_db
def test_campo_de_outro_tenant_nao_aparece_no_formulario(cenario):
    outro = TenantFactory(modulo_people=True)
    CampoCandidatura.all_tenants.create(tenant=outro, nome='Alheio',
                                        slug='alheio')

    extras = cenario['vaga'].campos_extras()

    assert extras == []


# ── 5. As guardas da tela ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_nao_apaga_campo_ja_respondido(cenario):
    """
    Apagar deixaria o valor no `dados_custom` sem nada que diga o que a chave
    significava. Pra parar de perguntar, o caminho e desativar.
    """
    campo = _campo(cenario)
    Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Gisele', whatsapp='5586999990006',
        dados_custom={'cnh': 'sim'})

    resposta = _cliente(cenario).post(
        reverse('people:campo_remover', args=[campo.pk]), follow=True)

    assert CampoCandidatura.all_tenants.filter(pk=campo.pk).exists()
    assert 'desativar' in resposta.content.decode().lower()


@pytest.mark.django_db
def test_apaga_campo_sem_resposta(cenario):
    campo = _campo(cenario)

    _cliente(cenario).post(reverse('people:campo_remover', args=[campo.pk]))

    assert not CampoCandidatura.all_tenants.filter(pk=campo.pk).exists()


@pytest.mark.django_db
def test_editar_nao_troca_o_slug(cenario):
    """
    O slug e a chave das respostas ja gravadas. Trocar deixaria toda resposta
    anterior orfa, sem erro nenhum: o campo so apareceria vazio.
    """
    campo = _campo(cenario, nome='Tem CNH?', slug='cnh')

    _cliente(cenario).post(reverse('people:campo_salvar'), {
        'pk': campo.pk, 'nome': 'Possui habilitação?', 'tipo': 'text'})

    campo.refresh_from_db()
    assert campo.nome == 'Possui habilitação?'
    assert campo.slug == 'cnh'


@pytest.mark.django_db
def test_lista_sem_opcao_e_recusada(cenario):
    resposta = _cliente(cenario).post(reverse('people:campo_salvar'), {
        'nome': 'Turno', 'tipo': 'select', 'opcoes': ''}, follow=True)

    assert 'pelo menos uma' in resposta.content.decode()
    assert not CampoCandidatura.all_tenants.filter(
        tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_quem_so_ve_nao_configura(cenario):
    cliente = _cliente(cenario, username='so_ve_campos',
                       funcionalidades=('people.ver',))

    assert cliente.get(reverse('people:campos_config')).status_code == 200
    assert cliente.post(reverse('people:campo_salvar'),
                        {'nome': 'X'}).status_code == 403


@pytest.mark.django_db
def test_nao_edita_campo_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheio = CampoCandidatura.all_tenants.create(tenant=outro, nome='Alheio',
                                                 slug='alheio')

    resposta = _cliente(cenario).post(reverse('people:campo_salvar'),
                                      {'pk': alheio.pk, 'nome': 'Sequestrado'})

    alheio.refresh_from_db()
    assert resposta.status_code == 404
    assert alheio.nome == 'Alheio'


# ── 6. A ficha do candidato ──────────────────────────────────────────────────
#
# Nao havia NENHUM teste abrindo people:candidato_detalhe, e foi por isso que um
# 500 chegou em prod em 21/07: eu inseri uma funcao auxiliar entre o decorator
# @requer_people e a view, entao o decorator passou a decorar a auxiliar. A view
# quebrava ao ser aberta E, pior, ficava sem checagem de permissao nenhuma.

@pytest.mark.django_db
def test_ficha_do_candidato_abre(cenario):
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Helena Dias', whatsapp='5586999990007')

    resposta = _cliente(cenario).get(
        reverse('people:candidato_detalhe', args=[candidato.pk]))

    assert resposta.status_code == 200
    assert 'Helena Dias' in resposta.content.decode()


@pytest.mark.django_db
def test_ficha_exige_permissao_de_people(cenario):
    """
    O decorator na view, e nao numa auxiliar. Sem ele, qualquer usuario logado
    do tenant abriria a ficha de um candidato, que e PII.
    """
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Igor Nunes', whatsapp='5586999990008')

    # Perfil COM PermissaoUsuario e sem nenhuma funcionalidade de People.
    # Usuario sem PermissaoUsuario nenhuma nao serve aqui: o sistema trata isso
    # como acesso total por retrocompatibilidade
    # (apps/sistema/decorators.py:175), entao o teste passaria por engano.
    cliente = _cliente(cenario, username='sem_people', funcionalidades=())

    resposta = cliente.get(
        reverse('people:candidato_detalhe', args=[candidato.pk]))

    assert resposta.status_code in (302, 403)


@pytest.mark.django_db
def test_ficha_mostra_a_resposta_custom_com_o_rotulo(cenario):
    """Rotulo do campo, nao a chave crua do JSON."""
    _campo(cenario, nome='Tem CNH categoria B?', slug='cnh')
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Joana Reis', whatsapp='5586999990009',
        dados_custom={'cnh': 'Sim'})

    corpo = _cliente(cenario).get(
        reverse('people:candidato_detalhe', args=[candidato.pk])).content.decode()

    assert 'Tem CNH categoria B?' in corpo
    assert 'cnh' not in corpo.replace('Tem CNH categoria B?', '')


@pytest.mark.django_db
def test_ficha_ignora_resposta_de_campo_apagado(cenario):
    """Sem o campo nao ha rotulo, e exibir "cnh_2: sim" e pior que omitir."""
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Karina Melo', whatsapp='5586999990010',
        dados_custom={'campo_que_nao_existe_mais': 'valor orfao'})

    corpo = _cliente(cenario).get(
        reverse('people:candidato_detalhe', args=[candidato.pk])).content.decode()

    assert 'valor orfao' not in corpo
