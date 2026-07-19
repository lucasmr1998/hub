"""Seed do FLUXO DE UPGRADE DE PLANO.

Executar (uma vez ou após mudanças):
    python manage.py shell -c "exec(open('popular_fluxo_upgrade.py').read())"

Fluxo (4 perguntas, roteamento sequencial 1→2→3→4):
  1. Escolher SERVIÇO ativo  (servicos_ativos_cliente)  role='servico'
  2. Escolher PLANO novo     (planos_upgrade_disponiveis) role='plano'
  3. CONFIRMAR (sim/não)                                  role='confirmacao'
  4. Mensagem de sucesso (encerramento)                   role='fim'

A saudação/"responde sim pra começar" foi REMOVIDA — o cliente já escolheu
"2) Upgrade" no menu e recebe a intro do engine; ir direto pro serviço evita
mensagem redundante. A confirmação (Q3) é o único gate sim/não; tanto 'sim'
quanto 'não' caem na Q4 (fim) — o helper só cria o UpgradePlano se confirmou.
"""

from vendas_web.models import FluxoAtendimento, QuestaoFluxo


def criar_fluxo_upgrade():
    print("🚀 Criando Fluxo de Upgrade de Plano...")

    fluxo, created = FluxoAtendimento.objects.get_or_create(
        nome="Fluxo de Upgrade de Plano",
        defaults={
            'descricao': 'Cliente existente solicita upgrade — escolhe serviço ativo, escolhe plano novo, confirma.',
            'tipo_fluxo': 'upgrade',
            'status': 'ativo',
            'max_tentativas': 3,
            'tempo_limite_minutos': 15,
            'permite_pular_questoes': False,
            'ativo': True,
            'criado_por': 'Sistema',
        },
    )
    if created:
        print(f"✅ Fluxo criado: {fluxo.nome}")
    else:
        fluxo.questoes.all().delete()  # re-seed limpo
        fluxo.tipo_fluxo = 'upgrade'
        fluxo.status = 'ativo'
        fluxo.ativo = True
        fluxo.save()
        print(f"♻  Fluxo recriado: {fluxo.nome}")

    # Q1 — Escolher SERVIÇO ativo
    QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=1,
        titulo="Qual desses serviços você quer melhorar?",
        tipo_questao='select',
        tipo_validacao='obrigatoria',
        opcoes_dinamicas_fonte='servicos_ativos_cliente',
        max_tentativas=2,
        estrategia_erro='repetir',
        ativo=True,
        variaveis_contexto={'upgrade_role': 'servico'},
    )
    print("✅ Q1 escolher serviço")

    # Q2 — Escolher PLANO novo
    QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=2,
        titulo="Show! Agora escolhe o plano novo (já tirei da lista o que você usa hoje):",
        tipo_questao='select',
        tipo_validacao='obrigatoria',
        opcoes_dinamicas_fonte='planos_upgrade_disponiveis',
        max_tentativas=2,
        estrategia_erro='repetir',
        ativo=True,
        variaveis_contexto={'upgrade_role': 'plano'},
    )
    print("✅ Q2 escolher plano")

    # Q3 — Confirmar
    QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=3,
        titulo=(
            "Confirma a migração pro plano novo? "
            "Responde *sim* que eu já disparo. ✅"
        ),
        tipo_questao='select',
        tipo_validacao='obrigatoria',
        opcoes_resposta=['sim', 'nao'],
        max_tentativas=2,
        estrategia_erro='repetir',
        ativo=True,
        variaveis_contexto={'upgrade_role': 'confirmacao'},
    )
    print("✅ Q3 confirmação")

    # Q4 — Mensagem de sucesso (encerramento)
    QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=4,
        titulo=(
            "Prontinho! ✅ Registramos sua migração. Vamos aplicar no sistema "
            "em alguns minutos e te avisamos assim que concluir. Obrigada pela "
            "confiança na *Megalink*! 💙"
        ),
        tipo_questao='texto',
        tipo_validacao='opcional',
        max_tentativas=1,
        estrategia_erro='avancar',
        ativo=True,
        variaveis_contexto={'upgrade_role': 'fim'},
    )
    print("✅ Q4 encerramento")

    print(f"\n🎉 Fluxo '{fluxo.nome}' pronto — id={fluxo.id}")
    return fluxo


fluxo = criar_fluxo_upgrade()
