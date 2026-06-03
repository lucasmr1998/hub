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


def montar_texto_venda(lead) -> str:
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
    if getattr(lead, 'plano_interesse', None):
        linhas.append(f'Plano: {lead.plano_interesse}')
    elif lead.id_plano_rp:
        linhas.append(f'Plano ID: {lead.id_plano_rp}')
    if lead.valor:
        try:
            linhas.append(f'Valor: R$ {float(lead.valor):.2f}'.replace('.', ','))
        except Exception:
            pass
    if lead.id_dia_vencimento:
        linhas.append(f'Vencimento: dia {lead.id_dia_vencimento}')
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


def enviar_venda_whatsapp(lead, telefone_destino: str) -> dict:
    """Envia resumo da venda + documentos pelo WhatsApp.

    Args:
        lead: instancia de LeadProspecto
        telefone_destino: numero do destinatario (sera normalizado pra 55XXXXXX)

    Returns:
        dict com {ok: bool, texto_enviado: bool, docs_enviados: int,
                  docs_falharam: int, motivo?: str}
    """
    from apps.integracoes.services.uazapi import UazapiService, UazapiServiceError

    resultado = {
        'ok': False, 'texto_enviado': False,
        'docs_enviados': 0, 'docs_falharam': 0,
    }

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

    # 1) Texto formatado
    try:
        texto = montar_texto_venda(lead)
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
    return resultado
