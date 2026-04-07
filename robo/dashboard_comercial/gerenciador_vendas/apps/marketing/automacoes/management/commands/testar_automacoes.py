"""
Teste END-TO-END do engine de automacoes.
Simula acoes reais e verifica resultados no banco.

Uso: python manage.py testar_automacoes --settings=gerenciador_vendas.settings_local
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Testa todos os componentes do engine de automacoes (end-to-end)'

    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('  TESTE E2E - ENGINE DE AUTOMACOES')
        self.stdout.write('=' * 60 + '\n')

        self.passed = 0
        self.failed = 0
        self.errors = []

        self._setup()

        self._test_1_gatilho_lead_criado()
        self._test_2_condicao_branching()
        self._test_3_acao_notificacao()
        self._test_4_acao_criar_tarefa()
        self._test_5_delay_e_pendentes()
        self._test_6_rate_limit()
        self._test_7_fluxo_completo_e2e()
        self._test_8_substituicao_variaveis()

        self._cleanup()

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'  RESULTADO: {self.passed} OK | {self.failed} FALHA')
        self.stdout.write('=' * 60)
        if self.errors:
            self.stdout.write('\n  FALHAS:')
            for e in self.errors:
                self.stdout.write(f'    - {e}')
        self.stdout.write('')

    def _ok(self, msg):
        self.passed += 1
        self.stdout.write(f'  [OK] {msg}')

    def _fail(self, msg):
        self.failed += 1
        self.errors.append(msg)
        self.stdout.write(f'  [FALHA] {msg}')

    def _setup(self):
        from apps.sistema.models import Tenant
        from apps.comercial.leads.models import LeadProspecto
        from apps.notificacoes.models import TipoNotificacao, CanalNotificacao
        from apps.comercial.crm.models import Pipeline, PipelineEstagio

        self.tenant = Tenant.objects.first()
        self.user = User.objects.filter(is_staff=True, is_active=True).first()

        # Desativar todas as regras existentes para nao interferir
        from apps.marketing.automacoes.models import RegraAutomacao
        self._regras_originais = list(
            RegraAutomacao.all_tenants.filter(ativa=True).values_list('id', flat=True)
        )
        RegraAutomacao.all_tenants.filter(ativa=True).update(ativa=False)

        # Lead de teste
        self.lead = LeadProspecto(
            tenant=self.tenant,
            nome_razaosocial='Lead E2E Automacoes',
            telefone='5511888880000',
            email='e2e@automacao.com',
            origem='site',
            score_qualificacao=8,
            cidade='Recife',
            estado='PE',
            valor=150,
        )
        self.lead._skip_automacao = True
        self.lead.save()

        # Notificacao tipo/canal
        TipoNotificacao.all_tenants.get_or_create(
            tenant=self.tenant, codigo='lead_novo',
            defaults={'nome': 'Novo Lead', 'descricao': 'Teste'}
        )
        CanalNotificacao.all_tenants.get_or_create(
            tenant=self.tenant, codigo='sistema',
            defaults={'nome': 'Sistema', 'descricao': 'Teste'}
        )

        # Pipeline e estagios para testes de CRM
        self.pipeline, _ = Pipeline.objects.get_or_create(
            tenant=self.tenant, slug='teste-e2e',
            defaults={'nome': 'Pipeline E2E', 'tipo': 'vendas'}
        )
        self.estagio_novo, _ = PipelineEstagio.objects.get_or_create(
            tenant=self.tenant, pipeline=self.pipeline, slug='novo',
            defaults={'nome': 'Novo', 'ordem': 1, 'tipo': 'novo'}
        )
        self.estagio_qualificado, _ = PipelineEstagio.objects.get_or_create(
            tenant=self.tenant, pipeline=self.pipeline, slug='qualificado',
            defaults={'nome': 'Qualificado', 'ordem': 2, 'tipo': 'qualificacao'}
        )

        self.stdout.write(f'\n  Setup: tenant={self.tenant.nome}, lead={self.lead.pk}\n')

    def _cleanup(self):
        from apps.marketing.automacoes.models import RegraAutomacao, ExecucaoPendente, ControleExecucao

        # Limpar dados de teste
        regras_teste = RegraAutomacao.all_tenants.filter(nome__startswith='__E2E__')
        ExecucaoPendente.all_tenants.filter(regra__in=regras_teste).delete()
        ControleExecucao.all_tenants.filter(regra__in=regras_teste).delete()
        # Manter logs e regras para auditoria
        regras_teste.update(ativa=False)

        # Reativar regras originais
        RegraAutomacao.all_tenants.filter(id__in=self._regras_originais).update(ativa=True)

    def _criar_regra_fluxo(self, nome, evento, nodos_config):
        """Helper: cria regra + nodos + conexoes."""
        from apps.marketing.automacoes.models import RegraAutomacao, NodoFluxo, ConexaoNodo

        regra = RegraAutomacao.all_tenants.create(
            tenant=self.tenant, nome=f'__E2E__{nome}',
            evento=evento, ativa=True, modo_fluxo=True,
        )

        nodos = {}
        for cfg in nodos_config:
            nodo = NodoFluxo.all_tenants.create(
                tenant=self.tenant, regra=regra,
                tipo=cfg['tipo'], subtipo=cfg.get('subtipo', ''),
                configuracao=cfg.get('config', {}),
                ordem=cfg.get('ordem', 0),
            )
            nodos[cfg['id']] = nodo

        for cfg in nodos_config:
            for conn in cfg.get('conexoes', []):
                ConexaoNodo.all_tenants.create(
                    tenant=self.tenant, regra=regra,
                    nodo_origem=nodos[cfg['id']],
                    nodo_destino=nodos[conn['destino']],
                    tipo_saida=conn.get('tipo', 'default'),
                )

        return regra, nodos

    # ================================================================
    # TESTE 1: Gatilho lead_criado (E2E via signal)
    # ================================================================
    def _test_1_gatilho_lead_criado(self):
        self.stdout.write('\n--- T1: GATILHO lead_criado (via signal real) ---')
        from apps.marketing.automacoes.models import LogExecucao
        from apps.comercial.leads.models import LeadProspecto
        from apps.notificacoes.models import Notificacao

        regra, nodos = self._criar_regra_fluxo('gatilho_signal', 'lead_criado', [
            {'id': 'trigger', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'ordem': 1,
             'conexoes': [{'destino': 'acao'}]},
            {'id': 'acao', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'ordem': 2,
             'config': {'template': 'E2E: Lead {{lead_nome}} criado via signal'}},
        ])

        notif_antes = Notificacao.all_tenants.count()

        # Criar lead REAL (sem _skip_automacao) para disparar signal
        lead_real = LeadProspecto.all_tenants.create(
            tenant=self.tenant,
            nome_razaosocial='Lead Signal E2E',
            telefone='5511777770000',
            email='signal@e2e.com',
            origem='whatsapp',
        )

        notif_depois = Notificacao.all_tenants.count()
        log = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['acao']).last()

        if notif_depois > notif_antes:
            self._ok('Notificacao criada pelo signal')
        else:
            self._fail('Notificacao NAO foi criada pelo signal')

        if log and log.lead_id == lead_real.pk:
            self._ok(f'Log com lead correto (id={lead_real.pk})')
        elif log:
            self._fail(f'Log existe mas lead_id={log.lead_id}, esperava {lead_real.pk}')
        else:
            self._fail('Nenhum log gerado')

        lead_real.delete()

    # ================================================================
    # TESTE 2: Condicao com branching real
    # ================================================================
    def _test_2_condicao_branching(self):
        self.stdout.write('\n--- T2: CONDICAO branching ---')
        from apps.marketing.automacoes.models import LogExecucao
        from apps.marketing.automacoes.engine import disparar_evento

        regra, nodos = self._criar_regra_fluxo('condicao_branch', 'lead_criado', [
            {'id': 'trigger', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'ordem': 1,
             'conexoes': [{'destino': 'cond'}]},
            {'id': 'cond', 'tipo': 'condition', 'subtipo': 'campo_check', 'ordem': 2,
             'config': {'campo': 'lead.score_qualificacao', 'operador': 'maior', 'valor': '5'},
             'conexoes': [
                 {'destino': 'acao_true', 'tipo': 'true'},
                 {'destino': 'acao_false', 'tipo': 'false'},
             ]},
            {'id': 'acao_true', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'ordem': 3,
             'config': {'template': 'E2E: Branch TRUE'}},
            {'id': 'acao_false', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'ordem': 4,
             'config': {'template': 'E2E: Branch FALSE'}},
        ])

        disparar_evento('lead_criado', {
            'lead': self.lead, 'lead_nome': self.lead.nome_razaosocial,
        }, tenant=self.tenant)

        log_cond = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['cond']).last()
        log_true = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['acao_true']).exists()
        log_false = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['acao_false']).exists()

        if log_cond and 'true' in (log_cond.resultado or ''):
            self._ok(f'Condicao avaliou: score 8 > 5 = true')
        else:
            self._fail(f'Condicao nao avaliou corretamente: {log_cond.resultado if log_cond else "sem log"}')

        if log_true and not log_false:
            self._ok('Branch TRUE executou, FALSE nao (correto)')
        else:
            self._fail(f'Branch errado: true={log_true}, false={log_false}')

    # ================================================================
    # TESTE 3: Acao notificacao (verifica no banco)
    # ================================================================
    def _test_3_acao_notificacao(self):
        self.stdout.write('\n--- T3: ACAO notificacao (verifica no banco) ---')
        from apps.marketing.automacoes.engine import disparar_evento
        from apps.notificacoes.models import Notificacao

        regra, _ = self._criar_regra_fluxo('acao_notif', 'lead_criado', [
            {'id': 'trigger', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'ordem': 1,
             'conexoes': [{'destino': 'acao'}]},
            {'id': 'acao', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'ordem': 2,
             'config': {'template': 'E2E: Notificacao para {{lead_nome}}'}},
        ])

        antes = Notificacao.all_tenants.count()
        disparar_evento('lead_criado', {
            'lead': self.lead, 'lead_nome': self.lead.nome_razaosocial,
        }, tenant=self.tenant)
        depois = Notificacao.all_tenants.count()

        if depois > antes:
            notif = Notificacao.all_tenants.order_by('-id').first()
            if 'Lead E2E' in (notif.mensagem or ''):
                self._ok(f'Notificacao criada com variavel substituida: "{notif.mensagem[:50]}"')
            else:
                self._ok(f'Notificacao criada: "{notif.mensagem[:50]}"')
        else:
            self._fail('Notificacao NAO foi criada no banco')

    # ================================================================
    # TESTE 4: Acao criar tarefa (verifica no CRM)
    # ================================================================
    def _test_4_acao_criar_tarefa(self):
        self.stdout.write('\n--- T4: ACAO criar_tarefa (verifica no CRM) ---')
        from apps.marketing.automacoes.engine import disparar_evento
        from apps.comercial.crm.models import TarefaCRM

        regra, _ = self._criar_regra_fluxo('acao_tarefa', 'lead_criado', [
            {'id': 'trigger', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'ordem': 1,
             'conexoes': [{'destino': 'acao'}]},
            {'id': 'acao', 'tipo': 'action', 'subtipo': 'criar_tarefa', 'ordem': 2,
             'config': {'template': 'titulo: Tarefa E2E {{lead_nome}}\ntipo: followup\nprioridade: alta'}},
        ])

        antes = TarefaCRM.objects.count()
        disparar_evento('lead_criado', {
            'lead': self.lead, 'lead_nome': self.lead.nome_razaosocial,
        }, tenant=self.tenant)
        depois = TarefaCRM.objects.count()

        if depois > antes:
            tarefa = TarefaCRM.objects.order_by('-id').first()
            checks = []
            if 'E2E' in tarefa.titulo:
                checks.append('titulo OK')
            if tarefa.lead_id == self.lead.pk:
                checks.append('lead OK')
            if tarefa.responsavel:
                checks.append(f'responsavel={tarefa.responsavel.username}')
            self._ok(f'Tarefa criada (pk={tarefa.pk}): {", ".join(checks)}')
        else:
            self._fail('Tarefa NAO foi criada no CRM')

    # ================================================================
    # TESTE 5: Delay + execucao pendente
    # ================================================================
    def _test_5_delay_e_pendentes(self):
        self.stdout.write('\n--- T5: DELAY + execucao pendente ---')
        from apps.marketing.automacoes.models import ExecucaoPendente, LogExecucao
        from apps.marketing.automacoes.engine import disparar_evento, executar_pendentes
        from apps.notificacoes.models import Notificacao

        regra, nodos = self._criar_regra_fluxo('delay', 'lead_criado', [
            {'id': 'trigger', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'ordem': 1,
             'conexoes': [{'destino': 'delay'}]},
            {'id': 'delay', 'tipo': 'delay', 'config': {'valor': 5, 'unidade': 'minutos'}, 'ordem': 2,
             'conexoes': [{'destino': 'acao'}]},
            {'id': 'acao', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'ordem': 3,
             'config': {'template': 'E2E: Pos-delay executado'}},
        ])

        disparar_evento('lead_criado', {
            'lead': self.lead, 'lead_nome': self.lead.nome_razaosocial,
        }, tenant=self.tenant)

        # 1. Verificar pendente criado
        pendente = ExecucaoPendente.all_tenants.filter(regra=regra, status='pendente').first()
        if pendente:
            self._ok(f'Pendente criado: agendado para {pendente.data_agendada.strftime("%H:%M")}')
        else:
            self._fail('Pendente NAO foi criado')
            return

        # 2. Verificar que acao pos-delay NAO executou ainda
        log_acao = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['acao']).exists()
        if not log_acao:
            self._ok('Acao pos-delay ainda nao executou (correto, delay pendente)')
        else:
            self._fail('Acao pos-delay executou antes do delay')

        # 3. Simular passagem de tempo e executar pendentes
        pendente.data_agendada = timezone.now() - timedelta(minutes=1)
        pendente.save(update_fields=['data_agendada'])

        notif_antes = Notificacao.all_tenants.count()
        count = executar_pendentes(tenant=self.tenant)
        notif_depois = Notificacao.all_tenants.count()

        if count > 0:
            self._ok(f'executar_pendentes processou {count} item(s)')
        else:
            self._fail('executar_pendentes nao processou nada')

        pendente.refresh_from_db()
        if pendente.status == 'executado':
            self._ok('Pendente marcado como executado')
        else:
            self._fail(f'Pendente status={pendente.status}, esperava executado')

        if notif_depois > notif_antes:
            self._ok('Acao pos-delay criou notificacao no banco')
        else:
            self._fail('Acao pos-delay NAO criou notificacao')

    # ================================================================
    # TESTE 6: Rate limit por lead
    # ================================================================
    def _test_6_rate_limit(self):
        self.stdout.write('\n--- T6: RATE LIMIT ---')
        from apps.marketing.automacoes.models import LogExecucao
        from apps.marketing.automacoes.engine import disparar_evento

        regra, nodos = self._criar_regra_fluxo('ratelimit', 'lead_criado', [
            {'id': 'trigger', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'ordem': 1,
             'conexoes': [{'destino': 'acao'}]},
            {'id': 'acao', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'ordem': 2,
             'config': {'template': 'E2E: Rate limit'}},
        ])
        regra.max_execucoes_por_lead = 2
        regra.periodo_limite_horas = 24
        regra.save(update_fields=['max_execucoes_por_lead', 'periodo_limite_horas'])

        ctx = {'lead': self.lead, 'lead_nome': self.lead.nome_razaosocial}

        # 1a e 2a execucao
        disparar_evento('lead_criado', ctx, tenant=self.tenant)
        disparar_evento('lead_criado', ctx, tenant=self.tenant)
        logs_2 = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['acao'], status='sucesso').count()

        if logs_2 == 2:
            self._ok('2 execucoes permitidas')
        else:
            self._fail(f'Esperava 2 execucoes, teve {logs_2}')

        # 3a execucao (deve ser bloqueada)
        disparar_evento('lead_criado', ctx, tenant=self.tenant)
        logs_3 = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['acao'], status='sucesso').count()

        if logs_3 == 2:
            self._ok('3a execucao bloqueada pelo rate limit')
        else:
            self._fail(f'Rate limit falhou: {logs_3} execucoes (esperava 2)')

    # ================================================================
    # TESTE 7: Fluxo completo E2E (trigger → condition → action real)
    # ================================================================
    def _test_7_fluxo_completo_e2e(self):
        self.stdout.write('\n--- T7: FLUXO COMPLETO E2E ---')
        from apps.marketing.automacoes.models import LogExecucao
        from apps.marketing.automacoes.engine import disparar_evento
        from apps.comercial.crm.models import TarefaCRM
        from apps.notificacoes.models import Notificacao

        regra, nodos = self._criar_regra_fluxo('fluxo_e2e', 'lead_criado', [
            {'id': 'trigger', 'tipo': 'trigger', 'subtipo': 'lead_criado', 'ordem': 1,
             'conexoes': [{'destino': 'cond'}]},
            {'id': 'cond', 'tipo': 'condition', 'subtipo': 'campo_check', 'ordem': 2,
             'config': {'campo': 'lead.cidade', 'operador': 'igual', 'valor': 'Recife'},
             'conexoes': [
                 {'destino': 'tarefa', 'tipo': 'true'},
                 {'destino': 'notif_fora', 'tipo': 'false'},
             ]},
            {'id': 'tarefa', 'tipo': 'action', 'subtipo': 'criar_tarefa', 'ordem': 3,
             'config': {'template': 'titulo: Visita E2E {{lead_nome}}\ntipo: visita\nprioridade: alta'}},
            {'id': 'notif_fora', 'tipo': 'action', 'subtipo': 'notificacao_sistema', 'ordem': 4,
             'config': {'template': 'E2E: Lead fora de cobertura'}},
        ])

        tarefas_antes = TarefaCRM.objects.count()
        notif_antes = Notificacao.all_tenants.count()

        # Lead tem cidade=Recife, deve seguir branch TRUE (criar tarefa)
        disparar_evento('lead_criado', {
            'lead': self.lead,
            'lead_nome': self.lead.nome_razaosocial,
            'lead_cidade': self.lead.cidade,
        }, tenant=self.tenant)

        tarefas_depois = TarefaCRM.objects.count()
        notif_depois = Notificacao.all_tenants.count()

        # Verificar condicao
        log_cond = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['cond']).last()
        if log_cond and 'true' in (log_cond.resultado or ''):
            self._ok('Condicao: cidade=Recife avaliou TRUE')
        else:
            self._fail(f'Condicao errada: {log_cond.resultado if log_cond else "sem log"}')

        # Verificar tarefa criada (branch true)
        if tarefas_depois > tarefas_antes:
            tarefa = TarefaCRM.objects.order_by('-id').first()
            self._ok(f'Tarefa criada no CRM: "{tarefa.titulo}" (branch TRUE)')
        else:
            self._fail('Tarefa NAO foi criada (branch TRUE falhou)')

        # Verificar que notificacao (branch false) NAO foi criada
        log_false = LogExecucao.all_tenants.filter(regra=regra, nodo=nodos['notif_fora']).exists()
        if not log_false:
            self._ok('Branch FALSE nao executou (correto)')
        else:
            self._fail('Branch FALSE executou indevidamente')

    # ================================================================
    # TESTE 8: Substituicao de variaveis
    # ================================================================
    def _test_8_substituicao_variaveis(self):
        self.stdout.write('\n--- T8: SUBSTITUICAO DE VARIAVEIS ---')
        from apps.marketing.automacoes.engine import _substituir_variaveis

        # Variaveis simples
        r = _substituir_variaveis('Ola {{lead_nome}}, tel {{telefone}}', {
            'lead_nome': 'Joao', 'telefone': '11999',
        })
        if 'Joao' in r and '11999' in r:
            self._ok(f'Variaveis simples: "{r}"')
        else:
            self._fail(f'Variaveis simples falhou: "{r}"')

        # Variaveis de objeto
        r2 = _substituir_variaveis('Lead: {{lead_nome_razaosocial}}', {
            'lead': self.lead,
        })
        if 'E2E' in r2:
            self._ok(f'Variaveis de objeto: "{r2}"')
        else:
            self._fail(f'Variaveis de objeto falhou: "{r2}"')
