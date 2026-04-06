"""
Testes do módulo de Automações (apps/marketing/automacoes/).

Cobre:
- Models (CRUD, propriedades, validações)
- Engine (disparar_evento, avaliação de condições, execução de ações)
- Signals (integração com eventos do sistema)
- Views (lista, criar, editar, toggle, excluir, histórico)
- Tenant isolation
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.sistema.middleware import set_current_tenant
from apps.marketing.automacoes.models import (
    RegraAutomacao, CondicaoRegra, AcaoRegra, LogExecucao,
    NodoFluxo, ConexaoNodo, ExecucaoPendente, ControleExecucao,
)
from apps.marketing.automacoes.engine import (
    disparar_evento, _substituir_variaveis, executar_pendentes, _verificar_controles,
    _acao_criar_tarefa, _acao_mover_estagio, _acao_atribuir_responsavel, _acao_dar_pontos,
)
from apps.notificacoes.models import TipoNotificacao, CanalNotificacao, Notificacao

from .factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory, RegraAutomacaoFactory, CondicaoRegraFactory,
    AcaoRegraFactory, LogExecucaoFactory, MembroClubeFactory,
    TipoNotificacaoFactory, CanalNotificacaoFactory,
    PipelineEstagioFactory, OportunidadeVendaFactory,
    NodoFluxoFactory, ExecucaoPendenteFactory,
)


# ============================================================================
# MODELS
# ============================================================================

class RegraAutomacaoModelTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)

    def test_criar_regra(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        self.assertTrue(regra.pk)
        self.assertTrue(regra.ativa)
        self.assertEqual(regra.total_execucoes, 0)

    def test_taxa_sucesso_sem_execucoes(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        self.assertEqual(regra.taxa_sucesso, 100)

    def test_taxa_sucesso_com_execucoes(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, total_execucoes=10, total_sucesso=8, total_erro=2)
        self.assertEqual(regra.taxa_sucesso, 80)

    def test_str(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, nome='Teste', evento='lead_criado')
        self.assertIn('Teste', str(regra))
        self.assertIn('Novo lead criado', str(regra))


class CondicaoRegraModelTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)

    def test_avaliar_igual_string(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        cond = CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='origem', operador='igual', valor='whatsapp')
        self.assertTrue(cond.avaliar({'origem': 'whatsapp'}))
        self.assertFalse(cond.avaliar({'origem': 'site'}))

    def test_avaliar_maior_numerico(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        cond = CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='score', operador='maior', valor='7')
        self.assertTrue(cond.avaliar({'score': 9}))
        self.assertFalse(cond.avaliar({'score': 5}))

    def test_avaliar_contem(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        cond = CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='cidade', operador='contem', valor='Teresina')
        self.assertTrue(cond.avaliar({'cidade': 'Teresina-PI'}))
        self.assertFalse(cond.avaliar({'cidade': 'Fortaleza'}))

    def test_avaliar_campo_aninhado(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        cond = CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='lead.origem', operador='igual', valor='whatsapp')
        self.assertTrue(cond.avaliar({'lead': {'origem': 'whatsapp'}}))

    def test_avaliar_campo_inexistente(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        cond = CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='campo_fake', operador='igual', valor='x')
        self.assertFalse(cond.avaliar({'outro': 'valor'}))

    def test_avaliar_menor_igual(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        cond = CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='valor', operador='menor_igual', valor='100')
        self.assertTrue(cond.avaliar({'valor': 100}))
        self.assertTrue(cond.avaliar({'valor': 50}))
        self.assertFalse(cond.avaliar({'valor': 150}))

    def test_avaliar_diferente(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        cond = CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='status', operador='diferente', valor='cancelado')
        self.assertTrue(cond.avaliar({'status': 'ativo'}))
        self.assertFalse(cond.avaliar({'status': 'cancelado'}))


class AcaoRegraModelTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)

    def test_delay_timedelta(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(tenant=self.tenant, regra=regra, delay_ativo=True, delay_valor=30, delay_unidade='minutos')
        self.assertEqual(acao.delay_timedelta.total_seconds(), 30 * 60)

    def test_delay_horas(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(tenant=self.tenant, regra=regra, delay_ativo=True, delay_valor=2, delay_unidade='horas')
        self.assertEqual(acao.delay_timedelta.total_seconds(), 2 * 3600)

    def test_delay_dias(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(tenant=self.tenant, regra=regra, delay_ativo=True, delay_valor=1, delay_unidade='dias')
        self.assertEqual(acao.delay_timedelta.total_seconds(), 86400)

    def test_sem_delay(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(tenant=self.tenant, regra=regra, delay_ativo=False)
        self.assertEqual(acao.delay_timedelta.total_seconds(), 0)

    def test_str_com_delay(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='criar_tarefa', delay_ativo=True, delay_valor=5, delay_unidade='minutos')
        self.assertIn('5 minutos', str(acao))

    def test_str_sem_delay(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='criar_tarefa', delay_ativo=False)
        self.assertNotIn('após', str(acao))


# ============================================================================
# ENGINE
# ============================================================================

class EngineSubstituirVariaveisTest(TestCase):
    def test_substituicao_simples(self):
        resultado = _substituir_variaveis('Olá {{nome}}, seu score é {{score}}', {'nome': 'João', 'score': 8})
        self.assertEqual(resultado, 'Olá João, seu score é 8')

    def test_variavel_inexistente_mantem_original(self):
        resultado = _substituir_variaveis('Olá {{nome}}, {{empresa}}', {'nome': 'Maria'})
        self.assertIn('Maria', resultado)
        self.assertIn('{{empresa}}', resultado)

    def test_contexto_vazio(self):
        resultado = _substituir_variaveis('Texto fixo', {})
        self.assertEqual(resultado, 'Texto fixo')


class EngineDispararEventoTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)
        ConfigEmpresaFactory(tenant=self.tenant)

        # Criar tipos/canais de notificação para ações
        self.tipo_notif = TipoNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='lead_novo', nome='Lead Novo',
            descricao='Teste', template_padrao='Teste', prioridade_padrao='normal',
        )
        self.canal_notif = CanalNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='sistema', nome='Sistema', ativo=True,
        )

    def test_evento_sem_regras_nao_faz_nada(self):
        disparar_evento('evento_fake', {}, tenant=self.tenant)
        self.assertEqual(LogExecucao.all_tenants.count(), 0)

    def test_evento_com_regra_sem_condicoes_executa(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='Novo lead: {{nome}}')

        disparar_evento('lead_criado', {'nome': 'João'}, tenant=self.tenant)

        regra.refresh_from_db()
        self.assertEqual(regra.total_execucoes, 1)
        self.assertEqual(regra.total_sucesso, 1)
        self.assertEqual(LogExecucao.all_tenants.filter(regra=regra, status='sucesso').count(), 1)

    def test_condicao_verdadeira_executa(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='origem', operador='igual', valor='whatsapp')
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='Lead via WhatsApp')

        disparar_evento('lead_criado', {'origem': 'whatsapp', 'nome': 'Maria'}, tenant=self.tenant)

        regra.refresh_from_db()
        self.assertEqual(regra.total_sucesso, 1)

    def test_condicao_falsa_nao_executa(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='origem', operador='igual', valor='whatsapp')
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='Não deve executar')

        disparar_evento('lead_criado', {'origem': 'site'}, tenant=self.tenant)

        regra.refresh_from_db()
        self.assertEqual(regra.total_execucoes, 0)
        self.assertEqual(LogExecucao.all_tenants.count(), 0)

    def test_regra_inativa_nao_executa(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado', ativa=False)
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='Não deve executar')

        disparar_evento('lead_criado', {'nome': 'João'}, tenant=self.tenant)

        regra.refresh_from_db()
        self.assertEqual(regra.total_execucoes, 0)

    def test_multiplas_condicoes_and(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='origem', operador='igual', valor='whatsapp', ordem=0)
        CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='score', operador='maior', valor='5', ordem=1)
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='teste')

        # Ambas verdadeiras
        disparar_evento('lead_criado', {'origem': 'whatsapp', 'score': 8}, tenant=self.tenant)
        regra.refresh_from_db()
        self.assertEqual(regra.total_sucesso, 1)

    def test_multiplas_condicoes_and_uma_falsa(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='origem', operador='igual', valor='whatsapp', ordem=0)
        CondicaoRegraFactory(tenant=self.tenant, regra=regra, campo='score', operador='maior', valor='5', ordem=1)
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='teste')

        # Score não atende
        disparar_evento('lead_criado', {'origem': 'whatsapp', 'score': 3}, tenant=self.tenant)
        regra.refresh_from_db()
        self.assertEqual(regra.total_execucoes, 0)

    def test_acao_com_delay_gera_log_agendado(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='notificacao_sistema',
            configuracao='teste delay', delay_ativo=True, delay_valor=30, delay_unidade='minutos',
        )

        disparar_evento('lead_criado', {'nome': 'João'}, tenant=self.tenant)

        log = LogExecucao.all_tenants.filter(regra=regra).first()
        self.assertEqual(log.status, 'agendado')
        self.assertIsNotNone(log.data_agendada)

    def test_acao_notificacao_sistema_cria_notificacao(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='Lead {{nome}} cadastrado')

        disparar_evento('lead_criado', {'nome': 'Ana'}, tenant=self.tenant)

        notif = Notificacao.all_tenants.filter(tenant=self.tenant).last()
        self.assertIsNotNone(notif)
        self.assertIn('Ana', notif.mensagem)

    @patch('apps.marketing.automacoes.engine.requests.post')
    def test_acao_whatsapp_chama_webhook(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='enviar_whatsapp', configuracao='Olá {{nome}}!')

        disparar_evento('lead_criado', {'nome': 'João', 'telefone': '86999990000'}, tenant=self.tenant)

        mock_post.assert_called_once()
        call_data = mock_post.call_args[1]['json']
        self.assertIn('João', call_data['mensagem'])
        self.assertEqual(call_data['telefone'], '86999990000')

    @patch('apps.marketing.automacoes.engine.requests.post')
    def test_acao_webhook_externo(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='venda_aprovada')
        AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='webhook',
            configuracao='URL: https://example.com/hook\nMétodo: POST',
        )

        disparar_evento('venda_aprovada', {'nome': 'Cliente'}, tenant=self.tenant)

        mock_post.assert_called_once()
        self.assertIn('example.com', mock_post.call_args[0][0])

    def test_acao_criar_tarefa(self):
        from apps.comercial.crm.models import TarefaCRM
        user = UserFactory(is_staff=True)
        PerfilFactory(user=user, tenant=self.tenant)

        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='criar_tarefa',
            configuracao='Título: Contatar {{nome}}\nTipo: ligacao\nPrioridade: alta',
        )

        disparar_evento('lead_criado', {'nome': 'Carlos'}, tenant=self.tenant)

        tarefa = TarefaCRM.all_tenants.filter(tenant=self.tenant).last()
        self.assertIsNotNone(tarefa)
        self.assertIn('Carlos', tarefa.titulo)
        self.assertEqual(tarefa.tipo, 'ligacao')
        self.assertEqual(tarefa.prioridade, 'alta')

    def test_acao_dar_pontos(self):
        membro = MembroClubeFactory(tenant=self.tenant, saldo=100)
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='indicacao_convertida')
        AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='dar_pontos',
            configuracao=f'Pontos: 50\nMotivo: Indicação convertida',
        )

        disparar_evento('indicacao_convertida', {'cpf': membro.cpf}, tenant=self.tenant)

        membro.refresh_from_db()
        self.assertEqual(membro.saldo, 150)

    def test_evento_sem_tenant_nao_executa(self):
        set_current_tenant(None)
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado')
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='teste')

        disparar_evento('lead_criado', {'nome': 'João'}, tenant=None)

        regra.refresh_from_db()
        self.assertEqual(regra.total_execucoes, 0)


# ============================================================================
# TENANT ISOLATION
# ============================================================================

class AutomacoesTenantIsolationTest(TestCase):
    def test_regras_isoladas_por_tenant(self):
        from apps.sistema.middleware import set_current_tenant
        set_current_tenant(None)

        t1 = TenantFactory()
        t2 = TenantFactory()
        TipoNotificacao.all_tenants.create(tenant=t1, codigo='lead_novo', nome='T', descricao='T', template_padrao='T', prioridade_padrao='normal')
        CanalNotificacao.all_tenants.create(tenant=t1, codigo='sistema', nome='S', ativo=True)
        TipoNotificacao.all_tenants.create(tenant=t2, codigo='lead_novo', nome='T', descricao='T', template_padrao='T', prioridade_padrao='normal')
        CanalNotificacao.all_tenants.create(tenant=t2, codigo='sistema', nome='S', ativo=True)

        r1 = RegraAutomacaoFactory(tenant=t1, evento='lead_criado')
        AcaoRegraFactory(tenant=t1, regra=r1, tipo='notificacao_sistema', configuracao='T1')

        r2 = RegraAutomacaoFactory(tenant=t2, evento='lead_criado')
        AcaoRegraFactory(tenant=t2, regra=r2, tipo='notificacao_sistema', configuracao='T2')

        # Disparar para tenant1
        disparar_evento('lead_criado', {'nome': 'X'}, tenant=t1)

        r1.refresh_from_db()
        r2.refresh_from_db()
        self.assertEqual(r1.total_sucesso, 1)
        self.assertEqual(r2.total_execucoes, 0)  # Tenant2 não tocado


# ============================================================================
# VIEWS
# ============================================================================

class AutomacoesViewsTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(is_staff=True)
        self.perfil = PerfilFactory(user=self.user, tenant=self.tenant)
        self.config = ConfigEmpresaFactory(tenant=self.tenant)
        self.client.login(username=self.user.username, password='senha123')
        set_current_tenant(self.tenant)

    def test_lista_automacoes(self):
        RegraAutomacaoFactory(tenant=self.tenant)
        resp = self.client.get(reverse('marketing_automacoes:lista'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Automações')

    def test_criar_automacao_get(self):
        resp = self.client.get(reverse('marketing_automacoes:criar'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Nova Automação')

    def test_criar_automacao_post(self):
        """Criar automação (nome/descricao) redireciona para editor visual."""
        resp = self.client.post(reverse('marketing_automacoes:criar'), {
            'nome': 'Regra de teste',
            'descricao': 'Teste automatizado',
        })
        self.assertEqual(resp.status_code, 302)
        regra = RegraAutomacao.all_tenants.filter(tenant=self.tenant, nome='Regra de teste').first()
        self.assertIsNotNone(regra)
        self.assertTrue(regra.modo_fluxo)
        self.assertIn('fluxo', resp.url)

    def test_editar_automacao(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, nome='Original')
        resp = self.client.post(reverse('marketing_automacoes:editar', args=[regra.pk]), {
            'nome': 'Editada',
            'descricao': 'Descrição editada',
        })
        self.assertEqual(resp.status_code, 302)
        regra.refresh_from_db()
        self.assertEqual(regra.nome, 'Editada')

    def test_toggle_automacao(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, ativa=True)
        resp = self.client.post(reverse('marketing_automacoes:toggle', args=[regra.pk]))
        self.assertEqual(resp.status_code, 200)
        regra.refresh_from_db()
        self.assertFalse(regra.ativa)

    def test_excluir_automacao(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        pk = regra.pk
        resp = self.client.post(reverse('marketing_automacoes:excluir', args=[pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(RegraAutomacao.all_tenants.filter(pk=pk).exists())

    def test_historico_automacao(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        LogExecucaoFactory(tenant=self.tenant, regra=regra, status='sucesso', resultado='OK')
        resp = self.client.get(reverse('marketing_automacoes:historico', args=[regra.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sucesso')

    def test_lista_sem_login_redireciona(self):
        self.client.logout()
        resp = self.client.get(reverse('marketing_automacoes:lista'))
        self.assertEqual(resp.status_code, 302)

    def test_editor_fluxo_get(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        resp = self.client.get(reverse('marketing_automacoes:editor_fluxo', args=[regra.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Drawflow')

    def test_dashboard_automacoes(self):
        resp = self.client.get(reverse('marketing_automacoes:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_api_lead_timeline(self):
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        LogExecucaoFactory(tenant=self.tenant, regra=regra, lead=lead)
        resp = self.client.get(reverse('marketing_automacoes:api_lead_timeline', args=[lead.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['logs']), 1)

    def test_salvar_fluxo(self):
        import json as json_lib
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        payload = {
            'drawflow_state': {'drawflow': {'Home': {'data': {}}}},
            'nodos': [
                {'id_temp': '1', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'config': {}, 'pos_x': 100, 'pos_y': 100},
                {'id_temp': '2', 'tipo': 'action', 'subtipo': 'enviar_whatsapp', 'config': {'template': 'Ola!'}, 'pos_x': 300, 'pos_y': 100},
            ],
            'conexoes': [
                {'origem': '1', 'destino': '2', 'tipo_saida': 'default'},
            ],
        }
        resp = self.client.post(
            reverse('marketing_automacoes:salvar_fluxo', args=[regra.pk]),
            json_lib.dumps(payload), content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        regra.refresh_from_db()
        self.assertTrue(regra.modo_fluxo)
        self.assertEqual(regra.nodos.count(), 2)
        self.assertEqual(regra.conexoes.count(), 1)


# ============================================================================
# MODO FLUXO (grafo visual)
# ============================================================================

class FluxoEngineTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)
        ConfigEmpresaFactory(tenant=self.tenant)
        self.tipo_notif = TipoNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='lead_novo', nome='Lead Novo',
            descricao='T', template_padrao='T', prioridade_padrao='normal',
        )
        self.canal_notif = CanalNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='sistema', nome='Sistema', ativo=True,
        )

    def _criar_fluxo_linear(self):
        """Cria regra com fluxo: trigger → action."""
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado', modo_fluxo=True)
        trigger = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='trigger', subtipo='lead_criado', ordem=0,
        )
        action = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='action', subtipo='notificacao_sistema',
            configuracao={'template': 'Lead {{nome}} criado'}, ordem=1,
        )
        ConexaoNodo.objects.create(
            tenant=self.tenant, regra=regra, nodo_origem=trigger, nodo_destino=action, tipo_saida='default',
        )
        return regra

    def _criar_fluxo_com_condicao(self):
        """Cria regra: trigger → condition → (true: action_a) / (false: action_b)."""
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado', modo_fluxo=True)
        trigger = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='trigger', subtipo='lead_criado', ordem=0,
        )
        condition = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='condition', subtipo='campo_check',
            configuracao={'campo': 'lead_origem', 'operador': 'igual', 'valor': 'whatsapp'}, ordem=1,
        )
        action_sim = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='action', subtipo='notificacao_sistema',
            configuracao={'template': 'Via WhatsApp: {{nome}}'}, ordem=2,
        )
        action_nao = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='action', subtipo='notificacao_sistema',
            configuracao={'template': 'Via outro canal: {{nome}}'}, ordem=3,
        )
        ConexaoNodo.objects.create(tenant=self.tenant, regra=regra, nodo_origem=trigger, nodo_destino=condition, tipo_saida='default')
        ConexaoNodo.objects.create(tenant=self.tenant, regra=regra, nodo_origem=condition, nodo_destino=action_sim, tipo_saida='true')
        ConexaoNodo.objects.create(tenant=self.tenant, regra=regra, nodo_origem=condition, nodo_destino=action_nao, tipo_saida='false')
        return regra

    def test_fluxo_linear_executa(self):
        regra = self._criar_fluxo_linear()
        disparar_evento('lead_criado', {'nome': 'João'}, tenant=self.tenant)
        regra.refresh_from_db()
        self.assertEqual(regra.total_sucesso, 1)

    def test_fluxo_condicao_true(self):
        regra = self._criar_fluxo_com_condicao()
        disparar_evento('lead_criado', {'nome': 'Maria', 'lead_origem': 'whatsapp'}, tenant=self.tenant)
        regra.refresh_from_db()
        self.assertEqual(regra.total_sucesso, 1)
        # Verifica que a notificação criada é a do branch true
        notif = Notificacao.all_tenants.filter(tenant=self.tenant).last()
        self.assertIn('WhatsApp', notif.mensagem)

    def test_fluxo_condicao_false(self):
        regra = self._criar_fluxo_com_condicao()
        disparar_evento('lead_criado', {'nome': 'Pedro', 'lead_origem': 'site'}, tenant=self.tenant)
        regra.refresh_from_db()
        self.assertEqual(regra.total_sucesso, 1)
        notif = Notificacao.all_tenants.filter(tenant=self.tenant).last()
        self.assertIn('outro canal', notif.mensagem)

    def test_fluxo_com_delay(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado', modo_fluxo=True)
        trigger = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='trigger', subtipo='lead_criado', ordem=0,
        )
        delay = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='delay', subtipo='delay',
            configuracao={'valor': 30, 'unidade': 'minutos'}, ordem=1,
        )
        action = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='action', subtipo='notificacao_sistema',
            configuracao={'template': 'Delayed: {{nome}}'}, ordem=2,
        )
        ConexaoNodo.objects.create(tenant=self.tenant, regra=regra, nodo_origem=trigger, nodo_destino=delay, tipo_saida='default')
        ConexaoNodo.objects.create(tenant=self.tenant, regra=regra, nodo_origem=delay, nodo_destino=action, tipo_saida='default')

        disparar_evento('lead_criado', {'nome': 'Carlos'}, tenant=self.tenant)

        # Não executou a ação ainda, criou pendente
        self.assertEqual(ExecucaoPendente.all_tenants.filter(status='pendente').count(), 1)
        pendente = ExecucaoPendente.all_tenants.first()
        self.assertEqual(pendente.nodo, delay)

    def test_fluxo_legacy_nao_afetado(self):
        """Regras legacy (modo_fluxo=False) continuam funcionando."""
        regra = RegraAutomacaoFactory(tenant=self.tenant, evento='lead_criado', modo_fluxo=False)
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='Legacy: {{nome}}')

        disparar_evento('lead_criado', {'nome': 'Ana'}, tenant=self.tenant)
        regra.refresh_from_db()
        self.assertEqual(regra.total_sucesso, 1)


# ============================================================================
# CONTROLES DE EXECUÇÃO
# ============================================================================

class ControleExecucaoTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)
        ConfigEmpresaFactory(tenant=self.tenant)
        TipoNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='lead_novo', nome='T', descricao='T',
            template_padrao='T', prioridade_padrao='normal',
        )
        CanalNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='sistema', nome='S', ativo=True,
        )

    def test_max_execucoes_bloqueia(self):
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()

        regra = RegraAutomacaoFactory(
            tenant=self.tenant, evento='lead_criado', max_execucoes_por_lead=2, periodo_limite_horas=24,
        )
        AcaoRegraFactory(tenant=self.tenant, regra=regra, tipo='notificacao_sistema', configuracao='test')

        # Primeira e segunda: ok
        self.assertTrue(_verificar_controles(regra, lead))
        self.assertTrue(_verificar_controles(regra, lead))
        # Terceira: bloqueada
        self.assertFalse(_verificar_controles(regra, lead))

    def test_cooldown_bloqueia(self):
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()

        regra = RegraAutomacaoFactory(
            tenant=self.tenant, evento='lead_criado', cooldown_horas=1,
        )

        self.assertTrue(_verificar_controles(regra, lead))
        # Imediatamente após: bloqueada pelo cooldown
        self.assertFalse(_verificar_controles(regra, lead))

    def test_sem_controles_sempre_passa(self):
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()

        regra = RegraAutomacaoFactory(
            tenant=self.tenant, max_execucoes_por_lead=0, cooldown_horas=0,
        )
        for _ in range(10):
            self.assertTrue(_verificar_controles(regra, lead))


# ============================================================================
# EXECUÇÃO DE PENDENTES
# ============================================================================

class ExecucaoPendenteTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)
        ConfigEmpresaFactory(tenant=self.tenant)
        TipoNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='lead_novo', nome='T', descricao='T',
            template_padrao='T', prioridade_padrao='normal',
        )
        CanalNotificacao.all_tenants.create(
            tenant=self.tenant, codigo='sistema', nome='S', ativo=True,
        )

    def test_executa_pendentes_vencidos(self):
        from datetime import timedelta
        regra = RegraAutomacaoFactory(tenant=self.tenant, modo_fluxo=True)
        delay_nodo = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='delay', subtipo='delay', ordem=0,
        )
        action_nodo = NodoFluxo.objects.create(
            tenant=self.tenant, regra=regra, tipo='action', subtipo='notificacao_sistema',
            configuracao={'template': 'Delayed ok'}, ordem=1,
        )
        ConexaoNodo.objects.create(
            tenant=self.tenant, regra=regra, nodo_origem=delay_nodo, nodo_destino=action_nodo, tipo_saida='default',
        )

        # Criar pendente com data no passado
        pendente = ExecucaoPendente.objects.create(
            tenant=self.tenant, regra=regra, nodo=delay_nodo,
            contexto_json={'nome': 'Teste'},
            data_agendada=timezone.now() - timedelta(minutes=5),
        )

        count = executar_pendentes(self.tenant)
        self.assertEqual(count, 1)

        pendente.refresh_from_db()
        self.assertEqual(pendente.status, 'executado')

    def test_nao_executa_pendentes_futuros(self):
        from datetime import timedelta
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        ExecucaoPendente.objects.create(
            tenant=self.tenant, regra=regra,
            contexto_json={},
            data_agendada=timezone.now() + timedelta(hours=1),
        )

        count = executar_pendentes(self.tenant)
        self.assertEqual(count, 0)


# ============================================================================
# NOVAS VIEWS
# ============================================================================

class NovasViewsTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(is_staff=True)
        self.perfil = PerfilFactory(user=self.user, tenant=self.tenant)
        self.config = ConfigEmpresaFactory(tenant=self.tenant)
        self.client.login(username=self.user.username, password='senha123')
        set_current_tenant(self.tenant)

    def test_editor_fluxo(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        resp = self.client.get(reverse('marketing_automacoes:editor_fluxo', args=[regra.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard(self):
        resp = self.client.get(reverse('marketing_automacoes:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_salvar_fluxo(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        payload = {
            'drawflow_state': {'drawflow': {'Home': {'data': {}}}},
            'nodos': [
                {'id_temp': '1', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'config': {}, 'pos_x': 100, 'pos_y': 100, 'ordem': 1},
                {'id_temp': '2', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'config': {'template': 'Ola'}, 'pos_x': 400, 'pos_y': 100, 'ordem': 2},
            ],
            'conexoes': [
                {'origem': '1', 'destino': '2', 'tipo_saida': 'default'},
            ],
        }
        import json
        resp = self.client.post(
            reverse('marketing_automacoes:salvar_fluxo', args=[regra.pk]),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.assertEqual(regra.nodos.count(), 2)
        self.assertEqual(regra.conexoes.count(), 1)

    def test_timeline_lead(self):
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()
        resp = self.client.get(reverse('marketing_automacoes:api_lead_timeline', args=[lead.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['logs'], [])


# ============================================================================
# TESTES DE AÇÕES INDIVIDUAIS DO ENGINE
# ============================================================================

class AcaoCriarTarefaTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(is_staff=True)
        self.perfil = PerfilFactory(user=self.user, tenant=self.tenant)
        set_current_tenant(self.tenant)

    def test_criar_tarefa_com_lead(self):
        from apps.comercial.crm.models import TarefaCRM
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='criar_tarefa',
            configuracao='Título: Contatar {{nome}}\nTipo: ligacao\nPrioridade: alta',
        )
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()

        resultado = _acao_criar_tarefa(regra, acao, {'nome': 'João', 'lead': lead})
        self.assertIn('Tarefa criada', resultado)
        tarefa = TarefaCRM.all_tenants.filter(tenant=self.tenant).last()
        self.assertIsNotNone(tarefa)
        self.assertEqual(tarefa.titulo, 'Contatar João')
        self.assertEqual(tarefa.tipo, 'ligacao')
        self.assertEqual(tarefa.prioridade, 'alta')

    def test_criar_tarefa_sem_responsavel_usa_staff(self):
        from apps.comercial.crm.models import TarefaCRM
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='criar_tarefa',
            configuracao='Título: Teste',
        )
        resultado = _acao_criar_tarefa(regra, acao, {'nome': 'X'})
        self.assertIn('Tarefa criada', resultado)
        tarefa = TarefaCRM.all_tenants.filter(tenant=self.tenant).last()
        self.assertEqual(tarefa.responsavel, self.user)


class AcaoMoverEstagioTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)

    def test_mover_estagio_com_sucesso(self):
        from apps.comercial.crm.models import Pipeline, PipelineEstagio
        pipeline = Pipeline.all_tenants.create(tenant=self.tenant, nome='Vendas', slug='vendas')
        estagio1 = PipelineEstagio.all_tenants.create(
            tenant=self.tenant, pipeline=pipeline, nome='Novo', slug='novo', ordem=1,
        )
        estagio2 = PipelineEstagio.all_tenants.create(
            tenant=self.tenant, pipeline=pipeline, nome='Qualificado', slug='qualificado', ordem=2,
        )
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()
        from apps.comercial.crm.models import OportunidadeVenda
        opp = OportunidadeVenda.all_tenants.create(
            tenant=self.tenant, lead=lead, pipeline=pipeline, estagio=estagio1,
        )

        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='mover_estagio',
            configuracao='Estágio: qualificado',
        )
        resultado = _acao_mover_estagio(regra, acao, {'oportunidade': opp})
        self.assertIn('Qualificado', resultado)
        opp.refresh_from_db()
        self.assertEqual(opp.estagio, estagio2)

    def test_mover_estagio_sem_oportunidade(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='mover_estagio',
            configuracao='Estágio: qualificado',
        )
        resultado = _acao_mover_estagio(regra, acao, {})
        self.assertIn('Sem oportunidade', resultado)


class AcaoAtribuirResponsavelTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        self.user1 = UserFactory(is_staff=True, username='vendedor1')
        self.user2 = UserFactory(is_staff=True, username='vendedor2')
        PerfilFactory(user=self.user1, tenant=self.tenant)
        PerfilFactory(user=self.user2, tenant=self.tenant)
        set_current_tenant(self.tenant)

    def test_atribuir_round_robin(self):
        from apps.comercial.crm.models import Pipeline, PipelineEstagio, OportunidadeVenda
        pipeline = Pipeline.all_tenants.create(tenant=self.tenant, nome='V', slug='v')
        estagio = PipelineEstagio.all_tenants.create(
            tenant=self.tenant, pipeline=pipeline, nome='N', slug='n', ordem=1,
        )
        lead = LeadProspectoFactory.build(tenant=self.tenant)
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()
        opp = OportunidadeVenda.all_tenants.create(
            tenant=self.tenant, lead=lead, pipeline=pipeline, estagio=estagio,
        )

        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='atribuir_responsavel',
            configuracao='Responsável: auto (round-robin)',
        )
        resultado = _acao_atribuir_responsavel(regra, acao, {'oportunidade': opp})
        self.assertIn('Responsável atribuído', resultado)
        opp.refresh_from_db()
        self.assertIn(opp.responsavel, [self.user1, self.user2])

    def test_atribuir_sem_oportunidade(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='atribuir_responsavel',
            configuracao='auto',
        )
        resultado = _acao_atribuir_responsavel(regra, acao, {})
        self.assertIn('Sem oportunidade', resultado)


class AcaoDarPontosTest(TestCase):
    def setUp(self):
        self.tenant = TenantFactory()
        set_current_tenant(self.tenant)

    def test_dar_pontos_com_sucesso(self):
        membro = MembroClubeFactory(tenant=self.tenant, cpf='12345678901', saldo=10)
        lead = LeadProspectoFactory.build(tenant=self.tenant, cpf_cnpj='123.456.789-01')
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()

        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='dar_pontos',
            configuracao='Pontos: 50\nMotivo: Teste',
        )
        resultado = _acao_dar_pontos(regra, acao, {'lead': lead})
        self.assertIn('50 pontos', resultado)
        membro.refresh_from_db()
        self.assertEqual(membro.saldo, 60)

    def test_dar_pontos_sem_cpf(self):
        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='dar_pontos',
            configuracao='Pontos: 10',
        )
        resultado = _acao_dar_pontos(regra, acao, {})
        self.assertIn('CPF não encontrado', resultado)

    def test_dar_pontos_membro_nao_encontrado(self):
        lead = LeadProspectoFactory.build(tenant=self.tenant, cpf_cnpj='999.888.777-66')
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead._skip_segmento = True
        lead.save()

        regra = RegraAutomacaoFactory(tenant=self.tenant)
        acao = AcaoRegraFactory(
            tenant=self.tenant, regra=regra, tipo='dar_pontos',
            configuracao='Pontos: 10',
        )
        resultado = _acao_dar_pontos(regra, acao, {'lead': lead})
        self.assertIn('Membro não encontrado', resultado)
