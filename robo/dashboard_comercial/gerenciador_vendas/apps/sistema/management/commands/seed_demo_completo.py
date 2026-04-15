"""
Seed completo do tenant Demo ISP.
Popula todos os modulos com dados realistas de um provedor de internet.
Idempotente: verifica existencia antes de criar.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class Command(BaseCommand):
    help = 'Popula todos os modulos do tenant Demo ISP com dados realistas'

    def handle(self, *args, **options):
        from apps.sistema.models import Tenant, PerfilUsuario
        from apps.sistema.middleware import set_current_tenant
        from django.contrib.auth.models import User

        demo = Tenant.objects.filter(nome__icontains='demo').first()
        if not demo:
            self.stdout.write(self.style.WARNING('Tenant Demo nao encontrado.'))
            return

        set_current_tenant(demo)
        agora = timezone.now()

        # Pegar usuarios
        users = {}
        for pu in PerfilUsuario.objects.filter(tenant=demo).select_related('user'):
            users[pu.user.username] = pu.user
        if not users:
            self.stdout.write(self.style.WARNING('Nenhum usuario no Demo ISP.'))
            return

        admin = users.get('demo') or list(users.values())[0]
        vendedor1 = users.get('vendedor1', admin)
        vendedor2 = users.get('vendedor2', admin)
        suporte_user = users.get('suporte', admin)

        self._criar_planos(demo, agora)
        self._criar_produtos(demo, agora)
        self._criar_campanhas(demo, agora)
        self._criar_tags(demo)
        self._criar_segmentos(demo)
        self._criar_tarefas(demo, agora, vendedor1, vendedor2)
        self._criar_notas(demo, agora, vendedor1, vendedor2)
        self._criar_metas(demo, agora, vendedor1, vendedor2)
        self._criar_inbox(demo, agora, vendedor1, vendedor2, suporte_user)
        self._criar_tickets(demo, agora, suporte_user, admin)
        self._criar_base_conhecimento(demo, agora, admin)

        self.stdout.write(self.style.SUCCESS('Seed demo completo finalizado.'))

    def _criar_planos(self, demo, agora):
        from apps.comercial.cadastro.models import PlanoInternet, OpcaoVencimento
        if PlanoInternet.objects.filter(tenant=demo).count() >= 3:
            self.stdout.write('  Planos ja existem. Pulando.')
            return

        planos = [
            ('Internet 100 Mbps', 100, 10, Decimal('69.90'), 'economico', 1),
            ('Internet 200 Mbps', 200, 20, Decimal('89.90'), '', 2),
            ('Internet 400 Mbps', 400, 40, Decimal('99.90'), 'popular', 3),
            ('Internet 620 Mbps', 620, 62, Decimal('119.90'), '', 4),
            ('Internet 1 Gbps', 1000, 500, Decimal('149.90'), 'premium', 5),
        ]
        for nome, down, up, valor, destaque, ordem in planos:
            PlanoInternet.objects.create(
                tenant=demo, nome=nome,
                descricao=f'Plano fibra optica {down}Mbps',
                velocidade_download=down, velocidade_upload=up,
                valor_mensal=valor, destaque=destaque,
                ativo=True, ordem_exibicao=ordem,
            )

        for dia in [5, 10, 20]:
            OpcaoVencimento.objects.get_or_create(
                tenant=demo, dia_vencimento=dia,
                defaults={'descricao': f'Dia {dia}'},
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(planos)} planos criados.'))

    def _criar_produtos(self, demo, agora):
        from apps.comercial.crm.models import ProdutoServico
        if ProdutoServico.objects.filter(tenant=demo).count() >= 3:
            self.stdout.write('  Produtos ja existem. Pulando.')
            return

        produtos = [
            ('Plano 100 Mbps', 'PLN-100', Decimal('69.90'), 'plano', 'mensal'),
            ('Plano 200 Mbps', 'PLN-200', Decimal('89.90'), 'plano', 'mensal'),
            ('Plano 400 Mbps', 'PLN-400', Decimal('99.90'), 'plano', 'mensal'),
            ('Plano 620 Mbps', 'PLN-620', Decimal('119.90'), 'plano', 'mensal'),
            ('Plano 1 Gbps', 'PLN-1G', Decimal('149.90'), 'plano', 'mensal'),
            ('Instalacao Padrao', 'SRV-INST', Decimal('0.00'), 'servico', 'avulso'),
            ('Roteador Wi-Fi 6', 'EQP-WIFI6', Decimal('199.90'), 'equipamento', 'avulso'),
            ('IP Fixo', 'ADD-IPFX', Decimal('29.90'), 'addon', 'mensal'),
        ]
        for nome, codigo, preco, cat, rec in produtos:
            ProdutoServico.objects.get_or_create(
                tenant=demo, codigo=codigo,
                defaults={'nome': nome, 'preco': preco, 'categoria': cat, 'recorrencia': rec, 'ativo': True},
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(produtos)} produtos criados.'))

    def _criar_campanhas(self, demo, agora):
        from apps.marketing.campanhas.models import CampanhaTrafego
        if CampanhaTrafego.objects.filter(tenant=demo).count() >= 3:
            self.stdout.write('  Campanhas ja existem. Pulando.')
            return

        campanhas = [
            ('Google Ads - Fibra Optica', 'google_fibra', 'fibra optica', 'google_ads', Decimal('2000'), 50, 37),
            ('Facebook - Internet Rapida', 'fb_internet', 'internet rapida', 'facebook_ads', Decimal('1500'), 40, 28),
            ('Instagram - Promo Mega', 'ig_promo', 'mega plano', 'instagram_ads', Decimal('800'), 25, 18),
            ('Email - Upgrade de Plano', 'email_upgrade', 'upgrade', 'email', Decimal('0'), 30, 22),
            ('Indicacao Amigo', 'indicacao', 'codigo amigo', 'outro', Decimal('0'), 20, 15),
        ]
        for nome, codigo, palavra, plat, orcamento, meta, realizados in campanhas:
            CampanhaTrafego.objects.create(
                tenant=demo, nome=nome, codigo=codigo,
                palavra_chave=palavra, plataforma=plat,
                ativa=True, data_inicio=agora - timedelta(days=30),
                orcamento=orcamento, meta_leads=meta,
                contador_deteccoes=realizados,
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(campanhas)} campanhas criadas.'))

    def _criar_tags(self, demo):
        from apps.comercial.crm.models import TagCRM
        if TagCRM.objects.filter(tenant=demo).count() >= 3:
            self.stdout.write('  Tags ja existem. Pulando.')
            return

        cores = ['#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6', '#06b6d4', '#6b7280']
        tags = ['Alto Potencial', 'Precisa Follow-up', 'Campanha Google',
                'Indicacao', 'Corporativo', 'Residencial', 'Sem Interesse']
        for i, t in enumerate(tags):
            TagCRM.objects.get_or_create(tenant=demo, nome=t, defaults={'cor_hex': cores[i % len(cores)]})
        self.stdout.write(self.style.SUCCESS(f'  {len(tags)} tags criadas.'))

    def _criar_segmentos(self, demo):
        from apps.comercial.crm.models import SegmentoCRM
        if SegmentoCRM.objects.filter(tenant=demo).count() >= 2:
            self.stdout.write('  Segmentos ja existem. Pulando.')
            return

        segmentos = [
            ('Leads Quentes', 'dinamico', 'score_qualificacao >= 7'),
            ('Sem Contato 30 dias', 'dinamico', 'ultimo_contato > 30 dias'),
            ('Campanha Google Ads', 'manual', ''),
        ]
        for nome, tipo, desc in segmentos:
            SegmentoCRM.objects.create(
                tenant=demo, nome=nome, tipo=tipo, ativo=True,
                descricao=desc,
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(segmentos)} segmentos criados.'))

    def _criar_tarefas(self, demo, agora, vendedor1, vendedor2):
        from apps.comercial.crm.models import TarefaCRM, OportunidadeVenda
        if TarefaCRM.objects.filter(tenant=demo).count() >= 5:
            self.stdout.write('  Tarefas ja existem. Pulando.')
            return

        oportunidades = list(OportunidadeVenda.objects.filter(tenant=demo)[:8])

        tarefas = [
            ('Ligar para confirmar interesse', 'ligacao', 'pendente', 'alta', vendedor1, 1, 0),
            ('Enviar proposta por email', 'email', 'pendente', 'normal', vendedor2, 2, 1),
            ('Follow-up WhatsApp', 'whatsapp', 'em_andamento', 'normal', vendedor1, 0, 2),
            ('Agendar visita tecnica', 'visita', 'pendente', 'alta', vendedor2, 3, 3),
            ('Preparar proposta corporativa', 'proposta', 'pendente', 'alta', vendedor1, 2, 4),
            ('Retorno sobre plano 620Mb', 'followup', 'pendente', 'normal', vendedor1, 1, 5),
            ('Enviar contrato por email', 'email', 'concluida', 'normal', vendedor2, -2, 6),
            ('Ligar para oferecer upgrade', 'ligacao', 'pendente', 'normal', vendedor2, 3, 7),
            ('Follow-up pos instalacao', 'followup', 'pendente', 'baixa', vendedor1, 5, 0),
            ('Confirmar documentacao', 'email', 'em_andamento', 'alta', vendedor2, 0, 1),
            ('Agendar instalacao', 'instalacao', 'pendente', 'alta', vendedor1, 2, 2),
            ('Retorno sobre cancelamento', 'ligacao', 'pendente', 'urgente', vendedor1, 0, 3),
        ]
        for titulo, tipo, status, prio, resp, dias, oport_idx in tarefas:
            oport = oportunidades[oport_idx % len(oportunidades)] if oportunidades else None
            TarefaCRM.objects.create(
                tenant=demo, responsavel=resp, titulo=titulo,
                tipo=tipo, status=status, prioridade=prio,
                oportunidade=oport,
                lead=oport.lead if oport else None,
                data_vencimento=agora + timedelta(days=dias),
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(tarefas)} tarefas criadas.'))

    def _criar_notas(self, demo, agora, vendedor1, vendedor2):
        from apps.comercial.crm.models import NotaInterna, OportunidadeVenda
        if NotaInterna.objects.filter(tenant=demo).count() >= 5:
            self.stdout.write('  Notas ja existem. Pulando.')
            return

        oportunidades = list(OportunidadeVenda.objects.filter(tenant=demo)[:6])

        notas = [
            ('Cliente demonstrou interesse no plano 620Mb. Pediu para ligar amanha.', 'ligacao', vendedor1, 0),
            ('Enviada proposta por email. Aguardando retorno.', 'email', vendedor2, 1),
            ('Cliente comparou com concorrente. Ofereci desconto de fidelidade.', 'reuniao', vendedor1, 2),
            ('Documentacao validada. Aguardando agendamento de instalacao.', 'geral', vendedor2, 3),
            ('Cliente quer upgrade para 1Gb. Agendar troca de equipamento.', 'importante', vendedor1, 4),
            ('Reclamacao sobre velocidade. Aberto chamado no suporte.', 'alerta', vendedor2, 5),
            ('Follow-up realizado. Cliente confirmou fechamento para sexta.', 'ligacao', vendedor1, 0),
            ('Reuniao com sindico do condominio. 20 unidades interessadas.', 'reuniao', vendedor2, 1),
        ]
        for conteudo, tipo, autor, oport_idx in notas:
            oport = oportunidades[oport_idx % len(oportunidades)] if oportunidades else None
            NotaInterna.objects.create(
                tenant=demo, autor=autor, conteudo=conteudo,
                tipo=tipo, oportunidade=oport,
                lead=oport.lead if oport else None,
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(notas)} notas criadas.'))

    def _criar_metas(self, demo, agora, vendedor1, vendedor2):
        from apps.comercial.crm.models import MetaVendas
        if MetaVendas.objects.filter(tenant=demo).count() >= 2:
            self.stdout.write('  Metas ja existem. Pulando.')
            return

        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

        MetaVendas.objects.create(
            tenant=demo, tipo='equipe', periodo='mensal',
            data_inicio=inicio_mes, data_fim=fim_mes,
            meta_vendas_quantidade=15, meta_vendas_valor=Decimal('8000'),
            meta_leads_qualificados=30,
            realizado_vendas_quantidade=9, realizado_vendas_valor=Decimal('4850'),
            realizado_leads=22,
        )
        MetaVendas.objects.create(
            tenant=demo, tipo='individual', periodo='mensal',
            data_inicio=inicio_mes, data_fim=fim_mes,
            vendedor=vendedor1,
            meta_vendas_quantidade=8, meta_vendas_valor=Decimal('4000'),
            meta_leads_qualificados=15,
            realizado_vendas_quantidade=5, realizado_vendas_valor=Decimal('2650'),
            realizado_leads=12,
        )
        MetaVendas.objects.create(
            tenant=demo, tipo='individual', periodo='mensal',
            data_inicio=inicio_mes, data_fim=fim_mes,
            vendedor=vendedor2,
            meta_vendas_quantidade=7, meta_vendas_valor=Decimal('4000'),
            meta_leads_qualificados=15,
            realizado_vendas_quantidade=4, realizado_vendas_valor=Decimal('2200'),
            realizado_leads=10,
        )
        self.stdout.write(self.style.SUCCESS('  3 metas criadas.'))

    def _criar_inbox(self, demo, agora, vendedor1, vendedor2, suporte_user):
        from apps.inbox.models import (
            CanalInbox, Conversa, Mensagem,
            EtiquetaConversa, RespostaRapida,
        )
        if Conversa.objects.filter(tenant=demo).count() >= 8:
            self.stdout.write('  Conversas inbox ja existem. Pulando.')
            return

        # Etiquetas
        for nome, cor in [('Vendas', '#3b82f6'), ('Suporte', '#ef4444'), ('Duvida', '#f59e0b'), ('Urgente', '#dc2626')]:
            EtiquetaConversa.objects.get_or_create(tenant=demo, nome=nome, defaults={'cor_hex': cor})

        # Respostas rapidas
        rapidas = [
            ('/saudacao', 'Saudacao', 'Ola! Bem-vindo a Demo ISP. Como posso ajudar?'),
            ('/horario', 'Horario', 'Nosso horario de atendimento e de segunda a sexta, das 8h as 18h.'),
            ('/planos', 'Planos', 'Temos planos de 100Mb (R$69,90), 200Mb (R$89,90), 400Mb (R$99,90), 620Mb (R$119,90) e 1Gb (R$149,90).'),
            ('/instalacao', 'Instalacao', 'A instalacao e gratuita e leva em media 3 dias uteis apos a aprovacao cadastral.'),
        ]
        for atalho, titulo, conteudo in rapidas:
            RespostaRapida.objects.get_or_create(
                tenant=demo, atalho=atalho,
                defaults={'titulo': titulo, 'conteudo': conteudo, 'criado_por': vendedor1},
            )

        # Canal
        canal = CanalInbox.objects.filter(tenant=demo, tipo='whatsapp').first()
        if not canal:
            canal = CanalInbox.objects.create(
                tenant=demo, tipo='whatsapp', nome='WhatsApp Vendas',
                provedor='uazapi', ativo=True,
            )

        # Conversas
        conversas_data = [
            ('Roberto Nascimento', '5589991234567', 'aberta', 'bot', vendedor1, [
                ('contato', 'Oi, quero saber sobre os planos de internet'),
                ('bot', 'Ola Roberto! Temos planos de 100Mb a 1Gb. Qual velocidade voce precisa?'),
                ('contato', 'Quanto custa o de 400 megas?'),
                ('bot', 'O plano 400Mb custa R$ 99,90/mes com instalacao gratuita!'),
            ]),
            ('Fernanda Costa', '5589992345678', 'aberta', 'humano', vendedor2, [
                ('contato', 'Boa tarde, minha internet esta muito lenta'),
                ('agente', 'Ola Fernanda! Vou verificar sua conexao. Pode me passar seu CPF?'),
                ('contato', '123.456.789-00'),
                ('agente', 'Identifiquei uma instabilidade. Vou reiniciar sua porta remotamente.'),
                ('contato', 'Ok, obrigada'),
            ]),
            ('Marcos Oliveira', '5589993456789', 'pendente', 'bot', None, [
                ('contato', 'Quero cancelar meu plano'),
                ('bot', 'Ola Marcos! Antes de cancelar, posso oferecer uma condicao especial?'),
            ]),
            ('Patricia Almeida', '5589994567890', 'resolvida', 'humano', vendedor1, [
                ('contato', 'Quando vao instalar minha internet?'),
                ('agente', 'Ola Patricia! Sua instalacao esta agendada para amanha entre 14h e 17h.'),
                ('contato', 'Perfeito, obrigada!'),
                ('agente', 'Por nada! Qualquer duvida, estamos a disposicao.'),
            ]),
            ('Empresa Tech Solutions', '5589995678901', 'aberta', 'humano', vendedor2, [
                ('contato', 'Preciso de um link dedicado para minha empresa'),
                ('agente', 'Ola! Temos links dedicados a partir de R$ 399/mes. Quantos funcionarios usam internet?'),
                ('contato', 'Somos 15 pessoas'),
                ('agente', 'Recomendo o link de 100Mb dedicado por R$ 599/mes. Posso agendar uma visita tecnica?'),
            ]),
            ('Ana Julia Santos', '5589996789012', 'resolvida', 'bot', vendedor1, [
                ('contato', 'Quero o plano de 620 megas'),
                ('bot', 'Otimo escolha! Vou precisar de alguns dados para o cadastro. Qual seu nome completo?'),
                ('contato', 'Ana Julia Santos'),
                ('bot', 'E seu CPF?'),
                ('contato', '987.654.321-00'),
                ('bot', 'Cadastro realizado! Instalacao em ate 3 dias uteis.'),
            ]),
            ('Joao Batista Lima', '5589997890123', 'aberta', 'bot', None, [
                ('contato', 'Boa noite'),
                ('bot', 'Ola! Sou o assistente virtual da Demo ISP. Como posso ajudar?'),
            ]),
            ('Carla Mendes', '5589998901234', 'pendente', 'humano', suporte_user, [
                ('contato', 'Minha internet caiu e nao volta'),
                ('agente', 'Ola Carla! Vou verificar. Sua regiao esta com manutencao programada ate as 22h.'),
                ('contato', 'Puxa, mas ninguem avisou'),
                ('agente', 'Peco desculpas. Vou registrar para melhorarmos a comunicacao.'),
            ]),
        ]

        numero = Conversa.objects.filter(tenant=demo).count()
        for nome, tel, status, modo, agente, msgs in conversas_data:
            numero += 1
            conv = Conversa(
                tenant=demo, numero=numero, canal=canal,
                contato_nome=nome, contato_telefone=tel,
                status=status, modo_atendimento=modo,
                agente=agente,
            )
            conv._skip_automacao = True
            conv.save()

            ultima_msg = None
            for j, (tipo, texto) in enumerate(msgs):
                msg = Mensagem(
                    tenant=demo, conversa=conv,
                    remetente_tipo=tipo,
                    remetente_nome=nome if tipo == 'contato' else ('Demo ISP' if tipo == 'bot' else agente.get_full_name() if agente else 'Agente'),
                    tipo_conteudo='texto', conteudo=texto,
                )
                msg._skip_automacao = True
                msg.save()
                ultima_msg = msg

            if ultima_msg:
                conv.ultima_mensagem_em = ultima_msg.data_envio
                conv.ultima_mensagem_preview = msgs[-1][1][:255]
                conv.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])

        self.stdout.write(self.style.SUCCESS(f'  {len(conversas_data)} conversas inbox criadas.'))

    def _criar_tickets(self, demo, agora, suporte_user, admin):
        from apps.suporte.models import Ticket, CategoriaTicket, ComentarioTicket
        if Ticket.objects.filter(tenant=demo).count() >= 5:
            self.stdout.write('  Tickets ja existem. Pulando.')
            return

        # Categorias
        from django.utils.text import slugify
        categorias = {}
        cat_data = [
            ('Problema de Conexao', 'problema-conexao'),
            ('Cobranca', 'cobranca'),
            ('Instalacao', 'instalacao'),
            ('Upgrade/Downgrade', 'upgrade-downgrade'),
            ('Cancelamento', 'cancelamento'),
        ]
        for nome, slug in cat_data:
            cat, _ = CategoriaTicket.objects.get_or_create(
                tenant=demo, slug=slug,
                defaults={'nome': nome},
            )
            categorias[nome] = cat

        tickets_data = [
            ('Internet caindo toda noite', 'Minha internet cai todos os dias por volta das 22h.', 'Problema de Conexao', 'aberto', 'alta', suporte_user, 0),
            ('Cobranca indevida na fatura', 'Estou sendo cobrado por um servico que nao contratei.', 'Cobranca', 'em_andamento', 'normal', suporte_user, 2),
            ('Atraso na instalacao', 'Ja fazem 5 dias e a instalacao nao foi feita.', 'Instalacao', 'aberto', 'urgente', suporte_user, 1),
            ('Quero fazer upgrade para 1Gb', 'Gostaria de trocar meu plano de 400Mb para 1Gb.', 'Upgrade/Downgrade', 'resolvido', 'normal', suporte_user, 5),
            ('Velocidade abaixo do contratado', 'Contratei 620Mb mas so chega 200Mb.', 'Problema de Conexao', 'em_andamento', 'alta', suporte_user, 3),
            ('Pedido de cancelamento', 'Quero cancelar pois estou mudando de cidade.', 'Cancelamento', 'aguardando_cliente', 'normal', suporte_user, 4),
            ('Roteador nao funciona', 'O roteador que instalaram nao liga mais.', 'Problema de Conexao', 'aberto', 'alta', suporte_user, 0),
            ('Segunda via de boleto', 'Perdi o boleto e preciso de uma segunda via.', 'Cobranca', 'resolvido', 'baixa', suporte_user, 7),
        ]

        numero = Ticket.objects.filter(tenant=demo).count()
        for titulo, desc, cat_nome, status, prio, atendente, dias in tickets_data:
            numero += 1
            ticket = Ticket.objects.create(
                tenant=demo, numero=numero, titulo=titulo,
                descricao=desc, status=status, prioridade=prio,
                categoria=categorias.get(cat_nome),
                solicitante=admin, atendente=atendente,
            )
            # Comentarios
            if status in ('em_andamento', 'resolvido'):
                ComentarioTicket.objects.create(
                    tenant=demo, ticket=ticket, autor=atendente,
                    mensagem='Verificando o problema. Vou entrar em contato com a equipe tecnica.',
                )
            if status == 'resolvido':
                ComentarioTicket.objects.create(
                    tenant=demo, ticket=ticket, autor=atendente,
                    mensagem='Problema resolvido. Caso persista, favor reabrir o chamado.',
                )

        self.stdout.write(self.style.SUCCESS(f'  {len(tickets_data)} tickets criados.'))

    def _criar_base_conhecimento(self, demo, agora, admin):
        from apps.suporte.models import CategoriaConhecimento, ArtigoConhecimento
        if ArtigoConhecimento.objects.filter(tenant=demo).count() >= 3:
            self.stdout.write('  Base de conhecimento ja existe. Pulando.')
            return

        cat_inst, _ = CategoriaConhecimento.objects.get_or_create(
            tenant=demo, slug='instalacao-configuracao',
            defaults={'nome': 'Instalacao e Configuracao', 'descricao': 'Artigos sobre instalacao e configuracao de internet'},
        )
        cat_prob, _ = CategoriaConhecimento.objects.get_or_create(
            tenant=demo, slug='problemas-comuns',
            defaults={'nome': 'Problemas Comuns', 'descricao': 'Solucoes para problemas frequentes'},
        )
        cat_plan, _ = CategoriaConhecimento.objects.get_or_create(
            tenant=demo, slug='planos-servicos',
            defaults={'nome': 'Planos e Servicos', 'descricao': 'Informacoes sobre planos e servicos'},
        )

        from django.utils.text import slugify
        artigos = [
            (cat_inst, 'Como configurar o roteador Wi-Fi', 'configurar-roteador',
             '1. Conecte o cabo de rede na porta WAN do roteador\n2. Acesse 192.168.0.1 no navegador\n3. Faca login com admin/admin\n4. Configure o nome da rede (SSID) e senha\n5. Salve e reinicie o roteador'),
            (cat_inst, 'Preparacao para instalacao', 'preparacao-instalacao',
             'Antes da visita do tecnico:\n- Tenha um ponto de energia proximo ao local de instalacao\n- Deixe o local acessivel\n- Tenha um documento com foto em maos\n- A instalacao leva em media 1 hora'),
            (cat_prob, 'Internet lenta: o que fazer', 'internet-lenta',
             'Passos para resolver lentidao:\n1. Reinicie o roteador (desligue, espere 30s, ligue)\n2. Teste com cabo de rede direto\n3. Verifique quantos dispositivos estao conectados\n4. Faca um teste de velocidade em speedtest.net\n5. Se persistir, abra um chamado'),
            (cat_prob, 'Sem conexao com a internet', 'sem-conexao',
             'Verifique:\n1. Se o roteador esta ligado (luzes acesas)\n2. Se o cabo de fibra esta conectado\n3. Reinicie o equipamento\n4. Se a luz PON estiver vermelha, ha problema na fibra\n5. Ligue para nosso suporte: 0800-123-4567'),
            (cat_plan, 'Comparativo de planos', 'comparativo-planos',
             'Nossos planos:\n- 100Mb: ideal para 1-2 pessoas, uso basico (R$ 69,90)\n- 200Mb: bom para familias pequenas (R$ 89,90)\n- 400Mb: recomendado para home office (R$ 99,90)\n- 620Mb: ideal para streaming 4K e jogos (R$ 119,90)\n- 1Gb: para uso intenso e empresas (R$ 149,90)'),
            (cat_plan, 'Como solicitar upgrade de plano', 'solicitar-upgrade',
             'Para fazer upgrade:\n1. Acesse nosso WhatsApp ou ligue\n2. Informe seu CPF e plano desejado\n3. A alteracao e feita em ate 30 minutos\n4. Nao ha custo de mudanca\n5. A nova velocidade ja vale no proximo ciclo'),
        ]
        for cat, titulo, slug, conteudo in artigos:
            ArtigoConhecimento.objects.get_or_create(
                tenant=demo, slug=slug,
                defaults={'categoria': cat, 'titulo': titulo, 'conteudo': conteudo, 'autor': admin, 'publicado': True},
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(artigos)} artigos de conhecimento criados.'))
