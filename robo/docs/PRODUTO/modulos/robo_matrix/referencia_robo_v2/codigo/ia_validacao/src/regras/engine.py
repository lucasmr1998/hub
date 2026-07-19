"""Engine de validação dirigido por regras.

Recebe `{question, answer, cellphone, lead_id, question_id?}` + a `regra` e:
1. Aplica o `extractor_tipo` da regra
2. Se válido, executa as ações em background (atualizar lead, status, tags, histórico)
3. Retorna o resultado padronizado pro Matrix

Não conhece "etapas" nem "fluxo" — só sabe aplicar uma regra a um par pergunta+resposta.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata
from typing import Any

from src.extractors import (
    extrair_cpf, validar_cpf,
    extrair_cep, consultar_cep_viacep,
    extrair_nome,
    extrair_telefone,
    extrair_data_nascimento,
)
from src.integracoes import robovendas
from src.regras.mensagens_client import mensagens_client
from src.integracoes import openai_imagens
from src.integracoes import openai_endereco
from src.regras import alvo as _alvo


def _set_status(lead_id: int, telefone: str, novo_status: str) -> bool:
    """Atualiza status_api no Django E sincroniza o cache do lead em memória.

    Helper que evita o bug recorrente de o cache do contexto ficar com
    status antigo após mudança no DB, fazendo /proximo-passo rotear errado.
    """
    ok = robovendas.atualizar_status(lead_id, novo_status)
    try:
        _alvo._ctx_patch_lead_cache(telefone, {'status_api': novo_status})  # noqa: SLF001
    except Exception:
        pass
    return ok


# Valor de limpeza por campo da coleta — respeita as constraints NOT-NULL do
# LeadProspecto: CharField → '' (nome/tipo_imovel/tipo_residencia/turno são
# null=False, então None estoura IntegrityError e ABORTA o update inteiro);
# Date/Boolean/Integer → None. Espelha CAMPOS_PARA_AJUSTE (onboarding).
_CLEAR_COLETA: dict = {
    'cpf_cnpj': '', 'nome_razaosocial': '', 'nome_confirmado': False,
    'data_nascimento': None,
    'email': '', 'tipo_imovel': '', 'cep': '', 'endereco_confirmado': None,
    'cidade': '', 'bairro': '', 'rua': '', 'numero_residencia': '',
    'tipo_residencia': '', 'ponto_referencia': '', 'id_plano_rp': None,
    'plano_confirmado': None, 'id_dia_vencimento': None,
    'dados_confirmados': None, 'doc_selfie_recebida': None,
    'doc_frente_recebida': None, 'doc_verso_recebida': None,
    'turno_instalacao': '', 'data_instalacao': None, 'id_hubsoft': '',
}


def _limpar_dados_coleta(lead_id: int, telefone: str, manter_cpf: bool = True) -> bool:
    """Zera os campos da sequência de coleta do lead (recomeçar do início).

    manter_cpf=True  → recomeça do NOME (mantém o CPF/id_hubsoft já informados).
    manter_cpf=False → zera também CPF/id_hubsoft → re-coleta desde o CPF.
    Só espelha no cache se o DB persistiu (senão o /proximo-passo leria dados
    'limpos' que não foram salvos).
    """
    payload = dict(_CLEAR_COLETA)
    if manter_cpf:
        payload.pop('cpf_cnpj', None)
        payload.pop('id_hubsoft', None)
    ok = _alvo.atualizar_alvo(lead_id, payload, telefone=telefone)
    if ok:
        _alvo._ctx_patch_lead_cache(  # noqa: SLF001
            telefone, {**payload, 'status_api': 'lead_novo'})
    else:
        logger.warning('_limpar_dados_coleta: atualizar_alvo falhou lead=%s', lead_id)
    return ok
from src.contexto.conversa import gerenciador as ctx_gerenciador

logger = logging.getLogger(__name__)


def _normalizar_texto(s: str) -> str:
    s = (s or '').strip().lower()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()


def _bairro_tem_viabilidade(bairro: str, resp_viab: dict) -> bool:
    """Decide se o endereço confirmado tem viabilidade, a partir da resposta
    de `/api/viabilidade/` (ver `RoboVendasClient.consultar_viabilidade`).

    Cidade sem NENHUM registro cadastrado → sem viabilidade. Registro com
    `atende_cidade_inteira=True` → viável em qualquer bairro. Caso contrário,
    o bairro informado precisa bater (normalizado) com algum bairro cadastrado
    — bairro vazio/desconhecido é tratado como sem viabilidade (conservador:
    não vender pra um bairro que não conseguimos confirmar).
    """
    registros = resp_viab.get('registros') or []
    if not registros:
        return False
    bairro_norm = _normalizar_texto(bairro)
    for reg in registros:
        if reg.get('atende_cidade_inteira'):
            return True
        if not bairro_norm:
            continue
        for b in reg.get('bairros') or []:
            if _normalizar_texto(b.get('nome')) == bairro_norm:
                return True
    return False


# ─────────────────────────────────────────────────────────────────────
# EXTRACTORS — cada um retorna (valido: bool, extracted: dict, motivo: str)
# ─────────────────────────────────────────────────────────────────────

def _ext_cpf(answer: str, config: dict) -> tuple[bool, dict, str]:
    cpf = extrair_cpf(answer)
    if not cpf:
        return False, {}, 'cpf_nao_identificado'
    if not validar_cpf(cpf):
        return False, {}, 'cpf_invalido'
    return True, {'cpf_cnpj': cpf}, ''


def _ext_cep(answer: str, config: dict) -> tuple[bool, dict, str]:
    cep = extrair_cep(answer)
    if not cep:
        return False, {}, 'cep_nao_identificado'
    via = consultar_cep_viacep(cep)
    if not via:
        return False, {}, 'cep_nao_existe'
    return True, {
        'cep': cep,
        'rua': via.get('logradouro', ''),
        'bairro': via.get('bairro', ''),
        'cidade': via.get('localidade', ''),
        'estado': via.get('uf', ''),
    }, ''


def _ext_nome(answer: str, config: dict) -> tuple[bool, dict, str]:
    r = extrair_nome(answer)
    if r.get('valido'):
        return True, {'nome_razaosocial': r['nome']}, ''
    return False, {}, r.get('motivo', 'nome_invalido')


def _ext_telefone(answer: str, config: dict) -> tuple[bool, dict, str]:
    tel = extrair_telefone(answer)
    if tel:
        return True, {'telefone': tel}, ''
    return False, {}, 'telefone_invalido'


def _ext_data(answer: str, config: dict) -> tuple[bool, dict, str]:
    r = extrair_data_nascimento(answer)
    if r.get('valido'):
        return True, {'data_nascimento': r['data']}, ''
    return False, {}, r.get('motivo', 'data_invalida')


def _ext_email(answer: str, config: dict) -> tuple[bool, dict, str]:
    if not answer:
        return False, {}, 'email_vazio'
    m = re.search(r'[\w\.\+\-]+@[\w\-]+\.[\w\.\-]+', answer)
    if m:
        return True, {'email': m.group(0).lower()}, ''
    return False, {}, 'email_invalido'


def _ext_numero(answer: str, config: dict) -> tuple[bool, dict, str]:
    a = (answer or '').strip().lower()
    if not a:
        return False, {}, 'numero_vazio'
    # Aceita S/N
    if a in {'s/n', 'sn', 'sem numero', 'sem número', 'sem'}:
        return True, {'numero_residencia': 'S/N'}, ''
    # Extrai dígitos
    m = re.search(r'\d+', a)
    if m:
        return True, {'numero_residencia': m.group(0)}, ''
    return False, {}, 'numero_invalido'


def _ext_opcao(answer: str, config: dict) -> tuple[bool, dict, str]:
    """Match contra extractor_config.opcoes = {valor_a_salvar: [aliases]}.

    Regras de match:
    - Alias com até 3 caracteres (ex: '1', '2', 'sim'): exige a resposta
      ser EXATAMENTE igual ao alias (ignorando pontuação). Evita falso
      match com substring (ex: '1' em '64011-852').
    - Alias com 4+ caracteres (ex: 'casa', 'empresa', 'manha'): aceita
      somente `alias in resposta` (cliente escreveu mais texto que inclui
      o alias). NÃO usar `resposta in alias` — uma resposta '2' acaba
      casando com qualquer alias longo que contenha '2' (ex: '620mb'),
      escolhendo o plano errado.
    """
    import re as _re
    opcoes = config.get('opcoes', {})
    if not opcoes:
        return True, {'opcao_escolhida': answer.strip()}, ''
    a = (answer or '').strip().lower()
    # Limpa pontuação/acentos soltos comuns em respostas curtas:
    # '1)', '1.', '1-', "1'", '1´', '1`', '1"' etc
    _LIXO = ' \t.)(-:,;!?´`\'"‘’“”'
    a_limpo = a.strip(_LIXO)

    # MAIS ESPECÍFICO PRIMEIRO: testa os aliases do MAIS LONGO pro mais curto,
    # independente da ordem das opções. Os botões da URA mandam o TEXTO da
    # opção ("1 Giga + Ponto", "Dia 15") — sem isso, "1 Giga + Ponto" casava
    # com o alias '1 giga' do plano errado e "Dia 15" com 'dia 1'.
    pares = [(valor, alias.lower().strip())
             for valor, aliases in opcoes.items()
             for alias in aliases if alias and alias.strip()]
    pares.sort(key=lambda p: -len(p[1]))

    for valor, al in pares:
        if len(al) <= 3:
            # Match exato pra aliases curtos (números, sim/nao)
            if a_limpo == al:
                return True, {'opcao': valor}, ''
        else:
            # Alias longo é substring DA resposta (cliente digitou frase).
            # NÃO testar o inverso pra evitar false-positive de chars únicos.
            if al in a:
                return True, {'opcao': valor}, ''
    return False, {}, 'opcao_nao_reconhecida'


def _ext_confirmacao(answer: str, config: dict) -> tuple[bool, dict, str]:
    a = (answer or '').strip().lower()
    if not a:
        return False, {}, 'confirmacao_ambigua'

    # Remove pontuação/acentos soltos (ex: "1)", "1.", "Sim,", "1´")
    a_limpo = a.strip(' \t.)(-:,;!?´`\'"‘’“”')

    # ── 1) Match EXATO pra respostas curtas (evita conflito de substring) ──
    SIM_EXATO = {'1', '01', 's', 'sim', 'ok', 'yes', 'y'}
    NAO_EXATO = {'2', '02', 'n', 'não', 'nao', 'no'}
    if a_limpo in SIM_EXATO:
        return True, {'confirmacao': True}, ''
    if a_limpo in NAO_EXATO:
        return True, {'confirmacao': False}, ''

    # ── 2) NÃO primeiro (pra "não está correto" não cair em "correto") ────
    # Inclui frases de "quero trocar/ver outro" (típicas da opção 2 da
    # confirmação de plano) — devem ser NÃO mesmo contendo "quero".
    NAO_PALAVRAS = ('não', 'nao', 'corrigir', 'errado', 'voltar', 'negativo',
                    'incorreto', 'errei', 'errou', 'ver outro', 'outro plano',
                    'trocar', 'mudar', 'outra opção', 'outra opcao')
    if any(w in a for w in NAO_PALAVRAS):
        return True, {'confirmacao': False}, ''

    # ── 3) SIM por substring de palavras longas (>= 3 chars) ──────────────
    SIM_PALAVRAS = ('sim', 'confirmo', 'confirmar', 'confirma', 'tudo certo',
                    'tá certo', 'ta certo', 'isso', 'claro', 'positivo',
                    'pode seguir', 'prosseguir', 'beleza', 'manda', 'correto',
                    'está correto', 'esta correto', 'corretissimo', 'corretíssimo',
                    'pode', 'certo', 'certeza', 'com certeza', 'aceito',
                    'fechou', 'fechado', 'bora', 'aham', 'uhum', 'exato',
                    'perfeito', 'isso mesmo', 'quero esse', 'quero sim',
                    'pode confirmar', 'pode prosseguir', 'vamos', 'show',
                    'ótimo', 'otimo', 'concordo', 'afirmativo')
    if any(w in a for w in SIM_PALAVRAS):
        return True, {'confirmacao': True}, ''

    return False, {}, 'confirmacao_ambigua'


def _ext_imagem(answer: str, config: dict) -> tuple[bool, dict, str]:
    """Valida imagem recebida pelo Matrix.

    O Matrix, ao receber upload no sol (allow_upload=1), preenche {#resposta_cliente}
    com o NOME do arquivo (ex: 'wamid.HBgMNTU...A.jpg'). Esta função:
    - Aceita: URL completa (http/https) → usa direto
    - Aceita: filename com extensão de imagem → constrói URL Matrix
    - Rejeita: texto que não parece arquivo de imagem → pede pra reenviar

    URL Matrix: https://megalink.matrixdobrasil.ai/public/imagens/uploads/msgs/YYYY/MM/{filename}
    """
    import datetime
    a = (answer or '').strip()
    if not a:
        return False, {}, 'imagem_nao_recebida'

    # Já é URL completa? usa direto
    if a.startswith('http://') or a.startswith('https://'):
        return True, {'url_imagem': a}, ''

    # É filename com extensão de imagem? constrói URL Matrix
    extensoes_validas = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.heic')
    if any(a.lower().endswith(ext) for ext in extensoes_validas):
        agora = datetime.datetime.now()
        url = f'https://megalink.matrixdobrasil.ai/public/imagens/uploads/msgs/{agora.year}/{agora.month:02d}/{a}'
        return True, {'url_imagem': url}, ''

    return False, {}, 'imagem_nao_recebida'


def _ext_texto_livre(answer: str, config: dict) -> tuple[bool, dict, str]:
    """Texto livre — aceita qualquer coisa não-vazia."""
    if answer and answer.strip():
        return True, {'valor': answer.strip()}, ''
    return False, {}, 'resposta_vazia'


def _ext_livre(answer: str, config: dict) -> tuple[bool, dict, str]:
    """Sempre aceita (mesmo vazio)."""
    return True, {'valor': (answer or '').strip()}, ''


EXTRACTORS = {
    'cpf': _ext_cpf,
    'cep': _ext_cep,
    'nome': _ext_nome,
    'telefone': _ext_telefone,
    'data_nascimento': _ext_data,
    'email': _ext_email,
    'numero': _ext_numero,
    'opcao': _ext_opcao,
    'confirmacao': _ext_confirmacao,
    'imagem': _ext_imagem,
    'texto_livre': _ext_texto_livre,
    'livre': _ext_livre,
}


# ─────────────────────────────────────────────────────────────────────
# AÇÕES (em background)
# ─────────────────────────────────────────────────────────────────────

def _aplicar_acoes_background(
    regra: dict,
    extracted: dict,
    cellphone: str,
    lead_id: int | None,
    question: str,
    answer: str,
):
    """Executa todas as ações da regra. Cada falha é isolada."""
    acoes_log: list[dict] = []

    # 1) Resolve lead_id: prioriza o que veio do request, depois cache no contexto,
    #    e só por último consulta Django.
    ctx = ctx_gerenciador.obter(cellphone)
    if not lead_id:
        lead_id = ctx.get('lead_id')
    if not lead_id:
        lead_id = robovendas.garantir_lead(cellphone)
        if not lead_id:
            return [{'tipo': 'garantir_lead', 'ok': False, 'motivo': 'falha ao criar/buscar lead'}]
        acoes_log.append({'tipo': 'garantir_lead', 'ok': True, 'lead_id': lead_id})
    # Cacheia pra próximas chamadas
    ctx['lead_id'] = lead_id

    # 1) Atualizar campo do lead
    campo = regra.get('campo_lead_atualizar') or ''
    payload: dict[str, Any] = {}

    # Caso especial: CEP — salva o endereço inteiro independente de campo_lead_atualizar
    if regra.get('extractor_tipo') == 'cep':
        payload = {k: v for k, v in extracted.items() if k in ('cep', 'rua', 'bairro', 'cidade', 'estado') and v}

    # Caso especial: CONFIRMAÇÃO — salva o boolean direto no campo
    elif regra.get('extractor_tipo') == 'confirmacao' and 'confirmacao' in extracted:
        if campo:
            payload[campo] = bool(extracted['confirmacao'])
        # confirmacao_plano NEGADA: NÃO gravar False — False conta como
        # "respondido" e o fluxo PULARIA a confirmação do próximo plano
        # escolhido. O hook síncrono já limpou plano_confirmado=None (e o
        # id_plano_rp) — esta ação em background regravava False por cima.
        if (regra.get('question_id') == 'confirmacao_plano'
                and extracted.get('confirmacao') is False):
            payload.pop(campo, None)
        # Confirmação de endereço NEGADA → limpa rua/bairro/cidade pra perguntar manual
        if (regra.get('question_id') == 'confirmacao_endereco'
                and extracted.get('confirmacao') is False):
            payload.update({'rua': '', 'bairro': '', 'cidade': ''})
        # Confirmação de agendamento NEGADA → limpa turno + data pra voltar
        # pra etapa de escolha. Matrix detecta data_instalacao vazia e volta
        # pra escolha_turno.
        if (regra.get('question_id') == 'confirmacao_agendamento'
                and extracted.get('confirmacao') is False):
            payload.update({'turno_instalacao': '', 'data_instalacao': None})

    if campo and extracted and not payload:
        valor_para_campo = extracted.get(campo)
        if valor_para_campo is None:
            valor_para_campo = extracted.get('valor') or extracted.get('opcao')
        if valor_para_campo is not None and valor_para_campo != '':
            # Converte pra int se o campo for de ID
            if campo in ('id_plano_rp', 'id_dia_vencimento', 'id_vendedor_rp', 'id_hubsoft'):
                try:
                    valor_para_campo = int(valor_para_campo)
                except (ValueError, TypeError):
                    pass
            payload = {campo: valor_para_campo}

    # Se for plano, também grava o valor monetário automaticamente
    if regra.get('extractor_tipo') == 'opcao' and campo == 'id_plano_rp':
        from src.integracoes.robovendas import PLANOS as _PLANOS
        for chave, info in _PLANOS.items():
            if info['id_plano_rp'] == payload.get('id_plano_rp'):
                payload['valor'] = info['valor']
                break

    # coleta_nome respondida no fluxo → confirma o nome (push name não conta)
    if extracted.get('nome_confirmado'):
        payload['nome_confirmado'] = True

    # Detecta se o lead está em fluxo de Novo Serviço (cliente Hubsoft contratando
    # serviço adicional). Se sim, campos vão pro NewService em vez do LeadProspecto,
    # e o status_api do lead NÃO deve ser alterado pelas regras (ele está marcado
    # como 'em_fluxo_new_service' até o fluxo finalizar).
    em_fluxo_ns = _alvo.descobrir_new_service_id(lead_id, cellphone) is not None

    if payload:
        ok = _alvo.atualizar_alvo(lead_id, payload, telefone=cellphone)
        acoes_log.append({'tipo': 'atualizar_alvo', 'ok': ok,
                          'alvo': 'new_service' if em_fluxo_ns else 'lead',
                          'campos': list(payload.keys())})

    # Se foi uma confirmação NEGADA, NÃO aplica ações "de sucesso"
    # (status_api, tags, histórico). O campo já foi salvo com False acima.
    confirmacao_negada = (
        regra.get('extractor_tipo') == 'confirmacao'
        and extracted.get('confirmacao') is False
    )

    # 2) Atualizar status_api (pula se confirmação foi negada OU se está em fluxo NS)
    novo_status = regra.get('status_api_apos_sucesso') or ''
    if novo_status and not confirmacao_negada and not em_fluxo_ns:
        ok = _set_status(lead_id, cellphone, novo_status)
        acoes_log.append({'tipo': 'atualizar_status', 'ok': ok, 'valor': novo_status})

    # 3) Adicionar/remover tags (pula se confirmação foi negada)
    tags_add = regra.get('tags_adicionar') or []
    tags_rem = regra.get('tags_remover') or []
    if (tags_add or tags_rem) and not confirmacao_negada:
        ok = robovendas.atualizar_tags(lead_id, tags_add=tags_add, tags_remove=tags_rem)
        acoes_log.append({'tipo': 'tags', 'ok': ok, 'add': tags_add, 'remove': tags_rem})

    # 4) Registrar histórico (pula se confirmação foi negada)
    hist_status = regra.get('historico_status_apos_sucesso') or ''
    if hist_status and not confirmacao_negada:
        template = regra.get('historico_observacoes_template') or ''
        observacoes = template.format(question=question, answer=answer, extracted=extracted) if template else ''
        ok = robovendas.registrar_historico(
            telefone=cellphone, lead_id=lead_id,
            status=hist_status, observacoes=observacoes,
        )
        acoes_log.append({'tipo': 'historico', 'ok': ok, 'status': hist_status})

    # 5) Registrar imagem + marcar boolean correspondente no lead
    if regra.get('extractor_tipo') == 'imagem' and extracted.get('url_imagem'):
        descricao = regra.get('descricao_imagem') or 'documento'
        # Status da imagem: se passou pelo openai_imagens com aprovado=True,
        # marca como 'aprovado_ia' (status intermediário — aguarda validação
        # humana na plataforma). Quando o usuário clicar em "Validar
        # Aprovação IA" no painel, vira 'documentos_validos' e dispara o
        # signal que aceita o contrato no Hubsoft.
        ia_check = extracted.get('ia_validacao') or {}
        status_img = ''
        obs_img = ''
        if ia_check.get('aprovado') is True:
            status_img = 'aprovado_ia'
            obs_img = f'Aprovado pela IA Vision: {ia_check.get("motivo", "")[:120]}'
        ok = _alvo.registrar_imagem_alvo(
            lead_id, extracted['url_imagem'], descricao,
            status_validacao=status_img, observacao_validacao=obs_img,
            telefone=cellphone,
        )
        acoes_log.append({'tipo': 'registrar_imagem', 'ok': ok,
                          'alvo': 'new_service' if em_fluxo_ns else 'lead',
                          'descricao': descricao, 'status': status_img})

        # Nota: o flag doc_*_recebida já foi marcado SÍNCRONO no
        # validar_por_regra (logo após a IA aprovar), antes de
        # _disparar_acoes começar. Aqui só registramos a imagem
        # (o registro pode demorar e não bloqueia o avanço do fluxo).

    return acoes_log


def _disparar_acoes(regra, extracted, cellphone, lead_id, question, answer):
    """Roda ações em thread daemon — não bloqueia a resposta."""
    t = threading.Thread(
        target=_aplicar_acoes_background,
        args=(regra, dict(extracted), cellphone, lead_id, question, answer),
        daemon=True,
    )
    t.start()


# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

def validar_por_regra(
    regra: dict,
    question: str,
    answer: str,
    cellphone: str,
    lead_id: int | None = None,
) -> dict:
    """Função principal: aplica uma regra a uma pergunta+resposta.

    Retorna o JSON pronto pra resposta do endpoint `/validar`.
    """
    # O cliente respondeu → reengajou: zera o contador de recontato por tempo de
    # espera, para a escalada de mensagens recomeçar do zero num próximo silêncio.
    try:
        ctx_gerenciador.resetar_tentativas(cellphone, '__recontato__')
    except Exception:  # noqa: BLE001
        pass

    extractor_tipo = regra.get('extractor_tipo', 'texto_livre')
    extractor_fn = EXTRACTORS.get(extractor_tipo, _ext_texto_livre)
    config = regra.get('extractor_config', {}) or {}

    # Menu de cliente existente: numeração DINÂMICA — a opção de upgrade só
    # aparece p/ quem tem serviço habilitado. Reconstrói as opções de extração
    # com a MESMA regra de exibição do onboarding, p/ que o número digitado pelo
    # cliente case com o que ele viu (sem buracos na numeração).
    if regra.get('question_id') == 'menu_cliente_existente':
        try:
            from src.menu_cliente import opcoes_extracao
            _lead = _alvo.consultar_lead_cached(lead_id, telefone=cellphone) if lead_id else None
            _tem = bool((_lead or {}).get('tem_servico_habilitado'))
            config = {**config, 'opcoes': opcoes_extracao(_tem)}
        except Exception as _e:  # noqa: BLE001
            logger.warning('menu dinâmico (extração) falhou lead=%s: %s', lead_id, _e)

    # Aplica extractor
    valido, extracted, motivo = extractor_fn(answer, config)

    # ── escolha_data: o botão da URA manda a DATA ("15/07/2026"), não o
    #    número. Se não casou com 1/2/3, procura a data na lista oferecida
    #    e converte pra opção correspondente.
    if not valido and regra.get('question_id') == 'escolha_data':
        _m_data = re.search(r'\d{2}/\d{2}/\d{4}', answer or '')
        if _m_data:
            try:
                from datetime import datetime as _dt
                _hoje = _dt.now().strftime('%d/%m/%Y')
                _datas = robovendas.consultar_datas_disponiveis(_hoje) or []
                for _i, _dstr in enumerate(_datas):
                    if _m_data.group(0) in str(_dstr) or str(_dstr) in _m_data.group(0):
                        valido, extracted, motivo = True, {'opcao': str(_i + 1)}, ''
                        logger.info('escolha_data por TEXTO: %r → opção %s',
                                    answer[:30], _i + 1)
                        break
            except Exception as e:  # noqa: BLE001
                logger.warning('escolha_data por texto falhou: %s', e)

    # Reservado pra ser preenchido no hook do escolha_data (mais abaixo),
    # após o mapeamento opção→data + salvamento no lead.
    agendamento_resultado: dict | None = None

    # ── coleta_nome válida → marca nome_confirmado ─────────────────────
    # O robô SEMPRE pergunta o nome completo: nome pré-preenchido (push name
    # do WhatsApp) não conta. Só o nome respondido AQUI confirma o campo.
    if (valido and regra.get('question_id') == 'coleta_nome'
            and extracted.get('nome_razaosocial')):
        extracted['nome_confirmado'] = True

    # NOTA: o gate de "retomar/recomeçar/outro CPF" (cliente que reabre com
    # cadastro em andamento) AGORA também roda no determinístico/Matrix:
    # onboarding._talvez_retomada mostra a pergunta (question_id=
    # 'retomada_confirmacao') e a resposta é tratada no bloco homônimo abaixo.
    # A camada conversacional (src.conversacional.retomada) segue independente.

    # ── Endereço CONFIRMADO → checa viabilidade técnica (cidade/bairro) ──
    # Cruza o endereço salvo do lead contra o cadastro de cobertura
    # (CidadeViabilidade/BairroViabilidade no Django). Se não tiver
    # viabilidade, transborda pro atendente em vez de seguir vendendo pra
    # uma região sem cobertura de rede. Falha na consulta (API fora do ar)
    # NÃO bloqueia a venda — segue o fluxo normal e só loga o problema.
    endereco_sem_viabilidade = False
    endereco_viab_em_new_service = False
    if (valido
            and regra.get('question_id') == 'confirmacao_endereco'
            and extracted.get('confirmacao') is True
            and lead_id):
        try:
            dados_alvo = _alvo.consultar_dados_alvo(lead_id, telefone=cellphone) or {}
            endereco_viab_em_new_service = dados_alvo.get('_alvo') == 'new_service'
            cep = (dados_alvo.get('cep') or '').strip()
            cidade = (dados_alvo.get('cidade') or '').strip()
            estado = (dados_alvo.get('estado') or '').strip()
            bairro = (dados_alvo.get('bairro') or '').strip()
            resp_viab = robovendas.consultar_viabilidade(cep=cep, cidade=cidade, uf=estado)
            if resp_viab and resp_viab.get('sucesso'):
                endereco_sem_viabilidade = not _bairro_tem_viabilidade(bairro, resp_viab)
        except Exception as e:
            logger.warning('Checagem de viabilidade falhou lead=%s: %s', lead_id, e)

    # ── tipo_imovel='empresa' → transbordo direto pra atendente ───────
    # Bot só atende vendas residenciais. Empresarial vai pra atendente
    # especializado que cuida de planos comerciais.
    # GUARDA contra race: se já estamos no fluxo de Novo Serviço E o NS atual
    # já tem tipo_imovel='casa', uma re-aplicação da regra (cliente mandou "2"
    # duas vezes, Matrix re-roteou com question_id velho) NÃO deve resetar pra
    # empresa — ignoramos o trigger.
    tipo_imovel_empresa = (
        valido
        and regra.get('question_id') == 'tipo_imovel'
        and extracted.get('opcao') == 'empresa'
    )
    if tipo_imovel_empresa and lead_id:
        try:
            _nsid_atual = _alvo.descobrir_new_service_id(lead_id, cellphone)
            if _nsid_atual:
                _ns_atual = robovendas.obter_new_service(_nsid_atual) or {}
                if (_ns_atual.get('tipo_imovel') or '') == 'casa':
                    # Race: cliente mandou "2" duas vezes, Matrix re-roteou.
                    # NS já é casa — desabilita o trigger empresa pra não
                    # transbordar e não sobrescrever. Trata como no-op.
                    logger.info(
                        'Ignorando re-aplicação tipo_imovel=empresa: NS %s já é casa (race)',
                        _nsid_atual,
                    )
                    tipo_imovel_empresa = False
                    # Limpa payload de escrita pra não sobrescrever
                    extracted.pop('opcao', None)
                    extracted.pop('tipo_imovel', None)
        except Exception as e:
            logger.warning('Falha guarda race tipo_imovel: %s', e)

    # ── Menu cliente existente: decide ação por opção escolhida ───────
    # Opção 1 (novo_servico)  → inicia fluxo de coleta de Novo Serviço
    #                           (cria NewService, marca lead em_fluxo_new_service)
    # Opções 2, 4 (upgrade/atendimento) → transbordo pra humano.
    # Opção 3 (acompanhar OS) → NÃO transborda: mostra info da OS + seta
    # status='aguardando_finalizacao' pra próxima volta perguntar finalizar/voltar.
    menu_acao: dict | None = None
    if (valido
            and regra.get('question_id') == 'menu_cliente_existente'
            and extracted.get('opcao')):
        opcao = extracted['opcao']
        if opcao == 'acompanhar_os' and lead_id:
            try:
                resp_os = robovendas.proxima_instalacao_lead(lead_id)
                menu_acao = {'tipo': 'acompanhar_os', 'os': resp_os}
            except Exception as e:
                logger.warning('Falha buscar OS lead=%s: %s', lead_id, e)
                menu_acao = {'tipo': 'acompanhar_os', 'os': None}
        elif opcao == 'novo_servico' and lead_id:
            nsid = _alvo.iniciar_fluxo_new_service(lead_id, telefone=cellphone)
            if nsid:
                menu_acao = {'tipo': 'iniciar_new_service', 'new_service_id': nsid}
                logger.info('Fluxo NewService iniciado: lead=%s ns=%s', lead_id, nsid)
            else:
                logger.warning('Falha iniciar NewService lead=%s — transbordando', lead_id)
                menu_acao = {'tipo': 'transbordo', 'opcao': opcao}
        elif opcao == 'upgrade_plano' and lead_id:
            aid = _alvo.iniciar_fluxo_upgrade(lead_id, telefone=cellphone)
            if aid:
                menu_acao = {'tipo': 'iniciar_upgrade', 'atendimento_id': aid}
                logger.info('Fluxo Upgrade iniciado: lead=%s atendimento=%s', lead_id, aid)
            else:
                logger.warning('Falha iniciar Upgrade lead=%s — transbordando', lead_id)
                menu_acao = {'tipo': 'transbordo', 'opcao': opcao}
        elif opcao == 'finalizar' and lead_id:
            # Cliente escolheu encerrar — marca status + flag pra próxima
            # /proximo-passo exibir despedida (mesma sessão).
            try:
                _set_status(lead_id, cellphone, 'atendimento_concluido')
                ctx_gerenciador.salvar_dado(cellphone, 'acabou_de_encerrar', True)
                menu_acao = {'tipo': 'finalizar'}
                logger.info('Cliente %s escolheu finalizar atendimento (lead=%s)', cellphone, lead_id)
            except Exception as e:
                logger.warning('Falha marcar atendimento_concluido lead=%s: %s', lead_id, e)
                menu_acao = {'tipo': 'transbordo', 'opcao': opcao}
        else:
            menu_acao = {'tipo': 'transbordo', 'opcao': opcao}

    # ── menu_cpf_confirmacao: é o CPF do número ou outro? ──────────────
    if (valido
            and regra.get('question_id') == 'menu_cpf_confirmacao'
            and extracted.get('opcao')
            and lead_id):
        opcao = extracted['opcao']
        if opcao == 'cpf_novo':
            # quer OUTRO CPF → é outra pessoa: zera CPF/id_hubsoft E TODOS os
            # dados de coleta já preenchidos. Senão, se o lead do número já tinha
            # cadastro completo (cliente conhecido), o /proximo-passo acha "tudo
            # preenchido" e TRANSBORDA em vez de re-coletar para o novo CPF.
            _set_status(lead_id, cellphone, 'lead_novo')
            _limpar_dados_coleta(lead_id, cellphone, manter_cpf=False)
            ctx_gerenciador.salvar_dado(cellphone, 'cpf_confirmado', False)
            menu_acao = {'tipo': 'cpf_novo'}
            logger.info('Cliente %s optou por OUTRO CPF — re-coleta completa (lead=%s)', cellphone, lead_id)
        else:  # cpf_atual (default)
            ctx_gerenciador.salvar_dado(cellphone, 'cpf_confirmado', True)
            menu_acao = {'tipo': 'cpf_atual'}
            logger.info('Cliente %s confirmou CPF atual (lead=%s)', cellphone, lead_id)

    # ── retomada_confirmacao: cliente reabriu com cadastro em andamento ──
    #   1) continuar → segue de onde parou (nenhuma limpeza)
    #   2) recomecar → zera os dados coletados MAS mantém o CPF (recomeça do nome)
    #   3) outro_cpf → zera tudo + CPF/id_hubsoft → re-coleta desde o CPF
    if (valido
            and regra.get('question_id') == 'retomada_confirmacao'
            and extracted.get('opcao')
            and lead_id):
        opcao = extracted['opcao']
        ctx_gerenciador.salvar_dado(cellphone, 'retomada_resolvida', True)
        if opcao == 'recomecar':
            _limpar_dados_coleta(lead_id, cellphone, manter_cpf=True)
            menu_acao = {'tipo': 'retomada_recomecar'}
            logger.info('Cliente %s optou por RECOMEÇAR (mantém CPF) lead=%s', cellphone, lead_id)
        elif opcao == 'outro_cpf':
            _set_status(lead_id, cellphone, 'lead_novo')
            _limpar_dados_coleta(lead_id, cellphone, manter_cpf=False)
            ctx_gerenciador.salvar_dado(cellphone, 'cpf_confirmado', False)
            menu_acao = {'tipo': 'retomada_outro_cpf'}
            logger.info('Cliente %s optou por OUTRO CPF (zera tudo) lead=%s', cellphone, lead_id)
        else:  # continuar (default)
            menu_acao = {'tipo': 'retomada_continuar'}
            logger.info('Cliente %s optou por CONTINUAR de onde parou lead=%s', cellphone, lead_id)

    # ── pergunta_finalizar: cliente decide voltar ao menu ou encerrar ──
    pergunta_finalizar_acao = ''
    if (valido
            and regra.get('question_id') == 'pergunta_finalizar'
            and extracted.get('opcao')
            and lead_id):
        opcao = extracted['opcao']
        if opcao == 'voltar_menu':
            # Volta o status pra cliente_ativo → proximo-passo mostra menu novamente
            try:
                _set_status(lead_id, cellphone, 'cliente_ativo')
                pergunta_finalizar_acao = 'voltar_menu'
            except Exception as e:
                logger.warning('Falha resetar status pra cliente_ativo lead=%s: %s', lead_id, e)
        elif opcao == 'encerrar':
            # Marca como atendido — proximo-passo encerra
            try:
                _set_status(lead_id, cellphone, 'atendimento_concluido')
                pergunta_finalizar_acao = 'encerrar'
                # Flag de contexto: indica que o encerramento foi recém-pedido
                # (mesma sessão). Próximo proximo-passo vai exibir despedida
                # e limpar essa flag. Se cliente voltar depois (sem flag),
                # proximo-passo trata como volta e reseta o status.
                ctx_gerenciador.salvar_dado(cellphone, 'acabou_de_encerrar', True)
            except Exception as e:
                logger.warning('Falha marcar atendimento_concluido lead=%s: %s', lead_id, e)

    # ── confirmacao_plano negada: limpa id_plano_rp+valor pra re-perguntar ──
    if (regra.get('question_id') == 'confirmacao_plano'
            and extracted.get('confirmacao') is False
            and lead_id):
        try:
            _alvo.atualizar_alvo(lead_id, {
                'id_plano_rp': None,
                'valor': None,
                'plano_confirmado': None,
            }, telefone=cellphone)
            logger.info('Plano negado: id_plano_rp limpo lead=%s', lead_id)
        except Exception as e:
            logger.warning('Falha limpar plano lead=%s: %s', lead_id, e)

    # ── Após coleta de CPF: detecta se é cliente Hubsoft existente ────
    # Chama o Django que consulta a API Hubsoft. Se achar, seta status_api=
    # 'cliente_ativo' no lead E retorna transbordo=True com msg do menu
    # (pra interromper o flow Matrix, que senão seguiria pra coleta_rg).
    eh_cliente_existente = False
    nome_cliente_hubsoft = ''
    if (valido
            and regra.get('question_id') == 'coleta_cpf'
            and extracted.get('cpf_cnpj')
            and lead_id):
        try:
            # Salva CPF AGORA pra que o Django consiga consultar.
            # Usa o dispatcher pra ATUALIZAR O CACHE DO LEAD em memória —
            # sem isso, a próxima /proximo-passo lê do cache stale e
            # repete a pergunta de CPF.
            logger.info('coleta_cpf hook: salvando cpf=%s lead=%s',
                        extracted['cpf_cnpj'], lead_id)
            _alvo.atualizar_alvo(lead_id, {'cpf_cnpj': extracted['cpf_cnpj']},
                                 telefone=cellphone)
            # cliente informou um CPF explicitamente → não re-perguntar atual/novo
            ctx_gerenciador.salvar_dado(cellphone, 'cpf_confirmado', True)
            logger.info('coleta_cpf hook: chamando verificar_cliente_por_cpf lead=%s', lead_id)
            resultado_check = robovendas.verificar_cliente_por_cpf(lead_id)
            logger.info('coleta_cpf hook: resposta=%s', resultado_check)
            if resultado_check and resultado_check.get('eh_cliente'):
                eh_cliente_existente = True
                nome_cliente_hubsoft = resultado_check.get('nome', '')
                extracted['eh_cliente_existente'] = True
                extracted['nome_cliente_hubsoft'] = nome_cliente_hubsoft
                # CRÍTICO: verificar_cliente_por_cpf atualizou status_api no
                # Django pra 'cliente_ativo'. Sincroniza o cache em memória
                # pra próxima /proximo-passo cair em STATUSES_MENU (e NÃO
                # repetir a coleta de CPF).
                _alvo._ctx_patch_lead_cache(cellphone, {  # noqa: SLF001
                    'status_api': 'cliente_ativo',
                    'nome_razaosocial': nome_cliente_hubsoft or '',
                })
                logger.info('CPF %s identificado como cliente Hubsoft (lead=%s, nome=%s) — cache atualizado',
                            extracted['cpf_cnpj'], lead_id, nome_cliente_hubsoft)
            elif resultado_check:
                logger.info('CPF %s NÃO encontrado no Hubsoft (lead=%s): %s',
                            extracted['cpf_cnpj'], lead_id,
                            resultado_check.get('mensagem', ''))
            else:
                logger.warning('verificar_cliente_por_cpf retornou None (lead=%s)', lead_id)
        except Exception as e:
            logger.exception('Falha verificar cliente por CPF lead=%s: %s', lead_id, e)

    # ── Mapeia opção 1/2/3 → data real (escolha_data) ─────────────────
    # Cliente responde '1', '2' ou '3' — o engine consulta as 3 próximas
    # datas disponíveis via apimatrix e mapeia pra data real em formato
    # ISO (YYYY-MM-DD), pronta pra salvar no DateField `data_instalacao`.
    # Se a consulta falhar, mantém valido=True (não punir cliente) e o
    # campo fica vazio — atendente humano resolve.
    if valido and regra.get('question_id') == 'escolha_data' and extracted.get('opcao'):
        try:
            from datetime import datetime
            opcao = extracted['opcao']
            hoje = datetime.now().strftime('%d/%m/%Y')
            datas = robovendas.consultar_datas_disponiveis(hoje)
            idx = int(opcao) - 1
            if 0 <= idx < len(datas):
                data_str = datas[idx]   # formato esperado: 'DD/MM/YYYY' ou similar
                # Normaliza pra ISO. Aceita DD/MM/YYYY ou YYYY-MM-DD.
                try:
                    dt = datetime.strptime(data_str, '%d/%m/%Y')
                except ValueError:
                    dt = datetime.strptime(data_str, '%Y-%m-%d')
                extracted['data_instalacao'] = dt.strftime('%Y-%m-%d')
                extracted['data_instalacao_label'] = data_str
                logger.info('Data instalação mapeada: lead=%s opcao=%s data=%s',
                            lead_id, opcao, data_str)

                # Salva data AGORA (no lead OU no NewService — via dispatcher).
                if lead_id:
                    try:
                        _alvo.atualizar_alvo(lead_id, {
                            'data_instalacao': extracted['data_instalacao'],
                        }, telefone=cellphone)
                    except Exception as e:
                        logger.warning('Falha pré-salvar data_instalacao lead=%s: %s', lead_id, e)
                    # Dispara abertura de atendimento + OS APENAS se NÃO estiver em fluxo
                    # de Novo Serviço (esse fluxo não integra com Hubsoft — só registra).
                    nsid_ativo = _alvo.descobrir_new_service_id(lead_id, cellphone)
                    if nsid_ativo:
                        try:
                            _alvo.encerrar_fluxo_new_service(
                                lead_id, nsid_ativo, telefone=cellphone,
                                observacoes=f'Cliente concluiu coleta — data {data_str}',
                            )
                            logger.info('NewService %s finalizado (lead=%s)', nsid_ativo, lead_id)
                            agendamento_resultado = {'status': 'new_service_finalizado'}
                        except Exception as e:
                            logger.exception('Falha finalizar NewService lead=%s: %s', lead_id, e)
                            agendamento_resultado = None
                    else:
                        try:
                            agendamento_resultado = robovendas.agendar_instalacao_ia(lead_id)
                            logger.info('Agendamento IA disparado lead=%s resultado=%s',
                                        lead_id, (agendamento_resultado or {}).get('status'))
                        except Exception as e:
                            logger.exception('Falha disparar agendamento IA lead=%s: %s', lead_id, e)
                            agendamento_resultado = None
            else:
                logger.warning('Opção %s fora do range das datas (lead=%s, datas=%s)',
                               opcao, lead_id, datas)
        except Exception as e:
            logger.warning('Falha mapear opção→data instalação: %s', e)

    # ── Estrutura ponto_referencia via IA + monta `endereco` completo ─
    # Última pergunta de endereço. Aqui consolidamos:
    #  1. `ponto_referencia` → string formatada do complemento (via IA):
    #     [APARTAMENTO] Edif. X - Bloco Y - 5º andar - Apto 502. Ref: ...
    #  2. `endereco` → string completa do endereço composta a partir dos
    #     campos rua/numero/bairro/cidade/estado/cep do lead. Útil pro
    #     time de instalação ver o endereço todo numa só linha.
    if valido and regra.get('question_id') == 'coleta_ponto_referencia':
        # 1) Estrutura ponto_referencia via IA
        try:
            res_end = openai_endereco.extrair_complemento(answer)
            if res_end.texto_estruturado:
                extracted['ponto_referencia'] = res_end.texto_estruturado
                extracted['endereco_componentes'] = res_end.componentes
                logger.info(
                    'Endereço estruturado: lead=%s tipo=%s saida=%s',
                    lead_id, res_end.tipo, res_end.texto_estruturado[:80],
                )
        except Exception as e:
            logger.warning('Falha extração estruturada ponto_referencia: %s', e)

        # 2) Monta `endereco` completo a partir dos campos do alvo atual
        #    (LeadProspecto ou NewService, conforme o fluxo)
        if lead_id:
            try:
                lead_atual = _alvo.consultar_dados_alvo(lead_id, telefone=cellphone) or {}
                partes_end = []
                rua = (lead_atual.get('rua') or '').strip()
                numero = (lead_atual.get('numero_residencia') or '').strip()
                bairro = (lead_atual.get('bairro') or '').strip()
                cidade = (lead_atual.get('cidade') or '').strip()
                estado = (lead_atual.get('estado') or '').strip()
                cep = (lead_atual.get('cep') or '').strip()
                if rua:
                    partes_end.append(f'{rua}{(", Nº " + numero) if numero else ""}')
                if bairro:
                    partes_end.append(bairro)
                if cidade or estado:
                    cidade_uf = f'{cidade}/{estado}' if (cidade and estado) else (cidade or estado)
                    partes_end.append(cidade_uf)
                if cep:
                    partes_end.append(f'CEP {cep}')
                endereco_completo = ' - '.join(partes_end)
                if endereco_completo:
                    extracted['endereco'] = endereco_completo[:500]
                    # Salva SÍNCRONO via dispatcher. Para fluxo de NewService,
                    # o campo `endereco` (TextField) não existe no NewService —
                    # então só grava no LeadProspecto se o alvo for lead.
                    if _alvo.descobrir_new_service_id(lead_id, cellphone) is None:
                        try:
                            robovendas.atualizar_lead(lead_id, {'endereco': endereco_completo[:500]})
                        except Exception as e2:
                            logger.warning('Falha salvar endereco lead=%s: %s', lead_id, e2)
                    logger.info('Endereço completo montado: lead=%s -> %s',
                                lead_id, endereco_completo[:120])
            except Exception as e:
                logger.warning('Falha montar endereco completo lead=%s: %s', lead_id, e)

    # ── Validação SÍNCRONA de imagem via OpenAI Vision ────────────────
    # Se o extractor de imagem aceitou a URL, ainda precisamos confirmar
    # via IA que a imagem corresponde ao tipo solicitado (selfie/frente/verso)
    # e está legível. Se rejeitar, sobrescreve valido=False pra pedir refoto.
    msg_refoto = ''
    motivo_validacao_ia = ''
    if valido and extractor_tipo == 'imagem' and extracted.get('url_imagem'):
        try:
            resultado_ia = openai_imagens.validar_imagem(
                url=extracted['url_imagem'],
                descricao=regra.get('descricao_imagem', ''),
            )
            extracted['ia_validacao'] = {
                'aprovado': resultado_ia.aprovado,
                'codigo': resultado_ia.motivo_codigo,
                'motivo': resultado_ia.motivo_humano,
            }
            if not resultado_ia.aprovado:
                valido = False
                motivo = f'ia_rejeitou:{resultado_ia.motivo_codigo}'
                msg_refoto = resultado_ia.msg_refoto
                motivo_validacao_ia = resultado_ia.motivo_humano
                logger.info(
                    'Imagem rejeitada pela IA: lead=%s desc=%s codigo=%s motivo=%s',
                    lead_id, regra.get('descricao_imagem'),
                    resultado_ia.motivo_codigo, resultado_ia.motivo_humano,
                )
        except Exception as e:
            # Em caso de erro na IA, NÃO bloqueia o fluxo — aceita a imagem
            # (cliente já passou pelo upload, melhor não punir falha do nosso lado).
            logger.warning('Erro validação IA imagem, aceitando por default: %s', e)
            extracted['ia_validacao'] = {'erro': str(e)}

        # ── Marca SÍNCRONO o flag doc_*_recebida (antes do _disparar_acoes) ──
        # Se a imagem foi aprovada pela IA (ou aceita por default em caso
        # de erro), atualiza o lead AGORA. Sem isso, _disparar_acoes em
        # background pode não terminar antes do Matrix chamar próximo-passo,
        # e o bot pediria a mesma foto de novo.
        if valido and lead_id:
            mapa_bool_sync = {
                'selfie_com_doc':  'doc_selfie_recebida',
                'frente_doc':      'doc_frente_recebida',
                'verso_doc':       'doc_verso_recebida',
            }
            campo_sync = mapa_bool_sync.get(regra.get('descricao_imagem', ''))
            if campo_sync:
                try:
                    _alvo.atualizar_alvo(lead_id, {campo_sync: True}, telefone=cellphone)
                    logger.info('Doc marcado síncrono: lead=%s campo=%s', lead_id, campo_sync)
                except Exception as e:
                    logger.warning('Falha marcar doc síncrono lead=%s: %s', lead_id, e)

    # Conta tentativa no contexto (por cellphone+question_id)
    ctx = ctx_gerenciador.obter(cellphone)
    tent_key = f'regra:{regra["question_id"]}'
    if not valido:
        tentativas = ctx_gerenciador.incrementar_tentativa(cellphone, tent_key)
    else:
        ctx_gerenciador.resetar_tentativas(cellphone, tent_key)
        tentativas = 0

    max_tent = regra.get('max_tentativas') or 3
    transbordo = False
    fim_fluxo = False

    if not valido and tentativas >= max_tent and regra.get('forcar_transbordo_apos_max'):
        transbordo = True

    # Menu cliente existente:
    # - Opções 1/2/4 (novo serviço, upgrade, atendimento) → transbordo
    #   (cliente solicitou explicitamente falar com humano).
    # - Opção 3 (acompanhar OS) → NÃO transborda. Seta status do lead pra
    #   'aguardando_finalizacao'; a próxima rodada do proximo-passo
    #   pergunta se quer voltar ao menu ou encerrar.
    if menu_acao:
        if menu_acao.get('tipo') == 'transbordo':
            transbordo = True
            # Camada de segurança: mesmo se o flow Matrix não estiver
            # patched (sem ramo needsReception=true → msg_pre_transbordo),
            # marca status pro proximo-passo detectar e transbordar
            # também na próxima chamada.
            if lead_id:
                try:
                    _set_status(lead_id, cellphone, 'transbordo_atendente')
                except Exception as e:
                    logger.warning('Falha setar transbordo_atendente lead=%s: %s', lead_id, e)
        elif menu_acao.get('tipo') == 'acompanhar_os' and lead_id:
            # Não transborda — só seta o status pra pos-OS
            try:
                _set_status(lead_id, cellphone, 'aguardando_finalizacao')
            except Exception as e:
                logger.warning('Falha setar aguardando_finalizacao lead=%s: %s', lead_id, e)

    # tipo_imovel='empresa' → bot só atende residencial, transborda pro atendente.
    # Muda o status_api pra 'transbordo_atendente' (mesmo do menu opção 3) para o
    # /proximo-passo seguinte HALTAR o fluxo (STATUS_ROTAS) — inclusive dentro do
    # Novo Serviço, abandonando a coleta em vez de seguir pedindo CEP.
    if tipo_imovel_empresa:
        transbordo = True
        if lead_id:
            try:
                _set_status(lead_id, cellphone, 'transbordo_atendente')
            except Exception as e:
                logger.warning('Falha setar transbordo_atendente (empresa) lead=%s: %s', lead_id, e)

    # Endereço confirmado SEM viabilidade → transborda pro atendente. Marca
    # 'venda_sem_viabilidade' (status real, mapeado no pipeline CRM) — que agora
    # está no STATUS_ROTAS do onboarding, então o /proximo-passo seguinte transborda.
    # Vale TAMBÉM no Novo Serviço (abandona a coleta e transborda).
    if endereco_sem_viabilidade:
        transbordo = True
        if lead_id:
            try:
                _set_status(lead_id, cellphone, 'venda_sem_viabilidade')
            except Exception as e:
                logger.warning('Falha setar venda_sem_viabilidade lead=%s: %s', lead_id, e)

    # Cliente Hubsoft detectado APÓS coleta_cpf: NÃO transborda. O engine
    # já marcou status_api='cliente_ativo' no lead — a próxima chamada de
    # /proximo-passo (red_volta_consulta) detecta esse status e retorna a
    # mensagem do menu via `mensagem_pergunta`. Aqui apenas garantimos
    # que a msg composta seja exibida ANTES via msg_resultado.

    # Monta mensagem ao cliente
    if valido:
        # Confirmação da resposta: respeita o texto configurado na ferramenta,
        # INCLUSIVE vazio → vazio = NÃO enviar confirmação (fica sem mensagem).
        # Só usa o default se a regra não tiver o campo (defensivo — a API
        # sempre manda msg_sucesso, então na prática vazio permanece vazio).
        _ms = regra.get('msg_sucesso')
        message = _ms if _ms is not None else 'Anotei!'
        # Confirmação NEGADA (cliente respondeu "não") → NÃO usar msg_sucesso
        # ("Plano confirmado!" após 'Ver outro plano' era errado). Fica vazio;
        # o /proximo-passo conduz (re-pergunta / fluxo de ajuste). Perguntas
        # com override próprio (ex.: confirmacao_agendamento) setam depois.
        if (regra.get('extractor_tipo') == 'confirmacao'
                and extracted.get('confirmacao') is False):
            message = ''
    elif transbordo:
        message = regra.get('msg_max_tentativas') or 'Vou te transferir pra um atendente. Aguarde um momentinho!'
    elif msg_refoto:
        # IA rejeitou a imagem — mensagem específica explicando o que refazer
        message = msg_refoto
    else:
        message = regra.get('msg_erro') or 'Hum, não entendi bem. Pode reformular?'

    # ── Confirmação de agendamento NEGADA → mensagem específica ─────────
    if (regra.get('question_id') == 'confirmacao_agendamento'
            and extracted.get('confirmacao') is False):
        message = (
            'Sem problemas! Vamos escolher outro turno e data. ##1f504##'
        )

    # ── Opção 1 do menu → iniciar fluxo Novo Serviço ───────────────────
    # O /proximo-passo da próxima volta detecta status='em_fluxo_new_service'
    # e devolve a primeira pergunta (tipo_imovel) na mensagem_pergunta.
    if menu_acao and menu_acao.get('tipo') == 'iniciar_new_service':
        message = mensagens_client.texto(
            'intro_novo_servico',
            'Que bom que você quer expandir conosco! ##1f389##\n\n'
            'Vamos cadastrar seu *novo serviço*. Vou precisar de alguns dados '
            'do *endereço da nova instalação*, escolha do *plano* e fotos do '
            'seu *documento*.')

    # ── Opção 2 do menu → iniciar fluxo Upgrade de Plano ───────────────
    # O /proximo-passo da próxima volta detecta status='em_fluxo_upgrade'
    # e devolve a primeira pergunta do upgrade na mensagem_pergunta.
    if menu_acao and menu_acao.get('tipo') == 'iniciar_upgrade':
        message = mensagens_client.texto(
            'intro_upgrade',
            'Boa! ##1f4c8## Vamos fazer seu *upgrade de plano*. É rapidinho!')

    # ── Resposta da pergunta de CPF → sem ack; o /proximo-passo conduz
    #    (cpf_atual → menu; cpf_novo → re-coleta de CPF).
    if menu_acao and menu_acao.get('tipo') in ('cpf_atual', 'cpf_novo'):
        message = ''

    # ── Resposta da retomada → sem ack; o /proximo-passo conduz
    #    (continuar → próxima pergunta; recomecar/outro_cpf → primeira pergunta).
    if menu_acao and menu_acao.get('tipo', '').startswith('retomada_'):
        message = ''

    # ── tipo_imovel='empresa' → mensagem de redirecionamento ───────────
    if tipo_imovel_empresa:
        message = mensagens_client.texto(
            'transbordo_empresa',
            'Entendi! Pra atendimento *empresarial* eu vou te transferir '
            'pra um consultor especializado em planos comerciais. ##1f4f1##\n\n'
            'Aguarde um momentinho ##263A##')

    # ── Endereço confirmado SEM viabilidade → avisa o cliente ──────────
    if endereco_sem_viabilidade:
        message = mensagens_client.texto(
            'transbordo_sem_viabilidade',
            'Poxa, verifiquei aqui e ainda não temos viabilidade técnica '
            'confirmada nesse endereço. ##1f622##\n\n'
            'Vou te transferir pra um atendente conferir as opções pra sua '
            'região. Aguarde um momentinho ##263A##')

    # ── CPF é de cliente Hubsoft existente → mensagem de boas-vindas ───
    # O MENU em si vem na próxima volta (api_proximo_passo retorna o menu
    # como mensagem_pergunta porque status_api='cliente_ativo').
    if eh_cliente_existente:
        primeiro_nome = (nome_cliente_hubsoft or '').split(' ')[0] if nome_cliente_hubsoft else ''
        saud = f'Olá *{primeiro_nome}*! ' if primeiro_nome else 'Olá! '
        message = (
            f'{saud}Identifiquei seu cadastro com a gente. ##1f44b##'
        )

    # ── Menu cliente existente: monta mensagem conforme opção ───────────
    if menu_acao:
        if menu_acao['tipo'] == 'acompanhar_os':
            os_resp = menu_acao.get('os') or {}
            if not os_resp.get('tem_os'):
                if os_resp.get('agendou'):
                    # cliente acabou de agendar — a OS ainda está sendo aberta
                    quando = os_resp.get('data_instalacao') or ''
                    quando_txt = f' para *{quando}*' if quando else ''
                    message = (
                        f'Seu agendamento de instalação{quando_txt} está sendo '
                        'processado. ##23f3##\n\n'
                        'Assim que a equipe confirmar, os detalhes da ordem de '
                        'serviço aparecem aqui. ##2705##'
                    )
                    # NÃO transborda — status fica aguardando_finalizacao (abaixo)
                else:
                    message = (
                        'Não encontrei nenhuma instalação no seu cadastro. ##1f50d##\n\n'
                        'Vou te transferir pra um atendente conferir.'
                    )
                    transbordo = True
            else:
                # Lista TODAS as OS de instalação (independente do serviço).
                # Endereço de cada uma é exibido pra cliente saber qual é.
                lista_oss = os_resp.get('oss') or []
                if not lista_oss:
                    # Fallback compat: usa `os` (singular) se o backend antigo
                    lista_oss = [os_resp.get('os')] if os_resp.get('os') else []

                def _fmt_data(d):
                    if d and 'T' in d:
                        d = d.split('T')[0]
                    if d and '-' in d and len(d) >= 10:
                        p = d[:10].split('-')
                        if len(p) == 3:
                            return f'{p[2]}/{p[1]}/{p[0]}'
                    return d or '—'

                def _fmt_data_turno(d):
                    """Data + TURNO (Manhã/Tarde), SEM o horário exato. O cliente
                    escolheu apenas o turno; a hora cravada na OS é operação interna
                    e não deve ser exibida. Deriva o turno da hora (< 12h = Manhã)."""
                    if not d:
                        return '—'
                    parte_data, _, parte_hora = d.replace('T', ' ').partition(' ')
                    data_fmt = _fmt_data(parte_data)
                    hh = (parte_hora or '').strip()[:2]
                    if hh.isdigit():
                        return f"{data_fmt} - {'Manhã' if int(hh) < 12 else 'Tarde'}"
                    return data_fmt

                total = len(lista_oss)
                if total == 1:
                    cabecalho = 'Encontrei sua instalação! ##1f50d##\n\n'
                else:
                    cabecalho = (
                        f'Encontrei *{total} instalações* no seu cadastro: ##1f50d##\n\n'
                    )

                blocos = []
                for i, o in enumerate(lista_oss, start=1):
                    o = o or {}
                    numero = o.get('numero') or '—'
                    status_label = o.get('status_label') or 'Em processamento'
                    finalizada = o.get('finalizada') is True
                    data_prog = o.get('data_programada') or ''
                    data_term = o.get('data_termino_executado') or ''
                    endereco_inst = (o.get('endereco_instalacao') or '').strip()
                    nome_servico = (o.get('nome_servico') or '').strip()
                    status_fech = (o.get('status_fechamento') or '').strip()

                    # Cabeçalho do bloco (se múltiplas, prefixa "Instalação N")
                    prefixo = f'*Instalação {i}*' if total > 1 else '*Detalhes*'
                    bloco = f'{prefixo}\n'
                    bloco += f'##1f4c4## *OS:* #{numero}\n'
                    if nome_servico:
                        bloco += f'##1f4e6## *Plano:* {nome_servico}\n'
                    bloco += f'##1f4cc## *Status:* {status_label}\n'
                    if finalizada and data_term:
                        bloco += f'##1f4c5## *Concluída em:* {_fmt_data(data_term)}\n'
                    elif data_prog:
                        bloco += f'##1f4c5## *Data programada:* {_fmt_data_turno(data_prog)}\n'
                    if endereco_inst:
                        bloco += f'##1f4cd## *Endereço:* {endereco_inst}\n'
                    if finalizada and status_fech:
                        bloco += f'##1f4dd## *Motivo:* {status_fech}\n'
                    blocos.append(bloco)

                rodape = '\nEm caso de dúvidas, fala com nosso atendimento. ##263A##'
                message = cabecalho + '\n'.join(blocos) + rodape
        elif menu_acao['tipo'] == 'transbordo':
            mapa_msg = {
                'novo_servico':  mensagens_client.texto(
                    'transbordo_novo_servico',
                    'Beleza! Vou te transferir pra um atendente '
                    'falar sobre novos serviços. ##1f680##'),
                'upgrade_plano': mensagens_client.texto(
                    'transbordo_upgrade',
                    'Show! Vou te transferir pra um atendente '
                    'falar sobre upgrade de plano. ##1f4c8##'),
                'atendimento':   mensagens_client.texto(
                    'transbordo_atendimento',
                    'Vou te transferir pra um atendente agora. ##1f4f1##'),
            }
            message = mapa_msg.get(menu_acao.get('opcao', ''),
                                   mensagens_client.texto(
                                       'transbordo_generico',
                                       'Vou te transferir pra um atendente.'))
        elif menu_acao['tipo'] == 'finalizar':
            message = mensagens_client.texto(
                'despedida_encerramento',
                'Obrigada pelo contato com a *Megalink*! ##1f499##\n\n'
                'Estamos sempre à disposição. Tenha um ótimo dia! ##1f31f##')

    # ── Sobrescreve mensagem com detalhes do agendamento ────────────────
    # Se a etapa for confirmação aceita E o backend conseguiu agendar,
    # mostra data/turno/técnico/horário pro cliente. Se ficou aguardando
    # sync, avisa que está finalizando. Em erro, transborda.
    if agendamento_resultado:
        status_ag = agendamento_resultado.get('status', '')
        dados = agendamento_resultado.get('dados', {}) or {}
        if status_ag == 'new_service_finalizado':
            # NewService concluído (cliente Hubsoft contratou serviço adicional).
            # Mostra resumo do que foi escolhido (turno + data) + parabeniza.
            # encerrar_fluxo_new_service já marcou status='finalizado' e
            # restaurou lead.status_api='cliente_ativo' → próxima volta cai no menu.
            data_inst = extracted.get('data_instalacao_label') or extracted.get('data_instalacao') or ''
            turno_extracted = extracted.get('turno_instalacao') or ''
            turno_label = 'Manhã' if turno_extracted == 'manha' else ('Tarde' if turno_extracted == 'tarde' else '')
            message = (
                '##1f389## *Nova contratação concluída com sucesso!*\n\n'
                '##2705## Recebemos todos os seus dados e documentos.\n'
            )
            if data_inst:
                message += f'##1f4c5## *Data preferida:* {data_inst}\n'
            if turno_label:
                message += f'##23f0## *Turno preferido:* {turno_label}\n'
            message += (
                '\nNossa equipe vai validar e em breve entra em contato pra '
                'confirmar a instalação. ##1f680##\n\n'
                'Obrigada pela confiança na *Megalink*! ##1f499##'
            )
        elif status_ag == 'agendado':
            turno_label = 'Manhã' if dados.get('turno') == 'manha' else 'Tarde'
            message = (
                f'Instalação confirmada! ##2705##\n\n'
                f'##1f4c5## Data: *{dados.get("data", "")}*\n'
                f'##23f0## Turno: *{turno_label}*'
            )
            # NÃO exibir horário exato — o cliente escolheu só data + turno.
            message += '\n\nObrigado por escolher a Megalink! ##1f680##'
            # Agendamento OK → seta status pra pergunta_finalizar (não transborda)
            if lead_id:
                try:
                    _set_status(lead_id, cellphone, 'aguardando_finalizacao')
                except Exception as e:
                    logger.warning('Falha setar aguardando_finalizacao pós-agendamento lead=%s: %s', lead_id, e)
        elif status_ag == 'aguardando_sync':
            message = (
                'Estamos finalizando seu cadastro no sistema. ##23f3##\n\n'
                'Em alguns instantes vou te confirmar o agendamento. '
                'Já pode me dizer se precisar de algo!'
            )
            # Worker reprocessa depois — seta status pra pergunta_finalizar
            # também (cliente pode encerrar ou esperar)
            if lead_id:
                try:
                    _set_status(lead_id, cellphone, 'aguardando_finalizacao')
                except Exception as e:
                    logger.warning('Falha setar aguardando_finalizacao lead=%s: %s', lead_id, e)
        else:
            # erro real na API — transborda (não conseguimos resolver)
            message = (
                'Houve um probleminha pra confirmar sua instalação. '
                'Vou te transferir pra um atendente finalizar. ##1f4f1##'
            )
            transbordo = True

    # Permite substituir placeholders {extracted} na mensagem
    try:
        message = message.format(extracted=extracted, **extracted)
    except (KeyError, IndexError):
        pass

    # ── Salva o campo principal SÍNCRONO (antes do background) ────────
    # O fluxo Matrix chama /proximo-passo logo após /validar. Se o campo
    # da regra (ex: tipo_residencia) só fosse salvo na thread de
    # _disparar_acoes, o /proximo-passo poderia ler o lead ANTES do save
    # terminar e repetir a mesma pergunta (loop). Por isso salvamos o
    # campo principal de forma síncrona aqui. As demais ações (status,
    # tags, histórico, registro de imagem) seguem em background.
    if valido and lead_id and regra.get('extractor_tipo') not in ('imagem', 'cep'):
        campo_sync = regra.get('campo_lead_atualizar') or ''
        ext_tipo = regra.get('extractor_tipo')
        if campo_sync and ext_tipo == 'confirmacao':
            # Confirmação: salva o booleano síncrono SÓ quando confirmou (True).
            # A negação (False) já é tratada pelos hooks específicos acima
            # (que limpam os campos relacionados — plano, agendamento, etc).
            # Sem este save síncrono, etapas de confirmação davam loop quando
            # o /proximo-passo lia o lead antes da thread de background salvar.
            if extracted.get('confirmacao') is True:
                try:
                    # _alvo roteia pro NewService quando em fluxo de novo
                    # serviço; senão grava no lead. Garante que o save
                    # síncrono vá pro alvo CERTO (evita loop no new_service).
                    _alvo.atualizar_alvo(lead_id, {campo_sync: True}, telefone=cellphone)
                    logger.info('Confirmação salva síncrono: lead=%s %s=True',
                                lead_id, campo_sync)
                except Exception as e:
                    logger.warning('Falha salvar confirmação síncrono lead=%s %s: %s',
                                   lead_id, campo_sync, e)
        elif campo_sync:
            # opcao/numero/texto/etc — valor em extracted[campo]|valor|opcao
            valor_sync = extracted.get(campo_sync)
            if valor_sync is None:
                valor_sync = extracted.get('valor') or extracted.get('opcao')
            if valor_sync is not None and valor_sync != '':
                if campo_sync in ('id_plano_rp', 'id_dia_vencimento',
                                  'id_vendedor_rp', 'id_hubsoft'):
                    try:
                        valor_sync = int(valor_sync)
                    except (ValueError, TypeError):
                        pass
                try:
                    _alvo.atualizar_alvo(lead_id, {campo_sync: valor_sync}, telefone=cellphone)
                    logger.info('Campo salvo síncrono: lead=%s %s=%s',
                                lead_id, campo_sync, valor_sync)
                except Exception as e:
                    logger.warning('Falha salvar campo síncrono lead=%s %s: %s',
                                   lead_id, campo_sync, e)

    # Dispara ações em background (se válido)
    actions_log = []
    if valido:
        _disparar_acoes(regra, extracted, cellphone, lead_id, question, answer)
        actions_log = [{'tipo': 'agendado_background', 'ok': True}]

    # ── Mensagem composta pelo engine pra Matrix exibir ────────────────
    # `mensagem_resposta` é o nome da variável que o flow_v5 captura no
    # api_validar. Vai parar no nó msg_resultado (válido) ou msg_pre_transbordo
    # (needsReception=true). Em caso de erro, msg_erro usa retorno_erro_api.
    # Pra etapas válidas SEM mensagem rica composta (ex: coleta_cpf comum),
    # mantemos a `mensagem_resposta` em branco — Matrix não exibe nada,
    # próxima pergunta vem do api_proximo_passo.
    mensagem_resposta_flow = ''
    if valido and (menu_acao or agendamento_resultado or eh_cliente_existente
                   or tipo_imovel_empresa):
        # Cenários "rich" — sempre exibe a msg composta
        mensagem_resposta_flow = message
    elif transbordo:
        mensagem_resposta_flow = message

    # ── Campos LEGADOS pra compat com o flow Matrix ───────────────────
    legados = {
        'answerIsCorrect': str(valido).lower(),     # "true"|"false"
        'resposta_correta': str(valido).lower(),
        'resposta_sem_erro_api': 'true' if valido else 'false',
        'errorMessage': '' if valido else message,
        'retorno_erro_api': '' if valido else message,
        'mensagem_resposta': mensagem_resposta_flow,
        'isAClient': 'true' if eh_cliente_existente else 'false',
        'hasCancelledService': 'false',
        'cancelado': 'false',
        'needsReception': 'true' if transbordo else 'false',
        'time_instalacao': '',
        'viabilidade_cep': 'true' if (valido and extractor_tipo == 'cep') else 'false',
        # Reflete a checagem real feita na confirmação de endereço (acima).
        # Em qualquer outra pergunta não há nova informação de viabilidade
        # nesta chamada, então mantém o default 'true' (não bloqueia).
        'givesServiceToCity': 'false' if endereco_sem_viabilidade else 'true',
        # Campos específicos do CEP
        'api_cep': message if extractor_tipo == 'cep' else '',
        'ret_cep': extracted.get('cep', ''),
        'ret_estado': extracted.get('estado', ''),
        'ret_cidade': extracted.get('cidade', ''),
        'ret_bairro': extracted.get('bairro', ''),
        'ret_rua': extracted.get('rua', ''),
    }

    return {
        # ── Schema V2 (novo) ──────────────────────────────────────────
        'valido': valido,
        'extracted_data': extracted,
        'message': message,
        'motivo_invalido': motivo,
        'intent': '',
        'transbordo': transbordo,
        'fim_fluxo': fim_fluxo,
        'actions_executed': actions_log,
        'regra_aplicada': regra['question_id'],
        'tentativas': tentativas,
        'usou_ia': False,
        'confianca': 1.0 if valido else 0.0,
        # ── Schema LEGADO (compat com flow Matrix antigo) ─────────────
        **legados,
    }
