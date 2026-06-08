"""Envio dos dados da venda (lead + documentos) por WhatsApp via uazapi.

Caso de uso original: pedido da Kelle (TR Carrion). Quando todos os documentos
do lead sao aprovados, manda pro vendedor um resumo + os documentos pra ela
ja anexar no HubSoft. Hoje envia pro telefone teste do Lucas (53981521653).

Tarefa Workspace #151.

Estrategia tecnica:
- Texto: monta string formatada com nome, CPF, plano, endereco, contato.
- Documentos: idealmente uazapi recebe URL publica. Como nossos PATHS sao
  autenticados (/inbox/api/conversas/X/midia/Y/), precisamos da URL externa
  original do uazapi (Mensagem.arquivo_url no formato consulteplus.uazapi.com/
  files/<hash>.jpg). Se expirada, pulamos a imagem e logamos warning — texto
  ainda eh enviado.

Uso:
    from apps.comercial.leads.services_whatsapp_venda import enviar_venda_whatsapp
    enviar_venda_whatsapp(lead, telefone_destino='53981521653')
"""
from __future__ import annotations

import logging
from datetime import date

from apps.integracoes.models import IntegracaoAPI

logger = logging.getLogger(__name__)


def _formatar_cpf(cpf: str) -> str:
    s = ''.join(c for c in (cpf or '') if c.isdigit())
    if len(s) == 11:
        return f'{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}'
    return cpf or ''


def _formatar_tel(tel: str) -> str:
    s = ''.join(c for c in (tel or '') if c.isdigit())
    if len(s) == 13 and s.startswith('55'):
        return f'+55 ({s[2:4]}) {s[4:9]}-{s[9:]}'
    if len(s) == 11:
        return f'({s[:2]}) {s[2:7]}-{s[7:]}'
    return tel or ''


def _resolver_plano(lead, oportunidade) -> tuple[str, str]:
    """Busca dado de plano em multiplas fontes pra preencher o resumo da venda.

    Ordem de busca:
    1. oportunidade.plano_interesse (campo direto)
    2. oportunidade.dados_custom['plano_interesse_texto']
    3. oportunidade.dados_custom['plano_id'] (ID Vero tipo 'A1', 'B3')
    4. Parse heuristico da conversa: procura mensagem do cliente respondendo "N"
       (1-8) apos o bot ter listado planos numerados
    5. lead.dados_custom['plano_interesse'] / ['plano_texto']

    Retorna (texto, valor_str). Vazio quando nao acha.
    """
    # 1, 2, 3 — Oportunidade
    if oportunidade is not None:
        txt = (getattr(oportunidade, 'plano_interesse', '') or '').strip()
        if txt:
            return txt, ''
        dc = (oportunidade.dados_custom or {}) if hasattr(oportunidade, 'dados_custom') else {}
        if dc.get('plano_interesse_texto'):
            return str(dc['plano_interesse_texto']).strip(), str(dc.get('plano_valor_pix', '') or '').strip()
        if dc.get('plano_id'):
            return f"ID Vero {dc['plano_id']}", ''

    # 5 — lead.dados_custom
    ldc = (lead.dados_custom or {}) if hasattr(lead, 'dados_custom') else {}
    if ldc.get('plano_interesse') or ldc.get('plano_texto'):
        return str(ldc.get('plano_interesse') or ldc.get('plano_texto')).strip(), \
               str(ldc.get('plano_valor', '') or '').strip()

    # 4 — Parse heuristico da conversa
    try:
        plano_parse = _parsear_plano_da_conversa(lead)
        if plano_parse:
            return plano_parse  # (texto, valor)
    except Exception as e:
        logger.debug('parse plano da conversa falhou (lead %s): %s', lead.id, e)

    return '', ''


