"""Modelos do app ia_validador.

Configuração por pergunta do fluxo Matrix. A API IA externa (FastAPI)
consulta esses registros via endpoint readonly e aplica a regra
correspondente quando o Matrix chama `/validar`.
"""
from django.db import models


class RegraValidacao(models.Model):
    """Regra de validação por pergunta (uma linha = uma pergunta do fluxo)."""

    # ── Identificação ────────────────────────────────────────────────
    question_id = models.SlugField(
        max_length=80, unique=True,
        verbose_name='ID da pergunta',
        help_text='Identificador único enviado pelo Matrix (ex: coleta_cpf)',
    )
    pergunta_padrao = models.TextField(
        verbose_name='Pergunta padrão',
        help_text='Texto da pergunta no Matrix (também usado pra matching textual quando question_id não vem)',
    )
    ordem = models.IntegerField(
        default=0,
        help_text='Ordem sugerida no fluxo (apenas informativo)',
    )
    descricao = models.CharField(max_length=200, blank=True,
                                  help_text='Descrição curta do propósito da regra')
    ativo = models.BooleanField(default=True)

    # ── Validação ────────────────────────────────────────────────────
    EXTRACTOR_CHOICES = [
        ('cpf', 'CPF (regex + dígito verificador)'),
        ('cep', 'CEP (regex + ViaCEP + cobertura)'),
        ('nome', 'Nome completo'),
        ('telefone', 'Telefone'),
        ('data_nascimento', 'Data nascimento (valida >=18)'),
        ('email', 'E-mail'),
        ('numero', 'Número (residência, etc)'),
        ('opcao', 'Opção de menu (1, 2, 3...)'),
        ('confirmacao', 'Sim/Não'),
        ('imagem', 'URL de imagem'),
        ('texto_livre', 'Texto livre (IA decide)'),
        ('livre', 'Sem validação (sempre aceita)'),
    ]
    extractor_tipo = models.CharField(
        max_length=20, choices=EXTRACTOR_CHOICES, default='texto_livre',
        verbose_name='Tipo de validador',
    )
    extractor_config = models.JSONField(
        default=dict, blank=True,
        verbose_name='Config do validador',
        help_text='JSON com config extra. Ex: {"opcoes": {"1": "manha", "2": "tarde"}} pra opcao',
    )
    instrucoes_ia = models.TextField(
        blank=True,
        verbose_name='Instruções extras pra IA',
        help_text='Texto adicional pro system prompt quando cai no fallback IA',
    )
    permite_pular = models.BooleanField(
        default=False,
        help_text='Cliente pode dizer "não" / "depois" e seguir',
    )
    max_tentativas = models.IntegerField(default=3)

    # ── Ações ao validar com sucesso ─────────────────────────────────
    campo_lead_atualizar = models.CharField(
        max_length=60, blank=True,
        verbose_name='Campo do lead a atualizar',
        help_text='Nome do campo no LeadProspecto (ex: cpf_cnpj). Recebe o valor de extracted_data.',
    )
    status_api_apos_sucesso = models.CharField(
        max_length=40, blank=True,
        verbose_name='status_api após sucesso',
        help_text='Ex: aguardando_assinatura, em_instalacao, pendente. Em branco = não muda.',
    )
    tags_adicionar = models.JSONField(
        default=list, blank=True,
        verbose_name='Tags a adicionar',
        help_text='Lista de strings: ["Comercial", "Endereço"]',
    )
    tags_remover = models.JSONField(default=list, blank=True)
    historico_status_apos_sucesso = models.CharField(
        max_length=40, blank=True,
        verbose_name='Status do histórico após sucesso',
        help_text='Ex: fluxo_inicializado, fluxo_finalizado. Em branco = não registra.',
    )
    historico_observacoes_template = models.TextField(
        blank=True,
        verbose_name='Template das observações do histórico',
        help_text='Variáveis disponíveis: {question}, {answer}, {extracted}',
    )
    descricao_imagem = models.CharField(
        max_length=50, blank=True,
        verbose_name='Descrição da imagem',
        help_text='Se extractor=imagem: ex: selfie_com_doc, frente_doc, verso_doc',
    )

    # ── Mensagens ─────────────────────────────────────────────────────
    msg_sucesso = models.TextField(
        blank=True,
        verbose_name='Mensagem de sucesso (padrão pro cliente)',
        help_text='Ex: "Anotei seu CPF!" — pode ter {extracted}',
    )
    msg_erro = models.TextField(
        blank=True,
        verbose_name='Mensagem de erro',
        help_text='Ex: "CPF inválido, pode conferir?"',
    )
    msg_max_tentativas = models.TextField(
        blank=True,
        verbose_name='Mensagem após exceder tentativas',
    )
    forcar_transbordo_apos_max = models.BooleanField(
        default=False,
        verbose_name='Forçar transbordo após máximo de tentativas',
    )

    # ── Auditoria ─────────────────────────────────────────────────────
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Regra de Validação'
        verbose_name_plural = 'Regras de Validação'
        ordering = ['ordem', 'question_id']

    def __str__(self):
        return f'{self.question_id} — {self.get_extractor_tipo_display()}'

    def to_dict(self):
        """Serialização pra API IA consumir."""
        return {
            'question_id': self.question_id,
            'pergunta_padrao': self.pergunta_padrao,
            'extractor_tipo': self.extractor_tipo,
            'extractor_config': self.extractor_config,
            'instrucoes_ia': self.instrucoes_ia,
            'permite_pular': self.permite_pular,
            'max_tentativas': self.max_tentativas,
            'campo_lead_atualizar': self.campo_lead_atualizar,
            'status_api_apos_sucesso': self.status_api_apos_sucesso,
            'tags_adicionar': self.tags_adicionar,
            'tags_remover': self.tags_remover,
            'historico_status_apos_sucesso': self.historico_status_apos_sucesso,
            'historico_observacoes_template': self.historico_observacoes_template,
            'descricao_imagem': self.descricao_imagem,
            'msg_sucesso': self.msg_sucesso,
            'msg_erro': self.msg_erro,
            'msg_max_tentativas': self.msg_max_tentativas,
            'forcar_transbordo_apos_max': self.forcar_transbordo_apos_max,
            'ativo': self.ativo,
        }


