"""
Popula dados de teste no Inbox.
Uso: python manage.py seed_inbox --settings=gerenciador_vendas.settings_local
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.sistema.models import Tenant
from apps.comercial.leads.models import LeadProspecto
from apps.inbox.models import (
    CanalInbox, EtiquetaConversa, Conversa, Mensagem, RespostaRapida,
)


class Command(BaseCommand):
    help = "Cria conversas, mensagens e respostas rapidas de teste no Inbox."

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='megalink', help='Slug do tenant (default: megalink)')

    def handle(self, *args, **options):
        slug = options['tenant']
        tenant = Tenant.objects.filter(slug=slug).first()
        if not tenant:
            self.stderr.write(f"Tenant '{slug}' nao encontrado.")
            return

        # Pegar os 2 primeiros usuarios com perfil neste tenant
        from apps.sistema.models import PerfilUsuario
        perfis = PerfilUsuario.objects.filter(tenant=tenant).select_related('user').order_by('user__id')[:2]
        agente1 = perfis[0].user if len(perfis) > 0 else None
        agente2 = perfis[1].user if len(perfis) > 1 else agente1
        now = timezone.now()

        # ── Canais ──────────────────────────────────────────────────
        canal_wpp, _ = CanalInbox.all_tenants.get_or_create(
            tenant=tenant, tipo='whatsapp',
            defaults={'nome': 'WhatsApp'}
        )
        CanalInbox.all_tenants.get_or_create(
            tenant=tenant, tipo='interno',
            defaults={'nome': 'Chat Interno'}
        )
        self.stdout.write("  Canais OK")

        # ── Etiquetas ───────────────────────────────────────────────
        cores = {
            'Urgente': '#ef4444',
            'VIP': '#f59e0b',
            'Novo Lead': '#22c55e',
            'Suporte': '#3b82f6',
            'Financeiro': '#8b5cf6',
        }
        etiquetas = {}
        for nome, cor in cores.items():
            e, _ = EtiquetaConversa.all_tenants.get_or_create(
                tenant=tenant, nome=nome, defaults={'cor_hex': cor}
            )
            etiquetas[nome] = e
        self.stdout.write("  Etiquetas OK")

        # ── Respostas Rapidas ───────────────────────────────────────
        respostas = [
            ('Saudacao', '/ola',
             'Ola! Obrigado por entrar em contato com a Megalink. Como posso ajudar?', 'geral'),
            ('Planos disponiveis', '/planos',
             'Temos planos a partir de R$79,90/mes com fibra optica. Qual sua regiao?', 'vendas'),
            ('Horario', '/horario',
             'Nosso atendimento funciona de segunda a sexta, das 8h as 18h, e sabado das 8h as 12h.', 'geral'),
            ('Aguarde', '/aguarde',
             'Um momento, por favor. Estou verificando as informacoes para voce.', 'geral'),
            ('Encerramento', '/tchau',
             'Obrigado pelo contato! Se precisar de mais alguma coisa, estamos a disposicao.', 'geral'),
        ]
        for titulo, atalho, conteudo, cat in respostas:
            RespostaRapida.all_tenants.get_or_create(
                tenant=tenant, atalho=atalho,
                defaults={'titulo': titulo, 'conteudo': conteudo, 'categoria': cat, 'criado_por': agente1}
            )
        self.stdout.write("  Respostas rapidas OK")

        # ── Conversas ───────────────────────────────────────────────
        leads = list(LeadProspecto.all_tenants.filter(tenant=tenant).order_by('-id')[:8])

        def lead_or(idx, fallback_nome, fallback_tel):
            if idx < len(leads):
                return leads[idx], leads[idx].nome_razaosocial, leads[idx].telefone
            return None, fallback_nome, fallback_tel

        conversas_spec = [
            # (lead_idx, fallback_nome, fallback_tel, status, agente, etiquetas, mensagens)
            {
                'lead_idx': 0, 'fn': 'Carlos Mendes', 'ft': '86999001001',
                'status': 'aberta', 'agente': agente1, 'tags': ['Novo Lead'],
                'msgs': [
                    ('contato', 'Boa tarde! Estou interessado em contratar internet fibra pra minha casa.', -45),
                    ('contato', 'Voces atendem no bairro Ininga?', -44),
                    ('agente', 'Ola! Obrigado pelo contato. Sim, temos cobertura no Ininga. Planos a partir de R$79,90.', -40),
                    ('contato', 'Que legal! Quais planos voces tem?', -35),
                    ('agente', 'Temos: Fibra 200MB R$79,90, Fibra 400MB R$99,90, Fibra 600MB R$129,90. Todos com Wi-Fi 6.', -30),
                    ('contato', 'Hmm, o de 400MB me interessa. Como faco pra contratar?', -5),
                ],
            },
            {
                'lead_idx': 1, 'fn': 'Ana Paula', 'ft': '86999002002',
                'status': 'aberta', 'agente': None, 'tags': ['Urgente'],
                'msgs': [
                    ('contato', 'Oi, minha internet caiu desde ontem e nao voltou mais', -15),
                    ('contato', 'Numero do contrato eh 45892', -14),
                    ('contato', 'Alguem pode me ajudar???', -3),
                ],
            },
            {
                'lead_idx': 2, 'fn': 'Roberto Filho', 'ft': '86999003003',
                'status': 'aberta', 'agente': agente2, 'tags': ['Financeiro'],
                'msgs': [
                    ('contato', 'Bom dia! Recebi uma cobranca em duplicidade no meu cartao esse mes.', -120),
                    ('agente', 'Bom dia Roberto! Vou verificar. Pode me informar o CPF cadastrado?', -110),
                    ('contato', '123.456.789-00', -105),
                    ('agente', 'Confirmado, houve cobranca duplicada. Ja solicitei o estorno, cai em ate 5 dias uteis.', -100),
                    ('contato', 'Perfeito, obrigado pela rapidez!', -95),
                ],
            },
            {
                'lead_idx': 3, 'fn': 'Fernanda Lima', 'ft': '86999004004',
                'status': 'pendente', 'agente': agente1, 'tags': [],
                'msgs': [
                    ('contato', 'Ola, gostaria de fazer upgrade do meu plano de 200MB para 600MB', -240),
                    ('agente', 'Oi Fernanda! O upgrade eh sem fidelidade e sem custo de instalacao.', -235),
                    ('contato', 'Otimo! Pode fazer a mudanca entao', -230),
                    ('agente', 'Preciso confirmar alguns dados. Pode enviar foto do RG frente e verso?', -225),
                    ('contato', 'Vou enviar assim que chegar em casa', -220),
                ],
            },
            {
                'lead_idx': 4, 'fn': 'Marcos Souza', 'ft': '86999005005',
                'status': 'resolvida', 'agente': agente1, 'tags': [],
                'msgs': [
                    ('contato', 'Boa noite, preciso da segunda via do boleto', -1440),
                    ('agente', 'Boa noite Marcos! Segue o link: https://megalink.com.br/boleto/98234', -1435),
                    ('contato', 'Recebi, muito obrigado!', -1430),
                    ('sistema', 'Conversa resolvida por Darlan Oliveira', -1429),
                ],
            },
            {
                'lead_idx': 5, 'fn': 'Juliana Alves', 'ft': '86999006006',
                'status': 'aberta', 'agente': None, 'tags': ['Novo Lead'],
                'msgs': [
                    ('contato', 'Oi, vi o anuncio de voces no Instagram. Quanto eh o plano de 400MB?', -8),
                ],
            },
            {
                'lead_idx': 6, 'fn': 'Pedro Henrique', 'ft': '86999007007',
                'status': 'aberta', 'agente': agente2, 'tags': ['Urgente'],
                'msgs': [
                    ('contato', 'A internet ta muito lenta, dando 20MB no teste e meu plano eh de 400MB', -25),
                    ('agente', 'Oi Pedro, pode reiniciar o roteador desligando da tomada por 30s?', -20),
                    ('contato', 'Fiz aqui, continua lento', -18),
                    ('agente', 'Identifiquei instabilidade na sua regiao. Equipe tecnica atuando. Previsao: 2h.', -15),
                    ('contato', 'Ok, obrigado por avisar', -12),
                ],
            },
        ]

        for spec in conversas_spec:
            lead, nome, tel = lead_or(spec['lead_idx'], spec['fn'], spec['ft'])

            c = Conversa(
                tenant=tenant,
                canal=canal_wpp,
                lead=lead,
                contato_nome=nome,
                contato_telefone=tel,
                status=spec['status'],
                agente=spec['agente'],
            )
            c._skip_automacao = True
            c.save()

            for rtype, texto, delta in spec['msgs']:
                agente = spec['agente']
                if rtype == 'agente' and agente:
                    rname = agente.get_full_name()
                elif rtype == 'contato':
                    rname = nome
                else:
                    rname = 'Sistema'

                m = Mensagem(
                    tenant=tenant,
                    conversa=c,
                    remetente_tipo=rtype,
                    remetente_nome=rname,
                    remetente_user=agente if rtype == 'agente' else None,
                    tipo_conteudo='sistema' if rtype == 'sistema' else 'texto',
                    conteudo=texto,
                    data_envio=now + timedelta(minutes=delta),
                    lida=(rtype != 'contato' or spec['status'] == 'resolvida'),
                )
                m._skip_automacao = True
                m.save()

            # Atualizar conversa
            ultima = c.mensagens.order_by('-data_envio').first()
            nao_lidas = c.mensagens.filter(lida=False, remetente_tipo='contato').count()
            c.ultima_mensagem_em = ultima.data_envio if ultima else now
            c.ultima_mensagem_preview = (ultima.conteudo[:255] if ultima else '')
            c.mensagens_nao_lidas = nao_lidas
            if spec['status'] == 'resolvida':
                c.data_resolucao = now + timedelta(minutes=-1429)
            c.save()

            # Etiquetas
            for tag in spec['tags']:
                if tag in etiquetas:
                    c.etiquetas.add(etiquetas[tag])

            self.stdout.write(
                f"  #{c.numero} {nome} ({spec['status']}) "
                f"- {c.mensagens.count()} msgs"
                + (f" [{', '.join(spec['tags'])}]" if spec['tags'] else "")
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nSeed completo! "
            f"{Conversa.all_tenants.filter(tenant=tenant).count()} conversas, "
            f"{Mensagem.all_tenants.filter(tenant=tenant).count()} mensagens"
        ))
