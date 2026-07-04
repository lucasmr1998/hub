"""
Registry declarativo de Data Sources do sistema de relatorios.

Cada Data Source mapeia uma entidade (model Django ou view) com:
- campos disponiveis pra filtro/agrupamento
- metricas suportadas
- como aplicar o filtro de tenant

Padrao espelha `apps/comercial/crm/services/automacao_condicoes.py` (registry
via decorator). Adicionar uma fonte nova = criar classe + decorator. Zero
mudanca no engine de query.

NUNCA expor SQL cru pro usuario — sempre ORM. Filtros validados contra schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


REGISTRY: dict[str, 'DataSource'] = {}


@dataclass
class FieldSpec:
    """Spec de um campo expostado pelo data source."""
    label: str
    tipo: str  # 'string' | 'choice' | 'integer' | 'decimal' | 'datetime' | 'date' | 'bool' | 'json'
    granularidades: list = field(default_factory=list)  # so pra datetime: ['dia','semana','mes','ano']
    choices: Optional[list] = None  # pra tipo='choice', lista [(valor, label)]
    choices_from: Optional[str] = None  # 'app.Model' pra carregar dinamico


@dataclass
class DataSource:
    slug: str
    label: str
    model_path: str  # 'app.Model' pra resolver lazy
    manager: str = 'objects'  # ja filtra tenant via TenantManager
    descricao: str = ''
    campos: dict = field(default_factory=dict)
    metricas: list = field(default_factory=lambda: ['count'])
    # default order_by ao tabular
    order_by_padrao: str = '-id'

    def resolve_model(self):
        """Lazy import pra evitar circular imports."""
        from django.apps import apps
        app_label, model_name = self.model_path.split('.')
        return apps.get_model(app_label, model_name)

    def get_manager(self):
        return getattr(self.resolve_model(), self.manager)


def registrar(ds: DataSource):
    """Registra um data source no REGISTRY."""
    REGISTRY[ds.slug] = ds
    return ds


def get(slug: str) -> Optional[DataSource]:
    return REGISTRY.get(slug)


def todos() -> list[DataSource]:
    return list(REGISTRY.values())


# ============================================================================
# REGISTRY — data sources implementados no MVP
# ============================================================================

registrar(DataSource(
    slug='oportunidade',
    label='Oportunidades',
    model_path='crm.OportunidadeVenda',
    descricao='Oportunidades do pipeline comercial (com lead, estagio, valor, responsavel).',
    campos={
        'titulo':                FieldSpec('Titulo', 'string'),
        'valor_estimado':        FieldSpec('Valor estimado', 'decimal'),
        'probabilidade':         FieldSpec('Probabilidade (%)', 'integer'),
        'prioridade':            FieldSpec('Prioridade', 'choice', choices=[
            ('baixa','Baixa'), ('normal','Normal'), ('alta','Alta'), ('urgente','Urgente'),
        ]),
        'origem_crm':            FieldSpec('Origem CRM', 'string'),
        'data_criacao':          FieldSpec('Criada em', 'datetime', granularidades=['dia','semana','mes','ano']),
        'data_fechamento_real':  FieldSpec('Fechada em', 'datetime', granularidades=['dia','semana','mes','ano']),
        'data_entrada_estagio':  FieldSpec('Entrou no estagio em', 'datetime'),
        'motivo_perda_categoria': FieldSpec('Motivo de perda (categoria legado)', 'choice'),
        'motivo_perda_ref__nome': FieldSpec('Motivo de perda (catalogo)', 'choice', choices_from='crm.MotivoPerda'),
        'estagio__is_final_perdido': FieldSpec('Estagio = Perdido', 'bool'),
        'estagio__is_final_ganho':  FieldSpec('Estagio = Ganho', 'bool'),
        'estagio__nome':         FieldSpec('Estagio', 'choice', choices_from='crm.PipelineEstagio'),
        'estagio__tipo':         FieldSpec('Tipo de estagio', 'choice'),
        'pipeline__nome':        FieldSpec('Pipeline', 'choice', choices_from='crm.Pipeline'),
        'responsavel__username': FieldSpec('Vendedor (login)', 'string'),
        'responsavel__first_name': FieldSpec('Vendedor (nome)', 'string'),
        'lead__nome_razaosocial': FieldSpec('Nome do lead', 'string'),
        'lead__cidade':          FieldSpec('Cidade', 'string'),
        'lead__estado':          FieldSpec('UF', 'string'),
        'lead__bairro':          FieldSpec('Bairro', 'string'),
        'lead__origem':          FieldSpec('Origem do lead', 'choice'),
        'lead__canal_entrada':   FieldSpec('Canal de entrada', 'choice'),
    },
    metricas=['count', 'sum:valor_estimado', 'avg:valor_estimado', 'avg:probabilidade'],
    order_by_padrao='-data_criacao',
))

registrar(DataSource(
    slug='lead',
    label='Leads',
    model_path='leads.LeadProspecto',
    descricao='Leads do funil (origem, cidade, status, etc).',
    campos={
        'nome_razaosocial':      FieldSpec('Nome', 'string'),
        'origem':                FieldSpec('Origem', 'choice'),
        'canal_entrada':         FieldSpec('Canal', 'choice'),
        'tipo_entrada':          FieldSpec('Tipo entrada', 'choice'),
        'cidade':                FieldSpec('Cidade', 'string'),
        'estado':                FieldSpec('UF', 'string'),
        'bairro':                FieldSpec('Bairro', 'string'),
        'status_api':            FieldSpec('Status API', 'choice'),
        'documentacao_validada': FieldSpec('Docs validados', 'bool'),
        'score_status':          FieldSpec('Score externo', 'choice'),
        'data_cadastro':         FieldSpec('Cadastrado em', 'datetime', granularidades=['dia','semana','mes','ano']),
        'data_atualizacao':      FieldSpec('Atualizado em', 'datetime'),
        'data_ultimo_contato':   FieldSpec('Ultimo contato', 'datetime'),
        'valor':                 FieldSpec('Valor estimado', 'decimal'),
        'score_qualificacao':    FieldSpec('Score qualificacao', 'integer'),
        'campanha_origem__nome': FieldSpec('Campanha origem', 'string'),
    },
    metricas=['count', 'avg:score_qualificacao', 'sum:valor'],
    order_by_padrao='-data_cadastro',
))

registrar(DataSource(
    slug='tarefa',
    label='Tarefas CRM',
    model_path='crm.TarefaCRM',
    descricao='Tarefas de follow-up (pendentes, vencidas, concluidas).',
    campos={
        'tipo':              FieldSpec('Tipo', 'choice'),
        'status':            FieldSpec('Status', 'choice', choices=[
            ('pendente','Pendente'), ('em_andamento','Em andamento'),
            ('concluida','Concluida'), ('cancelada','Cancelada'), ('vencida','Vencida'),
        ]),
        'prioridade':        FieldSpec('Prioridade', 'choice'),
        'responsavel__username': FieldSpec('Responsavel', 'string'),
        'data_criacao':      FieldSpec('Criada em', 'datetime', granularidades=['dia','semana','mes']),
        'data_vencimento':   FieldSpec('Vencimento', 'datetime'),
        'data_conclusao':    FieldSpec('Concluida em', 'datetime'),
    },
    metricas=['count'],
    order_by_padrao='-data_criacao',
))

registrar(DataSource(
    slug='venda',
    label='Vendas (CRM)',
    model_path='crm.Venda',
    descricao='Vendas registradas no CRM (com valor, status, lead).',
    campos={
        'valor':           FieldSpec('Valor', 'decimal'),
        'status':          FieldSpec('Status', 'choice'),
        'data_venda':      FieldSpec('Data da venda', 'datetime', granularidades=['dia','semana','mes','ano']),
        'plano__nome':     FieldSpec('Plano', 'string'),
        'lead__cidade':    FieldSpec('Cidade', 'string'),
        'lead__origem':    FieldSpec('Origem do lead', 'choice'),
    },
    metricas=['count', 'sum:valor', 'avg:valor'],
    order_by_padrao='-data_venda',
))

registrar(DataSource(
    slug='conversa',
    label='Conversas (Inbox)',
    model_path='inbox.Conversa',
    descricao='Conversas multicanal — pra TMA e volume por canal.',
    campos={
        'modo_atendimento':              FieldSpec('Modo', 'choice'),
        'data_abertura':                 FieldSpec('Aberta em', 'datetime', granularidades=['dia','semana','mes']),
        'data_resolucao':                FieldSpec('Resolvida em', 'datetime'),
        'tempo_primeira_resposta_seg':   FieldSpec('Tempo 1a resposta (s)', 'integer'),
    },
    metricas=['count', 'avg:tempo_primeira_resposta_seg'],
    order_by_padrao='-data_abertura',
))

registrar(DataSource(
    slug='historico_pipeline',
    label='Historico de Estagios',
    model_path='crm.HistoricoPipelineEstagio',
    descricao='Movimentos entre estagios. Util pra conversao por etapa + tempo por estagio.',
    campos={
        'estagio_anterior__nome': FieldSpec('Estagio anterior', 'choice'),
        'estagio_novo__nome':     FieldSpec('Estagio novo', 'choice'),
        'tempo_no_estagio_horas': FieldSpec('Tempo no estagio (h)', 'decimal'),
        'criado_em':              FieldSpec('Movido em', 'datetime', granularidades=['dia','semana','mes']),
        'movido_por__username':   FieldSpec('Movido por', 'string'),
    },
    metricas=['count', 'avg:tempo_no_estagio_horas'],
    order_by_padrao='-criado_em',
))

registrar(DataSource(
    slug='cliente_hubsoft',
    label='Clientes HubSoft',
    model_path='integracoes.ClienteHubsoft',
    descricao='Base de clientes HubSoft (espelho sincronizado). Pra relatorios de CS, churn, retencao, perfil demografico.',
    campos={
        # Identificacao
        'nome_razaosocial':        FieldSpec('Nome / Razao Social', 'string'),
        'cpf_cnpj':                FieldSpec('CPF/CNPJ', 'string'),
        'tipo_pessoa':             FieldSpec('Tipo Pessoa', 'choice', choices=[('pf','PF'),('pj','PJ')]),
        # Contato
        'telefone_primario':       FieldSpec('Telefone primario', 'string'),
        'email_principal':         FieldSpec('Email principal', 'string'),
        # Demografico
        'estado_civil':            FieldSpec('Estado civil', 'choice'),
        'genero':                  FieldSpec('Genero', 'choice'),
        'nacionalidade':           FieldSpec('Nacionalidade', 'string'),
        'profissao':               FieldSpec('Profissao', 'string'),
        'data_nascimento':         FieldSpec('Data nascimento', 'date', granularidades=['ano']),
        # Status + ciclo de vida
        'ativo':                   FieldSpec('Ativo', 'bool'),
        'alerta':                  FieldSpec('Tem alerta', 'bool'),
        'data_cadastro_hubsoft':   FieldSpec('Cadastrado no HubSoft em', 'datetime', granularidades=['dia','semana','mes','ano']),
        'data_atualizacao_hubsoft': FieldSpec('Ultima atualizacao HubSoft', 'datetime'),
        'data_criacao':            FieldSpec('Espelhado em', 'datetime', granularidades=['dia','semana','mes']),
        'data_sync':               FieldSpec('Sincronizado em', 'datetime'),
        # Churn
        'churn_score':             FieldSpec('Churn score (0-100)', 'integer'),
        'churn_atualizado_em':     FieldSpec('Churn atualizado em', 'datetime'),
        # Origem / classificacao
        'origem_cliente':          FieldSpec('Origem do cliente', 'choice'),
        'motivo_contratacao':      FieldSpec('Motivo da contratacao', 'choice'),
        # Cross-modulo
        'lead__origem':            FieldSpec('Origem do lead (Hubtrix)', 'choice'),
    },
    metricas=['count', 'avg:churn_score'],
    order_by_padrao='-data_cadastro_hubsoft',
))

registrar(DataSource(
    slug='servico_hubsoft',
    label='Servicos HubSoft',
    model_path='integracoes.ServicoClienteHubsoft',
    descricao='Servicos contratados (plano, valor, status, tecnologia, vendedor). Base pra receita, churn, performance de vendedor HubSoft.',
    campos={
        # Plano + valores
        'nome':                    FieldSpec('Plano (nome)', 'string'),
        'numero_plano':            FieldSpec('Numero do plano', 'integer'),
        'id_servico':              FieldSpec('ID do plano (HubSoft)', 'integer'),
        'valor':                   FieldSpec('Valor mensal (R$)', 'decimal'),
        'tecnologia':              FieldSpec('Tecnologia', 'choice'),
        'velocidade_download':     FieldSpec('Velocidade download', 'string'),
        'velocidade_upload':       FieldSpec('Velocidade upload', 'string'),
        # Status
        'status':                  FieldSpec('Status (texto)', 'string'),
        'status_prefixo':          FieldSpec('Status', 'choice', choices=[
            ('servico_habilitado', 'Ativo'),
            ('aguardando_instalacao', 'Aguardando instalacao'),
            ('servico_suspenso', 'Suspenso'),
            ('servico_cancelado', 'Cancelado'),
        ]),
        # Datas
        'data_habilitacao':        FieldSpec('Habilitado em', 'datetime', granularidades=['dia','semana','mes','ano']),
        'data_cancelamento':       FieldSpec('Cancelado em', 'datetime', granularidades=['dia','semana','mes','ano']),
        'data_atualizacao_servico': FieldSpec('Atualizado em', 'datetime'),
        'data_sync':               FieldSpec('Sincronizado em', 'datetime'),
        'vigencia_meses':          FieldSpec('Vigencia (meses)', 'integer'),
        # Cancelamento
        'motivo_cancelamento':     FieldSpec('Motivo cancelamento', 'string'),
        # Vendedor
        'id_vendedor':             FieldSpec('ID Vendedor HubSoft', 'integer'),
        'vendedor_nome':           FieldSpec('Vendedor (nome)', 'string'),
        'vendedor_email':          FieldSpec('Vendedor (email)', 'string'),
        # Cliente vinculado
        'cliente__nome_razaosocial': FieldSpec('Cliente (nome)', 'string'),
        'cliente__cpf_cnpj':       FieldSpec('Cliente (CPF/CNPJ)', 'string'),
        'cliente__tipo_pessoa':    FieldSpec('Tipo do cliente', 'choice'),
        'cliente__churn_score':    FieldSpec('Churn score do cliente', 'integer'),
        'cliente__origem_cliente': FieldSpec('Origem do cliente', 'choice'),
        # Contrato
        'id_cliente_servico_contrato': FieldSpec('ID Contrato HubSoft', 'integer'),
    },
    metricas=['count', 'sum:valor', 'avg:valor', 'avg:vigencia_meses', 'avg:cliente__churn_score'],
    order_by_padrao='-data_habilitacao',
))

registrar(DataSource(
    slug='fatura_hubsoft',
    label='Faturas HubSoft',
    model_path='integracoes.FaturaHubsoft',
    descricao='Faturas (abertas/pagas/vencidas) — base pra inadimplencia.',
    campos={
        'status':           FieldSpec('Status', 'choice', choices=[
            ('aberta','Aberta'), ('paga','Paga'),
            ('vencida','Vencida'), ('cancelada','Cancelada'),
        ]),
        'valor':            FieldSpec('Valor', 'decimal'),
        'data_vencimento':  FieldSpec('Vencimento', 'date', granularidades=['mes','ano']),
        'data_pagamento':   FieldSpec('Pagamento', 'date'),
        'forma_pagamento':  FieldSpec('Forma de pagamento', 'string'),
        'cliente__cidade':  FieldSpec('Cidade do cliente', 'string'),
    },
    metricas=['count', 'sum:valor'],
    order_by_padrao='-data_vencimento',
))

registrar(DataSource(
    slug='os_hubsoft',
    label='OS HubSoft',
    model_path='integracoes.OrdemServicoHubsoft',
    descricao='Ordens de servico reais (status atual no HubSoft).',
    campos={
        'status':           FieldSpec('Status', 'string'),
        'status_prefixo':   FieldSpec('Status (prefixo)', 'choice'),
        'tipo':             FieldSpec('Tipo', 'string'),
        'tecnico_nome':     FieldSpec('Tecnico', 'string'),
        'data_abertura':    FieldSpec('Aberta em', 'datetime', granularidades=['dia','semana','mes']),
        'data_conclusao':   FieldSpec('Concluida em', 'datetime'),
    },
    metricas=['count'],
    order_by_padrao='-data_abertura',
))

registrar(DataSource(
    slug='meta_vendas',
    label='Metas de Vendas',
    model_path='crm.MetaVendas',
    descricao='Metas e realizado por vendedor/equipe.',
    campos={
        'vendedor__username':         FieldSpec('Vendedor', 'string'),
        'meta_vendas_quantidade':     FieldSpec('Meta (qtd)', 'integer'),
        'meta_vendas_valor':          FieldSpec('Meta (valor)', 'decimal'),
        'realizado_vendas_quantidade': FieldSpec('Realizado (qtd)', 'integer'),
        'realizado_vendas_valor':     FieldSpec('Realizado (valor)', 'decimal'),
        'data_inicio':                FieldSpec('Inicio', 'date'),
        'data_fim':                   FieldSpec('Fim', 'date'),
    },
    metricas=['count', 'sum:meta_vendas_valor', 'sum:realizado_vendas_valor'],
    order_by_padrao='-data_inicio',
))
