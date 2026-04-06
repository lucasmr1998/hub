import logging

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta, time
from apps.sistema.mixins import TenantMixin

logger = logging.getLogger(__name__)


class FluxoAtendimento(TenantMixin):
    """
    Modelo para definir fluxos de atendimento personalizáveis
    Cada fluxo pode ter múltiplas questões em ordem específica
    """
    TIPO_FLUXO_CHOICES = [
        ('qualificacao', 'Qualificação de Lead'),
        ('vendas', 'Vendas'),
        ('suporte', 'Suporte'),
        ('onboarding', 'Onboarding'),
        ('pesquisa', 'Pesquisa de Satisfação'),
        ('customizado', 'Customizado'),
    ]

    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('rascunho', 'Rascunho'),
        ('teste', 'Em Teste'),
    ]

    nome = models.CharField(
        max_length=255,
        verbose_name="Nome do Fluxo",
        help_text="Nome identificador do fluxo de atendimento"
    )

    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada do fluxo"
    )

    tipo_fluxo = models.CharField(
        max_length=20,
        choices=TIPO_FLUXO_CHOICES,
        default='qualificacao',
        verbose_name="Tipo de Fluxo"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='rascunho',
        verbose_name="Status"
    )

    # Configurações do fluxo
    max_tentativas = models.PositiveIntegerField(
        default=3,
        verbose_name="Máximo de Tentativas",
        help_text="Número máximo de tentativas para completar o fluxo"
    )

    tempo_limite_minutos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo Limite (minutos)",
        help_text="Tempo máximo para completar o fluxo (opcional)"
    )

    permite_pular_questoes = models.BooleanField(
        default=False,
        verbose_name="Permite Pular Questões",
        help_text="Se o usuário pode pular questões opcionais"
    )

    # Campos de controle
    data_criacao = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Criação"
    )

    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )

    criado_por = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Criado Por"
    )

    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )

    # Canal que ativa este fluxo (None = qualquer canal / manual)
    CANAL_CHOICES = [
        ('qualquer', 'Qualquer Canal'),
        ('whatsapp', 'WhatsApp'),
        ('site', 'Site'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('google', 'Google Ads'),
        ('telefone', 'Telefone'),
        ('email', 'Email'),
        ('indicacao', 'Indicacao'),
        ('manual', 'Manual (somente API)'),
    ]
    canal = models.CharField(
        max_length=20,
        choices=CANAL_CHOICES,
        default='qualquer',
        verbose_name="Canal de Ativacao",
        help_text="Canal que dispara este fluxo automaticamente. 'Manual' = somente via API.",
        db_index=True,
    )

    # Dual-mode: legado (questoes lineares) vs visual (nodos + conexoes)
    modo_fluxo = models.BooleanField(
        default=False,
        verbose_name="Modo Fluxo Visual",
        help_text="True = fluxograma visual com nodos, False = questoes lineares (legado)"
    )
    fluxo_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Estado do Editor",
        help_text="Estado do Drawflow para re-import do editor visual"
    )

    class Meta:
        db_table = 'fluxos_atendimento'
        verbose_name = "Fluxo de Atendimento"
        verbose_name_plural = "🤖 01. Fluxos de Atendimento"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['tipo_fluxo']),
            models.Index(fields=['status']),
            models.Index(fields=['ativo']),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_fluxo_display()})"

    def get_questoes_ordenadas(self):
        """Retorna questões ordenadas por índice"""
        return self.questoes.filter(ativo=True).order_by('indice')

    def get_total_questoes(self):
        """Retorna total de questões ativas"""
        return self.questoes.filter(ativo=True).count()

    def get_questao_por_indice(self, indice):
        """Retorna questão específica por índice"""
        return self.questoes.filter(indice=indice, ativo=True).first()

    def get_proxima_questao(self, indice_atual):
        """Retorna próxima questão após o índice atual"""
        return self.questoes.filter(
            indice__gt=indice_atual,
            ativo=True
        ).order_by('indice').first()

    def get_questao_anterior(self, indice_atual):
        """Retorna questão anterior ao índice atual"""
        return self.questoes.filter(
            indice__lt=indice_atual,
            ativo=True
        ).order_by('indice').last()

    def pode_ser_usado(self):
        """Verifica se o fluxo pode ser usado"""
        if not (self.status == 'ativo' and self.ativo):
            return False
        if self.modo_fluxo:
            return self.nodos.filter(tipo='entrada').exists()
        return self.get_total_questoes() > 0

    def get_estatisticas(self):
        """Retorna estatísticas básicas do fluxo"""
        from django.db.models import Count, Avg

        atendimentos = self.atendimentos.all()
        total_atendimentos = atendimentos.count()
        atendimentos_completados = atendimentos.filter(status='completado').count()

        if total_atendimentos > 0:
            taxa_completacao = (atendimentos_completados / total_atendimentos) * 100
        else:
            taxa_completacao = 0

        tempo_medio = atendimentos.filter(
            tempo_total__isnull=False
        ).aggregate(
            tempo_medio=Avg('tempo_total')
        )['tempo_medio'] or 0

        return {
            'total_atendimentos': total_atendimentos,
            'atendimentos_completados': atendimentos_completados,
            'taxa_completacao': round(taxa_completacao, 2),
            'tempo_medio_segundos': round(tempo_medio, 2) if tempo_medio else 0,
        }


