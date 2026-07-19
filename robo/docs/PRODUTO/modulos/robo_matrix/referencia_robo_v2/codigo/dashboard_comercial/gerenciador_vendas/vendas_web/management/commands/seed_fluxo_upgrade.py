"""Cria/atualiza o Fluxo de Atendimento de UPGRADE de plano (idempotente).

Sem esse fluxo, ao escolher "2) Fazer upgrade de plano" no chat o endpoint
/api/upgrade-conversa/turno/ devolve 404 → iniciar_fluxo_upgrade retorna None →
o bot cai em transbordo ("Vou te transferir pra um atendente...").

Estrutura (cada questão marcada com variaveis_contexto.upgrade_role, lido por
upgrade_plano_service para montar o UpgradePlano):
  1. servico      → escolhe o serviço atual (fonte servicos_ativos_cliente)
  2. plano        → escolhe o plano novo  (fonte planos_upgrade_disponiveis)
  3. confirmacao  → SIM/NÃO
  4. fim          → mensagem de encerramento (dispara criação do UpgradePlano)

    manage.py seed_fluxo_upgrade
"""
from django.core.management.base import BaseCommand
from django.db import transaction


QUESTOES = [
    dict(indice=1, upgrade_role='servico', tipo_questao='select',
         titulo='Qual serviço você quer dar upgrade?',
         opcoes_dinamicas_fonte='servicos_ativos_cliente'),
    dict(indice=2, upgrade_role='plano', tipo_questao='select',
         titulo='Para qual plano deseja migrar?',
         opcoes_dinamicas_fonte='planos_upgrade_disponiveis'),
    dict(indice=3, upgrade_role='confirmacao', tipo_questao='select',
         titulo='Confirma o upgrade? Responda SIM ou NÃO.',
         opcoes_resposta=['sim', 'nao']),
    dict(indice=4, upgrade_role='fim', tipo_questao='texto',
         titulo='Perfeito! ##2705## Seu upgrade foi registrado e já está '
                'sendo processado. Em instantes seu plano será atualizado. ##1f680##'),
]


class Command(BaseCommand):
    help = 'Cria/atualiza o fluxo de upgrade de plano (idempotente)'

    @transaction.atomic
    def handle(self, *args, **opts):
        from vendas_web.models import FluxoAtendimento, QuestaoFluxo

        fluxo, criado = FluxoAtendimento.objects.update_or_create(
            tipo_fluxo='upgrade',
            defaults=dict(
                nome='Upgrade de Plano',
                descricao='Fluxo conversacional de upgrade/migração de plano '
                          '(cliente Hubsoft existente).',
                status='ativo', ativo=True, max_tentativas=3,
            ),
        )
        self.stdout.write(self.style.SUCCESS(
            f'Fluxo upgrade {"criado" if criado else "atualizado"} (id={fluxo.id})'))

        for q in QUESTOES:
            defaults = dict(
                titulo=q['titulo'],
                tipo_questao=q['tipo_questao'],
                tipo_validacao='obrigatoria' if q['indice'] != 4 else 'opcional',
                opcoes_resposta=q.get('opcoes_resposta') or [],
                opcoes_dinamicas_fonte=q.get('opcoes_dinamicas_fonte', '') or '',
                variaveis_contexto={'upgrade_role': q['upgrade_role']},
                ativo=True,
                ordem_exibicao=q['indice'],
            )
            obj, c = QuestaoFluxo.objects.update_or_create(
                fluxo=fluxo, indice=q['indice'], defaults=defaults)
            self.stdout.write(
                f'  q{q["indice"]} [{q["upgrade_role"]}] '
                f'{"criada" if c else "atualizada"} → {obj.titulo[:50]}')

        # remove questões extras de seeds antigos (mantém só as 4)
        extras = fluxo.questoes.exclude(indice__in=[q['indice'] for q in QUESTOES])
        n = extras.count()
        if n:
            extras.delete()
            self.stdout.write(self.style.WARNING(f'  {n} questão(ões) extra(s) removida(s)'))

        self.stdout.write(self.style.SUCCESS(
            f'OK — fluxo upgrade com {fluxo.get_total_questoes()} questões ativas'))
