"""Testes do seed do checklist de venda de internet via bot WhatsApp (etapa 1 da
migração do robô Matrix/Megalink): `apps/automacao/management/commands/seed_checklist_venda.py`.

Cobre: idempotência (2 rodadas, 22 itens, sem duplicar), checklist nasce INATIVO,
ordem dos itens bate com a sequência canônica do robô original, `full_clean()` em
todos os itens (prova que o seed nunca viola o contrato do Matrix — 2 a 5 opções),
condições dos itens condicionais preenchidas, e a adaptação obrigatória de nome de
empresa (nome do tenant aparece, "Megalink" nunca aparece).
"""
import pytest
from django.core.management import call_command

from apps.automacao.management.commands.seed_checklist_venda import NOME_CHECKLIST, SLUG_CHECKLIST
from apps.automacao.models import Checklist, ItemChecklist
from apps.comercial.crm.models import ProdutoServico
from tests.factories import TenantFactory

CHAVES_NA_ORDEM = [
    'cpf_cnpj', 'nome_razaosocial', 'data_nascimento', 'email', 'tipo_imovel',
    'cep', 'endereco_confirmado', 'cidade', 'bairro', 'rua', 'numero_residencia',
    'tipo_residencia', 'ponto_referencia', 'id_plano_rp', 'plano_confirmado',
    'id_dia_vencimento', 'dados_confirmados', 'doc_selfie_recebida',
    'doc_frente_recebida', 'doc_verso_recebida', 'turno_instalacao', 'data_instalacao',
]


def _rodar_seed(tenant):
    call_command('seed_checklist_venda', tenant=tenant.slug)


# ──────────────────────────────────────────────
# Idempotência
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_seed_idempotente_duas_rodadas_nao_duplica():
    tenant = TenantFactory()

    _rodar_seed(tenant)
    _rodar_seed(tenant)

    checklists = Checklist.all_tenants.filter(tenant=tenant, slug=SLUG_CHECKLIST)
    assert checklists.count() == 1
    itens = ItemChecklist.all_tenants.filter(checklist=checklists.first())
    assert itens.count() == 22


@pytest.mark.django_db
def test_seed_atualiza_pergunta_no_rerun_em_vez_de_duplicar():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    item = ItemChecklist.all_tenants.get(checklist=checklist, chave='nome_razaosocial')
    item.pergunta = 'Pergunta manualmente alterada'
    item.save(update_fields=['pergunta'])

    _rodar_seed(tenant)

    item.refresh_from_db()
    assert item.pergunta == 'Agora me passa seu *nome completo*?'
    assert ItemChecklist.all_tenants.filter(checklist=checklist, chave='nome_razaosocial').count() == 1


@pytest.mark.django_db
def test_rerun_nao_reativa_item_desativado_manualmente():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    item = ItemChecklist.all_tenants.get(checklist=checklist, chave='ponto_referencia')
    item.ativo = False
    item.save(update_fields=['ativo'])

    _rodar_seed(tenant)

    item.refresh_from_db()
    assert item.ativo is False  # preservado, o seed nunca liga/desliga item num re-run


@pytest.mark.django_db
def test_tenant_inexistente_falha():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command('seed_checklist_venda', tenant='nao-existe-999')


# ──────────────────────────────────────────────
# Checklist nasce inativo
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_checklist_nasce_inativo():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    assert checklist.ativo is False
    assert checklist.nome == NOME_CHECKLIST
    assert checklist.contexto == 'bot_vendas'
    assert checklist.modo_preenchimento == 'ia'
    assert checklist.entidade_alvo == 'lead'


@pytest.mark.django_db
def test_rerun_nao_reativa_checklist_ligado_manualmente():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    checklist.ativo = True
    checklist.save(update_fields=['ativo'])

    _rodar_seed(tenant)

    checklist.refresh_from_db()
    assert checklist.ativo is True  # preservado


# ──────────────────────────────────────────────
# Ordem dos itens
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_ordem_dos_itens_bate_com_sequencia_canonica():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    itens = list(ItemChecklist.all_tenants.filter(checklist=checklist).order_by('ordem', 'id'))

    assert [i.chave for i in itens] == CHAVES_NA_ORDEM
    assert [i.ordem for i in itens] == list(range(1, 23))


# ──────────────────────────────────────────────
# full_clean() — prova que o seed respeita o contrato do Matrix
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_todos_os_itens_passam_full_clean():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    itens = ItemChecklist.all_tenants.filter(checklist=checklist)
    assert itens.count() == 22
    for item in itens:
        item.full_clean()  # não deve levantar ValidationError pra nenhum item


@pytest.mark.django_db
def test_itens_de_opcoes_tem_entre_duas_e_cinco_opcoes():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    itens_opcoes = ItemChecklist.all_tenants.filter(checklist=checklist, tipo_resposta='opcoes')
    assert itens_opcoes.count() > 0
    for item in itens_opcoes:
        assert 2 <= len(item.opcoes) <= 5
        assert all(str(o.get('texto') or '').strip() for o in item.opcoes)


# ──────────────────────────────────────────────
# Condições (itens 8, 9, 10 e 12)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_condicoes_dos_itens_condicionais_preenchidas():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    for chave in ('cidade', 'bairro', 'rua'):
        item = ItemChecklist.all_tenants.get(checklist=checklist, chave=chave)
        assert item.condicao == {
            'chave': 'endereco_confirmado', 'operador': 'diferente', 'valor': 'sim',
        }

    tipo_residencia = ItemChecklist.all_tenants.get(checklist=checklist, chave='tipo_residencia')
    assert tipo_residencia.condicao == {'chave': 'tipo_imovel', 'operador': 'igual', 'valor': 'casa'}


