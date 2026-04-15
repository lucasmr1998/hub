"""
Seed de dados demo para pagina de Vendas (ClienteHubsoft + ServicoClienteHubsoft).
Simula clientes de um provedor de internet com planos, status e documentacao.
Idempotente: so cria se nao existir dados no tenant Demo ISP.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random


CLIENTES = [
    {
        'nome': 'FABIOLA PEREIRA ALMEIDA',
        'cpf': '099.307.343-33',
        'telefone': '(89) 98114-6166',
        'email': 'almeidafabiola090@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 1,
    },
    {
        'nome': 'JAKELINE DA SILVA PESSOA',
        'cpf': '021.735.623-04',
        'telefone': '(89) 98541-4073',
        'email': 'jakelinedasilvapessoapes@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 2,
    },
    {
        'nome': 'LEILIANE RODRIGUES',
        'cpf': '961.440.503-10',
        'telefone': '(89) 98126-0426',
        'email': 'rodrigues.leiliane@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 3,
    },
    {
        'nome': 'ENIVAN MARIANO DA SILVA FILHO',
        'cpf': '087.479.523-00',
        'telefone': '(89) 99974-0494',
        'email': 'marianoenivan8@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 2,
    },
    {
        'nome': 'CARLOS EDUARDO SANTOS',
        'cpf': '123.456.789-01',
        'telefone': '(89) 99812-3456',
        'email': 'carlos.santos@hotmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 10,
    },
    {
        'nome': 'MARIA JOSE DE OLIVEIRA',
        'cpf': '234.567.890-12',
        'telefone': '(89) 98765-4321',
        'email': 'maria.oliveira@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 200MB',
        'valor': Decimal('59.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 15,
    },
    {
        'nome': 'JOAO PEDRO ALVES COSTA',
        'cpf': '345.678.901-23',
        'telefone': '(89) 99654-3210',
        'email': 'jpedro.costa@outlook.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 7,
    },
    {
        'nome': 'ANA PAULA FERREIRA LIMA',
        'cpf': '456.789.012-34',
        'telefone': '(89) 98543-2109',
        'email': 'anapaula.lima@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 0,
    },
    {
        'nome': 'FRANCISCO DAS CHAGAS SOUSA',
        'cpf': '567.890.123-45',
        'telefone': '(89) 99432-1098',
        'email': 'chagas.sousa@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 1GB',
        'valor': Decimal('139.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 20,
    },
    {
        'nome': 'RAIMUNDA NONATA SILVA',
        'cpf': '678.901.234-56',
        'telefone': '(89) 98321-0987',
        'email': 'raimunda.silva@hotmail.com',
        'plano': '[VAREJO] MEGA PLANO 200MB',
        'valor': Decimal('59.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 25,
    },
    {
        'nome': 'PEDRO HENRIQUE ARAUJO',
        'cpf': '789.012.345-67',
        'telefone': '(89) 99210-9876',
        'email': 'pedro.araujo@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 1,
    },
    {
        'nome': 'ANTONIA MARIA NASCIMENTO',
        'cpf': '890.123.456-78',
        'telefone': '(89) 98109-8765',
        'email': 'antonia.nasc@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 12,
    },
    {
        'nome': 'LUCAS GABRIEL MENDES',
        'cpf': '901.234.567-89',
        'telefone': '(89) 99098-7654',
        'email': 'lucas.mendes@outlook.com',
        'plano': '[VAREJO] MEGA PLANO 1GB',
        'valor': Decimal('139.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 5,
    },
    {
        'nome': 'FRANCISCA SOUZA RIBEIRO',
        'cpf': '012.345.678-90',
        'telefone': '(89) 98987-6543',
        'email': 'fran.ribeiro@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 200MB',
        'valor': Decimal('59.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 0,
    },
    {
        'nome': 'JOSE RIBAMAR CARVALHO',
        'cpf': '147.258.369-01',
        'telefone': '(89) 99876-5432',
        'email': 'ribamar.carvalho@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 18,
    },
    {
        'nome': 'CONDOMINIO RESIDENCIAL AURORA',
        'cpf': '12.345.678/0001-90',
        'telefone': '(89) 3221-4567',
        'email': 'sindico@condaurora.com.br',
        'plano': '[CORPORATIVO] LINK DEDICADO 100MB',
        'valor': Decimal('599.00'),
        'status': 'Servico Habilitado',
        'dias_atras': 45,
        'tipo_pessoa': 'pj',
    },
    {
        'nome': 'ESCOLA MUNICIPAL SAO FRANCISCO',
        'cpf': '23.456.789/0001-01',
        'telefone': '(89) 3221-8901',
        'email': 'contato@emsaofrancisco.edu.br',
        'plano': '[CORPORATIVO] LINK DEDICADO 50MB',
        'valor': Decimal('399.00'),
        'status': 'Servico Habilitado',
        'dias_atras': 60,
        'tipo_pessoa': 'pj',
    },
    {
        'nome': 'SUPERMERCADO BOM PRECO LTDA',
        'cpf': '34.567.890/0001-12',
        'telefone': '(89) 3221-2345',
        'email': 'financeiro@bompreco.com.br',
        'plano': '[CORPORATIVO] MEGA EMPRESARIAL 300MB',
        'valor': Decimal('249.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 30,
        'tipo_pessoa': 'pj',
    },
    {
        'nome': 'RAFAELA BEATRIZ MOURA',
        'cpf': '258.369.147-02',
        'telefone': '(89) 98765-1234',
        'email': 'rafaela.moura@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 8,
    },
    {
        'nome': 'MARCOS VINICIUS PEREIRA',
        'cpf': '369.147.258-03',
        'telefone': '(89) 99654-9876',
        'email': 'marcos.vinicius@hotmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 0,
    },
]


CONVERSAS = [
    {
        'cliente_idx': 0,  # FABIOLA
        'protocolo': '85320001073829',
        'atendimento': '#1073829',
        'agente': 'Paulo Henrique',
        'servico': 'Backoffice de Vendas',
        'conta': '0800BJFibra',
        'status_conversa': 'Em atendimento',
        'mensagens': [
            ('cliente', 'Bom dia'),
            ('bot', 'Ola! Eu sou o assistente virtual da Demo ISP, tudo bem?'),
            ('bot', 'Qual curso voce tem interesse? Nossos cursos: Direito, Sistemas de Informacao, Psicologia, Enfermagem, Fisioterapia, Administracao.'),
            ('cliente', 'Quero saber sobre o plano de 620 megas'),
            ('bot', 'Otimo! O plano Mega 620MB custa R$ 99,90/mes com instalacao gratuita. Posso agendar a instalacao?'),
            ('cliente', 'Sim, pode agendar'),
            ('bot', 'Perfeito! Vou transferir voce para nosso time de instalacao. Obrigado por escolher a Demo ISP!'),
        ],
    },
    {
        'cliente_idx': 2,  # LEILIANE
        'protocolo': '85320001074001',
        'atendimento': '#1074001',
        'agente': 'Maria Clara',
        'servico': 'Vendas Online',
        'conta': 'WhatsAppVendas',
        'status_conversa': 'Finalizado',
        'mensagens': [
            ('cliente', 'Boa tarde, gostaria de contratar internet'),
            ('bot', 'Boa tarde! Bem-vinda a Demo ISP. Temos planos a partir de R$ 59,90. Qual velocidade voce precisa?'),
            ('cliente', 'Preciso de algo bom pra trabalhar em casa'),
            ('bot', 'Para home office recomendo o Mega 620MB por R$ 99,90/mes. Velocidade excelente para videoconferencias e downloads.'),
            ('cliente', 'Pode ser esse'),
            ('bot', 'Vou precisar de alguns dados. Qual seu nome completo?'),
            ('cliente', 'Leiliane Rodrigues'),
            ('bot', 'E o CPF?'),
            ('cliente', '961.440.503-10'),
            ('bot', 'Cadastro realizado com sucesso! A instalacao sera em ate 3 dias uteis. Obrigada, Leiliane!'),
        ],
    },
    {
        'cliente_idx': 4,  # CARLOS EDUARDO
        'protocolo': '85320001074123',
        'atendimento': '#1074123',
        'agente': 'Ana Beatriz',
        'servico': 'Retencao',
        'conta': 'WhatsAppRetencao',
        'status_conversa': 'Finalizado',
        'mensagens': [
            ('cliente', 'Oi, quero cancelar meu plano'),
            ('bot', 'Ola Carlos! Sinto muito em saber. Posso perguntar o motivo?'),
            ('cliente', 'Ta muito caro'),
            ('bot', 'Entendo. Que tal fazermos um upgrade? Posso oferecer o plano 400MB pelo mesmo valor que voce paga hoje.'),
            ('cliente', 'Quanto ficaria?'),
            ('bot', 'Ficaria R$ 79,90/mes com 400MB de velocidade. E uma oferta especial de fidelidade.'),
            ('cliente', 'Pode ser, aceito'),
            ('bot', 'Maravilha! Plano alterado com sucesso. Obrigada por continuar com a Demo ISP, Carlos!'),
        ],
    },
    {
        'cliente_idx': 6,  # JOAO PEDRO
        'protocolo': '85320001074256',
        'atendimento': '#1074256',
        'agente': 'Paulo Henrique',
        'servico': 'Suporte Tecnico',
        'conta': '0800Suporte',
        'status_conversa': 'Finalizado',
        'mensagens': [
            ('cliente', 'Minha internet ta lenta demais'),
            ('bot', 'Ola Joao! Vou verificar sua conexao. Pode me informar se o roteador esta com todas as luzes acesas?'),
            ('cliente', 'Sim, ta tudo aceso'),
            ('bot', 'Certo. Estou rodando um diagnostico remoto na sua conexao... Detectei uma instabilidade no sinal. Vou reiniciar sua porta remotamente.'),
            ('cliente', 'Ok'),
            ('bot', 'Pronto! O sinal foi normalizado. Pode testar a velocidade agora?'),
            ('cliente', 'Voltou normal, obrigado!'),
            ('bot', 'Que bom! Se precisar de algo mais, estamos a disposicao. Tenha um otimo dia!'),
        ],
    },
    {
        'cliente_idx': 8,  # FRANCISCO DAS CHAGAS
        'protocolo': '85320001074389',
        'atendimento': '#1074389',
        'agente': 'Maria Clara',
        'servico': 'Upgrade de Plano',
        'conta': 'WhatsAppVendas',
        'status_conversa': 'Finalizado',
        'mensagens': [
            ('cliente', 'Quero aumentar meu plano'),
            ('bot', 'Ola Francisco! Atualmente voce tem o plano Mega 620MB. Gostaria de fazer upgrade para o Mega 1GB?'),
            ('cliente', 'Quanto custa o de 1 giga?'),
            ('bot', 'O Mega 1GB custa R$ 139,90/mes. E nossa maior velocidade residencial!'),
            ('cliente', 'Fecha! Quero esse'),
            ('bot', 'Upgrade realizado! Seu plano ja foi alterado para Mega 1GB. A velocidade sera atualizada em ate 30 minutos.'),
            ('cliente', 'Valeu!'),
            ('bot', 'Por nada! Aproveite a velocidade. Qualquer duvida, e so chamar!'),
        ],
    },
]


def _gerar_html_conversa(cliente, conversa, data_base):
    """Gera HTML de conversa no formato padrao do sistema."""
    cpf_masked = cliente['cpf'][:4] + '***.***' + cliente['cpf'][-3:]
    tel_limpo = cliente['telefone'].replace('(', '55').replace(') ', '').replace('-', '')

    msgs_html = ''
    for j, (tipo, texto) in enumerate(conversa['mensagens']):
        ts = (data_base + timedelta(minutes=j * 2)).strftime('%Y-%m-%d %H:%M:%S')
        if tipo == 'cliente':
            nome = cliente['nome'].split()[0].title()
            msgs_html += f'''
        <div class="msg-wrapper cliente">
            <div class="bubble msg-cliente">
                <div class="msg-autor">{nome}</div>
                <div class="msg-texto">{texto}</div>
                <div class="msg-meta">{ts} &middot; TEXTO</div>
            </div>
        </div>
'''
        else:
            msgs_html += f'''
        <div class="msg-wrapper bot">
            <div class="bubble msg-bot">
                <div class="msg-autor">BOT</div>
                <div class="msg-texto">{texto}</div>
                <div class="msg-meta">{ts} &middot; TEXTO</div>
            </div>
        </div>
'''

    data_entrada = data_base.strftime('%Y-%m-%d %H:%M:%S')
    nome_primeiro = cliente['nome'].split()[0].title()

    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Conversa {conversa["atendimento"]} — {cliente["nome"]}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #1a1a1a; padding: 24px 16px; }}
        .container {{ max-width: 780px; margin: 0 auto; }}
        .header {{ background: #075e54; color: #fff; border-radius: 12px 12px 0 0; padding: 20px 24px; }}
        .header h1 {{ font-size: 1.2rem; margin-bottom: 4px; }}
        .header .meta {{ font-size: 0.82rem; opacity: 0.85; line-height: 1.6; }}
        .header .badge {{ display: inline-block; background: #128c7e; border-radius: 20px; padding: 2px 10px; font-size: 0.75rem; margin-top: 6px; }}
        .contact-card {{ background: #fff; border-left: 4px solid #25d366; padding: 14px 20px; display: flex; flex-wrap: wrap; gap: 12px 32px; font-size: 0.88rem; }}
        .contact-card .field {{ display: flex; flex-direction: column; }}
        .contact-card .label {{ font-size: 0.73rem; color: #777; text-transform: uppercase; }}
        .contact-card .value {{ font-weight: 600; color: #1a1a1a; }}
        .chat-area {{ background: #e5ddd5; padding: 20px 16px; min-height: 300px; border-radius: 0 0 12px 12px; }}
        .msg-wrapper {{ display: flex; margin-bottom: 10px; }}
        .msg-wrapper.cliente {{ justify-content: flex-start; }}
        .msg-wrapper.bot {{ justify-content: flex-end; }}
        .bubble {{ max-width: 72%; padding: 9px 13px 6px; border-radius: 8px; font-size: 0.9rem; line-height: 1.45; box-shadow: 0 1px 2px rgba(0,0,0,.13); }}
        .msg-cliente {{ background: #fff; border-top-left-radius: 2px; }}
        .msg-bot {{ background: #dcf8c6; border-top-right-radius: 2px; }}
        .msg-autor {{ font-size: 0.73rem; font-weight: 700; color: #075e54; margin-bottom: 3px; }}
        .msg-bot .msg-autor {{ color: #128c7e; }}
        .msg-texto {{ word-break: break-word; }}
        .msg-meta {{ font-size: 0.68rem; color: #999; text-align: right; margin-top: 4px; }}
        .footer {{ text-align: center; font-size: 0.74rem; color: #aaa; margin-top: 16px; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Conversa — {nome_primeiro}</h1>
        <div class="meta">
            Protocolo: <strong>{conversa["protocolo"]}</strong> &nbsp;|&nbsp;
            Atendimento: <strong>{conversa["atendimento"]}</strong><br>
            Entrada: {data_entrada} &nbsp;|&nbsp; Agente: {conversa["agente"]}<br>
            Servico: {conversa["servico"]} &nbsp;|&nbsp; Conta: {conversa["conta"]}
        </div>
        <div class="badge">{conversa["status_conversa"]}</div>
    </div>
    <div class="contact-card">
        <div class="field"><span class="label">Nome</span><span class="value">{nome_primeiro}</span></div>
        <div class="field"><span class="label">Telefone</span><span class="value">{tel_limpo}</span></div>
        <div class="field"><span class="label">CPF</span><span class="value">{cpf_masked}</span></div>
        <div class="field"><span class="label">Email</span><span class="value">{cliente["email"]}</span></div>
    </div>
    <div class="chat-area">{msgs_html}
    </div>
    <div class="footer">Conversa gerada pelo sistema Hubtrix</div>
</div>
</body>
</html>'''


class Command(BaseCommand):
    help = 'Cria dados demo de vendas (ClienteHubsoft + conversas) para o tenant Demo ISP'

    def handle(self, *args, **options):
        import os
        from django.conf import settings
        from apps.sistema.models import Tenant
        from apps.sistema.middleware import set_current_tenant
        from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft
        from apps.comercial.leads.models import LeadProspecto

        demo = Tenant.objects.filter(nome__icontains='demo').first()
        if not demo:
            self.stdout.write(self.style.WARNING('Tenant Demo nao encontrado. Pulando.'))
            return

        set_current_tenant(demo)

        # Verificar se ja tem dados
        existentes = ClienteHubsoft.objects.filter(tenant=demo).count()
        if existentes >= 10:
            self.stdout.write(f'  Demo ja tem {existentes} clientes. Pulando.')
            return

        agora = timezone.now()
        base_id = 67700

        # Criar clientes
        clientes_criados = []
        for i, c in enumerate(CLIENTES):
            data_venda = agora - timedelta(days=c['dias_atras'])
            tipo_pessoa = c.get('tipo_pessoa', 'pf')

            cliente = ClienteHubsoft.objects.create(
                tenant=demo,
                id_cliente=base_id + i,
                codigo_cliente=base_id + i,
                nome_razaosocial=c['nome'],
                tipo_pessoa=tipo_pessoa,
                cpf_cnpj=c['cpf'],
                telefone_primario=c['telefone'],
                email_principal=c['email'],
                data_cadastro_hubsoft=data_venda,
                ativo=True,
            )

            status_prefixo = 'A' if 'Habilitado' in c['status'] else 'AI'
            ServicoClienteHubsoft.objects.create(
                tenant=demo,
                cliente=cliente,
                id_cliente_servico=90000 + i,
                nome=c['plano'],
                valor=c['valor'],
                status=c['status'],
                status_prefixo=status_prefixo,
                tecnologia='FIBRA',
                data_venda=data_venda.strftime('%d/%m/%Y'),
                data_habilitacao=data_venda if 'Habilitado' in c['status'] else None,
            )
            clientes_criados.append((i, cliente, c))

        self.stdout.write(self.style.SUCCESS(
            f'  {len(CLIENTES)} clientes demo criados.'
        ))

        # Criar conversas HTML para alguns clientes
        base_dir = str(getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
        media_root = getattr(settings, 'MEDIA_ROOT', None) or os.path.join(base_dir, 'media')
        conversas_dir = os.path.join(media_root, 'conversas_atendimento')
        os.makedirs(conversas_dir, exist_ok=True)

        conversas_criadas = 0
        for conv in CONVERSAS:
            idx = conv['cliente_idx']
            c = CLIENTES[idx]
            data_venda = agora - timedelta(days=c['dias_atras'])
            data_conversa = data_venda - timedelta(hours=2)

            # Criar/buscar lead para vincular a conversa
            telefone_limpo = c['telefone'].replace('(', '').replace(') ', '').replace('-', '')
            lead, _ = LeadProspecto.objects.get_or_create(
                tenant=demo,
                telefone=telefone_limpo,
                defaults={
                    'nome_razaosocial': c['nome'],
                    'email': c['email'],
                    'origem': 'whatsapp',
                    'canal_entrada': 'whatsapp',
                },
            )

            # Vincular lead ao cliente hubsoft
            cliente_hub = ClienteHubsoft.objects.filter(
                tenant=demo, id_cliente=base_id + idx
            ).first()
            if cliente_hub and not cliente_hub.lead_id:
                cliente_hub.lead = lead
                cliente_hub.save(update_fields=['lead'])

            # Gerar HTML
            html_content = _gerar_html_conversa(c, conv, data_conversa)
            filename = f'demo_{lead.pk}_{conv["protocolo"][-6:]}.html'
            filepath = os.path.join(conversas_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Atualizar lead com path da conversa
            rel_path = f'conversas_atendimento/{filename}'
            lead.html_conversa_path = rel_path
            lead.save(update_fields=['html_conversa_path'])
            conversas_criadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'  {conversas_criadas} conversas demo criadas.'
        ))