class LogInteracaoIA(models.Model):
    """Log de toda interação com a API IA (validar / proximo-passo / validar-imagem).

    Armazena entrada+saída completa pra análise futura, auditoria e
    treinamento. Salvo em background via thread daemon — não impacta
    latência das respostas.
    """
    ENDPOINT_CHOICES = [
        ('validar',        'validar'),
        ('proximo-passo',  'proximo-passo'),
        ('validar-imagem', 'validar-imagem'),
        # Eventos do fluxo de contratação de Novo Serviço (cliente Hubsoft).
        # Cada evento (iniciado/atualizado/cancelado/finalizado) é logado pra
        # análise de funil + debug de regressões.
        ('new_service',    'new_service'),
        # Turno do fluxo conversacional (camada de IA por cima — /conv/turno).
        # Loga a análise da IA (campos extraídos, confirmação, intenção) +
        # decisão (qid_atual, campos salvos, próxima pergunta, transbordo).
        ('conv-turno',     'conv-turno'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    endpoint = models.CharField(max_length=40, choices=ENDPOINT_CHOICES, db_index=True)

    # Identificação
    cellphone = models.CharField(max_length=20, blank=True, default='', db_index=True)
    lead = models.ForeignKey(
        'vendas_web.LeadProspecto', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='interacoes_ia',
    )
    question_id = models.CharField(max_length=80, blank=True, default='', db_index=True)

    # Conteúdo da troca
    answer = models.TextField(blank=True, default='',
                              help_text='Resposta do cliente (em /validar)')
    mensagem_resposta = models.TextField(blank=True, default='',
                                          help_text='Mensagem composta pelo engine pro cliente')

    # Payloads completos pra auditoria
    payload_in = models.JSONField(default=dict, blank=True)
    payload_out = models.JSONField(default=dict, blank=True)

    # Métricas e status
    duracao_ms = models.IntegerField(null=True, blank=True)
    valido = models.BooleanField(null=True, blank=True)
    transbordou = models.BooleanField(default=False)
    motivo = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'logs_interacao_ia'
        verbose_name = 'Log Interação IA'
        verbose_name_plural = '🤖 Logs de Interação IA'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['cellphone', '-timestamp']),
            models.Index(fields=['lead', '-timestamp']),
            models.Index(fields=['endpoint', '-timestamp']),
        ]

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.endpoint} cel={self.cellphone} q={self.question_id}'


class MensagemRobo(models.Model):
    """Mensagens que o robô envia ao cliente — configuráveis pela ferramenta.

    Repositório chave→texto lido pelo engine (FastAPI) com cache/invalidação,
    igual às RegraValidacao. Cada `chave` corresponde a um ponto do fluxo. Se
    `texto` ficar vazio (ou inativo), o engine usa o texto PADRÃO embutido no
    código — então nada quebra ao apagar. Placeholders suportados dependem do
    ponto (ex.: {primeiro_nome}); documentados na tela.
    """
    GRUPO_CHOICES = [
        ('inicio', 'Início & boas-vindas'),
        ('boas_vindas_coleta', 'Coleta de dados (perguntas)'),
        ('endereco', 'Endereço'),
        ('planos', 'Planos & vitrine'),
        ('documentos', 'Documentos (fotos)'),
        ('agendamento', 'Agendamento da instalação'),
        ('confirmacoes_erros', 'Confirmações & erros'),
        ('menu_cliente', 'Menu do cliente'),
        ('recontato', 'Recontato (tempo de espera)'),
        ('retomada', 'Retomada de atendimento'),
        ('transbordo_encerramento', 'Transbordo & encerramento'),
    ]

    chave = models.CharField(max_length=60, unique=True,
                             help_text='Identificador do ponto do fluxo (não editar)')
    grupo = models.CharField(max_length=40, choices=GRUPO_CHOICES,
                             default='boas_vindas_coleta')
    rotulo = models.CharField(max_length=140, verbose_name='Rótulo')
    descricao = models.CharField(max_length=255, blank=True, default='',
                                 verbose_name='Quando é enviada')
    placeholders = models.CharField(max_length=200, blank=True, default='',
                                    help_text='Placeholders disponíveis, separados por vírgula')
    texto = models.TextField(blank=True, default='', verbose_name='Mensagem')
    texto_padrao = models.TextField(
        blank=True, default='', verbose_name='Texto padrão',
        help_text='Texto original de fábrica — usado pelo botão "Restaurar padrão".')
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mensagens_robo'
        verbose_name = 'Mensagem do Robô'
        verbose_name_plural = '💬 Mensagens do Robô'
        ordering = ['grupo', 'ordem', 'chave']

    def __str__(self):
        return f'{self.chave} ({self.get_grupo_display()})'

    def to_dict(self):
        """Serialização pra API IA consumir (engine lê chave→texto)."""
        return {'chave': self.chave, 'texto': self.texto, 'ativo': self.ativo}