def _parsear_plano_da_conversa(lead) -> tuple[str, str] | None:
    """Procura no historico de Mensagens:
       - Bot lista planos numerados ('1️⃣ 550 Mega + Wi-Fi 6\\n💰 R$ 97,90 ...')
       - Cliente responde "1" (ou "1 " ou similar)
       Retorna (texto_do_plano, valor) ou None se nao achar.
    """
    import re
    from apps.inbox.models import Mensagem, Conversa

    conv = Conversa.all_tenants.filter(lead=lead).order_by('-data_abertura').first()
    if not conv:
        return None
    msgs = list(
        Mensagem.all_tenants.filter(conversa=conv).order_by('data_envio')
    )
    if not msgs:
        return None

    # Encontra a ultima msg do bot que lista planos numerados (1, 2, 3, ...)
    NUM_EMOJIS = {
        '1️⃣': 1, '2️⃣': 2, '3️⃣': 3, '4️⃣': 4,
        '5️⃣': 5, '6️⃣': 6, '7️⃣': 7, '8️⃣': 8,
        '9️⃣': 9,
    }

    catalogo: dict[int, dict] = {}  # numero -> {label, valor}
    idx_catalogo = -1
    for i, m in enumerate(msgs):
        if m.remetente_tipo == 'contato':
            continue
        conteudo = m.conteudo or ''
        if not any(e in conteudo for e in NUM_EMOJIS):
            continue
        cat = _extrair_catalogo_planos(conteudo, NUM_EMOJIS)
        if cat:
            catalogo = cat
            idx_catalogo = i

    if not catalogo:
        return None

    # Procura escolha do cliente apos o catalogo
    for m in msgs[idx_catalogo + 1:]:
        if m.remetente_tipo != 'contato':
            continue
        resp = (m.conteudo or '').strip()
        match = re.match(r'^\s*(\d)\s*$', resp)
        if match:
            n = int(match.group(1))
            if n in catalogo:
                return catalogo[n]['label'], catalogo[n]['valor']
    return None


def _extrair_catalogo_planos(conteudo: str, num_emojis: dict) -> dict:
    """Parsea bloco do bot com lista numerada:
       '1️⃣ 550 Mega + Wi-Fi 6\\n💰 R$ 97,90 no PIX recorrente ou debito em conta\\n📄 R$ 107,90 no boleto\\n\\n2️⃣ ...'
       Retorna {1: {label, valor}, 2: {...}, ...}
    """
    import re
    catalogo = {}
    # Quebra por linhas com emoji numerico
    linhas = conteudo.split('\n')
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        n_atual = None
        for emoji, n in num_emojis.items():
            if linha.lstrip().startswith(emoji):
                n_atual = n
                label = linha.replace(emoji, '').strip()
                break
        if n_atual is None:
            i += 1
            continue
        # Valor (R$ ...) na proxima linha
        valor = ''
        if i + 1 < len(linhas):
            m_val = re.search(r'R\$\s*(\d+[.,]\d{2})', linhas[i + 1])
            if m_val:
                valor = m_val.group(1)
        catalogo[n_atual] = {'label': label, 'valor': valor}
        i += 1
    return catalogo


