"""Utilitarios do app leads.

resolver_link_interno_imagem: garante que o link de uma imagem de lead aponte
para o path interno autenticado (`/inbox/api/conversas/<c>/midia/<m>/`) e nao
para URL externa expiravel (whatsapp, uazapi). Usado tanto na escrita
(endpoint N8N /lead/imagem/) quanto na leitura (API que serve a modal de
documentos do CRM).

Historico do bug que originou isso: 02/06/2026 — incidente TR Carrion onde
44 ImagemLeadProspecto ficaram com link_url externo (script de recuperacao
Fabiana + race entre webhooks). Frontend renderiza `link_url` direto em
<img src=...>, links externos expiram em horas e quebram preview.
"""
from __future__ import annotations


_HOSTS_EXTERNOS = ('whatsapp.net', 'uazapi.com')


def _eh_link_externo(link_url: str) -> bool:
    """True se o link aponta pra recurso externo expiravel."""
    if not link_url:
        return False
    return any(host in link_url for host in _HOSTS_EXTERNOS)


def resolver_link_interno_imagem(img) -> str:
    """Retorna o melhor link_url disponivel pra renderizar a imagem.

    Estrategia (em ordem):
      1. Se ja for path interno (`/inbox/api/...`), retorna como esta.
      2. Se for externo, busca `inbox.Mensagem` do mesmo lead com
         `arquivo_url == link_url` e arquivo salvo. Se achar, retorna o
         path interno.
      3. Se nao achar, faz pareamento cronologico — busca todas as imgs
         broken do lead em ordem de criacao e todas as msgs imagem do lead
         em ordem de envio, parea pelo indice. Se o lead so tem 1 broken
         e 1 msg, pareamento e trivial.
      4. Fallback: retorna o link_url original (preview vai quebrar mas
         a UI deve mostrar warning).

    Nunca levanta excecao — em caso de erro retorna o link original.
    """
    link = img.link_url or ''
    if not _eh_link_externo(link):
        return link

    try:
        from apps.inbox.models import Mensagem
        # 1a tentativa: match exato por arquivo_url
        msg = (
            Mensagem.all_tenants
            .filter(
                conversa__lead_id=img.lead_id,
                arquivo_url=link,
            )
            .exclude(arquivo='')
            .first()
        )
        if msg and msg.conversa_id:
            return f'/inbox/api/conversas/{msg.conversa_id}/midia/{msg.pk}/'

        # 2a tentativa: pareamento cronologico
        from apps.comercial.leads.models import ImagemLeadProspecto
        imgs_broken = list(
            ImagemLeadProspecto.all_tenants
            .filter(lead_id=img.lead_id)
            .filter(link_url__regex=r'(whatsapp\.net|uazapi\.com)')
            .order_by('data_criacao')
            .values_list('pk', flat=True)
        )
        if img.pk in imgs_broken:
            idx = imgs_broken.index(img.pk)
            msgs = list(
                Mensagem.all_tenants
                .filter(
                    conversa__lead_id=img.lead_id,
                    tipo_conteudo__in=('imagem', 'arquivo', 'documento'),
                )
                .exclude(arquivo='')
                .order_by('data_envio')
            )
            if idx < len(msgs):
                m = msgs[idx]
                return f'/inbox/api/conversas/{m.conversa_id}/midia/{m.pk}/'
    except Exception:
        pass

    return link
