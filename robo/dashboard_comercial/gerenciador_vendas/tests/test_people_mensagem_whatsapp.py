"""
Mensagem sugerida de WhatsApp por etapa e por saida (tarefa 218, item 6).

Reuso da mecanica que ja existia no Departamento Pessoal (`MensagemEtapa`), com
a mesma decisao de produto: NADA E ENVIADO AUTOMATICAMENTE. O botao ABRE o
WhatsApp com o texto pronto e o RH manda do proprio numero. Funciona pra
qualquer cliente, sem integracao contratada e sem custo por mensagem.

O que estes testes defendem:

1. A constraint do banco que garante ETAPA OU SAIDA, nunca os dois nem nenhum.
   E a divisao que estrutura o modulo: etapa e dado, saida e codigo.
2. Saida tem PRECEDENCIA sobre etapa. Quem saiu continua apontando pra ultima
   etapa em que esteve, e mandar a mensagem daquela etapa pra quem foi reprovado
   seria constrangedor.
3. Candidato anonimizado pelo expurgo LGPD nao gera link de WhatsApp.
"""
import secrets

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from apps.people.models import (
    Candidato, Cargo, EtapaPipeline, MensagemRecrutamento, Unidade, Vaga,
)
from apps.people.services.pipeline import dar_saida
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
                                   titulo='Atendente noturno', status='publicada')
    etapa = EtapaPipeline.all_tenants.get(tenant=tenant, nome='Triagem')
    candidato = Candidato.all_tenants.create(
        tenant=tenant, unidade=unidade, vaga=vaga, etapa=etapa,
        nome_completo='Vitória Russi Santos', whatsapp='5586999998888')
    return {'tenant': tenant, 'unidade': unidade, 'vaga': vaga,
            'etapa': etapa, 'candidato': candidato}