@pytest.mark.django_db
def test_itens_elegiveis_respeita_condicoes_do_seed():
    """Roda as condições geradas pelo seed contra o motor de verdade
    (services/checklist.py) — não só confere o JSON, confere que ele FUNCIONA."""
    from apps.automacao.services import checklist as checklist_service

    tenant = TenantFactory()
    _rodar_seed(tenant)
    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)

    # Endereço confirmado -> cidade/bairro/rua ficam de fora
    elegiveis_confirmado = checklist_service.itens_elegiveis(checklist, {'endereco_confirmado': 'sim'})
    chaves_confirmado = {i.chave for i in elegiveis_confirmado}
    assert 'cidade' not in chaves_confirmado
    assert 'bairro' not in chaves_confirmado
    assert 'rua' not in chaves_confirmado

    # Endereço NÃO confirmado -> cidade/bairro/rua entram
    elegiveis_nao_confirmado = checklist_service.itens_elegiveis(checklist, {'endereco_confirmado': 'nao'})
    chaves_nao_confirmado = {i.chave for i in elegiveis_nao_confirmado}
    assert {'cidade', 'bairro', 'rua'} <= chaves_nao_confirmado

    # tipo_imovel=empresa -> tipo_residencia fica de fora
    elegiveis_empresa = checklist_service.itens_elegiveis(checklist, {'tipo_imovel': 'empresa'})
    assert 'tipo_residencia' not in {i.chave for i in elegiveis_empresa}

    # tipo_imovel=casa -> tipo_residencia entra
    elegiveis_casa = checklist_service.itens_elegiveis(checklist, {'tipo_imovel': 'casa'})
    assert 'tipo_residencia' in {i.chave for i in elegiveis_casa}


# ──────────────────────────────────────────────
# Adaptação obrigatória: nome do tenant, nunca "Megalink"
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_nome_do_tenant_aparece_e_megalink_nunca_aparece():
    tenant = TenantFactory(nome='Provedora Estrela')
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    itens = ItemChecklist.all_tenants.filter(checklist=checklist)

    for item in itens:
        assert 'Megalink' not in item.pergunta
        assert 'megalink' not in item.pergunta.lower()

    cpf = ItemChecklist.all_tenants.get(checklist=checklist, chave='cpf_cnpj')
    assert 'Provedora Estrela' in cpf.pergunta

    plano_confirmado = ItemChecklist.all_tenants.get(checklist=checklist, chave='plano_confirmado')
    assert 'Provedora Estrela' in plano_confirmado.pergunta
    # placeholders de runtime (não resolvidos em seed) continuam literais
    assert '{plano}' in plano_confirmado.pergunta
    assert '{valor}' in plano_confirmado.pergunta
    assert '{nome}' in plano_confirmado.pergunta


# ──────────────────────────────────────────────
# Planos (item 14): catálogo real vs placeholder
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_planos_usa_placeholder_quando_tenant_sem_catalogo():
    tenant = TenantFactory()
    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    item = ItemChecklist.all_tenants.get(checklist=checklist, chave='id_plano_rp')

    assert len(item.opcoes) == 3
    assert all('configurar' in o['texto'] for o in item.opcoes)
    assert 'placeholder' in item.ajuda.lower()
    # preços da Megalink nunca vazam pro placeholder
    assert '99,90' not in item.pergunta
    assert '129,90' not in item.pergunta
    assert '149,90' not in item.pergunta


@pytest.mark.django_db
def test_planos_usa_catalogo_real_quando_tenant_tem_tres_ou_mais_produtos_ativos():
    tenant = TenantFactory()
    # `codigo` tem unique_together (tenant, codigo) — mesmo em branco default '' colide
    # entre produtos do MESMO tenant, então cada um precisa de um código distinto.
    ProdutoServico.objects.create(tenant=tenant, nome='Fibra 300', codigo='F300', preco='79.90', ativo=True, ordem=1)
    ProdutoServico.objects.create(tenant=tenant, nome='Fibra 500', codigo='F500', preco='99.90', ativo=True, ordem=2)
    ProdutoServico.objects.create(tenant=tenant, nome='Fibra 700', codigo='F700', preco='119.90', ativo=True, ordem=3)
    ProdutoServico.objects.create(tenant=tenant, nome='Inativo', codigo='INA', preco='9.90', ativo=False, ordem=4)

    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    item = ItemChecklist.all_tenants.get(checklist=checklist, chave='id_plano_rp')

    nomes_opcoes = [o['texto'] for o in item.opcoes]
    assert any('Fibra 300' in t for t in nomes_opcoes)
    assert any('Fibra 500' in t for t in nomes_opcoes)
    assert any('Fibra 700' in t for t in nomes_opcoes)
    assert not any('configurar' in t for t in nomes_opcoes)
    assert 'catálogo real' in item.ajuda
    assert 'Megalink' not in item.pergunta


@pytest.mark.django_db
def test_planos_cai_pro_placeholder_com_apenas_dois_produtos_ativos():
    tenant = TenantFactory()
    ProdutoServico.objects.create(tenant=tenant, nome='Fibra 300', codigo='F300', preco='79.90', ativo=True, ordem=1)
    ProdutoServico.objects.create(tenant=tenant, nome='Fibra 500', codigo='F500', preco='99.90', ativo=True, ordem=2)

    _rodar_seed(tenant)

    checklist = Checklist.all_tenants.get(tenant=tenant, slug=SLUG_CHECKLIST)
    item = ItemChecklist.all_tenants.get(checklist=checklist, chave='id_plano_rp')
    assert all('configurar' in o['texto'] for o in item.opcoes)
