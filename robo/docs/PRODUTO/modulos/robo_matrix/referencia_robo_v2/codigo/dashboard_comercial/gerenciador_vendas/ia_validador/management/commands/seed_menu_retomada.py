"""Cria/atualiza a regra 'retomada_confirmacao' (idempotente).

Quando um cliente reabre o atendimento com um CADASTRO EM ANDAMENTO (lead
mid-registration — já passou do CPF mas não terminou), o bot pergunta ANTES de
emendar no meio se ele quer continuar de onde parou, recomeçar do início ou se é
para outro CPF. A pergunta é renderizada dinamicamente pelo engine
(onboarding._talvez_retomada); aqui definimos só o extractor da opção
(1=continuar, 2=recomeçar, 3=outro CPF).

    manage.py seed_menu_retomada
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria/atualiza a regra de retomada (continuar/recomeçar/outro CPF)"

    def handle(self, *args, **opts):
        from ia_validador.models import RegraValidacao

        regra, criada = RegraValidacao.objects.update_or_create(
            question_id='retomada_confirmacao',
            defaults={
                'ordem': 3,   # antes do menu_cpf_confirmacao (4) e do menu (5)
                'descricao': 'Cliente reabriu com cadastro em andamento — continuar/recomeçar/outro CPF',
                # Corpo da pergunta (editável na tela Mensagens). A saudação
                # "Oi, *Nome*!" é adicionada dinamicamente pelo engine. Mantenha
                # as opções 1/2/3 para o extractor casar.
                'pergunta_padrao': (
                    'Vi que a gente já tinha começado seu atendimento. '
                    'Como você quer seguir? ##1f504##\n\n'
                    '*1)* Continuar de onde paramos ##25b6##\n'
                    '*2)* Recomeçar do início ##1f501##\n'
                    '*3)* É para outro CPF ##1f194##\n\n'
                    '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._'
                ),
                'extractor_tipo': 'opcao',
                'extractor_config': {
                    'opcoes': {
                        'continuar': ['1', 'continua', 'continuar', 'de onde',
                                      'onde paramos', 'prosseguir', 'seguir',
                                      'retomar'],
                        'recomecar': ['2', 'recomecar', 'recomeçar', 'reiniciar',
                                      'inicio', 'início', 'do zero', 'zerar',
                                      'começar de novo', 'comecar de novo'],
                        'outro_cpf': ['3', 'outro', 'outra pessoa', 'novo cpf',
                                      'diferente'],
                    }
                },
                'campo_lead_atualizar': '',     # não persiste no lead — só rotear
                'msg_sucesso': '',              # engine/proximo-passo conduz
                'msg_erro': 'Por favor responda *1* (continuar), *2* (recomeçar) ou *3* (outro CPF).',
                'max_tentativas': 3,
                'permite_pular': False,
                'ativo': True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"regra retomada_confirmacao {'criada' if criada else 'atualizada'} "
            f"(id={regra.id})"))
