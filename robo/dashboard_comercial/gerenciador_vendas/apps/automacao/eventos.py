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


def _c(nome, label, tipo='texto'):
    return {'nome': nome, 'label': label, 'tipo': tipo}


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
            _c('var.segmento_nome', 'Segmento'),
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
    'oportunidade_movida': {
        'label': 'Oportunidade mudou de etapa', 'grupo': 'Comercial',
        'descricao': 'Uma oportunidade foi movida de estágio no funil.',
        'subcampos': [
            _c('var.estagio', 'Estágio (slug)'),
            _c('var.estagio_nome', 'Estágio (nome)'),
            _c('var.pipeline', 'Pipeline'),
            _c('oportunidade.titulo', 'Título'),
            _c('var.responsavel', 'Responsável'),
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
    # ---- Inbox / Atendimento ----
    'mensagem_recebida': {
        'label': 'Mensagem recebida', 'grupo': 'Inbox',
        'descricao': 'Um contato enviou uma mensagem no inbox.',
        'subcampos': [
            _c('var.conteudo', 'Conteúdo'),
            _c('var.canal', 'Canal'),
            _c('var.telefone', 'Telefone'),
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
