"""
Seed do fluxo de atendimento do Assistente CRM.
Idempotente: so cria se nao existe. Desativa fluxo antigo se houver.

Fluxo: entrada -> ia_agente (com tools CRM) -> finalizacao
"""
from django.core.management.base import BaseCommand

NOME_FLUXO = 'Assistente CRM v2'

SYSTEM_PROMPT = """Voce e o assistente Hubtrix, um copilot de CRM via WhatsApp.

Voce atende vendedores que estao em campo e precisam acessar o CRM pelo celular.

REGRAS:
- Seja conciso e direto (respostas curtas para WhatsApp)
- Use as tools do CRM para consultar dados e executar acoes
- Confirme acoes destrutivas antes de executar (marcar ganho/perda)
- Se o vendedor perguntar algo que nao e sobre CRM, responda de forma amigavel e breve
- Nunca invente dados, sempre use as tools para consultar"""

TOOLS_CRM = [
    'consultar_lead', 'listar_oportunidades', 'mover_oportunidade',
    'criar_nota', 'criar_tarefa', 'atualizar_lead', 'resumo_pipeline',
    'listar_tarefas', 'proxima_tarefa', 'agendar_followup',
    'buscar_historico', 'marcar_perda', 'marcar_ganho',
    'agenda_do_dia', 'ver_comandos',
]


class Command(BaseCommand):
    help = 'Cria o fluxo de atendimento do Assistente CRM (idempotente)'

    def handle(self, *args, **options):
        from apps.sistema.models import Tenant
        from apps.sistema.middleware import set_current_tenant
        from apps.comercial.atendimento.models import (
            FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento,
        )
        from apps.integracoes.models import IntegracaoAPI

        # Buscar tenant Aurora HQ
        tenant_aurora = Tenant.objects.filter(nome__icontains='aurora').first()
        if not tenant_aurora:
            self.stdout.write(self.style.WARNING('Tenant Aurora HQ nao encontrado. Pulando.'))
            return

        set_current_tenant(tenant_aurora)

        # Verificar se fluxo ja existe e esta completo
        existente = FluxoAtendimento.objects.filter(
            tenant=tenant_aurora, nome=NOME_FLUXO,
        ).first()

        if existente:
            if existente.nodos.filter(tipo='entrada').exists():
                self.stdout.write(f'  Fluxo "{NOME_FLUXO}" ja existe. Pulando.')
                return
            else:
                # Fluxo vazio/incompleto, remover e recriar
                self.stdout.write(f'  Fluxo "{NOME_FLUXO}" (pk={existente.pk}) incompleto. Removendo...')
                existente.delete()

        # Desativar fluxo antigo
        antigos = FluxoAtendimento.objects.filter(
            tenant=tenant_aurora, nome__icontains='assistente',
            ativo=True,
        )
        for f in antigos:
            f.ativo = False
            f.status = 'inativo'
            f.save(update_fields=['ativo', 'status'])
            self.stdout.write(f'  Fluxo antigo "{f.nome}" (pk={f.pk}) desativado.')

        # Buscar integracao IA (OpenAI do Aurora HQ, fallback qualquer)
        integracao_ia = IntegracaoAPI.all_tenants.filter(
            tenant=tenant_aurora, tipo__in=['openai', 'anthropic', 'groq'],
            ativa=True,
        ).first()

        if not integracao_ia:
            integracao_ia = IntegracaoAPI.all_tenants.filter(
                tipo__in=['openai', 'anthropic', 'groq'], ativa=True,
            ).first()

        integracao_ia_id = integracao_ia.pk if integracao_ia else None

        if not integracao_ia_id:
            self.stdout.write(self.style.WARNING(
                '  Nenhuma integracao IA encontrada. Fluxo criado sem IA configurada.'
            ))

        # Criar fluxo
        fluxo = FluxoAtendimento.objects.create(
            tenant=tenant_aurora,
            nome=NOME_FLUXO,
            canal='qualquer',
            ativo=True,
            status='ativo',
            modo_fluxo=True,
            max_tentativas=3,
        )

        # Nodos
        entrada = NodoFluxoAtendimento.objects.create(
            tenant=tenant_aurora, fluxo=fluxo,
            tipo='entrada', subtipo='inicio_fluxo',
            pos_x=100, pos_y=200, configuracao={},
        )

        agente = NodoFluxoAtendimento.objects.create(
            tenant=tenant_aurora, fluxo=fluxo,
            tipo='ia_agente', subtipo='ia_agente',
            pos_x=400, pos_y=200,
            configuracao={
                'integracao_ia_id': integracao_ia_id,
                'modelo': 'gpt-4o-mini',
                'max_turnos': 20,
                'system_prompt': SYSTEM_PROMPT,
                'tools_habilitadas': TOOLS_CRM,
                'tools_customizadas': [],
                'mensagem_timeout': 'Desculpe, nao consegui processar. Tente novamente.',
            },
        )

        fim = NodoFluxoAtendimento.objects.create(
            tenant=tenant_aurora, fluxo=fluxo,
            tipo='finalizacao', subtipo='fim_fluxo',
            pos_x=700, pos_y=200,
            configuracao={
                'mensagem_final': 'Ate logo! Se precisar, e so mandar mensagem.',
            },
        )

        # Conexoes
        ConexaoNodoAtendimento.objects.create(
            tenant=tenant_aurora, fluxo=fluxo,
            nodo_origem=entrada, nodo_destino=agente,
            tipo_saida='default',
        )
        ConexaoNodoAtendimento.objects.create(
            tenant=tenant_aurora, fluxo=fluxo,
            nodo_origem=agente, nodo_destino=fim,
            tipo_saida='default',
        )

        self.stdout.write(self.style.SUCCESS(
            f'  Fluxo "{NOME_FLUXO}" criado (pk={fluxo.pk}) com {3} nodos.'
        ))
