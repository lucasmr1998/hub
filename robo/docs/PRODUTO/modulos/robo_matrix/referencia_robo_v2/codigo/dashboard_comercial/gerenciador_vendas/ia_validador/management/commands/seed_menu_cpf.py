"""Cria/atualiza a regra 'menu_cpf_confirmacao' (idempotente).

Quando um número reconhecido (cliente Hubsoft) inicia um atendimento, o bot
pergunta ANTES do menu se o atendimento é para o CPF atrelado ao número ou um
novo CPF. A pergunta é renderizada dinamicamente pelo engine (onboarding.py),
aqui definimos só o extractor da opção (1=mesmo CPF, 2=outro CPF).

    manage.py seed_menu_cpf
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria/atualiza a regra de confirmação de CPF (atual/novo)"

    def handle(self, *args, **opts):
        from ia_validador.models import RegraValidacao

        regra, criada = RegraValidacao.objects.update_or_create(
            question_id='menu_cpf_confirmacao',
            defaults={
                'ordem': 4,   # antes do menu_cliente_existente (ordem 5)
                'descricao': 'Confirma se o atendimento é p/ o CPF do número ou outro',
                'pergunta_padrao': (
                    'Este atendimento é para o CPF atrelado a este número '
                    'ou para um outro CPF?\n\n'
                    '1) Sim, é esse CPF\n'
                    '2) Outro CPF'
                ),
                'extractor_tipo': 'opcao',
                'extractor_config': {
                    'opcoes': {
                        'cpf_atual': ['1', 'sim', 'atual', 'mesmo', 'esse',
                                      'este', 'é esse', 'isso', 'pode', 'confirmo'],
                        'cpf_novo': ['2', 'novo', 'outro', 'nao', 'não',
                                     'outra', 'diferente'],
                    }
                },
                'campo_lead_atualizar': '',     # não persiste no lead — só rotear
                'msg_sucesso': '',              # engine/proximo-passo conduz
                'msg_erro': 'Por favor responda *1* (mesmo CPF) ou *2* (outro CPF).',
                'max_tentativas': 3,
                'permite_pular': False,
                'ativo': True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"regra menu_cpf_confirmacao {'criada' if criada else 'atualizada'} "
            f"(id={regra.id})"))