def montar_texto_venda(lead, oportunidade=None) -> str:
    """Texto formatado da venda pra enviar via WhatsApp."""
    linhas = []
    linhas.append('🎉 *NOVA VENDA FECHADA*')
    linhas.append('━━━━━━━━━━━━━━━━━━━━━')
    linhas.append('')
    linhas.append('*👤 DADOS DO CLIENTE*')
    linhas.append(f'Nome: {lead.nome_razaosocial or "—"}')
    linhas.append(f'CPF: {_formatar_cpf(lead.cpf_cnpj)}')
    if lead.rg:
        linhas.append(f'RG: {lead.rg}')
    if lead.data_nascimento:
        try:
            linhas.append(f'Nascimento: {lead.data_nascimento.strftime("%d/%m/%Y")}')
        except Exception:
            linhas.append(f'Nascimento: {lead.data_nascimento}')
    linhas.append(f'Telefone: {_formatar_tel(lead.telefone)}')
    if lead.email:
        linhas.append(f'Email: {lead.email}')
    linhas.append('')

    linhas.append('*📍 ENDEREÇO*')
    rua_parts = [p for p in [lead.rua or lead.endereco, lead.numero_residencia] if p]
    if rua_parts:
        linhas.append(f'{", ".join(rua_parts)}')
    if lead.bairro:
        linhas.append(f'Bairro: {lead.bairro}')
    cidade_uf = ' / '.join(p for p in [lead.cidade, lead.estado] if p)
    if cidade_uf:
        linhas.append(f'Cidade: {cidade_uf}')
    if lead.cep:
        linhas.append(f'CEP: {lead.cep}')
    if lead.ponto_referencia:
        linhas.append(f'Ref: {lead.ponto_referencia}')
    linhas.append('')

    linhas.append('*📡 PLANO*')
    plano_texto, plano_valor = _resolver_plano(lead, oportunidade)
    if plano_texto:
        linhas.append(f'Plano: {plano_texto}')
    if plano_valor:
        linhas.append(f'Valor: R$ {plano_valor}')
    if lead.id_dia_vencimento:
        linhas.append(f'Vencimento: dia {lead.id_dia_vencimento}')
    if not plano_texto and not plano_valor:
        linhas.append('_Consultar conversa do cliente_')
    linhas.append('')

    # Snippet HubSoft (se ja virou prospect/cliente)
    if lead.id_hubsoft:
        linhas.append('*🏢 HUBSOFT*')
        linhas.append(f'ID Prospect: {lead.id_hubsoft}')
        if lead.id_vendedor_rp:
            linhas.append(f'Vendedor RP: {lead.id_vendedor_rp}')

    linhas.append('━━━━━━━━━━━━━━━━━━━━━')
    linhas.append(f'_Hubtrix • Lead #{lead.id} • {date.today().strftime("%d/%m/%Y")}_')

    return '\n'.join(linhas)


def _coletar_documentos(lead) -> list[dict]:
    """Pra cada imagem do lead, le o blob de Mensagem.arquivo (storage privado)
    e devolve como data URI base64. A uazapi aceita data URI no campo `file`
    do /send/media, entao nao precisamos expor /media/ publico nem furar a
    auth-gate de PII (RG/CNH).

    Retorna lista de {url, descricao}. Pula imagens onde nao acha blob legivel.
    """
    import base64
    import mimetypes
    from apps.inbox.models import Mensagem
    docs = []
    for img in lead.imagens.order_by('id'):
        link = img.link_url or ''
        msg = None
        if link.startswith('/inbox/api/conversas/'):
            try:
                msg_id = int(link.rstrip('/').split('/')[-1])
                msg = Mensagem.all_tenants.filter(pk=msg_id).first()
            except (ValueError, IndexError):
                pass

        if not msg or not msg.arquivo:
            logger.warning(
                'Lead %s: imagem #%s sem Mensagem.arquivo no storage privado — pulado',
                lead.id, img.id,
            )
            continue

        try:
            with msg.arquivo.open('rb') as fh:
                raw = fh.read()
        except Exception as e:
            logger.warning(
                'Lead %s: falha lendo arquivo da Mensagem %s: %s',
                lead.id, msg.id, e,
            )
            continue

        nome = msg.arquivo.name or ''
        mime, _ = mimetypes.guess_type(nome)
        if not mime:
            mime = 'image/jpeg'
        b64 = base64.b64encode(raw).decode('ascii')
        data_uri = f'data:{mime};base64,{b64}'

        docs.append({
            'url': data_uri,
            'descricao': img.descricao or 'Documento',
            'mime': mime,
            'tamanho': len(raw),
        })
    return docs


