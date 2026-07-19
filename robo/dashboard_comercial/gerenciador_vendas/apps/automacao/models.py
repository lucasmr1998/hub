"""
Persistência da engine de automação.

`Fluxo` guarda o grafo (nós + conexões) como JSON — o MESMO formato que o runtime
(`executar_fluxo`) consome e que o editor produz. JSONField em vez de models
normalizados de Nó/Conexão porque o runtime e o editor já falam esse dict; mantém
a impedância zero. (Normalizar depois, se precisar de query por nó.)
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sistema.mixins import TenantMixin


class Fluxo(TenantMixin):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default='')
    ativo = models.BooleanField(default=True, db_index=True)
    # {inicio, nodes: {handle: {tipo, config, pos, label}}, conexoes: [{de, para, saida}]}
    grafo = models.JSONField(default=dict)
    # Gatilho webhook: token secreto; POST em /automacao/webhook/<token>/ dispara o fluxo.
    webhook_token = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Índice denormalizado do gatilho de evento (preenchido no save a partir do grafo).
    # Permite achar rápido "quais fluxos escutam o evento X" sem varrer JSON em SQL.
    gatilho_evento = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Gatilho agenda (varredura): intervalo (min) sincronizado do grafo no save().
    # Preenchido = candidato do dispatcher `gatilhos.despachar_agendas`.
    agenda_intervalo_minutos = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    # Quando a última rodada de varredura foi disparada — base do CAS anti dupla
    # rodada em `gatilhos._rodar_agenda_do_fluxo`.
    agenda_ultima_rodada = models.DateTimeField(null=True, blank=True)
    # Convergência: id da RegraAutomacao (marketing) que originou este fluxo (tradutor).
    # Usado no cutover pra desligar a regra antiga ao ligar este fluxo. int simples
    # (sem FK) pra não acoplar a engine nova ao app de marketing.
    origem_regra = models.IntegerField(null=True, blank=True, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_fluxo'
        ordering = ['-atualizado_em']
        verbose_name = 'Fluxo de automação'
        verbose_name_plural = 'Fluxos de automação'

    def _evento_do_grafo(self):
        """Lê o evento do nó-gatilho de evento no grafo (ou '' se não houver)."""
        nodes = (self.grafo or {}).get('nodes') or {}
        for n in nodes.values():
            if n.get('tipo') == 'evento':
                return ((n.get('config') or {}).get('evento') or '').strip()
        return ''

    def _agenda_do_grafo(self):
        """Lê o `intervalo_minutos` do nó-gatilho `agenda` no grafo (ou None)."""
        nodes = (self.grafo or {}).get('nodes') or {}
        for n in nodes.values():
            if n.get('tipo') == 'agenda':
                try:
                    intervalo = int((n.get('config') or {}).get('intervalo_minutos') or 0)
                except (TypeError, ValueError):
                    return None
                return intervalo if intervalo > 0 else None
        return None

    def save(self, *args, **kwargs):
        # Mantém os índices de gatilho (evento + agenda) sincronizados com o grafo
        # em qualquer save.
        campos_sync = set()

        novo_evento = self._evento_do_grafo()
        if novo_evento != self.gatilho_evento:
            self.gatilho_evento = novo_evento
            campos_sync.add('gatilho_evento')

        novo_intervalo = self._agenda_do_grafo()
        if novo_intervalo != self.agenda_intervalo_minutos:
            self.agenda_intervalo_minutos = novo_intervalo
            campos_sync.add('agenda_intervalo_minutos')

        if campos_sync:
            uf = kwargs.get('update_fields')
            if uf is not None:
                kwargs['update_fields'] = list(set(uf) | campos_sync)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class ExecucaoFluxo(TenantMixin):
    """Uma execução de um fluxo. Guarda o estado serializado pra retoma (delay)."""
    STATUS = [
        ('pendente', 'pendente'),  # enfileirada por gatilho; o cron roda (deferido)
        ('rodando', 'rodando'), ('aguardando', 'aguardando'),
        ('completado', 'completado'), ('erro', 'erro'),
    ]
    fluxo = models.ForeignKey(Fluxo, on_delete=models.CASCADE, related_name='execucoes')
    status = models.CharField(max_length=20, choices=STATUS, default='rodando', db_index=True)
    estado = models.JSONField(default=dict)        # Contexto.serializar()
    no_pausado = models.CharField(max_length=200, blank=True, default='')  # handle do nó que pausou
    modo_espera = models.CharField(max_length=20, blank=True, default='')  # '' | 'timer' | 'resposta'
    # Âncora conversacional: o que a execução espera (ex: telefone normalizado).
    chave = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Âncora de jornada (enrollment): 1 execução ativa por lead por fluxo.
    lead = models.ForeignKey(
        'leads.LeadProspecto', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    agendado_para = models.DateTimeField(null=True, blank=True, db_index=True)
    # Claim atômico (hardening E3): quando um worker reivindicou esta execução
    # (status='rodando'). Base do CAS anti dupla execução e do watchdog.
    claimed_em = models.DateTimeField(null=True, blank=True)
    # Retry transitório (hardening E4): quantas vezes esta execução já foi retentada
    # após terminar em erro não tratado (teto em execucao.MAX_TENTATIVAS).
    tentativas = models.PositiveSmallIntegerField(default=0)
    trace = models.JSONField(default=list)
    erro = models.TextField(blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_execucao'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['status', 'agendado_para']),
            models.Index(fields=['status', 'modo_espera', 'chave']),
            models.Index(fields=['status', 'claimed_em']),      # watchdog (E3)
            models.Index(fields=['fluxo', 'lead', 'criado_em']),  # orçamento anti-loop (E5) + freios
        ]

    def __str__(self):
        return f'{self.fluxo_id} · {self.status}'


class Agente(TenantMixin):
    """Agente IA gerenciado: prompt + modelo + tools (D3) + conhecimento (D4).

    Definido UMA vez (área /automacao/agentes/) e referenciado pelos fluxos pelo
    nó `ia_agente`. Espelha o padrão da IntegracaoAPI (configura uma vez, usa por id).
    """
    EQUIPE_CHOICES = [
        ('executivo', 'Executivo'),
        ('produto', 'Produto'),
        ('comercial', 'Comercial'),
        ('marketing', 'Marketing'),
        ('tech', 'Tech'),
        ('operacoes', 'Operações'),
        ('fluxo', 'Fluxos / Bot'),
    ]

    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default='', help_text='Resumo curto do papel do agente.')
    integracao_ia = models.ForeignKey(
        'integracoes.IntegracaoAPI', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    # Vazio = usa o modelo default da integração (configuracoes_extras['modelo']).
    modelo = models.CharField(max_length=100, blank=True, default='')
    system_prompt = models.TextField(blank=True, default='')
    # Prompt do modo autonomo (cron/rotina), diferente do prompt de chat. Vazio = usa o system_prompt.
    prompt_autonomo = models.TextField(blank=True, default='')
    # D3: chaves das tools habilitadas (registry em services/ia_tools.py).
    tools = models.JSONField(default=list, blank=True)
    # D4: ids das CategoriaConhecimento que o agente enxerga no RAG (vazio = base inteira do tenant).
    base_categorias = models.JSONField(default=list, blank=True)
    # Tipo de memória (registry em services/memoria.py). 'conversa' = mensagens da
    # conversa atual; '' / desconhecido = sem memória (stateless). Extensível.
    memoria = models.CharField(max_length=30, default='conversa', blank=True)
    # Organizacao visual (estilo "empresa de agentes"): time + cor + icone + ordem.
    equipe = models.CharField(max_length=20, choices=EQUIPE_CHOICES, blank=True, default='', db_index=True)
    cor = models.CharField(max_length=7, blank=True, default='', help_text='Cor hex do card (ex: #1e3a8a).')
    icone = models.CharField(max_length=40, blank=True, default='bi-robot', help_text='Bootstrap Icon (bi-*).')
    ordem = models.PositiveIntegerField(default=0, help_text='Ordem de exibicao dentro do time.')
    ativo = models.BooleanField(default=True, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_agente'
        ordering = ['equipe', 'ordem', 'nome']
        verbose_name = 'Agente IA'
        verbose_name_plural = 'Agentes IA'

    def __str__(self):
        return self.nome


class Checklist(TenantMixin):
    """Roteiro de perguntas que um agente/bot conduz pra preencher dados de uma
    entidade (lead, oportunidade...) passo a passo. Multi assunto: venda, suporte,
    visita técnica etc — `contexto` é só rótulo/filtro, a engine trata igual.

    Fonte das perguntas do checklist configurável: o bot externo (Matrix) consome
    os itens daqui via API (Fase 2) em vez de ter as perguntas hardcoded no fluxo.
    """
    CONTEXTO_CHOICES = [
        ('bot_vendas', 'Bot de vendas'),
        ('onboarding', 'Onboarding'),
        ('suporte', 'Suporte'),
        ('visita_tecnica', 'Visita técnica'),
        ('outro', 'Outro'),
    ]
    MODO_PREENCHIMENTO_CHOICES = [
        ('ia', 'IA (bot)'),
        ('humano', 'Humano'),
        ('ambos', 'Ambos'),
    ]
    ENTIDADE_ALVO_CHOICES = [
        ('lead', 'Lead'),
        ('oportunidade', 'Oportunidade'),
    ]

    nome = models.CharField(max_length=200)
    # Identificador estável usado pela API/config do bot pra referenciar o
    # checklist — o nome pode mudar sem quebrar a integração.
    slug = models.SlugField(max_length=100)
    descricao = models.TextField(blank=True, default='')
    contexto = models.CharField(max_length=30, choices=CONTEXTO_CHOICES, default='bot_vendas', db_index=True)
    modo_preenchimento = models.CharField(max_length=20, choices=MODO_PREENCHIMENTO_CHOICES, default='ia')
    entidade_alvo = models.CharField(max_length=20, choices=ENTIDADE_ALVO_CHOICES, default='lead')
    # v1 só sugere (o bot pergunta mas o pipeline não trava sem resposta). Campo
    # existe pronto pra v2 endurecer (bloquear avanço de estágio sem checklist completo).
    bloqueia_avanco = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_checklist'
        unique_together = [('tenant', 'slug')]
        ordering = ['nome']
        verbose_name = 'Checklist'
        verbose_name_plural = 'Checklists'

    def __str__(self):
        return self.nome


class ItemChecklist(TenantMixin):
    """Uma pergunta do checklist. `campo`, quando setado, espelha a resposta num
    CampoCustomizado do CRM (aparece no painel "Dados personalizados" do
    lead/oportunidade); sem ele a resposta vive só em `RespostaChecklist`
    (ex: pergunta de triagem que não vira dado permanente)."""
    TIPO_RESPOSTA_CHOICES = [
        ('texto_livre', 'Texto livre'),
        ('opcoes', 'Múltipla escolha'),
    ]
    TIPO_VALIDACAO_CHOICES = [
        ('nenhuma', 'Nenhuma'),
        ('email', 'E-mail'),
        ('cpf_cnpj', 'CPF/CNPJ'),
        ('cep', 'CEP'),
        ('numero', 'Número'),
        ('data', 'Data'),
        ('regex', 'Regex customizado'),
        ('ia', 'IA (julgamento livre)'),
    ]
    ESTRATEGIA_ERRO_CHOICES = [
        ('repetir', 'Repetir a pergunta'),
        ('pular', 'Pular o item'),
        ('transbordar', 'Transbordar pra humano'),
        ('finalizar', 'Finalizar o checklist'),
    ]
    # Só estes 3 slugs existem do lado do Matrix hoje: cada um faz o Matrix
    # renderizar uma IMAGEM fixa de menu no WhatsApp (não é texto livre, é asset
    # publicado nos DOIS sistemas). Slug novo aqui sem par no Matrix não quebra
    # (cai no menu de texto comum), mas criar um slug de verdade exige mudança
    # nos DOIS lados — por isso a lista é fechada em vez de CharField livre.
    URA_TITULO_CHOICES = [
        ('', 'Nenhum (menu comum)'),
        ('confirmacao_plano_620', 'Confirmação plano 620'),
        ('confirmacao_plano_1g', 'Confirmação plano 1G'),
        ('confirmacao_plano_1g_ponto_adc', 'Confirmação plano 1G + ponto adicional'),
    ]

    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveIntegerField(default=0, db_index=True)
    # Slug lógico da resposta (ex: 'cep'). É a chave usada na `condicao` de OUTROS
    # itens e no dict de respostas que os services montam — único dentro do checklist.
    chave = models.CharField(max_length=60)
    pergunta = models.TextField()
    ajuda = models.CharField(max_length=200, blank=True, default='')
    tipo_resposta = models.CharField(max_length=20, choices=TIPO_RESPOSTA_CHOICES, default='texto_livre')
    # [{'texto': str, 'valor': str}] — só relevante quando tipo_resposta='opcoes'.
    opcoes = models.JSONField(default=list, blank=True)
    ura_titulo = models.CharField(max_length=60, blank=True, default='', choices=URA_TITULO_CHOICES)
    tipo_validacao = models.CharField(max_length=20, choices=TIPO_VALIDACAO_CHOICES, default='nenhuma')
    regex_validacao = models.CharField(max_length=200, blank=True, default='')
    # Instrucoes especificas pra IA validar ESTE item (ex: "aceite apenas nomes de
    # pessoa fisica, recuse nome de empresa"). Espelha o `RegraValidacao.instrucoes_ia`
    # do robo original. Preenchido = habilita a IA como SEGUNDA OPINIAO quando a
    # validacao deterministica falha (ver services/validacao.py::_com_segunda_opiniao_ia).
    # Vazio = uma reprovacao deterministica nunca aciona IA, pra nao gastar token a toa.
    instrucoes_ia = models.TextField(
        blank=True, default='',
        help_text=(
            'Instrucoes especificas pra IA validar ESTE item (ex: "aceite apenas nomes '
            'de pessoa fisica, recuse nome de empresa"). Preenchido, habilita a IA como '
            'segunda opiniao quando a validacao deterministica falhar.'
        ),
    )
    obrigatorio = models.BooleanField(default=True)
    # {'chave': 'x', 'operador': 'igual', 'valor': 'y'} — item só entra no roteiro
    # se a resposta já dada de `chave` bater com `valor` conforme `operador`.
    # Operadores suportados em services/checklist.py: igual, diferente, existe, nao_existe.
    condicao = models.JSONField(null=True, blank=True)
    max_tentativas = models.PositiveSmallIntegerField(default=3)
    estrategia_erro = models.CharField(max_length=20, choices=ESTRATEGIA_ERRO_CHOICES, default='repetir')
    mensagem_erro = models.TextField(blank=True, default='')
    mensagem_sucesso = models.TextField(blank=True, default='')
    mensagem_recontato = models.TextField(blank=True, default='')
    campo = models.ForeignKey(
        'leads.CampoCustomizado', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'automacao_checklist_item'
        unique_together = [('checklist', 'chave')]
        ordering = ['ordem', 'id']
        verbose_name = 'Item de checklist'
        verbose_name_plural = 'Itens de checklist'

    def clean(self):
        """Validações que protegem o contrato com o Matrix: o flow dele só tem
        branch fixo pra 2 a 5 opções (6+ cai no default e quebra em silêncio),
        `ura_titulo` só faz sentido em opções, e regex tem que compilar."""
        erros = {}

        if self.tipo_resposta == 'opcoes':
            opcoes = self.opcoes or []
            if not (2 <= len(opcoes) <= 5):
                erros['opcoes'] = (
                    'Múltipla escolha precisa ter entre 2 e 5 opções: o flow do Matrix '
                    'só tem branch pronto pra esses tamanhos; 6 ou mais cai no default '
                    'e quebra em silêncio.'
                )
            elif any(not isinstance(o, dict) or not str(o.get('texto') or '').strip() for o in opcoes):
                erros['opcoes'] = 'Toda opção precisa da chave "texto" preenchida.'
        elif self.ura_titulo:
            erros['ura_titulo'] = 'ura_titulo só faz sentido com tipo_resposta="opcoes".'

        if self.tipo_validacao == 'regex':
            if not self.regex_validacao:
                erros['regex_validacao'] = 'tipo_validacao="regex" exige regex_validacao preenchido.'
            else:
                try:
                    re.compile(self.regex_validacao)
                except re.error as exc:
                    erros['regex_validacao'] = f'Regex inválido: {exc}.'

        if self.condicao is not None:
            if not isinstance(self.condicao, dict) or 'chave' not in self.condicao or 'valor' not in self.condicao:
                erros['condicao'] = 'condicao precisa ser um objeto com as chaves "chave" e "valor".'

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f'{self.checklist_id} · {self.chave}'


class RespostaChecklist(TenantMixin):
    """Resposta de UM item do checklist, ancorada em qualquer entidade (genérico:
    serve pra lead, oportunidade, ticket...) via `entidade_tipo` + `entidade_id`
    em vez de FK direta — evita uma FK nullable por tipo de entidade que a engine
    venha a suportar."""
    ORIGEM_CHOICES = [
        ('bot', 'Bot'),
        ('humano', 'Humano'),
        ('importacao', 'Importação'),
    ]

    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='respostas')
    item = models.ForeignKey(ItemChecklist, on_delete=models.CASCADE, related_name='respostas')
    entidade_tipo = models.CharField(max_length=30, db_index=True)  # 'lead' | 'oportunidade' | ...
    entidade_id = models.PositiveIntegerField(db_index=True)
    valor = models.TextField(blank=True, default='')  # o que o cliente respondeu, bruto
    valor_processado = models.JSONField(null=True, blank=True)  # normalizado (cep limpo, opção escolhida...)
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default='bot')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_checklist_resposta'
        # 1 resposta corrente por item/entidade: responder de novo é UPDATE, não
        # linha nova (histórico de tentativa fica no `trace` da execução do fluxo).
        unique_together = [('item', 'entidade_tipo', 'entidade_id')]
        indexes = [
            models.Index(fields=['tenant', 'entidade_tipo', 'entidade_id']),
            models.Index(fields=['checklist', 'entidade_tipo', 'entidade_id']),
        ]
        verbose_name = 'Resposta de checklist'
        verbose_name_plural = 'Respostas de checklist'

    def __str__(self):
        return f'{self.item_id} · {self.entidade_tipo}#{self.entidade_id}'
