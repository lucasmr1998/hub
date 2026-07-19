"""Decisor de PRÓXIMO PASSO no fluxo de venda.

Quando o cliente entra no fluxo, o Matrix chama `/ia/proximo-passo` passando
{telefone, lead_id, ultima_mensagem}. Esta função olha o estado atual do lead
no Django e responde COM EXATIDÃO pra onde o flow deve direcionar.

Estratégia:
1. Se não tem lead_id, busca/cria via robovendas.garantir_lead
2. Carrega lead completo no Django
3. Mapeia status_api + campos preenchidos → identifier do próximo nó Matrix
4. Detecta intent da última mensagem (se houver) pra desvio rápido
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.integracoes import robovendas
from src.menu_cliente import montar_menu_texto
from src.regras import alvo as _alvo
from src.regras.mensagens_client import mensagens_client

logger = logging.getLogger(__name__)


# Sequência reduzida do fluxo "Contratar novo serviço" (cliente Hubsoft já
# cadastrado). Pula dados pessoais — esses vêm do LeadProspecto e não mudam.
SEQUENCIA_NEW_SERVICE = [
    # ───── TIPO DE IMÓVEL ─────────────────────────────────────────
    ('tipo_imovel',        'tipo_imovel',               'msg_pergunta'),
    # ───── ENDEREÇO de instalação (CEP primeiro) ─────────────────
    ('cep',                  'coleta_cep',                'msg_pergunta'),
    ('endereco_confirmado',  'confirmacao_endereco',      'msg_pergunta'),
    ('cidade',               'coleta_cidade',             'msg_pergunta'),
    ('bairro',               'coleta_bairro',             'msg_pergunta'),
    ('rua',                  'coleta_rua',                'msg_pergunta'),
    ('numero_residencia',    'coleta_numero',             'msg_pergunta'),
    ('tipo_residencia',      'coleta_tipo_residencia',    'msg_pergunta'),
    ('ponto_referencia',     'coleta_ponto_referencia',   'msg_pergunta'),
    # ───── PLANO E PAGAMENTO ─────────────────────────────────────
    ('id_plano_rp',        'escolha_plano',             'msg_pergunta'),
    ('plano_confirmado',   'confirmacao_plano',         'msg_pergunta'),
    ('id_dia_vencimento',  'dia_vencimento',            'msg_pergunta'),
    # ───── REVISÃO FINAL ─────────────────────────────────────────
    ('dados_confirmados',   'confirmacao_dados',         'msg_pergunta'),
    # ───── DOCUMENTAÇÃO ──────────────────────────────────────────
    ('doc_selfie_recebida', 'documentacao_selfie',      'msg_pergunta'),
    ('doc_frente_recebida', 'documentacao_frente_doc',  'msg_pergunta'),
    ('doc_verso_recebida',  'documentacao_verso_doc',   'msg_pergunta'),
    # ───── AGENDAMENTO ──────────────────────────────────────────
    ('turno_instalacao',   'escolha_turno',             'msg_pergunta'),
    ('data_instalacao',    'escolha_data',              'msg_pergunta'),
]


# Ordem CANÔNICA das perguntas do fluxo dinâmico de venda.
# Cada item: (campo_lead, question_id, identifier_msg_no_matrix)
#
# Estratégia:
# - CEP vem ANTES de cidade/rua/bairro: ao validar o CEP, o engine usa o
#   ViaCEP e preenche cidade/rua/bairro/estado automaticamente no lead.
#   Logo, na próxima iteração, esses campos já estão preenchidos e a API
#   pula direto pra `numero_residencia`.
# - Se o ViaCEP NÃO retornar algum campo (ex: CEP genérico XXXXX-000),
#   esses campos ficam vazios e a sequência pergunta um a um manualmente.
SEQUENCIA_COLETA = [
    # ───── DADOS PESSOAIS ──────────────────────────────────────────
    # CPF vem primeiro pra que possamos detectar se já é cliente Hubsoft
    # ANTES de pedir os outros dados. Se for, encaminha pra menu de cliente
    # existente (contratar/upgrade/acompanhar instalação/atendimento).
    ('cpf_cnpj',           'coleta_cpf',                'msg_pergunta'),
    ('nome_razaosocial',   'coleta_nome',               'msg_pergunta'),
    # RG removido da sequência — não é mais coletado (dados do RG físico
    # vêm pelas fotos enviadas, suficientes pra documentação).
    ('data_nascimento',    'coleta_data_nascimento',    'msg_pergunta'),
    ('email',              'coleta_email',              'msg_pergunta'),
    # ───── TIPO DE IMÓVEL ──────────────────────────────────────────
    ('tipo_imovel',        'tipo_imovel',               'msg_pergunta'),
    # ───── ENDEREÇO (CEP primeiro — ViaCEP preenche cidade/rua/bairro) ─
    ('cep',                  'coleta_cep',                'msg_pergunta'),
    ('endereco_confirmado',  'confirmacao_endereco',      'msg_pergunta'),  # confirma dados ViaCEP
    ('cidade',               'coleta_cidade',             'msg_pergunta'),  # só se NÃO confirmou
    ('bairro',               'coleta_bairro',             'msg_pergunta'),  # só se NÃO confirmou
    ('rua',                  'coleta_rua',                'msg_pergunta'),  # só se NÃO confirmou
    ('numero_residencia',    'coleta_numero',             'msg_pergunta'),
    # Tipo de residência → determina quais detalhes pedir no complemento
    # (só pergunta se tipo_imovel=casa; empresa não passa por aqui).
    ('tipo_residencia',      'coleta_tipo_residencia',    'msg_pergunta'),
    ('ponto_referencia',     'coleta_ponto_referencia',   'msg_pergunta'),
    # ───── PLANO E PAGAMENTO ───────────────────────────────────────
    ('id_plano_rp',        'escolha_plano',             'msg_pergunta'),
    # Após escolher, mostra descrição completa + pede confirmação.
    # Se cliente negar, engine limpa id_plano_rp e volta a perguntar.
    ('plano_confirmado',   'confirmacao_plano',         'msg_pergunta'),
    ('id_dia_vencimento',  'dia_vencimento',            'msg_pergunta'),
    # ───── REVISÃO FINAL — confirmação ANTES dos documentos ────────
    ('dados_confirmados',   'confirmacao_dados',         'msg_pergunta'),
    # ───── DOCUMENTAÇÃO (após confirmação) ─────────────────────────
    ('doc_selfie_recebida', 'documentacao_selfie',      'msg_pergunta'),
    ('doc_frente_recebida', 'documentacao_frente_doc',  'msg_pergunta'),
    ('doc_verso_recebida',  'documentacao_verso_doc',   'msg_pergunta'),
    # ───── AGENDAMENTO (após docs aprovados) ───────────────────────
    # Turno + data — após escolha_data válida, o engine dispara
    # automaticamente a abertura de atendimento + OS via Matrix.
    # Sem etapa de confirmação extra: o cliente já confirmou os dados
    # antes dos docs; turno/data são as últimas escolhas e seguem direto.
    ('turno_instalacao',   'escolha_turno',             'msg_pergunta'),
    ('data_instalacao',    'escolha_data',              'msg_pergunta'),
]


# Mapa de nomes de plano por id_plano_rp (espelho de robovendas.PLANOS)
PLANOS_LABELS = {
    1648: ('Plano de 1GB Turbo',          129.90),
    1649: ('Plano de 620MB',               99.90),
    2088: ('1 Giga + Ponto Adicional',    149.90),
}

# Reverso de robovendas.DIAS_VENCIMENTO — id_dia_vencimento → dia real
# Usado pra exibir o dia escolhido na confirmação final.
DIA_VENCIMENTO_LABELS = {
    28: 1,
    9:  5,
    5:  15,
    6:  20,
}

# Campos do lead que devem ser limpos quando o cliente pede ajuste.
# (Boolean usa None, CharField usa '', IntegerField usa None.)
CAMPOS_PARA_AJUSTE: dict[str, dict] = {
    'endereco': {
        'cep': '', 'rua': '', 'bairro': '', 'cidade': '', 'estado': '',
        'numero_residencia': '', 'ponto_referencia': '',
        'endereco_confirmado': None,
    },
    'dados_pessoais': {
        'nome_razaosocial': '', 'cpf_cnpj': '', 'rg': '',
        'data_nascimento': None, 'email': '',
    },
    'plano': {
        'id_plano_rp': None, 'id_dia_vencimento': None, 'valor': None,
    },
}

# Status do lead → roteamento direto (atalho — pula a sequência de coleta)
# IMPORTANTE:
#   - cliente_ativo, instalacao_agendada → menu (tratados em decidir_proximo_passo)
#   - aguardando_assinatura → transbordo (não tem serviço/OS ainda)
#   - pendente → estado transitório (signal Django cadastra prospecto)
STATUS_ROTAS = {
    'aguardando_assinatura': ('aguardar_assinatura', 'msg_aguardando_assinatura',
                              'Cliente cadastrado, aguardando assinatura externa'),
    'cancelado': ('transbordo_retencao', 'msg_1',
                  'Cliente cancelado — retenção'),
    # Cliente escolheu opção 1/2/4 do menu (novo serviço, upgrade, atendimento).
    # Garante transbordo via /proximo-passo mesmo se o ramo
    # needsReception=true do flow Matrix não estiver atualizado.
    'transbordo_atendente': ('transbordo_comercial', 'msg_1',
                             'Cliente solicitou atendente humano via menu'),
    # Endereço sem viabilidade técnica → transbordo (mensagem já enviada no
    # /validar; aqui o /proximo-passo só halta o fluxo e sinaliza transbordo).
    'venda_sem_viabilidade': ('transbordo_comercial', 'msg_1',
                              'Endereço sem viabilidade técnica — transbordo'),
}

# Valores genéricos de nome_razaosocial que o api_8 cria automaticamente
# (CONTATO.NOME do WhatsApp ou placeholder). Quando o lead tem APENAS isso,
# ainda precisamos perguntar o nome completo formalmente.
NOMES_GENERICOS = {'Lead WhatsApp', 'Cliente', 'Lead', 'Contato', '', None}


def _decidir_status_apos_retorno(lead: dict, dados: dict) -> str:
    """Cliente com status='atendimento_concluido' VOLTOU a interagir.

    Decide pra qual status reverter baseado nos dados disponíveis:
    - id_hubsoft preenchido → cliente_ativo (já é cliente Hubsoft, menu)
    - data_instalacao preenchida → instalacao_agendada (acabou de agendar, menu)
    - Senão → lead_novo (recomeça o fluxo de venda)
    """
    if lead.get('id_hubsoft'):
        return 'cliente_ativo'
    if dados.get('data_instalacao'):
        return 'instalacao_agendada'
    return 'lead_novo'


def _nome_eh_generico(nome: str | None) -> bool:
    """Detecta se o nome do lead é placeholder/incompleto.

    Considerado genérico quando:
    - Vazio / None / só whitespace
    - Está na lista NOMES_GENERICOS
    - Tem apenas 1 palavra (cliente real informa nome + sobrenome)
    - Tem menos de 3 caracteres
    """
    if not nome:
        return True
    s = str(nome).strip()
    if not s or s in NOMES_GENERICOS:
        return True
    if len(s) < 3:
        return True
    # 1 palavra só = WhatsApp display name, não nome completo formal
    if len(s.split()) < 2:
        return True
    return False


def _intent_da_mensagem(msg: str) -> str:
    """Detecta intent simples por keywords. Não usa IA — barato e rápido."""
    if not msg:
        return ''
    s = msg.lower().strip()
    if any(k in s for k in ('contratar', 'plano', 'internet', 'quero', 'assinar')):
        return 'contratar'
    if any(k in s for k in ('suporte', 'problema', 'lento', 'caiu', 'sem internet', 'não funciona')):
        return 'suporte'
    if any(k in s for k in ('cancelar', 'cancelamento', 'sair')):
        return 'cancelar'
    if any(k in s for k in ('boleto', 'fatura', '2ª via', 'segunda via', 'pagamento')):
        return 'financeiro'
    if any(k in s for k in ('oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'tudo bem')):
        return 'cumprimento'
    return ''


# Palavras que indicam desistir do fluxo atual e voltar ao menu.
_KEYWORDS_VOLTAR_MENU = ('menu', 'voltar', 'cancelar', 'desistir', 'sair', 'recomeçar', 'recomecar')


def _quer_voltar_menu(msg: str) -> bool:
    """True se a mensagem indica abandonar o fluxo e voltar ao menu.

    Inclui mensagem VAZIA — que é o sinal de início de uma nova conversa
    (o /api/start manda ultima_mensagem='') — para que uma conversa nova NÃO
    retome um fluxo (upgrade/novo serviço) deixado pela metade.
    """
    s = (msg or '').lower().strip()
    if not s:
        return True
    return any(k in s for k in _KEYWORDS_VOLTAR_MENU)


def _tem_progresso_cadastro(dados_coletados: dict) -> bool:
    """True se o lead já passou do CPF — tem CPF E ao menos um outro campo da
    sequência preenchido. É o sinal de 'atendimento já começado' que justifica
    perguntar retomar/recomeçar em vez de emendar no meio."""
    tem_cpf = bool((dados_coletados.get('cpf_cnpj') or '')
                   if not isinstance(dados_coletados.get('cpf_cnpj'), bool)
                   else dados_coletados.get('cpf_cnpj'))
    if not tem_cpf:
        return False
    for campo, _, _ in SEQUENCIA_COLETA:
        if campo == 'cpf_cnpj':
            continue
        v = dados_coletados.get(campo)
        if isinstance(v, bool):
            return True          # bool definido = respondido
        if v:
            return True          # string/num não-vazio
    return False


# Corpo PADRÃO da pergunta de retomada (fallback). O texto real é configurável
# na ferramenta (tela Mensagens) e chega via regra retomada_confirmacao
# (pergunta_padrao). A saudação "Oi, *Nome*!" é sempre dinâmica (não editável).
_RETOMADA_CORPO_PADRAO = (
    'Vi que a gente já tinha começado seu atendimento. '
    'Como você quer seguir? ##1f504##\n\n'
    '*1)* Continuar de onde paramos ##25b6##\n'
    '*2)* Recomeçar do início ##1f501##\n'
    '*3)* É para outro CPF ##1f194##\n\n'
    '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._'
)


def _texto_retomada() -> str:
    """Corpo da pergunta de retomada — configurável na ferramenta (chave
    retomada_corpo), com fallback para o texto padrão. Mantém 1/2/3 pro
    extractor casar."""
    return mensagens_client.texto('retomada_corpo', _RETOMADA_CORPO_PADRAO)


def _primeiro_nome(lead) -> str:
    """Primeiro nome LIMPO para saudações — tira pontuação/símbolos e dígitos
    (ex.: nome 'Thiago:' vindo do push name do WhatsApp vira 'Thiago'). Retorna
    '' se não sobrar nada utilizável (aí a saudação cai no 'Oi!' sem nome)."""
    nome = ((lead or {}).get('nome_razaosocial') or '').strip()
    if not nome:
        return ''
    prim = nome.split(' ')[0]
    prim = re.sub(r'[^A-Za-zÀ-ÿ]', '', prim)   # mantém só letras (inclui acentos)
    return prim


def _talvez_retomada(telefone, lead_id, dados_coletados, intent,
                     ultima_mensagem, lead) -> dict[str, Any] | None:
    """Gate de RETOMADA (só leads em cadastro). Quando o cliente REABRE o
    atendimento (saudação tipo 'oi' OU mensagem vazia) e já tem cadastro em
    andamento, pergunta se quer continuar / recomeçar / trocar de CPF — em vez
    de cair direto na próxima pergunta pendente. Retorna a resposta pronta, ou
    None quando o gate não se aplica (segue o fluxo normal)."""
    # sinal de REABERTURA de sessão: cumprimento ('oi'...) ou mensagem vazia
    abertura = (intent == 'cumprimento') or not (ultima_mensagem or '').strip()
    if not abertura:
        return None
    if not _tem_progresso_cadastro(dados_coletados):
        return None
    # já resolvido nesta sessão? (evita re-perguntar a cada volta)
    try:
        from src.contexto.conversa import gerenciador as _ctx_g
        if (_ctx_g.obter(telefone) or {}).get('dados_extraidos', {}) \
                .get('retomada_resolvida'):
            return None
    except Exception:
        pass
    prim = _primeiro_nome(lead)
    saud = f'Oi, *{prim}*! ##1f44b##' if prim else 'Oi! ##1f44b##'
    return _resposta(
        lead_id=lead_id, status='lead_novo',
        proximo='msg_pergunta', pergunta_id='retomada_confirmacao',
        deve_perguntar=True, deve_transbordar=False,
        motivo='Cliente reabriu atendimento com cadastro em andamento',
        msg=f'{saud} {_texto_retomada()}',
        intent=intent, dados=dados_coletados,
    )


def _msg_boasvindas_cpf() -> str:
    """1ª mensagem do lead novo: boas-vindas + pedido de CPF — EDITÁVEIS no
    painel Mensagens do Robô (chaves boasvindas_lead_novo e pergunta_cpf_cnpj)."""
    boasvindas = mensagens_client.texto(
        'boasvindas_lead_novo',
        'Oi! Que bom ter você aqui na *Megalink* ##1f680##')
    cpf = mensagens_client.texto(
        'pergunta_cpf_cnpj',
        'Pra começar, pode me informar seu *CPF*? ##1f194##\n\n'
        '_Exemplo: 999.999.999-99_\n\n'
        'Vou usar pra verificar se você já tem cadastro com a gente.')
    return f'{boasvindas}\n\n{cpf}'


def _aplicar_nome(texto: str, nome: str) -> str:
    """Placeholder {nome} nos textos do painel. Sem nome, remove também a
    vírgula anterior ("Ótima notícia, {nome}!" → "Ótima notícia!")."""
    if nome:
        return texto.replace('{nome}', nome)
    return texto.replace(', {nome}', '').replace('{nome}', '').replace('  ', ' ')


def decidir_proximo_passo(
    telefone: str,
    lead_id: int | None,
    ultima_mensagem: str = '',
) -> dict[str, Any]:
    """Decide o próximo passo do cliente no fluxo Matrix.

    Args:
        telefone: telefone do contato (qualquer formato)
        lead_id: id do lead Django (se já conhecido)
        ultima_mensagem: última mensagem enviada pelo cliente (opcional)

    Returns:
        Dict com a decisão, contendo:
        - proximo_passo: identifier do nó Matrix (ex: "msg_cep")
        - proxima_pergunta_id: question_id pra setar question_id_atual no Matrix
        - status_lead: status_api atual
        - dados_ja_coletados: campos do lead já preenchidos
        - deve_perguntar: True se deve continuar coletando
        - deve_transbordar: True se deve transferir pra humano
        - mensagem_inicial: mensagem sugerida pra começar
        - intent_detectado: intent extraída da última mensagem
        - motivo: explicação humana da decisão
        - lead_id: id final usado (criado se necessário)
    """
    intent = _intent_da_mensagem(ultima_mensagem)

    # Nova conversa (mensagem vazia) → re-perguntar o CPF (atual/novo) antes do
    # menu. Limpa o flag de confirmação de CPF da sessão para que a pergunta
    # apareça de novo a cada novo atendimento.
    if not (ultima_mensagem or '').strip():
        try:
            from src.contexto.conversa import gerenciador as _ctx_g
            _ctx_g.salvar_dado(telefone, 'cpf_confirmado', False)
            # nova sessão → o gate de retomada deve poder aparecer de novo
            _ctx_g.salvar_dado(telefone, 'retomada_resolvida', False)
        except Exception:
            pass

    # 1. Garante que temos um lead_id
    if not lead_id:
        lead_id = robovendas.buscar_lead_por_telefone(telefone)
    if not lead_id:
        # Cliente totalmente novo — cria lead e manda pra início do fluxo de vendas
        lead_id = robovendas.registrar_lead(telefone)
        if not lead_id:
            return _resposta(
                lead_id=None, status='erro',
                proximo='ser_5', pergunta_id='',
                deve_perguntar=False, deve_transbordar=True,
                motivo='Não foi possível criar lead — transbordando',
                msg='Vou te transferir pra um atendente.',
                intent=intent, dados={},
            )
        return _resposta(
            lead_id=lead_id, status='lead_novo',
            proximo='msg_sol_cpf', pergunta_id='coleta_cpf',
            deve_perguntar=True, deve_transbordar=False,
            motivo='Lead novo criado — começar pelo CPF',
            msg=_msg_boasvindas_cpf(),
            intent=intent, dados={},
        )

    # 2. Lead existe — carrega dados completos (via cache do alvo: evita
    #    bater no Django toda hora e levar 503 do nginx rate-limit)
    lead = _alvo.consultar_lead_cached(lead_id, telefone=telefone)
    if not lead:
        # Distingue LEAD APAGADO de instabilidade. O flow/Matrix pode carregar
        # um lead_id antigo (variável de sessão) de um lead que não existe mais
        # (404) — nesse caso a re-busca por telefone responde 200 e vazio:
        # criamos um lead NOVO e recomeçamos do CPF (senão o cliente ficava em
        # loop infinito de "instabilidade... manda de novo").
        consulta_ok, lead_id_real = robovendas.verificar_lead_existe(telefone)
        if consulta_ok and lead_id_real and lead_id_real != lead_id:
            # id do flow era stale, mas o telefone TEM lead → usa o id real
            logger.warning('lead_id=%s stale p/ tel=%s — usando lead real %s',
                           lead_id, telefone, lead_id_real)
            lead_id = lead_id_real
            lead = _alvo.consultar_lead_cached(lead_id, telefone=telefone)
        elif consulta_ok and lead_id_real is None:
            logger.warning('lead_id=%s não existe mais (tel=%s) — criando lead '
                           'novo e recomeçando do CPF', lead_id, telefone)
            novo_id = robovendas.registrar_lead(telefone)
            if novo_id:
                return _resposta(
                    lead_id=novo_id, status='lead_novo',
                    proximo='msg_sol_cpf', pergunta_id='coleta_cpf',
                    deve_perguntar=True, deve_transbordar=False,
                    motivo='Lead antigo inexistente — novo lead criado, começar pelo CPF',
                    msg=_msg_boasvindas_cpf(),
                    intent=intent, dados={},
                )
    if not lead:
        # Falha transitória (503 do nginx, timeout etc). Lead existe (temos
        # id) — NÃO podemos recomeçar como cliente novo pedindo CPF, pois
        # o cliente já é conhecido. Pede pra repetir a última msg.
        logger.warning('consultar_lead_completo retornou None lead_id=%s tel=%s '
                       '— pedindo retry ao cliente', lead_id, telefone)
        return _resposta(
            lead_id=lead_id, status='erro_consulta_transitorio',
            proximo='msg_pergunta', pergunta_id='',
            deve_perguntar=True, deve_transbordar=False,
            motivo='Falha transitória ao consultar lead — solicita retry',
            msg=(
                'Tive uma instabilidade aqui agora ##1f615##\n\n'
                'Pode mandar sua última mensagem de novo? ##1f64f##'
            ),
            intent=intent, dados={},
        )

    status_api = (lead.get('status_api') or '').strip()
    # Preserva booleans (True/False) e None — não usa truthiness, que confundiria False com vazio
    dados_coletados = {
        campo: lead.get(campo) if isinstance(lead.get(campo), bool) else (lead.get(campo) or '')
        for campo, _, _ in SEQUENCIA_COLETA
    }

    # SEMPRE perguntar o nome completo (decisão 2026-07-13): o nome só conta
    # como coletado se foi CONFIRMADO pelo fluxo (coleta_nome) ou digitado por
    # um operador — nome pré-preenchido (push name do WhatsApp via Matrix, ex.
    # 'Opl', 'Duda Moreira') NÃO vale e o robô pergunta de novo.
    if not lead.get('nome_confirmado'):
        dados_coletados['nome_razaosocial'] = ''
    # (redundância defensiva: genérico nunca conta, mesmo se confirmado errado)
    elif _nome_eh_generico(dados_coletados.get('nome_razaosocial')):
        dados_coletados['nome_razaosocial'] = ''

    # ── FLUXO NOVO SERVIÇO ───────────────────────────────────────────
    # Cliente Hubsoft escolheu "1) Contratar novo serviço" no menu.
    # engine.iniciar_fluxo_new_service criou um NewService e marcou o lead
    # com status='em_fluxo_new_service'. Daqui em diante, reusamos a IA
    # com a SEQUENCIA_NEW_SERVICE, mas lendo do NewService (não do lead).
    #
    # CASO ESPECIAL: cliente cumprimenta, pede pra voltar ao menu (menu/voltar/
    # cancelar/...) OU inicia uma conversa nova (mensagem vazia) no meio do fluxo
    # — interpretamos como abandono. Cancela o NewService em coleta, reseta o
    # status pra cliente_ativo e volta pro menu (cai no STATUSES_MENU abaixo).
    if status_api == 'em_fluxo_new_service' and (
            intent == 'cumprimento' or _quer_voltar_menu(ultima_mensagem)):
        nsid_cur = _alvo.descobrir_new_service_id(lead_id, telefone=telefone)
        ok_cancel = False
        if nsid_cur:
            try:
                ok_cancel = robovendas.atualizar_new_service(nsid_cur, {'status': 'cancelado'})
            except Exception as e:
                logger.warning('Falha cancelar NewService %s: %s', nsid_cur, e)
        try:
            robovendas.atualizar_status(lead_id, 'cliente_ativo')
        except Exception as e:
            logger.warning('Falha resetar status do lead %s: %s', lead_id, e)
        from src.contexto.conversa import gerenciador as _ctx
        _ctx.salvar_dado(telefone, 'new_service_id_em_coleta', None)
        _ctx.salvar_dado(telefone, 'new_service_cache', None)
        _alvo._log_ns(  # noqa: SLF001
            'cancelado_por_cumprimento',
            lead_id=lead_id, telefone=telefone, new_service_id=nsid_cur,
            valido=ok_cancel,
            payload_in={'intent': intent, 'ultima_mensagem': ultima_mensagem[:80]},
            payload_out={'novo_status_lead': 'cliente_ativo', 'ns_cancelado': bool(nsid_cur)},
            mensagem='Cliente cumprimentou no meio do fluxo — abandono detectado',
        )
        status_api = 'cliente_ativo'  # cai no STATUSES_MENU abaixo
        logger.info('Cliente %s cumprimentou no fluxo NS — cancelando ns=%s e voltando ao menu',
                    telefone, nsid_cur)

    if status_api == 'em_fluxo_new_service':
        dados_ns = _alvo.consultar_dados_alvo(lead_id, telefone=telefone) or lead
        dados_ns_coletados = {
            campo: dados_ns.get(campo) if isinstance(dados_ns.get(campo), bool)
                  else (dados_ns.get(campo) or '')
            for campo, _, _ in SEQUENCIA_NEW_SERVICE
        }
        tipo_imovel_ns = (dados_ns_coletados.get('tipo_imovel') or '').strip()
        for campo, qid, identifier in SEQUENCIA_NEW_SERVICE:
            if campo == 'tipo_residencia' and tipo_imovel_ns and tipo_imovel_ns != 'casa':
                continue
            valor = dados_ns_coletados.get(campo)
            if isinstance(valor, bool):
                continue
            if valor:
                continue
            return _resposta(
                lead_id=lead_id, status='em_fluxo_new_service',
                proximo=identifier, pergunta_id=qid,
                deve_perguntar=True, deve_transbordar=False,
                motivo=f'Novo Serviço: próxima pergunta {qid} (falta: {campo})',
                msg=_msg_pergunta(dados_ns, campo, is_novo=False,
                                  eh_primeira_pergunta=False),
                intent=intent, dados=dados_ns_coletados,
            )
        # Todos os campos preenchidos — engine deveria ter finalizado.
        # Defensivo: finaliza aqui e devolve msg de sucesso.
        nsid = dados_ns.get('_new_service_id')
        if nsid:
            _alvo.encerrar_fluxo_new_service(lead_id, nsid, telefone=telefone,
                                             observacoes='Finalizado por onboarding (fallback)')
        return _resposta(
            lead_id=lead_id, status='cliente_ativo',
            proximo='red_encerrar', pergunta_id='',
            deve_perguntar=False, deve_transbordar=False,
            motivo='Novo Serviço concluído — fim do fluxo',
            msg=(
                'Pronto! ##2705## Sua *nova contratação* foi registrada com sucesso.\n\n'
                'Nossa equipe vai validar os documentos e em breve entrará em '
                'contato pra agendar a instalação. ##1f4c5##\n\n'
                'Obrigada pela confiança na *Megalink*! ##1f499##'
            ),
            intent=intent, dados=dados_ns_coletados,
        )

    # ── FLUXO UPGRADE DE PLANO ───────────────────────────────────────
    # Cliente Hubsoft escolheu "2) Fazer upgrade de plano" no menu.
    # engine.iniciar_fluxo_upgrade criou um AtendimentoFluxo (fluxo upgrade)
    # e marcou status='em_fluxo_upgrade'. Aqui SÓ MOSTRAMOS a pergunta atual
    # (modo "mostrar" do /api/upgrade-conversa/turno/). A RESPOSTA do cliente
    # é submetida pelo /ia/validar (question_id='upgrade_turno').
    #
    # Cumprimento, "voltar ao menu" (menu/voltar/cancelar/...) ou conversa nova
    # (mensagem vazia) no meio = abandono → volta pro menu.
    if status_api == 'em_fluxo_upgrade' and (
            intent == 'cumprimento' or _quer_voltar_menu(ultima_mensagem)):
        _alvo.encerrar_fluxo_upgrade(lead_id, telefone=telefone)
        status_api = 'cliente_ativo'  # cai no STATUSES_MENU abaixo
        logger.info('Cliente %s cumprimentou no fluxo upgrade — voltando ao menu', telefone)

    if status_api == 'em_fluxo_upgrade':
        resp = robovendas.turno_upgrade(lead_id, '')  # modo mostrar
        if not resp:
            return _resposta(
                lead_id=lead_id, status='em_fluxo_upgrade',
                proximo='transbordo_comercial', pergunta_id='',
                deve_perguntar=False, deve_transbordar=True,
                motivo='Falha no fluxo de upgrade — transbordo',
                msg=('Tive um probleminha aqui pra montar seu upgrade. '
                     'Vou te transferir pra um atendente. ##1f4f1##'),
                intent=intent, dados={})
        if resp.get('finalizado'):
            # Sucesso → ENCERRA o atendimento (status atendimento_concluido).
            # A mensagem de sucesso é a última e a conversa fecha no red_encerrar.
            _alvo.encerrar_fluxo_upgrade(lead_id, telefone=telefone,
                                         upgrade_id=resp.get('upgrade_id'),
                                         status_final='atendimento_concluido')
            return _resposta(
                lead_id=lead_id, status='atendimento_concluido',
                proximo='red_encerrar', pergunta_id='',
                deve_perguntar=False, deve_transbordar=False,
                motivo='Upgrade concluído — encerra o atendimento',
                msg=(resp.get('mensagem_final')
                     or 'Pronto! Registramos sua solicitação de upgrade. ##2705##'),
                intent=intent, dados={})
        if resp.get('sem_opcoes'):
            _alvo.encerrar_fluxo_upgrade(lead_id, telefone=telefone)
            return _resposta(
                lead_id=lead_id, status='em_fluxo_upgrade',
                proximo='transbordo_comercial', pergunta_id='',
                deve_perguntar=False, deve_transbordar=True,
                motivo='Sem opções de upgrade — transbordo',
                msg=(resp.get('mensagem')
                     or 'Não encontrei opções de upgrade pra você agora. '
                        'Vou te transferir pra um atendente. ##1f4f1##'),
                intent=intent, dados={})
        _msg_up = resp.get('mensagem') or ''
        if _msg_up:
            _msg_up += '\n\n_##1f519## Ou digite *menu* para voltar._'
        return _resposta(
            lead_id=lead_id, status='em_fluxo_upgrade',
            proximo='msg_pergunta', pergunta_id=resp.get('pergunta_id') or 'upgrade_turno',
            deve_perguntar=True, deve_transbordar=False,
            motivo=f'Upgrade: pergunta {resp.get("indice")}',
            msg=_msg_up,
            intent=intent, dados={})

    # 3. Status especiais — atalhos (cliente já avançou ou já é cliente)
    # 3.a) Cliente já cadastrado COM serviço/OS no Hubsoft → menu
    # Inclui apenas status onde faz sentido oferecer as 4 opções
    # (contratar/upgrade/acompanhar OS/atendimento):
    #   - cliente_ativo: detectado via API Hubsoft pelo CPF (tem serviço)
    #   - instalacao_agendada: acabou de agendar via bot (tem OS aberta)
    # aguardando_assinatura NÃO entra aqui — cliente ainda não tem
    # serviço/OS, então cai no STATUS_ROTAS (transbordo direto).
    STATUSES_MENU = {
        'cliente_ativo',
        'instalacao_agendada',
    }
    # 3.b) Cliente já viu a OS / agendou — pergunta se quer mais algo ou encerrar
    if status_api == 'aguardando_finalizacao':
        return _resposta(
            lead_id=lead_id, status='aguardando_finalizacao',
            proximo='msg_pergunta', pergunta_id='pergunta_finalizar',
            deve_perguntar=True, deve_transbordar=False,
            motivo='Aguardando cliente decidir se finaliza ou continua',
            msg=_msg_pergunta(lead, '_pergunta_finalizar_', is_novo=False,
                              eh_primeira_pergunta=False),
            intent=intent, dados=dados_coletados,
        )

    # 3.c) Atendimento concluído:
    # - Se 'acabou_de_encerrar' está marcado no contexto → exibe despedida e
    #   encerra (mesma sessão em que cliente escolheu encerrar).
    # - Se NÃO está marcado → cliente VOLTOU depois. Reseta o status pra
    #   permitir nova interação (cliente Hubsoft = cliente_ativo;
    #   instalação agendada = instalacao_agendada; senão, segue como
    #   lead já cadastrado).
    if status_api == 'atendimento_concluido':
        from src.contexto.conversa import gerenciador as _ctx
        ctx = _ctx.obter(telefone)
        flag_recem = ctx.get('dados_extraidos', {}).get('acabou_de_encerrar')
        if flag_recem:
            # Mesma sessão — exibe despedida + limpa flag (single-shot)
            ctx['dados_extraidos']['acabou_de_encerrar'] = False
            return _resposta(
                lead_id=lead_id, status='atendimento_concluido',
                proximo='red_encerrar', pergunta_id='',
                deve_perguntar=False, deve_transbordar=False,
                motivo='Atendimento concluído — encerra fluxo (mesma sessão)',
                msg=mensagens_client.texto(
                    'despedida_encerramento',
                    'Obrigada pelo contato com a *Megalink*! ##1f499##\n\n'
                    'Estamos sempre à disposição. Tenha um ótimo dia! ##1f31f##'),
                intent=intent, dados=dados_coletados,
            )
        # Cliente voltou — reverte status pra um adequado e continua
        novo_status = _decidir_status_apos_retorno(lead, dados_coletados)
        try:
            robovendas.atualizar_status(lead_id, novo_status)
        except Exception:
            pass
        status_api = novo_status   # continua o roteamento abaixo

    # Número reconhecido → ANTES do menu, confirma se o atendimento é para o
    # CPF atrelado a este número ou para um novo CPF. Re-pergunta a CADA novo
    # contato: um cumprimento ('oi'/'olá') em estado de menu é tratado como
    # ABERTURA de atendimento → zera o flag e pergunta de novo (pedido do
    # usuário: todo contato deve confirmar se é o mesmo CPF do último
    # atendimento). Respostas de menu (números) não re-perguntam.
    if status_api in STATUSES_MENU:
        cpf_confirmado = False
        try:
            from src.contexto.conversa import gerenciador as _ctx_g
            if intent == 'cumprimento':
                _ctx_g.salvar_dado(telefone, 'cpf_confirmado', False)
            else:
                cpf_confirmado = bool((_ctx_g.obter(telefone) or {})
                                      .get('dados_extraidos', {}).get('cpf_confirmado'))
        except Exception:
            cpf_confirmado = False
        if not cpf_confirmado:
            cpf_raw = ''.join(c for c in str(lead.get('cpf_cnpj') or '') if c.isdigit())
            cpf_mask = (f'***.***.{cpf_raw[6:9]}-{cpf_raw[9:11]}'
                        if len(cpf_raw) == 11 else 'atrelado a este número')
            nome_raw = (lead.get('nome_razaosocial') or '').strip()
            prim = '' if _nome_eh_generico(nome_raw) else _primeiro_nome(lead)
            saud = f'Olá *{prim}*! ##1f44b## ' if prim else 'Olá! ##1f44b## '
            return _resposta(
                lead_id=lead_id, status=status_api,
                proximo='msg_pergunta', pergunta_id='menu_cpf_confirmacao',
                deve_perguntar=True, deve_transbordar=False,
                motivo='Cliente reconhecido — confirmar CPF (atual/novo) antes do menu',
                msg=saud + mensagens_client.texto(
                    'menu_cpf_corpo',
                    'Vi que este número já tem cadastro com a gente.\n\n'
                    'Este atendimento é para o *CPF {cpf}* (atrelado a este '
                    'número) ou para um *outro CPF*?\n\n'
                    '*1)* ##2705## Sim, é esse CPF\n'
                    '*2)* ##1f194## Outro CPF\n\n'
                    '_##1f4cc## Responda com *1* ou *2*._'
                ).replace('{cpf}', cpf_mask),
                intent=intent, dados=dados_coletados,
            )

    if status_api in STATUSES_MENU:
        nome_cliente = (lead.get('nome_razaosocial') or '').strip()
        # Cumprimenta pelo nome (limpo) — mas NUNCA com nome genérico do
        # WhatsApp ('Lead WhatsApp' → "Perfeito, Lead!" ficava estranho).
        primeiro_nome = '' if _nome_eh_generico(nome_cliente) else _primeiro_nome(lead)
        if primeiro_nome:
            saud_extra = f'Perfeito, *{primeiro_nome}*! ##2705## '
        else:
            saud_extra = 'Perfeito! ##2705## '
        return _resposta(
            lead_id=lead_id, status=status_api,
            proximo='msg_pergunta', pergunta_id='menu_cliente_existente',
            deve_perguntar=True, deve_transbordar=False,
            motivo=f'Cliente já cadastrado ({status_api}) — apresentar menu',
            msg=(
                saud_extra + mensagens_client.texto('menu_saudacao_pergunta', 'Como posso te ajudar hoje?') + '\n\n'
                + montar_menu_texto(bool(lead.get('tem_servico_habilitado')))
            ),
            intent=intent, dados=dados_coletados,
        )

    # CASO ESPECIAL: cliente que está em 'transbordo_atendente' E
    # acabou de cumprimentar (oi/olá) → nova sessão. Reseta pra 'cliente_ativo'
    # e cai no menu. Não exigimos id_hubsoft (pode estar vazio em leads que
    # nunca passaram pelo sync), porque se o status é 'transbordo_atendente'
    # foi porque o menu Hubsoft mostrou — o que só ocorre pra cliente.
    if (status_api == 'transbordo_atendente'
            and intent == 'cumprimento'):
        try:
            robovendas.atualizar_status(lead_id, 'cliente_ativo')
            _alvo._ctx_patch_lead_cache(telefone, {'status_api': 'cliente_ativo'})  # noqa: SLF001
        except Exception as e:
            logger.warning('Falha resetar transbordo_atendente lead=%s: %s', lead_id, e)
        status_api = 'cliente_ativo'  # cai no STATUSES_MENU acima... wait
        # Como STATUSES_MENU já foi checado, refaz a checagem agora:
        if status_api in STATUSES_MENU:
            nome_cliente = (lead.get('nome_razaosocial') or '').strip()
            primeiro_nome = nome_cliente.split(' ')[0] if nome_cliente else ''
            saud_extra = (
                f'Olá *{primeiro_nome}*! ##1f44b## Vi que você já tem cadastro com a gente.\n\n'
                if primeiro_nome
                else 'Olá! ##1f44b## Vi que você já tem cadastro com a gente.\n\n'
            )
            return _resposta(
                lead_id=lead_id, status=status_api,
                proximo='msg_pergunta', pergunta_id='menu_cliente_existente',
                deve_perguntar=True, deve_transbordar=False,
                motivo='Cliente cumprimentou pós-transbordo — reset ao menu',
                msg=(
                    saud_extra + mensagens_client.texto('menu_saudacao_pergunta', 'Como posso te ajudar hoje?') + '\n\n'
                    + montar_menu_texto(bool(lead.get('tem_servico_habilitado')))
                ),
                intent=intent, dados=dados_coletados,
            )

    if status_api in STATUS_ROTAS:
        rota, identifier, motivo = STATUS_ROTAS[status_api]
        transbordo = rota.startswith('transbordo_')
        return _resposta(
            lead_id=lead_id, status=status_api,
            proximo=identifier, pergunta_id='',
            deve_perguntar=False, deve_transbordar=transbordo,
            motivo=motivo, msg='', intent=intent, dados=dados_coletados,
        )

    # 3.b) Cliente NEGOU os dados finais (dados_confirmados=False)
    #      → entra no fluxo de ajuste: pergunta o que quer corrigir, limpa
    #        os campos relacionados e re-pergunta até voltar pra confirmação.
    if dados_coletados.get('dados_confirmados') is False:
        tipo_ajuste = (lead.get('tipo_ajuste') or '').strip()
        if not tipo_ajuste:
            # Ainda não disse o que ajustar — pergunta
            return _resposta(
                lead_id=lead_id, status='ajuste_pendente',
                proximo='msg_pergunta', pergunta_id='o_que_ajustar',
                deve_perguntar=True, deve_transbordar=False,
                motivo='Cliente negou os dados — perguntando o que quer ajustar',
                msg=mensagens_client.texto(
                    'pergunta_o_que_ajustar',
                    'Sem problema! O que você quer ajustar? ##1f527##\n\n'
                    '*1)* ##1f4cd## Endereço\n'
                    '*2)* ##1f464## Dados pessoais\n'
                    '*3)* ##1f4e6## Plano selecionado\n\n'
                    '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._'
                ),
                intent=intent, dados=dados_coletados,
            )
        # Já sabe o que ajustar — limpa os campos e reseta as flags
        campos = CAMPOS_PARA_AJUSTE.get(tipo_ajuste, {})
        if campos:
            payload = dict(campos)
            payload['dados_confirmados'] = None
            payload['tipo_ajuste'] = ''
            robovendas.atualizar_lead(lead_id, payload)
            # zera no dict local pra que o loop abaixo pegue o primeiro vazio
            for c, v in campos.items():
                # SEQUENCIA_COLETA só tem alguns desses campos; mantém consistência
                if c in dados_coletados:
                    dados_coletados[c] = v if isinstance(v, bool) or v is None else ''
            dados_coletados['dados_confirmados'] = None
        # cai pro loop normal abaixo — vai re-perguntar os campos limpos

    # 4. Status default ('lead_novo', 'processamento_manual' ou vazio)
    #    → Encontrar o primeiro campo VAZIO da sequência e retornar
    is_novo = status_api == 'lead_novo' or not status_api
    # É a "primeira" pergunta se nenhum campo (não-bool) da sequência foi coletado
    eh_primeira = not any(
        v for v in dados_coletados.values()
        if not isinstance(v, bool)
    )
    # GATE DE RETOMADA (determinístico/Matrix): cliente REABRIU o atendimento
    # (saudação 'oi'... ou msg vazia) com cadastro em andamento → pergunta
    # continuar/recomeçar/outro CPF antes de emendar na próxima pergunta.
    # Vale para TODOS os status que caem no laço de coleta abaixo — não só
    # 'lead_novo': 'processamento_manual' (lead que já começou mas o automático
    # parou) e vazio também são "em cadastro". A resposta é tratada no engine.py
    # (question_id='retomada_confirmacao').
    em_cadastro = status_api in ('lead_novo', 'processamento_manual') or not status_api
    if em_cadastro:
        _resp_ret = _talvez_retomada(telefone, lead_id, dados_coletados,
                                     intent, ultima_mensagem, lead)
        if _resp_ret is not None:
            return _resp_ret

    tipo_imovel_atual = (dados_coletados.get('tipo_imovel') or '').strip()
    for campo, qid, identifier in SEQUENCIA_COLETA:
        # tipo_residencia só faz sentido pra residencial. Empresa não passa
        # por aqui (já transbordou antes pela regra tipo_imovel), mas como
        # precaução, pula esse campo se tipo_imovel for diferente de 'casa'.
        if campo == 'tipo_residencia' and tipo_imovel_atual and tipo_imovel_atual != 'casa':
            continue

        valor = dados_coletados.get(campo)
        # Boolean definido (True ou False) = preenchido; None ou string vazia = vazio
        if isinstance(valor, bool):
            continue  # já respondido (True ou False)
        if valor:
            continue  # string não-vazia
        # campo vazio → essa é a próxima pergunta
        return _resposta(
            lead_id=lead_id,
            status='lead_novo' if is_novo else (status_api or 'em_andamento'),
            proximo=identifier, pergunta_id=qid,
            deve_perguntar=True, deve_transbordar=False,
            motivo=f'Próxima pergunta: {qid} (falta: {campo})',
            msg=_msg_pergunta(lead, campo, is_novo=is_novo,
                              eh_primeira_pergunta=eh_primeira),
            intent=intent, dados=dados_coletados,
        )

    # 5. Todos os campos preenchidos — fluxo finalizado
    # Se chegou aqui, todos os campos (incluindo turno_instalacao e data_instalacao)
    # estão preenchidos. O agendamento deveria já ter sido disparado quando
    # escolha_data foi validada (engine.py). status_api='instalacao_agendada'
    # deveria ter sido setado, então STATUS_ROTAS já roteou pra ja_agendado.
    # Se mesmo assim caiu aqui, transborda com mensagem de conclusão.
    return _resposta(
        lead_id=lead_id, status=status_api or 'pre_assinatura',
        proximo='ser_5', pergunta_id='',
        deve_perguntar=False, deve_transbordar=True,
        motivo='Fluxo concluído — todos os dados coletados',
        msg='Tudo pronto! ##2705## Vou te transferir pra um atendente finalizar.',
        intent=intent, dados=dados_coletados,
    )


def _msg_pergunta(lead: dict, campo_faltante: str, is_novo: bool = False,
                  eh_primeira_pergunta: bool = False) -> str:
    """Constrói a mensagem da pergunta atual.

    - `eh_primeira_pergunta`: True só na PRIMEIRA pergunta do cliente
      (sem dados coletados ainda). Aí usa saudação de boas-vindas.
    - Demais perguntas: vão direto ao ponto, sem saudação repetida.

    Opções (plano, tipo_imovel, turno, vencimento) são listadas inline
    pra cliente saber o que escolher.
    """
    nome_raw = lead.get('nome_razaosocial') or ''
    if _nome_eh_generico(nome_raw):
        nome_raw = ''
    primeiro_nome = nome_raw.split(' ')[0] if nome_raw else ''

    # Saudação SÓ na primeira pergunta (boas-vindas inicial)
    if eh_primeira_pergunta:
        if primeiro_nome:
            saud = f'Oi {primeiro_nome}! ##263A##\n\n'
        else:
            saud = 'Oi! Que bom ter você aqui na *Megalink* ##1f680##\n\n'
    else:
        saud = ''  # mensagens seguintes vão direto

    # Mensagem dinâmica de confirmação FINAL — só mostra campos preenchidos
    # (evita placeholders '?' visíveis pro cliente em campos que não temos)
    if campo_faltante == 'dados_confirmados':
        nome    = (lead.get('nome_razaosocial') or '').strip()
        cpf     = (lead.get('cpf_cnpj') or '').strip()
        nasc    = lead.get('data_nascimento') or ''
        if hasattr(nasc, 'strftime'):
            nasc = nasc.strftime('%d/%m/%Y')
        nasc    = str(nasc).strip()
        email   = (lead.get('email') or '').strip()
        cep     = (lead.get('cep') or '').strip()
        rua     = (lead.get('rua') or '').strip()
        num     = (lead.get('numero_residencia') or '').strip()
        bairro  = (lead.get('bairro') or '').strip()
        cidade  = (lead.get('cidade') or '').strip()
        estado  = (lead.get('estado') or '').strip()

        id_venc = lead.get('id_dia_vencimento')
        dia_real = DIA_VENCIMENTO_LABELS.get(id_venc)
        id_plano = lead.get('id_plano_rp')
        plano_label, plano_valor = PLANOS_LABELS.get(id_plano, ('', None))

        linhas = [
            '*Confirme seus dados, por favor:* ##1f4dd##',
            'Revise as informações antes de finalizarmos seu cadastro.',
            '',
            '*Plano Selecionado*',
        ]
        if plano_label:
            linhas.append(f'##1f4e6## Plano: {plano_label}')
        if plano_valor:
            valor_str = f'R$ {plano_valor:.2f}'.replace('.', ',')
            linhas.append(f'##1f4b0## Valor: {valor_str}')
        if dia_real:
            linhas.append(f'##1f4c5## Vencimento: Dia {dia_real}')

        linhas += ['', '*Dados Pessoais*']
        if nome:
            linhas.append(f'##1f464## Nome: {nome}')
        if cpf:
            linhas.append(f'##1f194## CPF: {cpf}')
        if nasc:
            linhas.append(f'##1f382## Nascimento: {nasc}')
        if email:
            linhas.append(f'##2709## E-mail: {email}')

        linhas += ['', '*Endereço*']
        if cep:
            linhas.append(f'##1f3f7## CEP: {cep}')
        if rua:
            linhas.append(f'##1f6e3## Rua: {rua}' + (f', Nº {num}' if num else ''))
        elif num:
            linhas.append(f'##1f6e3## Nº {num}')
        if bairro:
            linhas.append(f'##1f3d8## Bairro: {bairro}')
        if cidade or estado:
            cid_uf = f'{cidade}/{estado}' if (cidade and estado) else (cidade or estado)
            linhas.append(f'##1f306## Cidade: {cid_uf}')

        linhas += [
            '',
            '_Este plano possui fidelidade de 12 meses. O valor com desconto '
            'é válido para pagamentos realizados até a data de vencimento._',
            '',
            '*Está tudo certo com essas informações?*',
            '',
            '*1)* ##2705## Sim, pode prosseguir',
            '*2)* ##274c## Não, preciso ajustar',
        ]
        return saud + '\n'.join(linhas)

    # Mensagem dinâmica de confirmação de endereço (mostra SÓ o que ViaCEP
    # retornou — campos vazios são omitidos pra não exibir '?')
    if campo_faltante == 'endereco_confirmado':
        cep    = (lead.get('cep') or '').strip()
        rua    = (lead.get('rua') or '').strip()
        bairro = (lead.get('bairro') or '').strip()
        cidade = (lead.get('cidade') or '').strip()
        estado = (lead.get('estado') or '').strip()

        titulo = mensagens_client.texto(
            'confirmacao_endereco_titulo',
            '##1f4cd## *Confira o endereço que encontrei:*')
        linhas = [titulo + '\n']
        if cep:
            linhas.append(f'##1f3f7## *CEP:* {cep}')
        if rua:
            linhas.append(f'##1f6e3## *Rua:* {rua}')
        if bairro:
            linhas.append(f'##1f3d8## *Bairro:* {bairro}')
        if cidade or estado:
            cid_uf = f'{cidade}/{estado}' if (cidade and estado) else (cidade or estado)
            linhas.append(f'##1f306## *Cidade:* {cid_uf}')

        rodape = mensagens_client.texto(
            'confirmacao_endereco_rodape',
            'Está tudo certo?\n\n'
            '*1)* ##2705## Sim, está correto\n'
            '*2)* ##274c## Não, preciso corrigir')
        return saud + '\n'.join(linhas) + '\n\n' + rodape

    # Mensagem do coleta_tipo_residencia
    if campo_faltante == 'tipo_residencia':
        return saud + mensagens_client.texto(
            'pergunta_tipo_residencia',
            '##1f3e0## *Qual o tipo de imóvel?*\n\n'
            '*1)* ##1f3d8## Casa térrea / sobrado\n'
            '*2)* ##1f3e2## Apartamento\n'
            '*3)* ##1f3df## Condomínio fechado\n\n'
            '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._')

    # Mensagem dinâmica de coleta_ponto_referencia — adapta ao tipo_residencia
    if campo_faltante == 'ponto_referencia':
        tipo = (lead.get('tipo_residencia') or '').strip()
        if tipo == 'apartamento':
            return saud + mensagens_client.texto(
                'pergunta_ponto_ref_apartamento',
                '##1f3e2## *Pra ajudar nosso time na instalação, me passe '
                'os detalhes do seu apartamento:*\n\n'
                '- Nome do *edifício*\n'
                '- *Bloco/torre* (se houver)\n'
                '- *Andar*\n'
                '- *Número do apartamento*\n'
                '- *Ponto de referência* externo (opcional, ex: perto da padaria X)\n\n'
                '_Pode mandar tudo em uma única mensagem ##263A##_')
        if tipo == 'condominio':
            return saud + mensagens_client.texto(
                'pergunta_ponto_ref_condominio',
                '##1f3df## *Pra ajudar nosso time na instalação, me passe '
                'os detalhes do seu condomínio:*\n\n'
                '- Nome do *condomínio*\n'
                '- *Quadra/bloco* (se houver)\n'
                '- *Número da casa*\n'
                '- *Ponto de referência* externo (opcional, ex: portaria 2)\n\n'
                '_Pode mandar tudo em uma única mensagem ##263A##_')
        # Casa térrea ou tipo ainda não definido → só ponto de referência
        return saud + mensagens_client.texto(
            'pergunta_ponto_ref_casa',
            '##1f3d8## *Tem algum ponto de referência perto da sua casa?* ##263A##\n\n'
            '_Exemplo: perto da padaria do João, em frente à praça._')

    # Mensagem dinâmica de confirmacao_plano — descrição rica do plano escolhido
    # (TEXTOS EDITÁVEIS no painel; placeholder {nome} vira o 1º nome do cliente)
    if campo_faltante == 'plano_confirmado':
        id_plano = lead.get('id_plano_rp')
        nome_contato = (lead.get('nome_razaosocial') or '').strip()
        primeiro_nome = '' if _nome_eh_generico(nome_contato) else _primeiro_nome(lead)
        RODAPE_PLANO = ('*Confirma a contratação desse plano?*\n\n'
                        '*1)* ##2705## Sim, quero esse plano\n'
                        '*2)* ##274c## Não, quero ver outro')
        if id_plano == 1649:
            corpo = mensagens_client.texto(
                'confirmacao_plano_620',
                '##1f4e3## *Ótima notícia, {nome}!*\n\n'
                'Temos uma promoção exclusiva da *Megalink* válida somente '
                'neste mês, com condições especiais para pagamento até a '
                'data de vencimento.\n\n'
                '##1f4f6## *Internet que você pode confiar*\n\n'
                'Contrate *620 Mega* de velocidade e tenha internet rápida '
                'e estável para toda a sua casa.\n\n'
                '##1f4b0## *Apenas R$ 99,90 por mês*\n'
                '_(valor com desconto de pontualidade)_\n\n'
                '##1f680## *Ideal para:*\n'
                '- Assistir filmes e séries sem travar\n'
                '- Jogos online com mais estabilidade\n'
                '- Chamadas de vídeo e home office\n\n' + RODAPE_PLANO)
            return saud + _aplicar_nome(corpo, primeiro_nome)
        if id_plano == 1648:
            corpo = mensagens_client.texto(
                'confirmacao_plano_1g',
                '##1f4e3## *Ótima notícia, {nome}!*\n\n'
                'Temos uma promoção exclusiva da *Megalink* válida somente '
                'neste mês, com condições especiais para pagamento até a '
                'data de vencimento.\n\n'
                '##1f4f6## *Internet que você pode confiar*\n\n'
                'Contrate o *Plano de 1GB Turbo* e tenha uma conexão ultra '
                'rápida e estável para toda a sua casa.\n\n'
                '##1f4b0## *Apenas R$ 129,90 por mês*\n'
                '_(valor com desconto de pontualidade)_\n\n'
                '##1f680## *Ideal para:*\n'
                '- Assistir filmes e séries em alta qualidade sem travar\n'
                '- Jogos online com máxima performance\n'
                '- Chamadas de vídeo e home office sem interrupções\n'
                '- Vários dispositivos conectados ao mesmo tempo\n\n' + RODAPE_PLANO)
            return saud + _aplicar_nome(corpo, primeiro_nome)
        if id_plano == 2088:
            corpo = mensagens_client.texto(
                'confirmacao_plano_1g_ponto_adc',
                '##1f4e3## *Ótima notícia, {nome}!*\n\n'
                'Temos uma promoção exclusiva da *Megalink* válida somente '
                'neste mês, com condições especiais para pagamento até a '
                'data de vencimento.\n\n'
                '##1f4f6## *Internet que você pode confiar*\n\n'
                'Contrate o *1 Giga + Ponto Adicional* e tenha conexão ultra '
                'rápida com um *segundo ponto de Wi-Fi* para cobrir toda a casa.\n\n'
                '##1f4b0## *Apenas R$ 149,90 por mês*\n'
                '_(valor com desconto de pontualidade)_\n\n'
                '##1f680## *Ideal para:*\n'
                '- Casas grandes ou de dois andares (Wi-Fi em todo canto)\n'
                '- Filmes, séries e jogos em vários cômodos ao mesmo tempo\n'
                '- Home office com estabilidade em qualquer ambiente\n\n' + RODAPE_PLANO)
            return saud + _aplicar_nome(corpo, primeiro_nome)
        # Fallback (plano desconhecido)
        return saud + mensagens_client.texto(
            'confirmacao_plano_generica',
            'Confirma o plano escolhido?\n\n'
            '*1)* ##2705## Sim\n'
            '*2)* ##274c## Não, quero ver outro')

    # Mensagem dinâmica de pergunta_finalizar — após atendimento concluído
    if campo_faltante == '_pergunta_finalizar_':
        return mensagens_client.texto(
            'pergunta_finalizar',
            'Posso te ajudar com mais alguma coisa? ##263A##\n\n'
            '*1)* ##1f504## Sim, voltar ao menu\n'
            '*2)* ##2705## Não, obrigado!')

    # Mensagem dinâmica de escolha_data — busca as 3 próximas datas da API matrix
    if campo_faltante == 'data_instalacao':
        from datetime import datetime
        datas: list[str] = []
        try:
            # robovendas é a INSTÂNCIA exportada pelo __init__ — chamada direta
            from src.integracoes import robovendas
            hoje = datetime.now().strftime('%d/%m/%Y')
            datas = robovendas.consultar_datas_disponiveis(hoje) or []
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning(
                'Falha consultar_datas_disponiveis pra msg dinâmica: %s', _e
            )
        if len(datas) >= 3:
            return saud + (
                '##1f4c5## *Essas são as próximas datas disponíveis pra instalação:*\n\n'
                f'*1)* {datas[0]}\n'
                f'*2)* {datas[1]}\n'
                f'*3)* {datas[2]}\n\n'
                '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._'
            )
        # Fallback se API não retornar datas
        return saud + (
            '##1f4c5## *Qual a melhor data pra instalação?*\n\n'
            '_Digite no formato 01/01/2026, ou aguarde um momentinho que '
            'vou tentar buscar as datas disponíveis._'
        )

    mapa_msgs = {
        'nome_razaosocial':  'Agora me passa seu *nome completo*?',
        'cpf_cnpj':          'Pra começar, pode me informar seu *CPF*? ##1f194##\n\n'
                             '_Exemplo: 999.999.999-99_\n\n'
                             'Vou usar pra verificar se você já tem cadastro com a gente.',
        'rg':                'Agora, digite o número do seu *RG*.',
        'data_nascimento':   'Informe sua *data de nascimento*.\n\n_Formato: 01/01/2000_',
        'email':             'Pode me informar seu *e-mail*?\n\n_Exemplo: nome@exemplo.com_',
        'cidade':            'Em qual *cidade* você reside?',
        'cep':               'Pode me passar o *CEP* da sua residência? ##1f3e0##\n\n_Formato: 64000-000_',
        'rua':               'Qual é o *nome da sua rua*?',
        'bairro':            'Qual é o *bairro*?',
        'numero_residencia': 'Qual o *número da residência*?\n\n_Se não tiver, envie *S/N*_',
        'ponto_referencia':  'Tem algum *ponto de referência* perto da sua casa? ##263A##',
        'data_instalacao':   'Qual a melhor *data* pra instalação?\n\n_Formato: 01/01/2026_',

        # ── Perguntas COM OPÇÕES (formato lúdico WhatsApp) ──────────
        # Instrução SEMPRE explicita o formato esperado + exemplo do que
        # vale, pra reduzir resposta inválida tipo "Dia 20".
        'tipo_imovel': (
            '##1f3e0## *A internet será para qual tipo de imóvel?*\n\n'
            '*1)* ##1f3e1## Casa\n'
            '*2)* ##1f3e2## Empresa\n\n'
            '_##1f4cc## Responda apenas com o *número* da opção (*1* ou *2*)._'
        ),
        'id_plano_rp': (
            '##1f4e6## *Nossos planos disponíveis:*\n\n'
            '*1)* ##1f680## *Plano 620 Mega*\n'
            '      ##1f4b0## R$ 99,90/mês\n\n'
            '*2)* ##26a1## *Plano 1G Turbo*\n'
            '      ##1f4b0## R$ 129,90/mês\n\n'
            '*3)* ##1f4f6## *1 Giga + Ponto Adicional*\n'
            '      ##1f4b0## R$ 149,90/mês\n\n'
            '_##1f4cc## Responda apenas com o *número* do plano (*1*, *2* ou *3*)._'
        ),
        'id_dia_vencimento': (
            '##1f4c5## *Qual o melhor dia pro vencimento da fatura?*\n\n'
            '*1)* Dia 1\n'
            '*2)* Dia 5\n'
            '*3)* Dia 15\n'
            '*4)* Dia 20\n\n'
            '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2*, *3* ou *4*)._'
        ),
        'turno_instalacao': (
            '##23f0## *Qual o melhor turno pra instalação?*\n\n'
            '*1)* ##1f305## Manhã\n'
            '*2)* ##2600## Tarde\n\n'
            '_##1f4cc## Responda apenas com o *número* da opção (*1* ou *2*)._'
        ),

        # ── DOCUMENTAÇÃO (3 imagens) ────────────────────────────────
        'doc_selfie_recebida': (
            '##1f4f8## *Pra finalizar, preciso de 3 fotos.*\n\n'
            '*1ª foto:* envie uma *SELFIE* segurando seu RG ou CNH ao lado do rosto.\n\n'
            '_Mande a foto como anexo no chat._'
        ),
        'doc_frente_recebida': (
            '##1f4f7## *2ª foto:* envie a *FRENTE* do seu documento (RG ou CNH).\n\n'
            '_Confira se as informações estão legíveis antes de enviar._'
        ),
        'doc_verso_recebida': (
            '##1f4f7## *3ª foto:* envie o *VERSO* do seu documento.\n\n'
            '_Última foto, depois finalizamos!_'
        ),
    }
    base = mapa_msgs.get(
        campo_faltante,
        f'Pode me passar seu {campo_faltante.replace("_", " ")}?',
    )
    # Override configurável na ferramenta (chave pergunta_<campo>). Só as chaves
    # semeadas ficam editáveis; as demais mantêm o texto acima (fallback).
    base = mensagens_client.texto(f'pergunta_{campo_faltante}', base)
    return saud + base


def _sanitize(s: Any) -> Any:
    """Remove caracteres de controle (\\n, \\r, \\t) que quebram o JSON
    quando o Matrix interpola {#var} dentro de strings JSON do body.
    """
    if isinstance(s, str):
        return s.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
    return s


_RE_EMOJI_TOKEN = re.compile(r'##([0-9a-fA-F]{2,6})##')


def _token_para_emoji(m) -> str:
    try:
        return chr(int(m.group(1), 16))
    except (ValueError, OverflowError):
        return ''


def _limpar_texto_ura(s: str) -> str:
    """Texto de OPÇÃO: sem emoji, sem markdown, uma linha só."""
    s = _RE_EMOJI_TOKEN.sub('', s or '')
    s = s.replace('*', '').replace('_', '')
    return re.sub(r'\s+', ' ', s).strip()


def _estilizar_pergunta_ura(linhas: list[str]) -> str:
    """Corpo da PERGUNTA estilizado pro WhatsApp: mantém quebras de linha,
    *negrito* e os tokens de emoji ##hex## COMO ESTÃO — é o padrão do canal
    (o Matrix converte o token no envio; emoji unicode direto vira '!'/'?')."""
    txt = '\n'.join(linhas)
    txt = re.sub(r'[ \t]+\n', '\n', txt)          # espaços soltos no fim de linha
    txt = re.sub(r'\n{3,}', '\n\n', txt)          # no máx. 1 linha em branco
    return txt.strip()


# Rótulos CURTOS (≤ 20 caracteres — limite dos botões do WhatsApp) para as
# opções conhecidas. Casados por palavra-chave no texto completo da opção,
# então continuam funcionando se os textos forem editados levemente.
_OPCOES_CURTAS: list[tuple[re.Pattern, str]] = [
    (re.compile(p, re.I), rotulo) for p, rotulo in [
        (r'sim,?\s*é esse cpf',            'Sim, é esse CPF'),
        (r'outro cpf',                     'Outro CPF'),
        (r'continuar de onde',             'Continuar'),
        (r'recome[çc]ar do in[ií]cio',     'Recomeçar'),
        (r'contratar um novo servi',       'Novo serviço'),
        (r'upgrade de plano',              'Upgrade de plano'),
        (r'acompanhar status',             'Status instalação'),
        (r'falar com atendimento',         'Atendimento'),
        (r'finalizar atendimento',         'Finalizar'),
        (r'sim,?\s*est[áa] correto',       'Sim, está correto'),
        (r'n[ãa]o,?\s*preciso corrigir',   'Não, corrigir'),
        (r'sim,?\s*quero esse plano',      'Sim, quero esse'),
        (r'n[ãa]o,?\s*quero ver outro',    'Ver outro plano'),
        (r'casa t[ée]rrea',                'Casa térrea'),
        (r'condom[íi]nio',                 'Condomínio'),
        (r'apartamento',                   'Apartamento'),
        (r'ponto adicional',               '1 Giga + Ponto'),
        (r'1\s*g(iga)?\s*turbo|1g\b',      '1 Giga Turbo'),
        (r'620',                           '620 Mega'),
        (r'sim,?\s*voltar ao menu',        'Voltar ao menu'),
        (r'n[ãa]o,?\s*obrigado',           'Encerrar'),
        (r'dados pessoais',                'Dados pessoais'),
        (r'plano selecionado',             'Plano'),
        (r'endere[çc]o',                   'Endereço'),
        (r'^manh[ãa]\b',                   'Manhã'),
        (r'^tarde\b',                      'Tarde'),
        (r'^sim\b',                        'Sim'),
        (r'^n[ãa]o\b',                     'Não'),
    ]
]

# Ruído comum em opções dinâmicas (nomes de serviço/plano do HubSoft)
_RE_PRECO = re.compile(r'\s*[—-]\s*R\$\s*[\d.,]+(\s*/\s*m[êe]s)?', re.I)
_RE_PARENTESE = re.compile(r'\s*\([^)]*\)')
_RE_PREFIXO_PLANO = re.compile(r'^\s*(mega\s+)?plano\s+', re.I)


def _encurtar_opcao(texto: str) -> str:
    """Rótulo da opção com NO MÁXIMO 20 caracteres (botões do WhatsApp)."""
    for padrao, rotulo in _OPCOES_CURTAS:
        if padrao.search(texto):
            return rotulo
    t = _RE_PRECO.sub('', texto)
    t = _RE_PARENTESE.sub(' ', t)
    t = _RE_PREFIXO_PLANO.sub('', t)
    t = re.sub(r'\s+', ' ', t).strip(' .-—')
    if len(t) > 20:
        t = t[:19].rstrip() + '…'
    return t or texto[:20]


_RE_OPCAO_URA = re.compile(r'^\s*\*?(\d+)\)\*?\s*(.*\S)\s*$')
_RE_INSTRUCAO_URA = re.compile(r'responda\s+(apenas\s+)?com', re.I)


def montar_ura(pergunta_id: str, msg: str) -> dict | None:
    """Estrutura a URA de OPÇÕES a partir da mensagem da pergunta.

    Campo ADITIVO do /proximo-passo:
    - `pergunta`      → corpo ESTILIZADO pro WhatsApp (quebras de linha,
                        *negrito* e emojis reais) — usar no body da URA.
    - `pergunta_safe` → mesma pergunta em linha única (p/ bodies JSON).
    - `opcoes[].texto`→ rótulo CURTO (≤ 20 chars — limite de botão).
    - `opcoes[].texto_completo` → texto integral da opção (p/ descrição).
    Pergunta aberta (sem opções) → None (campo `ura` sai null).
    """
    if not msg:
        return None
    opcoes: list[dict] = []
    linhas_pergunta: list[str] = []
    for linha in msg.split('\n'):
        m = _RE_OPCAO_URA.match(linha) if linha.strip() else None
        if m:
            texto = _limpar_texto_ura(m.group(2))
            if texto:
                opcoes.append({'numero': m.group(1), 'texto_completo': texto})
            continue
        if _RE_INSTRUCAO_URA.search(linha):
            continue
        if opcoes:
            limpo = _limpar_texto_ura(linha)
            if limpo:
                # linha de continuação da última opção (ex.: preço do plano)
                opcoes[-1]['texto_completo'] += f' — {limpo}'
        else:
            linhas_pergunta.append(linha)
    if len(opcoes) < 2:
        return None
    for o in opcoes:
        o['texto'] = _encurtar_opcao(o['texto_completo'])
    pergunta = _estilizar_pergunta_ura(linhas_pergunta)
    return {
        'tipo': 'opcoes',
        'titulo': pergunta_id or '',
        'pergunta': pergunta,
        'pergunta_safe': re.sub(r'\s+', ' ', pergunta).strip(),
        'opcoes': opcoes,
        'total_opcoes': len(opcoes),
        'respostas_validas': [o['numero'] for o in opcoes],
    }


# Sufixo do título da URA de confirmação de plano — identifica QUAL plano está
# sendo confirmado (roteamento no Matrix): confirmacao_plano_620 ·
# confirmacao_plano_1g · confirmacao_plano_1g_ponto_adc.
PLANO_SUFIXO_URA = {1649: '620', 1648: '1g', 2088: '1g_ponto_adc'}


def _titulo_ura(pergunta_id: str, dados: dict) -> str:
    """Título da URA — específico por plano na confirmação de plano."""
    if pergunta_id == 'confirmacao_plano':
        try:
            suf = PLANO_SUFIXO_URA.get(int((dados or {}).get('id_plano_rp') or 0))
        except (TypeError, ValueError):
            suf = None
        if suf:
            return f'confirmacao_plano_{suf}'
    return pergunta_id or ''


def _resposta(*, lead_id, status, proximo, pergunta_id, deve_perguntar,
              deve_transbordar, motivo, msg, intent, dados) -> dict:
    return {
        'lead_id': lead_id,
        'status_lead': _sanitize(status),
        'proximo_passo': _sanitize(proximo),
        'proxima_pergunta_id': _sanitize(pergunta_id),
        'deve_perguntar': deve_perguntar,
        'deve_transbordar': deve_transbordar,
        'motivo': _sanitize(motivo),
        'mensagem_inicial': msg,           # com \n pra formatar bonito no WhatsApp
        'mensagem_inicial_safe': _sanitize(msg),  # sem \n — use em bodies JSON
        'intent_detectado': _sanitize(intent),
        'dados_ja_coletados': dados,
        # URA estruturada (aditivo): null em pergunta aberta; objeto quando a
        # mensagem oferece opções numeradas ao cliente. Título da confirmação
        # de plano é específico por plano (confirmacao_plano_620/1g/1g_ponto_adc).
        'ura': montar_ura(_titulo_ura(pergunta_id, dados),
                          msg if deve_perguntar else ''),
    }


# ─────────────────────────────────────────────────────────────────────
# RECONTATO POR TEMPO DE ESPERA (cliente não respondeu a uma pergunta)
# ─────────────────────────────────────────────────────────────────────
# Quantas tentativas de reengajamento antes de encerrar/pausar.
MAX_RECONTATO = 3

# Mensagens ESCALONADAS — uma diferente a cada silêncio. O objetivo é FISGAR o
# cliente de volta (não repetir a pergunta). A pergunta pendente é re-perguntada
# quando o cliente responde e o fluxo retoma (via /proximo-passo ou reentrada no
# nó da pergunta no Matrix). {saud} = "Oi, Nome! " (ou "Oi! " sem nome).
# SEM EMOJIS: no WhatsApp do fluxo Matrix os emojis chegam como "?" — texto puro.
_MSGS_RECONTATO = [
    "{saud}Vi que você parou por aqui. Ainda consigo te ajudar? "
    "É só me mandar um *oi* que a gente continua de onde parou.",

    "{saud}Não quero tomar seu tempo. Em poucos minutos a gente finaliza seu "
    "atendimento. Ainda está por aí? Me responde que eu sigo com você.",

    "{saud}Essa é a última mensagem por aqui. Se ainda tiver interesse, é só me "
    "responder que eu retomo na hora, de onde a gente parou.",
]

_MSG_DESPEDIDA_RECONTATO = (
    "{saud}Vou pausar seu atendimento por enquanto. Quando quiser retomar, é só "
    "me chamar de novo que a gente continua de onde parou. Até breve!"
)


def _saudacao_recontato(lead) -> str:
    primeiro = _primeiro_nome(lead)
    return f'Oi, {primeiro}! ' if primeiro else 'Oi! '


def decidir_recontato(telefone: str, lead_id: int | None = None,
                      pergunta_id: str = '', ultima_mensagem: str = '') -> dict:
    """Decisor de RECONTATO — chamado pelo Matrix quando o cliente NÃO responde
    (caiu no "tempo de espera").

    Escala uma mensagem de reengajamento diferente a cada silêncio consecutivo.
    Depois de MAX_RECONTATO tentativas, responde `acao='encerrar'`. O contador
    zera automaticamente quando o cliente volta a responder (reset no /validar).
    """
    from src.contexto.conversa import gerenciador as _ctx_g
    n = _ctx_g.incrementar_tentativa(telefone, '__recontato__')

    lead = None
    try:
        lead = _alvo.consultar_lead_cached(lead_id, telefone=telefone)
    except Exception as e:  # noqa: BLE001
        logger.warning('recontato: consultar_lead falhou tel=%s: %s', telefone, e)
    saud = _saudacao_recontato(lead)

    if n > MAX_RECONTATO:
        # Esgotou as tentativas. NÃO resetar o contador aqui: se o Matrix voltar
        # a chamar /recontato (o laço de tempo-de-espera continua firing), um
        # reset reiniciaria a escalada num LOOP (foi o que aconteceu — 7 msgs).
        # Manda a despedida UMA única vez (n == MAX+1); dos próximos silêncios em
        # diante, 'encerrar' com mensagem VAZIA → pausa silenciosa, só aguardando
        # o cliente. O contador só zera quando o cliente responde (/validar).
        primeira_vez = (n == MAX_RECONTATO + 1)
        corpo_desp = mensagens_client.texto('recontato_despedida', _MSG_DESPEDIDA_RECONTATO)
        msg = corpo_desp.replace('{saud}', saud) if primeira_vez else ''
        return {
            'acao': 'encerrar', 'tentativa': n, 'max_tentativas': MAX_RECONTATO,
            'mensagem': msg, 'mensagem_safe': _sanitize(msg) if msg else '',
            'reperguntar': False, 'pergunta_id': pergunta_id, 'deve_transbordar': False,
        }

    corpo = mensagens_client.texto(f'recontato_{n}', _MSGS_RECONTATO[n - 1])
    msg = corpo.replace('{saud}', saud)
    return {
        'acao': 'recontatar', 'tentativa': n, 'max_tentativas': MAX_RECONTATO,
        'mensagem': msg, 'mensagem_safe': _sanitize(msg),
        # na última tentativa, sinaliza que o Matrix pode já emendar a pergunta
        # pendente após a fisgada, se preferir (opcional).
        'reperguntar': (n == MAX_RECONTATO), 'pergunta_id': pergunta_id,
        'deve_transbordar': False,
    }