class QuestaoFluxo(TenantMixin):
    """
    Modelo para questões individuais dentro de um fluxo inteligente
    Suporte completo para roteamento condicional e integração com IA
    """
    TIPO_QUESTAO_CHOICES = [
        ('texto', 'Texto Livre'),
        ('numero', 'Número'),
        ('email', 'Email'),
        ('telefone', 'Telefone'),
        ('cpf_cnpj', 'CPF/CNPJ'),
        ('cep', 'CEP'),
        ('endereco', 'Endereço'),
        ('select', 'Seleção Única'),
        ('multiselect', 'Seleção Múltipla'),
        ('data', 'Data'),
        ('hora', 'Hora'),
        ('data_hora', 'Data e Hora'),
        ('boolean', 'Sim/Não'),
        ('escala', 'Escala (1-10)'),
        ('arquivo', 'Upload de Arquivo'),
        # Novos tipos para integração
        ('planos_internet', 'Seleção de Planos Internet'),
        ('vencimentos', 'Seleção de Vencimentos'),
        ('opcoes_dinamicas', 'Opções Dinâmicas'),
        ('ia_validacao', 'Validação por IA'),
        ('condicional_complexa', 'Condicional Complexa'),
    ]

    TIPO_VALIDACAO_CHOICES = [
        ('obrigatoria', 'Obrigatória'),
        ('opcional', 'Opcional'),
        ('condicional', 'Condicional'),
        ('ia_assistida', 'IA Assistida'),
        ('validacao_customizada', 'Validação Customizada'),
    ]

    ESTRATEGIA_ERRO_CHOICES = [
        ('repetir', 'Repetir Questão'),
        ('pular', 'Pular Questão'),
        ('redirecionar', 'Redirecionar'),
        ('finalizar', 'Finalizar Fluxo'),
        ('escalar_humano', 'Escalar para Humano'),
    ]

    fluxo = models.ForeignKey(
        FluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='questoes',
        verbose_name="Fluxo"
    )

    indice = models.PositiveIntegerField(
        verbose_name="Índice",
        help_text="Ordem da questão no fluxo (1, 2, 3...)"
    )

    titulo = models.CharField(
        max_length=255,
        verbose_name="Título da Questão",
        help_text="Texto da pergunta para o usuário"
    )

    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição adicional ou instruções"
    )

    tipo_questao = models.CharField(
        max_length=20,
        choices=TIPO_QUESTAO_CHOICES,
        default='texto',
        verbose_name="Tipo de Questão"
    )

    tipo_validacao = models.CharField(
        max_length=25,
        choices=TIPO_VALIDACAO_CHOICES,
        default='obrigatoria',
        verbose_name="Tipo de Validação"
    )

    # Configurações de resposta
    opcoes_resposta = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Opções de Resposta",
        help_text="Lista de opções para questões de seleção"
    )

    resposta_padrao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Resposta Padrão",
        help_text="Resposta padrão ou placeholder"
    )

    # Validações
    regex_validacao = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Regex de Validação",
        help_text="Expressão regular para validação customizada"
    )

    tamanho_minimo = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tamanho Mínimo",
        help_text="Tamanho mínimo da resposta"
    )

    tamanho_maximo = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tamanho Máximo",
        help_text="Tamanho máximo da resposta"
    )

    valor_minimo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor Mínimo",
        help_text="Valor mínimo para questões numéricas"
    )

    valor_maximo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor Máximo",
        help_text="Valor máximo para questões numéricas"
    )

    # Lógica condicional básica (mantida para compatibilidade)
    questao_dependencia = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Questão de Dependência",
        help_text="Questão que deve ser respondida antes desta"
    )

    valor_dependencia = models.TextField(
        null=True,
        blank=True,
        verbose_name="Valor de Dependência",
        help_text="Valor específico da questão de dependência para mostrar esta"
    )

    # Sistema de roteamento inteligente
    roteamento_respostas = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name="Roteamento por Respostas",
        help_text="Mapeamento de respostas para próximas questões: {resposta: questao_id}"
    )

    questao_padrao_proxima = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questoes_anteriores_padrao',
        verbose_name="Questão Padrão Próxima",
        help_text="Questão padrão caso resposta não tenha roteamento específico"
    )

    # Configurações de validação por IA
    prompt_ia_validacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Prompt para IA",
        help_text="Prompt específico para validação da resposta por IA"
    )

    criterios_ia = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Critérios de IA",
        help_text="Critérios específicos para validação: {criterio: peso}"
    )

    # Controle de repetições e erros
    max_tentativas = models.PositiveIntegerField(
        default=3,
        verbose_name="Máximo de Tentativas",
        help_text="Número máximo de tentativas antes de aplicar estratégia de erro"
    )

    estrategia_erro = models.CharField(
        max_length=20,
        choices=ESTRATEGIA_ERRO_CHOICES,
        default='repetir',
        verbose_name="Estratégia de Erro"
    )

    questao_erro_redirecionamento = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questoes_erro_origem',
        verbose_name="Questão para Redirecionamento de Erro"
    )

    # Mensagens personalizadas
    mensagem_erro_padrao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem de Erro Padrão",
        help_text="Mensagem exibida quando resposta é inválida"
    )

    mensagem_tentativa_esgotada = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem Tentativas Esgotadas",
        help_text="Mensagem quando máximo de tentativas é atingido"
    )

    instrucoes_resposta_correta = models.TextField(
        null=True,
        blank=True,
        verbose_name="Instruções para Resposta Correta",
        help_text="Orientações sobre como responder corretamente"
    )

    # Campos de controle
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativa"
    )

    permite_voltar = models.BooleanField(
        default=True,
        verbose_name="Permite Voltar",
        help_text="Se o usuário pode voltar para esta questão"
    )

    permite_editar = models.BooleanField(
        default=True,
        verbose_name="Permite Editar",
        help_text="Se a resposta pode ser editada após enviada"
    )

    ordem_exibicao = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordem de Exibição",
        help_text="Ordem para exibição na interface"
    )

    # Integração com N8N
    webhook_n8n_validacao = models.URLField(
        null=True,
        blank=True,
        verbose_name="Webhook N8N para Validação",
        help_text="URL do webhook N8N para validação customizada"
    )

    webhook_n8n_pos_resposta = models.URLField(
        null=True,
        blank=True,
        verbose_name="Webhook N8N Pós-Resposta",
        help_text="URL do webhook N8N executado após resposta válida"
    )

    # Configurações dinâmicas
    opcoes_dinamicas_fonte = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('planos_internet', 'Planos de Internet'),
            ('opcoes_vencimento', 'Opções de Vencimento'),
            ('api_externa', 'API Externa'),
            ('query_customizada', 'Query Customizada'),
        ],
        verbose_name="Fonte de Opções Dinâmicas"
    )

    query_opcoes_dinamicas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Query para Opções Dinâmicas",
        help_text="Query SQL ou configuração para buscar opções dinamicamente"
    )

    # Configurações de contexto
    variaveis_contexto = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name="Variáveis de Contexto",
        help_text="Variáveis que podem ser usadas na questão: {nome: valor}"
    )

    template_questao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Template da Questão",
        help_text="Template com variáveis: 'Olá {{nome}}, qual seu plano preferido?'"
    )

    class Meta:
        db_table = 'questoes_fluxo'
        verbose_name = "Questão do Fluxo"
        verbose_name_plural = "🤖 02. Questões do Fluxo"
        ordering = ['fluxo', 'indice']
        unique_together = [('fluxo', 'indice')]
        indexes = [
            models.Index(fields=['fluxo', 'indice']),
            models.Index(fields=['tipo_questao']),
            models.Index(fields=['ativo']),
        ]

    def __str__(self):
        return f"{self.fluxo.nome} - Q{self.indice}: {self.titulo}"

    def get_opcoes_formatadas(self, contexto=None):
        """Retorna opções de resposta formatadas (estáticas ou dinâmicas)"""
        # Opções dinâmicas
        if self.opcoes_dinamicas_fonte:
            return self._get_opcoes_dinamicas(contexto)

        # Opções estáticas
        if self.opcoes_resposta and isinstance(self.opcoes_resposta, list):
            return self.opcoes_resposta
        return []

    def _get_opcoes_dinamicas(self, contexto=None):
        """Busca opções dinâmicas baseadas na fonte configurada"""
        if self.opcoes_dinamicas_fonte == 'planos_internet':
            planos = PlanoInternet.objects.filter(ativo=True).order_by('ordem_exibicao', 'valor_mensal')
            opcoes = []
            for plano in planos:
                opcoes.append({
                    'valor': str(plano.id),
                    'texto': f"{plano.nome} - {plano.get_velocidade_formatada()} - {plano.get_valor_formatado()}",
                    'dados_extras': {
                        'id_sistema_externo': plano.id_sistema_externo,
                        'valor_mensal': float(plano.valor_mensal),
                        'velocidade': plano.velocidade_download
                    }
                })
            # Adicionar opção "Ver mais"
            opcoes.append({
                'valor': 'ver_mais_planos',
                'texto': '📋 Ver mais opções de planos',
                'tipo': 'acao_especial'
            })
            return opcoes

        elif self.opcoes_dinamicas_fonte == 'opcoes_vencimento':
            vencimentos = OpcaoVencimento.objects.filter(ativo=True).order_by('ordem_exibicao')
            opcoes = []
            for venc in vencimentos:
                opcoes.append({
                    'valor': str(venc.id),
                    'texto': f"Dia {venc.dia_vencimento} - {venc.descricao}",
                    'dados_extras': {
                        'dia_vencimento': venc.dia_vencimento
                    }
                })
            # Adicionar opção "Ver mais"
            opcoes.append({
                'valor': 'ver_mais_vencimentos',
                'texto': '📅 Ver mais opções de vencimento',
                'tipo': 'acao_especial'
            })
            return opcoes

        elif self.opcoes_dinamicas_fonte == 'query_customizada' and self.query_opcoes_dinamicas:
            return self._executar_query_customizada(contexto)

        return []

    def _executar_query_customizada(self, contexto=None):
        """Executa query customizada para buscar opções"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(self.query_opcoes_dinamicas)
                resultados = cursor.fetchall()
                opcoes = []
                for resultado in resultados:
                    opcoes.append({
                        'valor': str(resultado[0]),
                        'texto': str(resultado[1]),
                        'dados_extras': resultado[2] if len(resultado) > 2 else {}
                    })
                return opcoes
        except Exception as e:
            logger.error("Erro ao executar query customizada: %s", e)
            return []

    def get_questao_renderizada(self, contexto=None):
        """Retorna a questão com template processado"""
        if self.template_questao and contexto:
            try:
                from django.template import Template, Context
                template = Template(self.template_questao)
                return template.render(Context(contexto))
            except:
                pass
        return self.titulo

    def validar_resposta(self, resposta, contexto=None, tentativa=1):
        """
        Valida uma resposta baseada nas regras da questão (com IA e roteamento)
        Retorna (valido, mensagem_erro, dados_extras)
        """
        if not resposta and self.tipo_validacao == 'obrigatoria':
            return False, self._get_mensagem_erro_personalizada("obrigatoria"), {}

        if not resposta:
            return True, "", {}

        # Validação por IA primeiro (se configurada)
        if self.tipo_validacao == 'ia_assistida' and self.prompt_ia_validacao:
            resultado_ia = self._validar_com_ia(resposta, contexto)
            if not resultado_ia['valido']:
                return False, resultado_ia['mensagem'], resultado_ia

        # Validações tradicionais
        resultado_tradicional = self._validar_tradicional(resposta)
        if not resultado_tradicional[0]:
            return resultado_tradicional

        # Validação específica para opções dinâmicas
        if self.opcoes_dinamicas_fonte:
            resultado_dinamico = self._validar_opcoes_dinamicas(resposta, contexto)
            if not resultado_dinamico[0]:
                return resultado_dinamico

        # Webhook N8N para validação customizada
        if self.webhook_n8n_validacao:
            resultado_webhook = self._validar_com_webhook_n8n(resposta, contexto, tentativa)
            if not resultado_webhook[0]:
                return resultado_webhook

        return True, "", {'resposta_processada': resposta}

    def _validar_tradicional(self, resposta):
        """Validações tradicionais (mantidas para compatibilidade)"""
        # Validação de tamanho
        if self.tamanho_minimo and len(str(resposta)) < self.tamanho_minimo:
            return False, f"Resposta deve ter pelo menos {self.tamanho_minimo} caracteres", {}

        if self.tamanho_maximo and len(str(resposta)) > self.tamanho_maximo:
            return False, f"Resposta deve ter no máximo {self.tamanho_maximo} caracteres", {}

        # Validação de regex
        if self.regex_validacao:
            import re
            if not re.match(self.regex_validacao, str(resposta)):
                return False, self._get_mensagem_erro_personalizada("formato"), {}

        # Validação de valores numéricos
        if self.tipo_questao == 'numero':
            try:
                valor = float(resposta)
                if self.valor_minimo is not None and valor < self.valor_minimo:
                    return False, f"Valor deve ser maior ou igual a {self.valor_minimo}", {}
                if self.valor_maximo is not None and valor > self.valor_maximo:
                    return False, f"Valor deve ser menor ou igual a {self.valor_maximo}", {}
            except ValueError:
                return False, "Resposta deve ser um número válido", {}

        # Validação de email
        if self.tipo_questao == 'email':
            from django.core.validators import EmailValidator
            validator = EmailValidator()
            try:
                validator(resposta)
            except:
                return False, "Email inválido", {}

        # Validação de opções estáticas
        if self.tipo_questao in ['select', 'multiselect'] and self.opcoes_resposta:
            if self.tipo_questao == 'select':
                if resposta not in self.opcoes_resposta:
                    return False, "Opção selecionada não é válida", {}
            else:  # multiselect
                if not isinstance(resposta, list):
                    return False, "Resposta deve ser uma lista de opções", {}
                for opcao in resposta:
                    if opcao not in self.opcoes_resposta:
                        return False, f"Opção '{opcao}' não é válida", {}

        return True, "", {}

    def _validar_opcoes_dinamicas(self, resposta, contexto=None):
        """Valida respostas para opções dinâmicas"""
        opcoes = self.get_opcoes_formatadas(contexto)
        valores_validos = [opcao['valor'] for opcao in opcoes]

        if resposta not in valores_validos:
            return False, "Opção selecionada não é válida para as opções disponíveis", {}

        # Verificar se é uma ação especial
        opcao_selecionada = next((op for op in opcoes if op['valor'] == resposta), None)
        if opcao_selecionada and opcao_selecionada.get('tipo') == 'acao_especial':
            return True, "", {
                'acao_especial': True,
                'tipo_acao': opcao_selecionada['valor'],
                'dados_opcao': opcao_selecionada
            }

        return True, "", {'opcao_selecionada': opcao_selecionada}

    def _validar_com_ia(self, resposta, contexto=None):
        """Validação usando IA (implementação base - integrar com seu provedor de IA)"""
        try:
            # Aqui você integraria com sua IA (OpenAI, Claude, etc.)
            # Por enquanto, retorna validação básica
            prompt = self.prompt_ia_validacao.replace('{{resposta}}', str(resposta))
            if contexto:
                for chave, valor in contexto.items():
                    prompt = prompt.replace(f'{{{{{chave}}}}}', str(valor))

            # Implementar chamada para IA aqui
            # resultado_ia = chamar_ia(prompt, self.criterios_ia)

            return {
                'valido': True,
                'mensagem': '',
                'confianca': 0.95,
                'sugestoes': []
            }
        except Exception as e:
            return {
                'valido': False,
                'mensagem': f"Erro na validação por IA: {str(e)}",
                'confianca': 0.0,
                'sugestoes': []
            }

    def _validar_com_webhook_n8n(self, resposta, contexto=None, tentativa=1):
        """Validação usando webhook N8N"""
        try:
            import requests
            import json

            payload = {
                'questao_id': self.id,
                'resposta': resposta,
                'contexto': contexto or {},
                'tentativa': tentativa,
                'dados_questao': {
                    'titulo': self.titulo,
                    'tipo': self.tipo_questao,
                    'criterios_ia': self.criterios_ia
                }
            }

            response = requests.post(
                self.webhook_n8n_validacao,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                resultado = response.json()
                return resultado.get('valido', True), resultado.get('mensagem', ''), resultado
            else:
                return False, "Erro na validação externa", {}

        except Exception as e:
            # Em caso de erro, não bloquear o fluxo
            return True, "", {'erro_webhook': str(e)}

    def _get_mensagem_erro_personalizada(self, tipo_erro):
        """Retorna mensagem de erro personalizada"""
        if self.mensagem_erro_padrao:
            return self.mensagem_erro_padrao

        mensagens = {
            'obrigatoria': "Esta questão é obrigatória",
            'formato': "Formato da resposta não é válido",
            'tentativas_esgotadas': self.mensagem_tentativa_esgotada or "Número máximo de tentativas atingido"
        }

        mensagem = mensagens.get(tipo_erro, "Resposta inválida")

        if self.instrucoes_resposta_correta:
            mensagem += f"\n\n💡 {self.instrucoes_resposta_correta}"

        return mensagem

    def deve_ser_exibida(self, respostas_anteriores):
        """
        Verifica se a questão deve ser exibida baseada em dependências
        """
        if not self.questao_dependencia:
            return True

        # Buscar resposta da questão de dependência
        resposta_dependencia = respostas_anteriores.get(str(self.questao_dependencia.indice))

        if not resposta_dependencia:
            return False

        # Se não há valor específico de dependência, sempre exibe
        if not self.valor_dependencia:
            return True

        # Verificar se a resposta corresponde ao valor esperado
        return str(resposta_dependencia) == str(self.valor_dependencia)

    def get_proxima_questao_inteligente(self, resposta, contexto=None):
        """
        Determina a próxima questão baseada na resposta (ROTEAMENTO INTELIGENTE)
        Retorna (questao_obj, acao_especial, dados_extras)
        """
        # 1. Verificar roteamento específico por resposta
        if self.roteamento_respostas and str(resposta) in self.roteamento_respostas:
            questao_id = self.roteamento_respostas[str(resposta)]
            try:
                proxima_questao = QuestaoFluxo.objects.get(id=questao_id, ativo=True)
                return proxima_questao, None, {'roteamento_tipo': 'especifico'}
            except QuestaoFluxo.DoesNotExist:
                pass

        # 2. Verificar ações especiais (ver mais planos, ver mais vencimentos, etc.)
        if self.opcoes_dinamicas_fonte:
            acao_especial = self._processar_acao_especial(resposta, contexto)
            if acao_especial:
                return None, acao_especial, {'roteamento_tipo': 'acao_especial'}

        # 3. Questão padrão próxima (se configurada)
        if self.questao_padrao_proxima:
            return self.questao_padrao_proxima, None, {'roteamento_tipo': 'padrao'}

        # 4. Próxima questão por índice (comportamento tradicional)
        proxima_por_indice = self.fluxo.get_proxima_questao(self.indice)
        if proxima_por_indice:
            return proxima_por_indice, None, {'roteamento_tipo': 'sequencial'}

        # 5. Fim do fluxo
        return None, 'finalizar_fluxo', {'roteamento_tipo': 'fim_fluxo'}

    def _processar_acao_especial(self, resposta, contexto=None):
        """Processa ações especiais como 'ver mais planos'"""
        if resposta == 'ver_mais_planos':
            # Buscar questão específica para mais planos
            questao_mais_planos = self.fluxo.questoes.filter(
                tipo_questao='planos_internet',
                titulo__icontains='mais planos'
            ).first()

            if questao_mais_planos:
                return {
                    'tipo': 'redirecionar_questao',
                    'questao_destino': questao_mais_planos.id,
                    'mensagem': 'Aqui estão mais opções de planos para você:'
                }

            return {
                'tipo': 'mostrar_opcoes_expandidas',
                'fonte': 'planos_internet_completo',
                'mensagem': 'Vou mostrar todos os planos disponíveis:'
            }

        elif resposta == 'ver_mais_vencimentos':
            questao_mais_vencimentos = self.fluxo.questoes.filter(
                tipo_questao='vencimentos',
                titulo__icontains='mais vencimentos'
            ).first()

            if questao_mais_vencimentos:
                return {
                    'tipo': 'redirecionar_questao',
                    'questao_destino': questao_mais_vencimentos.id,
                    'mensagem': 'Aqui estão mais opções de vencimento:'
                }

            return {
                'tipo': 'mostrar_opcoes_expandidas',
                'fonte': 'opcoes_vencimento_completo',
                'mensagem': 'Vou mostrar todas as opções de vencimento:'
            }

        return None

    def aplicar_estrategia_erro(self, tentativa_atual, contexto=None):
        """
        Aplica estratégia de erro baseada no número de tentativas
        Retorna (acao, dados_acao)
        """
        if tentativa_atual >= self.max_tentativas:
            if self.estrategia_erro == 'repetir':
                return 'repetir_questao', {
                    'mensagem': self._get_mensagem_erro_personalizada("tentativas_esgotadas"),
                    'reiniciar_tentativas': True
                }

            elif self.estrategia_erro == 'pular':
                proxima_questao = self.fluxo.get_proxima_questao(self.indice)
                return 'pular_questao', {
                    'questao_destino': proxima_questao.id if proxima_questao else None,
                    'mensagem': "Vamos pular esta questão e continuar."
                }

            elif self.estrategia_erro == 'redirecionar' and self.questao_erro_redirecionamento:
                return 'redirecionar', {
                    'questao_destino': self.questao_erro_redirecionamento.id,
                    'mensagem': "Vou te ajudar de uma forma diferente."
                }

            elif self.estrategia_erro == 'escalar_humano':
                return 'escalar_humano', {
                    'mensagem': "Vou transferir você para um atendente humano que pode te ajudar melhor.",
                    'motivo': f"Dificuldade na questão: {self.titulo}"
                }

            elif self.estrategia_erro == 'finalizar':
                return 'finalizar_fluxo', {
                    'mensagem': "Não conseguimos prosseguir. Obrigado pelo seu tempo.",
                    'motivo': 'tentativas_esgotadas'
                }

        # Tentativa normal - repetir questão
        return 'repetir_questao', {
            'mensagem': self._get_mensagem_erro_personalizada("formato"),
            'tentativas_restantes': self.max_tentativas - tentativa_atual
        }

    def executar_webhook_pos_resposta(self, resposta, contexto=None):
        """Executa webhook N8N após resposta válida"""
        if not self.webhook_n8n_pos_resposta:
            return True

        try:
            import requests

            payload = {
                'questao_id': self.id,
                'resposta': resposta,
                'contexto': contexto or {},
                'dados_questao': {
                    'titulo': self.titulo,
                    'tipo': self.tipo_questao,
                    'indice': self.indice
                },
                'timestamp': timezone.now().isoformat()
            }

            response = requests.post(
                self.webhook_n8n_pos_resposta,
                json=payload,
                timeout=5  # Timeout menor para não bloquear o fluxo
            )

            return response.status_code == 200

        except Exception as e:
            # Log do erro, mas não bloquear o fluxo
            logger.error("Erro ao executar webhook pos-resposta: %s", e)
            return False

    def clean(self):
        """Validação personalizada do modelo"""
        from django.core.exceptions import ValidationError

        # Se não tem índice, calcular automaticamente
        if not self.indice and self.fluxo:
            ultimo_indice = self.fluxo.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0
            self.indice = ultimo_indice + 1

        # Verificar se o índice já existe para este fluxo
        if self.pk:  # Se é uma edição
            existing = QuestaoFluxo.objects.filter(
                fluxo=self.fluxo,
                indice=self.indice
            ).exclude(pk=self.pk).exists()
        else:  # Se é uma criação
            existing = QuestaoFluxo.objects.filter(
                fluxo=self.fluxo,
                indice=self.indice
            ).exists()

        if existing:
            raise ValidationError({
                'indice': f'Já existe uma questão com índice {self.indice} neste fluxo.'
            })

        super().clean()

    def save(self, *args, **kwargs):
        # Garantir que o índice seja preenchido antes de salvar
        if not self.indice and self.fluxo:
            ultimo_indice = self.fluxo.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0
            self.indice = ultimo_indice + 1

        super().save(*args, **kwargs)


class TentativaResposta(TenantMixin):
    """
    Modelo para rastrear tentativas de resposta em questões
    Essencial para controle de IA e estratégias de erro
    """
    atendimento = models.ForeignKey(
        'AtendimentoFluxo',
        on_delete=models.CASCADE,
        related_name='tentativas_respostas',
        verbose_name="Atendimento"
    )

    questao = models.ForeignKey(
        QuestaoFluxo,
        on_delete=models.CASCADE,
        related_name='tentativas',
        verbose_name="Questão"
    )

    tentativa_numero = models.PositiveIntegerField(
        verbose_name="Número da Tentativa"
    )

    resposta_original = models.TextField(
        verbose_name="Resposta Original"
    )

    resposta_processada = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resposta Processada"
    )

    valida = models.BooleanField(
        default=False,
        verbose_name="Resposta Válida"
    )

    mensagem_erro = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem de Erro"
    )

    # Dados da validação por IA
    resultado_ia = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado da IA",
        help_text="Resultado completo da validação por IA"
    )

    confianca_ia = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Confiança da IA",
        help_text="Score de confiança da IA (0.0 a 1.0)"
    )

    # Dados do webhook N8N
    resultado_webhook = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado do Webhook N8N"
    )

    # Estratégia aplicada
    estrategia_aplicada = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Estratégia Aplicada"
    )

    # Dados de contexto
    contexto_tentativa = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Contexto da Tentativa"
    )

    # Timestamps
    data_tentativa = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data da Tentativa"
    )

    tempo_resposta_segundos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo de Resposta (segundos)"
    )

    # Dados de auditoria
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )

    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent"
    )

    class Meta:
        db_table = 'tentativas_resposta'
        verbose_name = 'Tentativa de Resposta'
        verbose_name_plural = "🔧 02. Tentativas de Resposta"
        ordering = ['-data_tentativa']
        indexes = [
            models.Index(fields=['atendimento', 'questao']),
            models.Index(fields=['tentativa_numero']),
            models.Index(fields=['valida']),
            models.Index(fields=['data_tentativa']),
        ]
        unique_together = [('atendimento', 'questao', 'tentativa_numero')]

    def __str__(self):
        return f"{self.atendimento} - Q{self.questao.indice} - Tentativa {self.tentativa_numero}"

    def get_tempo_resposta_formatado(self):
        """Retorna tempo de resposta formatado"""
        if self.tempo_resposta_segundos:
            if self.tempo_resposta_segundos < 60:
                return f"{self.tempo_resposta_segundos}s"
            else:
                minutos = self.tempo_resposta_segundos // 60
                segundos = self.tempo_resposta_segundos % 60
                return f"{minutos}m {segundos}s"
        return "N/A"

    def get_resultado_ia_resumido(self):
        """Retorna resumo do resultado da IA"""
        if self.resultado_ia:
            return {
                'valido': self.resultado_ia.get('valido', False),
                'confianca': self.confianca_ia,
                'sugestoes': len(self.resultado_ia.get('sugestoes', [])),
                'criterios_atendidos': len([c for c in self.resultado_ia.get('criterios', {}).values() if c])
            }
        return None


class AtendimentoFluxo(TenantMixin):
    """
    Modelo para controlar uma sessão de atendimento específica
    Relaciona lead/prospecto com um fluxo e controla o progresso
    """
    STATUS_CHOICES = [
        ('iniciado', 'Iniciado'),
        ('em_andamento', 'Em Andamento'),
        ('pausado', 'Pausado'),
        ('completado', 'Completado'),
        ('abandonado', 'Abandonado'),
        ('erro', 'Erro'),
        ('cancelado', 'Cancelado'),
        ('aguardando_validacao', 'Aguardando Validação'),
        ('validado', 'Validado'),
        ('rejeitado', 'Rejeitado'),
    ]

    # Relacionamentos principais
    lead = models.ForeignKey(
        'leads.LeadProspecto',
        on_delete=models.CASCADE,
        related_name='atendimentos_fluxo',
        verbose_name="Lead/Prospecto"
    )

    fluxo = models.ForeignKey(
        FluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='atendimentos',
        verbose_name="Fluxo"
    )

    # Relacionamento opcional com histórico de contato
    historico_contato = models.ForeignKey(
        'leads.HistoricoContato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_fluxo',
        verbose_name="Histórico de Contato"
    )

    # Controle de progresso
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='iniciado',
        verbose_name="Status"
    )

    questao_atual = models.PositiveIntegerField(
        default=1,
        verbose_name="Questão Atual",
        help_text="Índice da questão atual no fluxo"
    )

    # Posicao no modo fluxo visual (nodo atual)
    nodo_atual = models.ForeignKey(
        'NodoFluxoAtendimento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_atuais',
        verbose_name="Nodo Atual",
        help_text="Nodo atual no modo fluxo visual"
    )

    total_questoes = models.PositiveIntegerField(
        verbose_name="Total de Questões",
        help_text="Total de questões no fluxo"
    )

    questoes_respondidas = models.PositiveIntegerField(
        default=0,
        verbose_name="Questões Respondidas"
    )

    # Controle de tempo
    data_inicio = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data de Início"
    )

    data_ultima_atividade = models.DateTimeField(
        auto_now=True,
        verbose_name="Data da Última Atividade"
    )

    data_conclusao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Conclusão"
    )

    tempo_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo Total (segundos)",
        help_text="Tempo total para completar o fluxo"
    )

    # Controle de tentativas
    tentativas_atual = models.PositiveIntegerField(
        default=0,
        verbose_name="Tentativas Atuais"
    )

    max_tentativas = models.PositiveIntegerField(
        default=3,
        verbose_name="Máximo de Tentativas"
    )

    # Dados do atendimento
    dados_respostas = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name="Dados das Respostas",
        help_text="JSON com todas as respostas do usuário"


    )

    observacoes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações",
        help_text="Observações sobre o atendimento"
    )

    # Campos de auditoria
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )

    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent"
    )

    dispositivo = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Dispositivo",
        help_text="Tipo de dispositivo usado"
    )

    # Campos para integração
    id_externo = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID Externo",
        help_text="ID em sistema externo (ex: Hubsoft)"
    )

    resultado_final = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado Final",
        help_text="Resultado processado do atendimento"
    )

    score_qualificacao = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Score de Qualificação",
        help_text="Score calculado baseado nas respostas"
    )

    class Meta:
        db_table = 'atendimentos_fluxo'
        verbose_name = "Atendimento de Fluxo"
        verbose_name_plural = "🤖 03. Atendimentos de Fluxo"
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['lead']),
            models.Index(fields=['fluxo']),
            models.Index(fields=['status']),
            models.Index(fields=['data_inicio']),
            models.Index(fields=['questao_atual']),
            models.Index(fields=['id_externo']),
            # Índices compostos para consultas eficientes
            models.Index(fields=['lead', 'status']),
            models.Index(fields=['fluxo', 'status']),
            models.Index(fields=['data_inicio', 'status']),
        ]

    def __str__(self):
        return f"{self.lead.nome_razaosocial} - {self.fluxo.nome} ({self.status})"

    def get_status_display(self):  # compatível com chamadas existentes
        if not self.status:
            return "Não definido"
        try:
            return StatusConfiguravel.get_label('atendimento_status', self.status)
        except Exception:
            mapping = dict(self.STATUS_CHOICES)
            return mapping.get(self.status, self.status)

    def get_progresso_percentual(self):
        """Retorna progresso em percentual"""
        if not self.total_questoes or self.total_questoes == 0:
            return 0
        return round((self.questoes_respondidas / self.total_questoes) * 100, 1)

    def get_questao_atual_obj(self):
        """Retorna objeto da questão atual"""
        return self.fluxo.get_questao_por_indice(self.questao_atual)

    def get_proxima_questao(self):
        """Retorna próxima questão a ser exibida"""
        return self.fluxo.get_proxima_questao(self.questao_atual)

    def get_questao_anterior(self):
        """Retorna questão anterior"""
        return self.fluxo.get_questao_anterior(self.questao_atual)

    def pode_avancar(self):
        """Verifica se pode avançar para próxima questão"""
        questao_atual = self.get_questao_atual_obj()
        if not questao_atual:
            return False

        # Verificar se a questão atual foi respondida
        resposta_atual = self.dados_respostas.get(str(self.questao_atual))
        if questao_atual.tipo_validacao == 'obrigatoria' and not resposta_atual:
            return False

        return True

    def pode_voltar(self):
        """Verifica se pode voltar para questão anterior"""
        questao_atual = self.get_questao_atual_obj()
        if not questao_atual:
            return False

        return questao_atual.permite_voltar and self.questao_atual > 1

    def responder_questao_inteligente(self, indice_questao, resposta, contexto=None, ip_origem=None, user_agent=None):
        """
        Registra resposta para uma questão usando sistema inteligente
        Retorna (sucesso, mensagem, proxima_acao, dados_extras)
        """
        questao = self.fluxo.get_questao_por_indice(indice_questao)
        if not questao:
            return False, "Questão não encontrada", None, {}

        # Verificar número de tentativas para esta questão
        tentativa_numero = self.tentativas_respostas.filter(questao=questao).count() + 1

        # Criar registro da tentativa
        tentativa = TentativaResposta.objects.create(
            atendimento=self,
            questao=questao,
            tentativa_numero=tentativa_numero,
            resposta_original=resposta,
            contexto_tentativa=contexto or {},
            ip_origem=ip_origem,
            user_agent=user_agent
        )

        # Validação inteligente
        valido, mensagem_erro, dados_validacao = questao.validar_resposta(resposta, contexto, tentativa_numero)

        # Atualizar tentativa com resultado
        tentativa.valida = valido
        tentativa.mensagem_erro = mensagem_erro
        tentativa.resposta_processada = dados_validacao

        # Extrair dados específicos da validação
        if 'resultado_ia' in dados_validacao:
            tentativa.resultado_ia = dados_validacao['resultado_ia']
            tentativa.confianca_ia = dados_validacao['resultado_ia'].get('confianca', 0)

        if 'resultado_webhook' in dados_validacao:
            tentativa.resultado_webhook = dados_validacao['resultado_webhook']

        tentativa.save()

        # Se resposta é válida
        if valido:
            # Executar webhook pós-resposta
            questao.executar_webhook_pos_resposta(resposta, contexto)

            # Verificar se esta questão já foi respondida antes
            questao_ja_respondida = str(indice_questao) in self.dados_respostas

            # Registrar resposta nos dados do atendimento
            self.dados_respostas[str(indice_questao)] = {
                'resposta': resposta,
                'data_resposta': timezone.now().isoformat(),
                'valida': True,
                'tentativas': tentativa_numero,
                'dados_validacao': dados_validacao
            }

            # Atualizar contadores
            if not questao_ja_respondida:
                self.questoes_respondidas += 1

            # Determinar próxima ação usando roteamento inteligente
            proxima_questao, acao_especial, dados_roteamento = questao.get_proxima_questao_inteligente(resposta, contexto)

            self.save()

            if acao_especial:
                return True, "Resposta válida", acao_especial, {
                    'dados_roteamento': dados_roteamento,
                    'dados_validacao': dados_validacao,
                    'tentativas': tentativa_numero
                }
            elif proxima_questao:
                return True, "Resposta válida", 'proxima_questao', {
                    'proxima_questao': proxima_questao,
                    'dados_roteamento': dados_roteamento,
                    'dados_validacao': dados_validacao,
                    'tentativas': tentativa_numero
                }
            else:
                return True, "Resposta válida", 'finalizar_fluxo', {
                    'dados_roteamento': dados_roteamento,
                    'dados_validacao': dados_validacao,
                    'tentativas': tentativa_numero
                }

        # Se resposta é inválida, aplicar estratégia de erro
        else:
            acao_erro, dados_acao = questao.aplicar_estrategia_erro(tentativa_numero, contexto)
            tentativa.estrategia_aplicada = acao_erro
            tentativa.save()

            return False, mensagem_erro, acao_erro, {
                'dados_acao': dados_acao,
                'tentativas': tentativa_numero,
                'max_tentativas': questao.max_tentativas,
                'dados_validacao': dados_validacao
            }

    def responder_questao(self, indice_questao, resposta, validar=True):
        """
        Método legado mantido para compatibilidade
        """
        resultado = self.responder_questao_inteligente(indice_questao, resposta)
        return resultado[0], resultado[1]

    def avancar_questao(self):
        """
        Avança para próxima questão
        Retorna (sucesso, proxima_questao)
        """
        if not self.pode_avancar():
            return False, "Não é possível avançar"

        proxima_questao = self.get_proxima_questao()
        if proxima_questao:
            self.questao_atual = proxima_questao.indice
            self.save()
            return True, proxima_questao

        # Se não há próxima questão, finalizar
        self.finalizar_atendimento()
        return True, None

    def voltar_questao(self):
        """
        Volta para questão anterior
        Retorna (sucesso, questao_anterior)
        """
        if not self.pode_voltar():
            return False, "Não é possível voltar"

        questao_anterior = self.get_questao_anterior()
        if questao_anterior:
            self.questao_atual = questao_anterior.indice
            self.save()
            return True, questao_anterior

        return False, "Questão anterior não encontrada"

    def finalizar_atendimento(self, sucesso=True):
        """
        Finaliza o atendimento
        """
        self.status = 'completado' if sucesso else 'abandonado'
        self.data_conclusao = timezone.now()

        # Calcular tempo total
        if self.data_inicio and self.data_conclusao:
            tempo_delta = self.data_conclusao - self.data_inicio
            self.tempo_total = int(tempo_delta.total_seconds())

        # Calcular score de qualificação
        self.score_qualificacao = self.calcular_score_qualificacao()

        self.save()

        # Atualizar lead se necessário
        self.atualizar_lead_com_resultados()

    def calcular_score_qualificacao(self):
        """
        Calcula score de qualificação baseado nas respostas
        """
        score = 5  # Score base

        # Lógica de cálculo baseada no tipo de fluxo e respostas
        if self.fluxo.tipo_fluxo == 'qualificacao':
            # Score baseado em respostas específicas
            for indice, dados in self.dados_respostas.items():
                questao = self.fluxo.get_questao_por_indice(int(indice))
                if questao and dados.get('valida'):
                    # Lógica específica para cada tipo de questão
                    if questao.tipo_questao == 'escala':
                        try:
                            valor = int(dados['resposta'])
                            if valor >= 8:
                                score += 2
                            elif valor >= 6:
                                score += 1
                            elif valor <= 3:
                                score -= 1
                        except:
                            pass

        return max(1, min(10, score))

    def atualizar_lead_com_resultados(self):
        """
        Atualiza o lead com resultados do atendimento
        """
        if self.status == 'completado' and self.score_qualificacao:
            # Atualizar score do lead
            self.lead.score_qualificacao = self.score_qualificacao
            self.lead.save()

            # Adicionar observações sobre o fluxo
            if self.observacoes:
                if not self.lead.observacoes:
                    self.lead.observacoes = ""
                self.lead.observacoes += f"\n\nFluxo {self.fluxo.nome} ({self.data_conclusao.strftime('%d/%m/%Y %H:%M')}):\n{self.observacoes}"
                self.lead.save()

    def get_tempo_formatado(self):
        """Retorna tempo total formatado"""
        if self.tempo_total:
            if self.tempo_total < 60:
                return f"{self.tempo_total}s"
            elif self.tempo_total < 3600:
                minutos = self.tempo_total // 60
                segundos = self.tempo_total % 60
                return f"{minutos}m {segundos}s"
            else:
                horas = self.tempo_total // 3600
                minutos = (self.tempo_total % 3600) // 60
                return f"{horas}h {minutos}m"
        return "N/A"

    def get_respostas_formatadas(self):
        """Retorna respostas formatadas para exibição"""
        respostas_formatadas = []

        if not self.total_questoes or self.total_questoes == 0:
            return respostas_formatadas

        for indice in range(1, self.total_questoes + 1):
            questao = self.fluxo.get_questao_por_indice(indice)
            if questao:
                dados_resposta = self.dados_respostas.get(str(indice), {})
                resposta = dados_resposta.get('resposta', 'Não respondida')

                respostas_formatadas.append({
                    'indice': indice,
                    'questao': questao.titulo,
                    'resposta': resposta,
                    'respondida': bool(dados_resposta),
                    'valida': dados_resposta.get('valida', False),
                    'data_resposta': dados_resposta.get('data_resposta'),
                })

        return respostas_formatadas

    def pode_ser_reiniciado(self):
        """Verifica se o atendimento pode ser reiniciado"""
        return self.status in ['completado', 'abandonado', 'cancelado']

    def reiniciar_atendimento(self):
        """Reinicia o atendimento do início"""
        if not self.pode_ser_reiniciado():
            return False

        self.status = 'iniciado'
        self.questao_atual = 1
        self.questoes_respondidas = 0
        self.dados_respostas = {}
        self.data_inicio = timezone.now()
        self.data_conclusao = None
        self.tempo_total = None
        self.tentativas_atual += 1
        self.observacoes = None
        self.resultado_final = None
        self.score_qualificacao = None

        self.save()
        return True

    def get_estatisticas_tentativas(self):
        """Retorna estatísticas das tentativas de resposta"""
        tentativas = self.tentativas_respostas.all()

        if not tentativas.exists():
            return {}

        stats = {
            'total_tentativas': tentativas.count(),
            'tentativas_validas': tentativas.filter(valida=True).count(),
            'tentativas_invalidas': tentativas.filter(valida=False).count(),
            'questoes_com_multiplas_tentativas': tentativas.values('questao').annotate(
                total=models.Count('id')
            ).filter(total__gt=1).count(),
            'media_tentativas_por_questao': tentativas.values('questao').annotate(
                total=models.Count('id')
            ).aggregate(media=models.Avg('total'))['media'] or 0,
            'tentativas_por_ia': tentativas.filter(resultado_ia__isnull=False).count(),
            'media_confianca_ia': tentativas.filter(
                confianca_ia__isnull=False
            ).aggregate(media=models.Avg('confianca_ia'))['media'] or 0,
            'estrategias_aplicadas': list(tentativas.exclude(
                estrategia_aplicada__isnull=True
            ).values_list('estrategia_aplicada', flat=True).distinct())
        }

        # Taxa de sucesso
        if stats['total_tentativas'] > 0:
            stats['taxa_sucesso'] = (stats['tentativas_validas'] / stats['total_tentativas']) * 100
        else:
            stats['taxa_sucesso'] = 0

        return stats

    def get_questoes_problematicas(self):
        """Identifica questões com maior número de erros"""
        from django.db.models import Count, Avg

        questoes_stats = self.tentativas_respostas.values(
            'questao__id', 'questao__titulo', 'questao__indice'
        ).annotate(
            total_tentativas=Count('id'),
            tentativas_invalidas=Count('id', filter=models.Q(valida=False)),
            media_confianca_ia=Avg('confianca_ia')
        ).filter(tentativas_invalidas__gt=0).order_by('-tentativas_invalidas')

        problematicas = []
        for stat in questoes_stats:
            if stat['tentativas_invalidas'] >= 2:  # 2 ou mais erros
                problematicas.append({
                    'questao_id': stat['questao__id'],
                    'titulo': stat['questao__titulo'],
                    'indice': stat['questao__indice'],
                    'total_tentativas': stat['total_tentativas'],
                    'erros': stat['tentativas_invalidas'],
                    'taxa_erro': (stat['tentativas_invalidas'] / stat['total_tentativas']) * 100,
                    'media_confianca_ia': stat['media_confianca_ia'] or 0
                })

        return problematicas

    def get_contexto_dinamico(self):
        """Gera contexto dinâmico para usar em templates de questões"""
        contexto = {
            'nome_cliente': self.lead.nome_razaosocial,
            'telefone_cliente': self.lead.telefone,
            'email_cliente': self.lead.email or '',
            'progresso_percentual': self.get_progresso_percentual(),
            'questoes_respondidas': self.questoes_respondidas,
            'total_questoes': self.total_questoes,
            'tempo_atendimento': self.get_tempo_formatado(),
            'tentativas_atuais': self.tentativas_respostas.count(),
        }

        # Adicionar dados das respostas anteriores
        for indice, dados in self.dados_respostas.items():
            contexto[f'resposta_q{indice}'] = dados.get('resposta', '')

        # Adicionar dados do lead
        if self.lead.valor:
            contexto['valor_lead'] = self.lead.get_valor_formatado()

        if self.lead.cidade:
            contexto['cidade_cliente'] = self.lead.cidade

        if self.lead.estado:
            contexto['estado_cliente'] = self.lead.estado

        return contexto


class RespostaQuestao(TenantMixin):
    """
    Modelo para armazenar respostas individuais de questões
    Permite histórico detalhado e auditoria completa
    """
    atendimento = models.ForeignKey(
        AtendimentoFluxo,
        on_delete=models.CASCADE,
        related_name='respostas_detalhadas',
        verbose_name="Atendimento"
    )

    questao = models.ForeignKey(
        QuestaoFluxo,
        on_delete=models.CASCADE,
        related_name='respostas',
        verbose_name="Questão"
    )

    resposta = models.TextField(
        verbose_name="Resposta"
    )

    resposta_processada = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resposta Processada",
        help_text="Resposta processada/validada em formato estruturado"
    )

    valida = models.BooleanField(
        default=True,
        verbose_name="Válida"
    )

    mensagem_erro = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem de Erro"
    )

    tentativas = models.PositiveIntegerField(
        default=1,
        verbose_name="Tentativas"
    )

    data_resposta = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data da Resposta"
    )

    tempo_resposta = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo de Resposta (segundos)",
        help_text="Tempo para responder esta questão"
    )

    # Campos de auditoria
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )

    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User Agent"
    )

    dados_extras = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Dados Extras",
        help_text="Dados adicionais sobre a resposta"
    )

    class Meta:
        db_table = 'respostas_questao'
        verbose_name = "Resposta de Questão"
        verbose_name_plural = "🔧 01. Respostas de Questões"
        ordering = ['atendimento', 'questao', '-data_resposta']
        indexes = [
            models.Index(fields=['atendimento', 'questao']),
            models.Index(fields=['data_resposta']),
            models.Index(fields=['valida']),
        ]

    def __str__(self):
        return f"{self.atendimento} - Q{self.questao.indice}: {self.resposta[:50]}"

    def get_tempo_resposta_formatado(self):
        """Retorna tempo de resposta formatado"""
        if self.tempo_resposta:
            if self.tempo_resposta < 60:
                return f"{self.tempo_resposta}s"
            else:
                minutos = self.tempo_resposta // 60
                segundos = self.tempo_resposta % 60
                return f"{minutos}m {segundos}s"
        return "N/A"


# ============================================================================
# SISTEMA DE FLUXOS VISUAIS (NODE-BASED)
# Paralelo ao legado (QuestaoFluxo). Ativado via FluxoAtendimento.modo_fluxo
# ============================================================================

class NodoFluxoAtendimento(TenantMixin):
    """No do fluxograma visual de atendimento."""

    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('questao', 'Questao'),
        ('condicao', 'Condicao'),
        ('acao', 'Acao'),
        ('delay', 'Delay'),
        ('finalizacao', 'Finalizacao'),
    ]

    fluxo = models.ForeignKey(
        FluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='nodos',
        verbose_name="Fluxo"
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        verbose_name="Tipo do Nodo"
    )
    subtipo = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Subtipo",
        help_text="Ex: texto, select, campo_check, enviar_whatsapp, webhook"
    )
    configuracao = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuracao",
        help_text="Config do nodo: titulo, opcoes, campo/operador/valor, template, delay"
    )
    pos_x = models.IntegerField(default=0, verbose_name="Posicao X")
    pos_y = models.IntegerField(default=0, verbose_name="Posicao Y")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")

    class Meta:
        db_table = 'atendimento_nodofluxo'
        verbose_name = "Nodo do Fluxo"
        verbose_name_plural = "Nodos do Fluxo"
        ordering = ['ordem']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.subtipo or 'sem subtipo'} (#{self.id})"


class ConexaoNodoAtendimento(TenantMixin):
    """Aresta dirigida entre dois nodos do fluxograma de atendimento."""

    TIPO_SAIDA_CHOICES = [
        ('default', 'Padrao'),
        ('true', 'Verdadeiro (Sim)'),
        ('false', 'Falso (Nao)'),
    ]

    fluxo = models.ForeignKey(
        FluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='conexoes',
        verbose_name="Fluxo"
    )
    nodo_origem = models.ForeignKey(
        NodoFluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='saidas',
        verbose_name="Nodo Origem"
    )
    nodo_destino = models.ForeignKey(
        NodoFluxoAtendimento,
        on_delete=models.CASCADE,
        related_name='entradas',
        verbose_name="Nodo Destino"
    )
    tipo_saida = models.CharField(
        max_length=10,
        choices=TIPO_SAIDA_CHOICES,
        default='default',
        verbose_name="Tipo de Saida"
    )

    class Meta:
        db_table = 'atendimento_conexaonodo'
        verbose_name = "Conexao"
        verbose_name_plural = "Conexoes"
        unique_together = [['nodo_origem', 'nodo_destino', 'tipo_saida']]

    def __str__(self):
        return f"{self.nodo_origem} → {self.nodo_destino} ({self.tipo_saida})"


class ExecucaoFluxoAtendimento(TenantMixin):
    """Fila de execucoes pendentes (delays) no fluxo visual de atendimento."""

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('executado', 'Executado'),
        ('cancelado', 'Cancelado'),
        ('erro', 'Erro'),
    ]

    atendimento = models.ForeignKey(
        'AtendimentoFluxo',
        on_delete=models.CASCADE,
        related_name='execucoes_pendentes',
        verbose_name="Atendimento"
    )
    nodo = models.ForeignKey(
        NodoFluxoAtendimento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execucoes_pendentes',
        verbose_name="Nodo"
    )
    contexto_json = models.JSONField(
        default=dict,
        verbose_name="Contexto",
        help_text="Contexto serializado para retomar execucao"
    )
    data_agendada = models.DateTimeField(
        db_index=True,
        verbose_name="Data Agendada"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name="Status"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_execucao = models.DateTimeField(null=True, blank=True)
    resultado = models.TextField(blank=True)

    class Meta:
        db_table = 'atendimento_execucao_pendente'
        verbose_name = "Execucao Pendente"
        verbose_name_plural = "Execucoes Pendentes"
        ordering = ['data_agendada']
        indexes = [
            models.Index(fields=['status', 'data_agendada']),
        ]

    def __str__(self):
        return f"Exec #{self.id} - {self.status} - {self.data_agendada}"


class LogFluxoAtendimento(TenantMixin):
    """Registro de cada passo executado no fluxo visual de atendimento."""

    STATUS_CHOICES = [
        ('sucesso', 'Sucesso'),
        ('erro', 'Erro'),
        ('aguardando', 'Aguardando Resposta'),
        ('agendado', 'Agendado (Delay)'),
    ]

    atendimento = models.ForeignKey(
        'AtendimentoFluxo',
        on_delete=models.CASCADE,
        related_name='logs_fluxo',
        verbose_name="Atendimento"
    )
    nodo = models.ForeignKey(
        NodoFluxoAtendimento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name="Nodo"
    )
    lead = models.ForeignKey(
        'leads.LeadProspecto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_fluxo_atendimento',
        verbose_name="Lead",
        db_index=True,
    )
    tipo_nodo = models.CharField(max_length=20, blank=True, verbose_name="Tipo do Nodo")
    subtipo_nodo = models.CharField(max_length=50, blank=True, verbose_name="Subtipo do Nodo")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sucesso')
    mensagem = models.TextField(blank=True, verbose_name="Mensagem/Resultado")
    dados = models.JSONField(default=dict, blank=True, verbose_name="Dados Extras")
    data_execucao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Execucao")

    class Meta:
        db_table = 'atendimento_log_fluxo'
        verbose_name = "Log do Fluxo"
        verbose_name_plural = "Logs do Fluxo"
        ordering = ['-data_execucao']
        indexes = [
            models.Index(fields=['atendimento', '-data_execucao']),
            models.Index(fields=['lead', '-data_execucao']),
        ]

    def __str__(self):
        return f"[{self.status}] {self.tipo_nodo}/{self.subtipo_nodo} - {self.data_execucao}"