def _cliente(cenario, funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username='rh_msg', password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'], nome='P msg')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


# ── A constraint: etapa OU saida ─────────────────────────────────────────────

@pytest.mark.django_db
def test_banco_recusa_etapa_e_saida_juntas(cenario):
    """
    Linha com os dois so seria descoberta quando a tela nao achasse a mensagem,
    e o sintoma seria "sumiu", nao "esta errado".
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MensagemRecrutamento.all_tenants.create(
                tenant=cenario['tenant'], etapa=cenario['etapa'],
                saida='inapto', texto='x')


@pytest.mark.django_db
def test_banco_recusa_sem_etapa_e_sem_saida(cenario):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MensagemRecrutamento.all_tenants.create(
                tenant=cenario['tenant'], texto='x')


@pytest.mark.django_db
def test_uma_mensagem_por_etapa(cenario):
    MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], etapa=cenario['etapa'], texto='primeira')

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MensagemRecrutamento.all_tenants.create(
                tenant=cenario['tenant'], etapa=cenario['etapa'], texto='segunda')


# ── Render dos placeholders ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_render_troca_os_placeholders(cenario):
    msg = MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], etapa=cenario['etapa'],
        texto='Olá, {{primeiro_nome}}! Sobre a vaga de {{vaga}} na {{unidade}}.')

    texto = msg.render(cenario['candidato'])

    assert texto == ('Olá, Vitória! Sobre a vaga de Atendente noturno '
                     'na Loja Centro.')


@pytest.mark.django_db
def test_placeholder_sem_valor_vira_vazio_e_nao_fica_na_tela(cenario):
    """
    A mensagem vai pro candidato. Ver `{{vaga}}` cru e pior que a frase ficar
    mais curta.
    """
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Sem Vaga', whatsapp='5586999997777')
    msg = MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], saida='inapto', texto='Vaga: {{vaga}}.')

    texto = msg.render(candidato)

    assert '{{' not in texto
    assert texto == 'Vaga: .'


# ── Qual mensagem aparece ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_mostra_a_mensagem_da_etapa_atual(cenario):
    MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], etapa=cenario['etapa'], texto='Da triagem')

    assert cenario['candidato'].mensagem_sugerida() == 'Da triagem'


@pytest.mark.django_db
def test_saida_tem_precedencia_sobre_a_etapa(cenario):
    """
    Quem saiu continua apontando pra ultima etapa em que esteve. Mandar a
    mensagem daquela etapa pra quem foi reprovado seria constrangedor.
    """
    MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], etapa=cenario['etapa'], texto='Da triagem')
    MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], saida='inapto', texto='Não seguimos desta vez')

    dar_saida(cenario['candidato'], 'inapto', motivo='Perfil fora do mínimo')
    cenario['candidato'].refresh_from_db()

    assert cenario['candidato'].mensagem_sugerida() == 'Não seguimos desta vez'


@pytest.mark.django_db
def test_sem_mensagem_configurada_devolve_vazio(cenario):
    """Vazio faz o bloco inteiro sumir da ficha, em vez de aparecer em branco."""
    assert cenario['candidato'].mensagem_sugerida() == ''


@pytest.mark.django_db
def test_mensagem_de_outro_tenant_nao_vaza(cenario):
    outro = TenantFactory(modulo_people=True)
    etapa_alheia = EtapaPipeline.do_escopo(outro).first()
    MensagemRecrutamento.all_tenants.create(
        tenant=outro, etapa=etapa_alheia, texto='Do outro tenant')

    assert cenario['candidato'].mensagem_sugerida() == ''


# ── O link do WhatsApp ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_link_whatsapp_usa_wa_me_com_o_texto(cenario):
    link = cenario['candidato'].link_whatsapp('Olá, tudo bem?')

    assert link.startswith('https://wa.me/5586999998888?text=')
    assert 'Ol%C3%A1' in link          # o texto vai codificado


@pytest.mark.django_db
def test_candidato_anonimizado_nao_gera_link(cenario):
    """
    O expurgo LGPD apaga o numero. Um `wa.me/` sem numero abriria uma tela de
    erro do WhatsApp em vez de simplesmente nao aparecer.
    """
    cenario['candidato'].anonimizar()
    cenario['candidato'].refresh_from_db()

    assert cenario['candidato'].link_whatsapp('oi') == ''


# ── A tela de configuracao ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_salva_mensagem_pela_tela_de_fluxo(cenario):
    _cliente(cenario).post(reverse('people:fluxo_mensagem_salvar'), {
        'etapa': cenario['etapa'].pk, 'texto': 'Oi, {{primeiro_nome}}!'})

    msg = MensagemRecrutamento.all_tenants.get(tenant=cenario['tenant'])
    assert msg.etapa_id == cenario['etapa'].pk
    assert msg.texto == 'Oi, {{primeiro_nome}}!'


@pytest.mark.django_db
def test_texto_vazio_apaga_a_mensagem(cenario):
    """
    Mensagem vazia configurada e indistinguivel de nao ter mensagem. Deixar as
    duas formas conviverem faria a ficha ter que checar as duas.
    """
    MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], etapa=cenario['etapa'], texto='alguma coisa')

    _cliente(cenario).post(reverse('people:fluxo_mensagem_salvar'), {
        'etapa': cenario['etapa'].pk, 'texto': '   '})

    assert not MensagemRecrutamento.all_tenants.filter(
        tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_etapa_e_saida_juntas_e_recusado_antes_do_banco(cenario):
    """Checar na view evita devolver IntegrityError na cara do usuario."""
    resposta = _cliente(cenario).post(reverse('people:fluxo_mensagem_salvar'), {
        'etapa': cenario['etapa'].pk, 'saida': 'inapto', 'texto': 'x'},
        follow=True)

    assert 'uma etapa ou uma saída' in resposta.content.decode()
    assert not MensagemRecrutamento.all_tenants.exists()


@pytest.mark.django_db
def test_quem_so_ve_nao_configura_mensagem(cenario):
    cliente = _cliente(cenario, funcionalidades=('people.ver',))

    resposta = cliente.post(reverse('people:fluxo_mensagem_salvar'),
                            {'saida': 'inapto', 'texto': 'x'})

    assert resposta.status_code == 403


# ── A ficha do candidato ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_ficha_mostra_o_bloco_com_a_mensagem(cenario):
    MensagemRecrutamento.all_tenants.create(
        tenant=cenario['tenant'], etapa=cenario['etapa'],
        texto='Oi, {{primeiro_nome}}! Vamos conversar?')

    corpo = _cliente(cenario).get(
        reverse('people:candidato_detalhe',
                args=[cenario['candidato'].pk])).content.decode()

    assert 'Oi, Vitória! Vamos conversar?' in corpo
    assert 'Abrir no WhatsApp' in corpo


@pytest.mark.django_db
def test_ficha_sem_mensagem_nao_mostra_o_bloco(cenario):
    corpo = _cliente(cenario).get(
        reverse('people:candidato_detalhe',
                args=[cenario['candidato'].pk])).content.decode()

    assert 'Abrir no WhatsApp' not in corpo
