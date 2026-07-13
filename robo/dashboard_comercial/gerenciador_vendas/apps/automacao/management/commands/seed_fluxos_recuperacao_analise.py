"""Seed dos fluxos das tarefas #180 (recuperacao de oportunidades perdidas) e
#181 (analise automatica de atendimentos Matrix), na engine de automacao nova.

Idempotente POR NOME (get por tenant + nome): re-rodar atualiza grafo/descricao
em vez de duplicar. `ativo` só é setado em False na CRIACAO; num fluxo que já
existe, o campo NUNCA é tocado (o comando nunca liga nem desliga um fluxo). O
`Agente` "Analista de Atendimentos" segue a mesma regra.

Nasce tudo INATIVO: rodar este comando não muda nenhum comportamento em
producao, só cadastra os fluxos/agente pra alguem revisar e ativar manualmente
no editor. F2/F3 NAO enviam mensagem automatica pro cliente final (decisao de
produto): eles criam uma TAREFA pra vendedora dona da oportunidade retomar o
contato pessoalmente. Janela/prazo/guarda de contato recente sao configuraveis
no no de gatilho de cada fluxo, sem precisar editar este seed.

Uso:
    python manage.py seed_fluxos_recuperacao_analise --tenant nuvyon \\
        --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand, CommandError

from apps.automacao.models import Agente, Fluxo
from apps.automacao.runtime import validar_fluxo

NOME_AGENTE = 'Analista de Atendimentos'

DESCRICAO_AGENTE = (
    'Le o transcript de um atendimento Matrix finalizado e devolve um resumo, '
    'se a venda foi perdida e o motivo sugerido do catalogo de MotivoPerda do tenant. '
    'O catalogo de motivos vai INLINE no system prompt (gerado no momento do seed). '
    'Se o catalogo de motivos mudar, re-rodar o seed pra atualizar o prompt.'
)


def _system_prompt_agente(tenant):
    """Monta o system prompt com o CATALOGO DE MOTIVOS do tenant embutido (achado
    do piloto fluxo 25: o agente inventou motivo fora do catalogo). A tool
    `listar_motivos_perda` continua disponivel como reforco/checagem, mas o
    catalogo inline evita a rodada de tool-call na maioria dos casos e reduz a
    chance do modelo alucinar um nome parecido.

    O prompt tambem pede `conclusao`: uma linha ja pronta pra virar nota,
    montada pelo proprio LLM (mata a lacuna de "Perda sugerida: " vazio quando
    nao ha perda, que o template fixo antigo deixava passar).
    """
    from apps.comercial.crm.models import MotivoPerda

    nomes = list(
        MotivoPerda.all_tenants.filter(tenant=tenant, ativo=True)
        .order_by('ordem', 'nome').values_list('nome', flat=True)
    )
    catalogo = ', '.join(nomes) if nomes else '(nenhum motivo cadastrado no tenant)'

    return (
        'Voce analisa transcripts de atendimentos de um provedor de internet que foram '
        'transferidos para atendimento humano e finalizados. Sua saida e SEMPRE um unico '
        'JSON valido, sem nenhum texto antes ou depois, no formato:\n'
        '{"resumo": "<resumo fiel do atendimento em 2 a 4 frases>", "perdido": true|false, '
        '"motivo_nome": "<nome exato de um motivo do catalogo>"|null, '
        '"confianca": "alta"|"media"|"baixa", '
        '"conclusao": "<uma linha, pronta para virar nota>"}\n'
        f'CATALOGO DE MOTIVOS DO TENANT: {catalogo}. Use exatamente estes nomes.\n'
        'Regras: "perdido" = true somente se a conversa evidencia que a venda NAO avancou '
        '(cliente desistiu, sem retorno, sem cobertura, preco, debito etc). Quando '
        'perdido=true, use a tool listar_motivos_perda para confirmar o catalogo do tenant e '
        'escolha o motivo_nome EXATAMENTE como esta no catalogo acima (o mais adequado a '
        'conversa). Se nenhum motivo do catalogo servir ou perdido=false, motivo_nome=null. '
        'Nao invente motivos fora do catalogo. Em "conclusao", escreva a linha pronta pra '
        'nota: se perdido=true e motivo_nome preenchido, use exatamente '
        '"Perda sugerida: <motivo_nome> (confianca <confianca>)"; caso contrario, use '
        'exatamente "Sem perda identificada no atendimento."'
    )


NOME_F1 = '[#181] Analise de atendimentos Matrix'
NOME_F2 = '[#180] Recuperacao sem retorno, tarefa'
NOME_F3 = '[#180] Recuperacao inviabilidade, tarefa'
NOME_F4 = '[#180] Recuperacao, lead respondeu, reabrir'

DESCRICAO_F1 = (
    'Varredura horaria dos atendimentos Matrix finalizados nas ultimas 48h ainda sem '
    'analise. O Agente IA "Analista de Atendimentos" le o transcript, resume o '
    'atendimento e classifica se a venda foi perdida (com o motivo sugerido do '
    'catalogo do tenant). Cria uma nota na oportunidade com o resumo e, quando '
    'perdido, define o motivo de perda (somente se a oportunidade ainda nao tiver '
    'um E estiver de fato em estagio de perda; caso contrario o no so pula, sem '
    'erro). Tarefa #181. Nasce INATIVO, revisar antes de ligar.'
)

DESCRICAO_F2 = (
    'NAO envia mensagem automatica pro cliente final. Cria uma TAREFA pra vendedora '
    'responsavel retomar contato pessoalmente, com oportunidades perdidas ha 15+ dias '
    'pelo motivo "Sem retorno" que ainda nao tem uma tarefa de retomada (marcador '
    'recuperacao_iniciada) e cujo lead a vendedora nao contatou nos ultimos 7 dias '
    '(sem_contato_dias). So entram oportunidades COM responsavel definido '
    '(exige_responsavel), pra a tarefa nunca nascer orfa. Janela, prazo e a guarda de '
    'contato recente sao configuraveis no no de gatilho. Tarefa #180. Nasce INATIVO.'
)

DESCRICAO_F3 = (
    'NAO envia mensagem automatica pro cliente final. Cria uma TAREFA pra vendedora '
    'responsavel quando uma oportunidade perdida ha 15+ dias por falta de viabilidade '
    'tecnica passa a ter cobertura no CEP (consulta hubsoft_planos_cep antes de criar '
    'a tarefa, e lista os planos disponiveis na descricao). So entram oportunidades '
    'COM responsavel definido (exige_responsavel), pra a tarefa nunca nascer orfa. '
    'Janela e prazo sao configuraveis no no de gatilho. Tarefa #180. Nasce INATIVO.'
)

DESCRICAO_F4 = (
    'Reabre a oportunidade quando o lead responde ao contato (evento historico_contato '
    'com status "resposta"), desde que a oportunidade tenha uma tarefa de retomada '
    'criada por um dos fluxos de recuperacao (marcador recuperacao_iniciada). O estagio '
    'de reabertura (em-atendimento) e configuravel no no "reabrir": ajustar se o '
    'pipeline do tenant usar outro slug. Tarefa #180. Nasce INATIVO.'
)


def _grafo_f1(agente_id):
    nodes = {
        'trigger': {
            'tipo': 'agenda',
            'config': {
                'intervalo_minutos': 60,
                'varredura': 'atendimentos_matrix_finalizados',
                'varredura_config': {'janela_dias': '2'},
                'max_por_rodada': 10,
                'max_por_lead': 1,
            },
            'pos': {'x': 0, 'y': 0},
            'label': 'Varredura: atendimentos Matrix finalizados',
        },
        'transcript': {
            'tipo': 'matrix_atendimento',
            'config': {'codigo': '{{var.id_atendimento_matrix}}', 'anonimizar': True},
            'pos': {'x': 240, 'y': 0},
            'label': 'Transcript do atendimento',
        },
        'analista': {
            'tipo': 'ia_agente',
            'config': {'agente_id': str(agente_id), 'mensagem': '{{nodes.transcript.transcript}}'},
            'pos': {'x': 480, 'y': 0},
            'label': 'Agente IA: Analista de Atendimentos',
        },
        'json': {
            'tipo': 'extrair_json',
            'config': {'origem': '{{nodes.analista.resposta}}'},
            'pos': {'x': 720, 'y': 0},
            'label': 'Extrair JSON da analise',
        },
        'nota': {
            'tipo': 'criar_nota',
            'config': {
                'texto': (
                    'Analise automatica do atendimento {{var.id_atendimento_matrix}}:\n\n'
                    '{{nodes.json.resumo}}\n\n'
                    '{{nodes.json.conclusao}}'
                ),
            },
            'pos': {'x': 960, 'y': 0},
            'label': 'Nota: resumo da analise',
        },
        'marcador': {
            'tipo': 'definir_propriedade_oportunidade',
            'config': {'propriedade': 'marcador', 'chave': 'analise_atendimento_matrix'},
            'pos': {'x': 1200, 'y': 0},
            'label': 'Marcar atendimento analisado',
        },
        'se_perdido': {
            'tipo': 'if',
            'config': {
                'esquerda': '{{nodes.json.perdido}}',
                'operador': 'igual',
                # `perdido` chega como bool Python (json.loads). O resolvedor de
                # template devolve o valor BRUTO (full-match), então o `if`
                # compara str(True)/str(False), por isso 'True' com maiúscula.
                'direita': 'True',
            },
            'pos': {'x': 1440, 'y': 0},
            'label': 'Perdido?',
        },
        'motivo': {
            'tipo': 'definir_propriedade_oportunidade',
            'config': {
                'propriedade': 'motivo_perda',
                'valor': '{{nodes.json.motivo_nome}}',
                'somente_se_vazio': True,
            },
            # REDE DE SEGURANÇA real (achado piloto fluxo 25) não é este `if`
            # (que só economiza a chamada quando o LLM já diz perdido=false):
            # é o handler `motivo_perda`, que só aplica com a op em estágio
            # `is_final_perdido` e nunca levanta (motivo fora do catálogo vira
            # skip, não erro/retry).
            'pos': {'x': 1680, 'y': 0},
            'label': 'Definir motivo de perda',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'transcript', 'saida': 'default'},
        {'de': 'transcript', 'para': 'analista', 'saida': 'sucesso'},
        {'de': 'analista', 'para': 'json', 'saida': 'sucesso'},
        {'de': 'json', 'para': 'nota', 'saida': 'sucesso'},
        {'de': 'nota', 'para': 'marcador', 'saida': 'sucesso'},
        {'de': 'marcador', 'para': 'se_perdido', 'saida': 'sucesso'},
        {'de': 'se_perdido', 'para': 'motivo', 'saida': 'true'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


def _config_tarefa(titulo, descricao, *, tipo='whatsapp', prioridade='alta', prazo_dias='2'):
    """Config do nó `criar_tarefa` compartilhada entre F2/F3 (opção B: humano no
    loop — cria tarefa pra vendedora responsável, nunca dispara mensagem
    automática pro cliente final)."""
    return {
        'titulo': titulo,
        'tipo': tipo,
        'prioridade': prioridade,
        'prazo_dias': prazo_dias,
        'descricao': descricao,
    }


_DESCRICAO_TAREFA_F2 = (
    'Lead perdido ha {{var.dias_perdida}} dias por "{{var.motivo_perda_nome}}".\n'
    'Telefone: {{lead.telefone}}\n'
    '\n'
    'Vale uma segunda tentativa: quem some raramente e quem nao quer.\n'
    'A analise do atendimento (resumo do que aconteceu e por que parou) esta na\n'
    'linha do tempo desta oportunidade.\n'
    '\n'
    'Se o cliente responder, a oportunidade reabre sozinha e volta pro seu funil.'
)


def _grafo_f2():
    nodes = {
        'trigger': {
            'tipo': 'agenda',
            'config': {
                'intervalo_minutos': 1440,
                'varredura': 'oportunidades_perdidas',
                'varredura_config': {
                    'janela_dias_min': '15',
                    'motivo_ref_nome': 'Sem retorno',
                    'sem_marcador': 'recuperacao_iniciada',
                    'exige_responsavel': 'true',
                    'sem_contato_dias': '7',
                },
                'max_por_rodada': 15,
                'max_por_lead': 1,
            },
            'pos': {'x': 0, 'y': 0},
            'label': 'Varredura: oportunidades perdidas (Sem retorno)',
        },
        'tarefa': {
            'tipo': 'criar_tarefa',
            'config': _config_tarefa(
                'Retomar contato: {{lead.nome_razaosocial}}', _DESCRICAO_TAREFA_F2,
            ),
            'pos': {'x': 240, 'y': 0},
            'label': 'Tarefa: retomar contato',
        },
        'marcador': {
            'tipo': 'definir_propriedade_oportunidade',
            'config': {'propriedade': 'marcador', 'chave': 'recuperacao_iniciada'},
            'pos': {'x': 480, 'y': 0},
            'label': 'Marcar recuperacao iniciada',
        },
        'nota': {
            'tipo': 'criar_nota',
            'config': {'texto': (
                'Tarefa de retomada criada para {{lead.nome_razaosocial}} '
                '(perdido ha {{var.dias_perdida}} dias).'
            )},
            'pos': {'x': 720, 'y': 0},
            'label': 'Nota: tarefa de retomada criada',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'tarefa', 'saida': 'default'},
        {'de': 'tarefa', 'para': 'marcador', 'saida': 'sucesso'},
        {'de': 'marcador', 'para': 'nota', 'saida': 'sucesso'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


_DESCRICAO_TAREFA_F3 = (
    'O CEP {{lead.cep}} de {{lead.nome_razaosocial}} passou a ter viabilidade '
    'tecnica (a oportunidade estava perdida ha {{var.dias_perdida}} dias por falta '
    'de cobertura).\n'
    'Telefone: {{lead.telefone}}\n'
    '\n'
    'Planos disponiveis agora ({{nodes.viabilidade.total}}): {{nodes.viabilidade.planos}}\n'
    '\n'
    'Vale confirmar com o cliente se ainda tem interesse.'
)


def _grafo_f3():
    nodes = {
        'trigger': {
            'tipo': 'agenda',
            'config': {
                'intervalo_minutos': 1440,
                'varredura': 'oportunidades_perdidas',
                'varredura_config': {
                    'janela_dias_min': '15',
                    'motivo_ref_nome': 'Sem viabilidade técnica',
                    'sem_marcador': 'recuperacao_iniciada',
                    'exige_responsavel': 'true',
                },
                'max_por_rodada': 15,
                'max_por_lead': 1,
            },
            'pos': {'x': 0, 'y': 0},
            'label': 'Varredura: oportunidades perdidas (viabilidade)',
        },
        'viabilidade': {
            'tipo': 'hubsoft_planos_cep',
            'config': {'cep': '{{lead.cep}}'},
            'pos': {'x': 240, 'y': 0},
            'label': 'HubSoft: planos por CEP',
        },
        'tem_cobertura': {
            'tipo': 'if',
            'config': {
                'esquerda': '{{nodes.viabilidade.total}}',
                'operador': 'maior',
                'direita': '0',
            },
            'pos': {'x': 480, 'y': 0},
            'label': 'Tem cobertura agora?',
        },
        'tarefa': {
            'tipo': 'criar_tarefa',
            'config': _config_tarefa(
                'Agora tem cobertura: {{lead.nome_razaosocial}}', _DESCRICAO_TAREFA_F3,
            ),
            'pos': {'x': 720, 'y': 0},
            'label': 'Tarefa: retomar contato (cobertura nova)',
        },
        'marcador': {
            'tipo': 'definir_propriedade_oportunidade',
            'config': {'propriedade': 'marcador', 'chave': 'recuperacao_iniciada'},
            'pos': {'x': 960, 'y': 0},
            'label': 'Marcar recuperacao iniciada',
        },
        'nota': {
            'tipo': 'criar_nota',
            'config': {'texto': (
                'Tarefa de retomada criada para {{lead.nome_razaosocial}} '
                '(agora ha cobertura no CEP).'
            )},
            'pos': {'x': 1200, 'y': 0},
            'label': 'Nota: tarefa de retomada criada (cobertura nova)',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'viabilidade', 'saida': 'default'},
        {'de': 'viabilidade', 'para': 'tem_cobertura', 'saida': 'sucesso'},
        {'de': 'tem_cobertura', 'para': 'tarefa', 'saida': 'true'},
        {'de': 'tarefa', 'para': 'marcador', 'saida': 'sucesso'},
        {'de': 'marcador', 'para': 'nota', 'saida': 'sucesso'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


def _grafo_f4():
    nodes = {
        'trigger': {
            'tipo': 'evento',
            'config': {
                'evento': 'historico_contato',
                'filtros': [{'campo': 'var.status', 'operador': 'igual', 'valor': 'resposta'}],
                'max_por_lead': 1,
            },
            'pos': {'x': 0, 'y': 0},
            'label': 'Evento: historico de contato (resposta)',
        },
        'foi_recontatado': {
            'tipo': 'condicao_comercial',
            'config': {
                'tipo_condicao': 'oportunidade_dados_custom',
                'operador': 'existe',
                'campo': 'recuperacao_iniciada',
                'valor': '',
            },
            'pos': {'x': 240, 'y': 0},
            'label': 'Foi recontatado antes?',
        },
        'reabrir': {
            'tipo': 'reabrir_oportunidade',
            'config': {
                'estagio_slug': 'em-atendimento',
                'motivo': 'Lead respondeu ao recontato automatico',
            },
            'pos': {'x': 480, 'y': 0},
            'label': 'Reabrir oportunidade',
        },
        'nota': {
            'tipo': 'criar_nota',
            'config': {'texto': 'Lead respondeu ao recontato. Oportunidade reaberta automaticamente.'},
            'pos': {'x': 720, 'y': 0},
            'label': 'Nota: lead respondeu, reaberta',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'foi_recontatado', 'saida': 'default'},
        {'de': 'foi_recontatado', 'para': 'reabrir', 'saida': 'true'},
        {'de': 'reabrir', 'para': 'nota', 'saida': 'sucesso'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


class Command(BaseCommand):
    help = (
        'Seed dos fluxos das tarefas #180/#181 (recuperacao de oportunidades perdidas + '
        'analise de atendimentos Matrix). Idempotente por nome, tudo nasce INATIVO.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (obrigatório).')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant

        slug = (opts.get('tenant') or '').strip()
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' não encontrado.")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Seed fluxos recuperacao/analise, tenant: {tenant.slug}'))

        agente, agente_criado = self._upsert_agente(tenant)
        self.stdout.write(
            f'  {"criado" if agente_criado else "atualizado"}: agente "{agente.nome}" '
            f'(id={agente.pk}, ativo={agente.ativo})')

        grafos = {
            NOME_F1: (_grafo_f1(agente.pk), DESCRICAO_F1),
            NOME_F2: (_grafo_f2(), DESCRICAO_F2),
            NOME_F3: (_grafo_f3(), DESCRICAO_F3),
            NOME_F4: (_grafo_f4(), DESCRICAO_F4),
        }

        # Falha cedo: nenhum fluxo é escrito se algum grafo for estruturalmente inválido.
        for nome, (grafo, _descricao) in grafos.items():
            erros = validar_fluxo(grafo)
            if erros:
                raise CommandError(f'Grafo inválido para "{nome}": {"; ".join(erros)}')

        for nome, (grafo, descricao) in grafos.items():
            fluxo, criado = self._upsert_fluxo(tenant, nome, descricao, grafo)
            self.stdout.write(
                f'  {"criado" if criado else "atualizado"}: fluxo "{fluxo.nome}" '
                f'(id={fluxo.pk}, ativo={fluxo.ativo})')

        self.stdout.write(self.style.SUCCESS('Seed concluído. Tudo nasce INATIVO, revisar antes de ativar.'))

    def _upsert_agente(self, tenant):
        agente = Agente.all_tenants.filter(tenant=tenant, nome=NOME_AGENTE).first()
        criado = agente is None
        if agente is None:
            agente = Agente(tenant=tenant, nome=NOME_AGENTE, ativo=False)
        agente.equipe = 'comercial'
        agente.icone = 'bi-clipboard-data'
        agente.memoria = ''
        agente.tools = ['listar_motivos_perda']
        agente.integracao_ia = None
        agente.descricao = DESCRICAO_AGENTE
        agente.system_prompt = _system_prompt_agente(tenant)
        agente.save()
        return agente, criado

    def _upsert_fluxo(self, tenant, nome, descricao, grafo):
        fluxo = Fluxo.all_tenants.filter(tenant=tenant, nome=nome).first()
        criado = fluxo is None
        if fluxo is None:
            fluxo = Fluxo.all_tenants.create(
                tenant=tenant, nome=nome, descricao=descricao, grafo=grafo, ativo=False,
            )
            return fluxo, criado
        fluxo.descricao = descricao
        fluxo.grafo = grafo
        fluxo.save()  # `ativo` propositalmente intocado (nunca liga/desliga num re-run)
        return fluxo, criado
