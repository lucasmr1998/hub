"""
Cron de recontato automatico para atendimentos parados.

Detecta atendimentos com bot aguardando resposta ha mais de X minutos
e envia mensagem de recontato. Apos esgotar tentativas, finaliza.

Uso:
    python manage.py executar_recontato --settings=gerenciador_vendas.settings_local_pg

Crontab (a cada 5 minutos):
    */5 * * * * cd /path/to/project && python manage.py executar_recontato
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa recontato automatico para atendimentos parados'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, default='',
                            help='Filtrar por tenant (slug ou parte do nome)')

    def handle(self, *args, **options):
        from apps.sistema.models import Tenant
        from apps.sistema.middleware import set_current_tenant

        filtro_tenant = options['tenant']
        tenants = Tenant.objects.filter(ativo=True)
        if filtro_tenant:
            tenants = tenants.filter(nome__icontains=filtro_tenant)

        total_recontatos = 0
        total_finalizados = 0

        for tenant in tenants:
            set_current_tenant(tenant)
            r, f = self._processar_tenant(tenant)
            total_recontatos += r
            total_finalizados += f

        if total_recontatos or total_finalizados:
            self.stdout.write(self.style.SUCCESS(
                f'Recontato: {total_recontatos} enviados, {total_finalizados} finalizados'
            ))

    def _processar_tenant(self, tenant):
        from apps.comercial.atendimento.models import AtendimentoFluxo

        agora = timezone.now()
        recontatos = 0
        finalizados = 0

        # Buscar atendimentos parados com recontato ativo no fluxo
        atendimentos = AtendimentoFluxo.objects.filter(
            fluxo__tenant=tenant,
            status__in=['iniciado', 'em_andamento'],
            fluxo__recontato_ativo=True,
            nodo_atual__isnull=False,  # bot aguardando resposta
        ).select_related('fluxo', 'lead', 'nodo_atual')

        for atend in atendimentos:
            config = atend.fluxo.recontato_config or {}
            tentativas_config = config.get('tentativas', [])
            if not tentativas_config:
                continue

            # Verificar se e hora de enviar recontato
            if atend.recontato_proximo_em:
                if agora < atend.recontato_proximo_em:
                    continue  # Ainda nao e hora
            else:
                # Primeira verificacao: usar data_ultima_atividade + tempo da 1a tentativa
                tempo_1a = tentativas_config[0].get('tempo_minutos', 60)
                if agora < atend.data_ultima_atividade + timedelta(minutes=tempo_1a):
                    continue  # Ainda nao e hora

            idx = atend.recontato_tentativas

            if idx < len(tentativas_config):
                # Enviar recontato
                tentativa = tentativas_config[idx]
                mensagem = tentativa.get('mensagem', '')

                if not mensagem and config.get('usar_ia'):
                    mensagem = self._gerar_mensagem_ia(atend, config)

                if not mensagem:
                    mensagem = f'Oi! Notei que voce parou de responder. Posso te ajudar com algo?'

                # Substituir variaveis
                from apps.comercial.atendimento.engine import _substituir_variaveis, _construir_contexto
                contexto = _construir_contexto(atend)
                mensagem = _substituir_variaveis(mensagem, contexto)

                # Enviar via inbox
                self._enviar_mensagem(atend, mensagem, tenant)

                # Atualizar controle
                atend.recontato_tentativas = idx + 1

                # Calcular proximo recontato
                if idx + 1 < len(tentativas_config):
                    prox_tempo = tentativas_config[idx + 1].get('tempo_minutos', 1440)
                    atend.recontato_proximo_em = agora + timedelta(minutes=prox_tempo)
                else:
                    atend.recontato_proximo_em = None  # Sera finalizado na proxima execucao

                atend.save(update_fields=['recontato_tentativas', 'recontato_proximo_em'])
                recontatos += 1

                logger.info(
                    "Recontato #%d enviado: atend=%s, lead=%s",
                    idx + 1, atend.pk, atend.lead.nome_razaosocial
                )

            else:
                # Todas as tentativas esgotadas
                acao_final = config.get('acao_final', 'abandonar')

                if acao_final == 'transferir_humano':
                    self._transferir_para_humano(atend, tenant)
                else:
                    atend.status = 'abandonado'
                    atend.motivo_finalizacao = 'sem_resposta'
                    atend.data_conclusao = agora
                    atend.nodo_atual = None
                    atend.save(update_fields=[
                        'status', 'motivo_finalizacao', 'data_conclusao', 'nodo_atual'
                    ])

                    # Atualizar conversa
                    self._marcar_conversa_finalizada(atend, tenant)

                finalizados += 1
                logger.info(
                    "Recontato esgotado: atend=%s, lead=%s, acao=%s",
                    atend.pk, atend.lead.nome_razaosocial, acao_final
                )

        return recontatos, finalizados

    def _enviar_mensagem(self, atend, mensagem, tenant):
        """Envia mensagem de recontato via inbox."""
        from apps.inbox.models import Conversa
        from apps.inbox.signals import _enviar_mensagens_bot

        conversa = Conversa.objects.filter(
            lead=atend.lead,
            status__in=['aberta', 'pendente'],
        ).order_by('-ultima_mensagem_em').first()

        if conversa:
            _enviar_mensagens_bot(tenant, conversa, mensagem, 'Hubtrix')

    def _transferir_para_humano(self, atend, tenant):
        """Transfere para fila humana quando recontato esgota."""
        from apps.inbox.models import Conversa
        from apps.inbox.distribution import distribuir_conversa

        atend.status = 'transferido'
        atend.motivo_finalizacao = 'sem_resposta'
        atend.data_conclusao = timezone.now()
        atend.nodo_atual = None
        atend.save(update_fields=[
            'status', 'motivo_finalizacao', 'data_conclusao', 'nodo_atual'
        ])

        conversa = Conversa.objects.filter(
            lead=atend.lead,
            status__in=['aberta', 'pendente'],
        ).order_by('-ultima_mensagem_em').first()

        if conversa:
            conversa.modo_atendimento = 'humano'
            conversa.save(update_fields=['modo_atendimento'])
            distribuir_conversa(conversa, tenant)

    def _marcar_conversa_finalizada(self, atend, tenant):
        """Marca conversa como finalizada pelo bot."""
        from apps.inbox.models import Conversa

        conversa = Conversa.objects.filter(
            lead=atend.lead,
            status__in=['aberta', 'pendente'],
        ).order_by('-ultima_mensagem_em').first()

        if conversa:
            conversa.modo_atendimento = 'finalizado_bot'
            conversa.save(update_fields=['modo_atendimento'])

    def _gerar_mensagem_ia(self, atend, config):
        """Gera mensagem de recontato usando IA."""
        from apps.comercial.atendimento.engine import (
            _obter_integracao_ia, _chamar_llm_simples, _construir_contexto
        )

        nodo = atend.nodo_atual
        if not nodo:
            return ''

        integracao = _obter_integracao_ia(
            nodo.configuracao or {}, atend.fluxo.tenant
        )
        if not integracao:
            return ''

        contexto = _construir_contexto(atend)
        titulo_questao = nodo.configuracao.get('titulo', '')

        prompt = (
            f"O candidato parou de responder no meio de um atendimento. "
            f"A ultima pergunta foi: \"{titulo_questao}\". "
            f"Nome do candidato: {atend.lead.nome_razaosocial or 'desconhecido'}. "
            f"Tentativa de recontato #{atend.recontato_tentativas + 1}. "
            f"Gere uma mensagem curta, educada e amigavel para retomar o contato. "
            f"Texto puro sem markdown."
        )

        messages = [
            {'role': 'system', 'content': prompt},
        ]

        return _chamar_llm_simples(integracao, '', messages) or ''