def enviar_venda_whatsapp(lead, telefone_destino: str, oportunidade=None) -> dict:
    """Envia resumo da venda + documentos pelo WhatsApp.

    Args:
        lead: instancia de LeadProspecto
        telefone_destino: numero do destinatario (sera normalizado pra 55XXXXXX)
        oportunidade: OportunidadeVenda relacionada (opcional). Se nao passado,
            busca a primeira do lead. Usado pra extrair dados do plano.

    Returns:
        dict com {ok: bool, texto_enviado: bool, docs_enviados: int,
                  docs_falharam: int, motivo?: str}
    """
    from apps.integracoes.services.uazapi import UazapiService, UazapiServiceError

    resultado = {
        'ok': False, 'texto_enviado': False,
        'docs_enviados': 0, 'docs_falharam': 0,
    }

    # IDEMPOTENCIA: nao reenvia se ja foi disparado pra esse lead
    flag_ja = (lead.dados_custom or {}).get('venda_whatsapp_enviada')
    if flag_ja:
        resultado['ok'] = True
        resultado['motivo'] = 'ja enviado anteriormente em ' + str(
            (lead.dados_custom or {}).get('venda_whatsapp_enviada_em', '?')
        )
        logger.info('[venda_whatsapp] lead=%s pulado (idempotente)', lead.id)
        return resultado

    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=lead.tenant, tipo='uazapi', ativa=True,
    ).first()
    if not integracao:
        resultado['motivo'] = f'tenant {lead.tenant.slug} sem IntegracaoAPI uazapi ativa'
        logger.warning(resultado['motivo'])
        return resultado

    try:
        uaz = UazapiService(integracao=integracao)
    except UazapiServiceError as e:
        resultado['motivo'] = f'falha ao iniciar UazapiService: {e}'
        logger.error(resultado['motivo'])
        return resultado

    # Recupera oportunidade do lead se nao veio (pra ler plano)
    if oportunidade is None:
        try:
            from apps.comercial.crm.models import OportunidadeVenda
            oportunidade = OportunidadeVenda.all_tenants.filter(
                tenant=lead.tenant, lead=lead,
            ).order_by('-id').first()
        except Exception as e:
            logger.debug('falha ao buscar oportunidade lead %s: %s', lead.id, e)

    # 1) Texto formatado
    try:
        texto = montar_texto_venda(lead, oportunidade=oportunidade)
        uaz.enviar_texto(telefone_destino, texto)
        resultado['texto_enviado'] = True
    except Exception as e:
        resultado['motivo'] = f'falha enviar texto: {type(e).__name__}: {e}'
        logger.error(resultado['motivo'])
        return resultado

    # 2) Documentos (data URI base64, lido do storage privado)
    docs = _coletar_documentos(lead)
    for d in docs:
        try:
            mime = d.get('mime') or ''
            if mime.startswith('image/'):
                uaz.enviar_midia(telefone_destino, d['url'], tipo='image',
                                 legenda=d['descricao'])
            else:
                # PDF, etc.
                nome = d['descricao']
                if mime == 'application/pdf' and not nome.lower().endswith('.pdf'):
                    nome += '.pdf'
                uaz.enviar_midia(telefone_destino, d['url'], tipo='document',
                                 nome_arquivo=nome)
            resultado['docs_enviados'] += 1
        except Exception as e:
            resultado['docs_falharam'] += 1
            logger.warning(
                'Lead %s: falha enviar doc %r (%s bytes, %s): %s',
                lead.id, d['descricao'], d.get('tamanho'), d.get('mime'), e,
            )

    resultado['ok'] = True

    # IDEMPOTENCIA: marca flag pra nao reenviar
    try:
        from django.utils import timezone as _tz
        dc = dict(lead.dados_custom or {})
        dc['venda_whatsapp_enviada'] = True
        dc['venda_whatsapp_enviada_em'] = _tz.now().isoformat()
        dc['venda_whatsapp_telefone_destino'] = telefone_destino
        lead.dados_custom = dc
        lead.save(update_fields=['dados_custom'])
        logger.info('[venda_whatsapp] lead=%s flag idempotencia gravada', lead.id)
    except Exception as e:
        logger.error('[venda_whatsapp] lead=%s falha ao gravar flag idempotencia: %s', lead.id, e)

    return resultado
