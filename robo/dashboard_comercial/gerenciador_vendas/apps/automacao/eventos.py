"""
Catálogo de eventos do sistema (gatilho por evento).

Mapeado dos signals/cron dos motores atuais (marketing/automacoes, crm, inbox).
Cada evento entrega entidades (lead/oportunidade/conversa/mensagem) e escalares.
`subcampos` lista os caminhos filtráveis (o que o nó Evento pode usar nos filtros
e o que o fluxo pode referenciar via {{...}}).

Convenção dos caminhos: entidade → `lead.<campo>` / `oportunidade.<campo>`;
escalar do contexto do evento → `var.<chave>`.

Obs: o WIRING (assinar os signals e rodar os fluxos do evento) é fase separada.
Aqui é só o mapa + o que o editor mostra.
"""


def _c(nome, label, tipo='texto', fonte=None):
    d = {'nome': nome, 'label': label, 'tipo': tipo}
    if fonte:
        d['fonte'] = fonte   # dropdown dinâmico (ver apps/automacao/opcoes.py)
    return d


EVENTOS = {
    # ---- Leads ----
    'lead_criado': {
        'label': 'Lead criado', 'grupo': 'Leads',
        'descricao': 'Um novo lead entrou no sistema.',
        'subcampos': [
            _c('lead.origem', 'Origem'),
            _c('lead.score_qualificacao', 'Score', 'numero'),
            _c('lead.cidade', 'Cidade'),
            _c('lead.estado', 'Estado (UF)'),
            _c('lead.status_api', 'Status API'),
            _c('var.lead_email', 'E-mail'),
            _c('var.lead_telefone', 'Telefone'),
        ],
    },
    'lead_qualificado': {
        'label': 'Lead qualificado (score)', 'grupo': 'Leads',
        'descricao': 'O score do lead atingiu o mínimo de qualificação.',
        'subcampos': [
            _c('lead.score_qualificacao', 'Score', 'numero'),
            _c('lead.origem', 'Origem'),
            _c('var.telefone', 'Telefone'),
        ],
    },
    'lead_status_pendente': {
        'label': 'Lead pronto p/ integração', 'grupo': 'Leads',
        'descricao': 'O lead atingiu status pendente (pronto pra integração externa).',
        'subcampos': [
            _c('lead.status_api', 'Status API'),
            _c('var.lead_id_hubsoft', 'ID HubSoft'),
            _c('var.telefone', 'Telefone'),
        ],
    },
    'docs_validados': {
        'label': 'Documentos validados', 'grupo': 'Leads',
        'descricao': 'Todos os documentos do lead foram validados.',
        'subcampos': [
            _c('lead.origem', 'Origem'),
            _c('var.telefone', 'Telefone'),
        ],
    },
    'lead_entrou_segmento': {
        'label': 'Lead entrou em segmento', 'grupo': 'Leads',
        'descricao': 'O lead passou a pertencer a um segmento.',
        'subcampos': [
            _c('var.segmento_nome', 'Segmento', fonte='segmentos'),
            _c('lead.origem', 'Origem'),
        ],
    },
    'lead_sem_contato': {
        'label': 'Lead sem contato há X dias', 'grupo': 'Leads',
        'descricao': 'Lead sem histórico de contato há N dias (cron).',
        'subcampos': [
            _c('var.dias_sem_contato', 'Dias sem contato', 'numero'),
            _c('lead.origem', 'Origem'),
        ],
    },
    # ---- CRM / Comercial ----
    'oportunidade_criada': {
        'label': 'Oportunidade criada', 'grupo': 'Comercial',
        'descricao': 'Uma oportunidade foi criada (manual ou automática).',
        'subcampos': [
            _c('var.estagio', 'Estágio (slug)', fonte='estagios'),
            _c('var.origem_crm', 'Origem'),
            _c('var.lead_id_hubsoft', 'ID HubSoft'),
        ],
    },
    'oportunidade_movida': {
        'label': 'Oportunidade mudou de etapa', 'grupo': 'Comercial',
        'descricao': 'Uma oportunidade foi movida de estágio no funil.',
        'subcampos': [
            _c('var.estagio', 'Estágio (slug)', fonte='estagios'),
            _c('var.estagio_nome', 'Estágio (nome)'),
            _c('var.pipeline', 'Pipeline', fonte='pipelines'),
            _c('oportunidade.titulo', 'Título'),
            _c('var.responsavel', 'Responsável', fonte='responsaveis'),
        ],
    },
    'indicacao_convertida': {
        'label': 'Indicação convertida', 'grupo': 'Comercial',
        'descricao': 'Uma indicação virou cliente.',
        'subcampos': [
            _c('var.nome_indicado', 'Nome do indicado'),
            _c('var.telefone_indicado', 'Telefone do indicado'),
            _c('var.membro_indicador', 'Membro indicador'),
        ],
    },
    'tarefa_vencida': {
        'label': 'Tarefa vencida', 'grupo': 'Comercial',
        'descricao': 'Uma tarefa do CRM passou do vencimento (cron).',
        'subcampos': [
            _c('var.tarefa_titulo', 'Título da tarefa'),
        ],
    },
    'crm_reavaliar_oportunidade': {
        'label': 'Reavaliar oportunidade (funil)', 'grupo': 'Comercial',
        'descricao': ('Pulso interno: algo mudou no lead/oportunidade e as regras do funil '
                      'devem ser reavaliadas. Espelha os disparos do motor antigo '
                      '(RegraPipelineEstagio) na migração da automação do funil.'),
        'subcampos': [
            _c('var.estagio', 'Estágio (slug)', fonte='estagios'),
            _c('oportunidade.titulo', 'Título'),
            _c('var.trigger', 'Origem do pulso'),
        ],
    },
    # ---- Funil (eventos finos da migração) ----
    # Cada um dispara no MOMENTO real de negócio; substituem o pulso genérico.
    'documento_status_mudou': {
        'label': 'Documento mudou de status', 'grupo': 'Funil',
        'descricao': 'Um documento/imagem do lead mudou de status (recebido, validado, rejeitado).',
        'subcampos': [
            _c('var.status', 'Status do documento'),
            _c('lead.cpf_cnpj', 'CPF/CNPJ'),
        ],
    },
    'tag_adicionada': {
        'label': 'Tag adicionada', 'grupo': 'Funil',
        'descricao': 'Uma tag foi adicionada ao lead/oportunidade.',
        'subcampos': [
            _c('var.tag', 'Tag'),
        ],
    },
    'historico_contato': {
        'label': 'Histórico de contato registrado', 'grupo': 'Funil',
        'descricao': 'Um HistoricoContato foi criado (ex: resposta do bot, fluxo finalizado).',
        'subcampos': [
            _c('var.status', 'Status do histórico'),
        ],
    },
    'lead_campo_mudou': {
        'label': 'Campo do lead preenchido', 'grupo': 'Funil',
        'descricao': 'Um campo-chave do lead passou a ter valor (id_plano_rp, id_dia_vencimento, cep...).',
        'subcampos': [
            _c('var.campo', 'Campo'),
            _c('var.valor', 'Novo valor'),
        ],
    },
    'lead_status_mudou': {
        'label': 'Status do lead mudou (status_api)', 'grupo': 'Funil',
        'descricao': 'O `status_api` do lead mudou (ex: aguardando_assinatura, convertido_cliente).',
        'subcampos': [
            _c('var.status_api', 'Status API'),
        ],
    },
    'servico_hubsoft_mudou': {
        'label': 'Serviço HubSoft mudou de status', 'grupo': 'Funil',
        'descricao': 'Um serviço do cliente no HubSoft mudou de status (ex: ATIVO).',
        'subcampos': [
            _c('var.status', 'Status do serviço'),
        ],
    },
    'viabilidade_consultada': {
        'label': 'Viabilidade consultada', 'grupo': 'Funil',
        'descricao': 'Saiu o resultado da viabilidade técnica do endereço (fora_cobertura, pendente_revisao, ok).',
        'subcampos': [
            _c('var.viabilidade_status', 'Status da viabilidade'),
            _c('lead.cidade', 'Cidade'),
        ],
    },
    'conversa_modo_mudou': {
        'label': 'Modo da conversa mudou', 'grupo': 'Funil',
        'descricao': 'O modo de atendimento da conversa mudou (bot, humano, finalizado_bot).',
        'subcampos': [
            _c('var.modo', 'Modo'),
            _c('lead.cidade', 'Cidade'),
        ],
    },
    'conversa_atribuida': {
        'label': 'Conversa atribuída a vendedor', 'grupo': 'Funil',
        'descricao': 'Uma conversa foi atribuída a um agente/vendedor.',
        'subcampos': [
            _c('var.responsavel', 'Responsável'),
        ],
    },
    # ---- Inbox / Atendimento ----
    'mensagem_recebida': {
        'label': 'Mensagem recebida', 'grupo': 'Inbox',
        'descricao': 'Um contato enviou uma mensagem no inbox.',
        'subcampos': [
            _c('var.conteudo', 'Conteúdo'),
            _c('var.canal', 'Canal'),
            _c('var.telefone', 'Telefone'),
            _c('var.modo_atendimento', 'Modo de atendimento'),
        ],
    },
    'conversa_aberta': {
        'label': 'Conversa aberta', 'grupo': 'Inbox',
        'descricao': 'Uma nova conversa foi aberta no inbox.',
        'subcampos': [
            _c('var.canal', 'Canal'),
            _c('var.telefone', 'Telefone'),
        ],
    },
    'conversa_resolvida': {
        'label': 'Conversa resolvida', 'grupo': 'Inbox',
        'descricao': 'Uma conversa foi marcada como resolvida.',
        'subcampos': [
            _c('var.telefone', 'Telefone'),
        ],
    },
}


def catalogo():
    """Lista pro endpoint/editor: tipo + label + grupo + descricao + subcampos."""
    return [
        {'tipo': tipo, 'label': e['label'], 'grupo': e['grupo'],
         'descricao': e['descricao'], 'subcampos': e['subcampos']}
        for tipo, e in EVENTOS.items()
    ]


def opcoes_eventos():
    return list(EVENTOS.keys())
