"""Utilitarios do app leads.

resolver_link_interno_imagem: garante que o link de uma imagem de lead aponte
para o path interno autenticado (`/inbox/api/conversas/<c>/midia/<m>/`) e nao
para URL externa expiravel (whatsapp, uazapi).

validar_lead_pronto_para_prospect: pre-flight check ANTES de chamar
HubsoftService.cadastrar_prospecto. Evita ir pro HubSoft com dado invalido
(que retorna erro generico) e marca status_api especifico pra cada falha.
Hoje aplica so pra Nuvyon (unica em prod com HubSoft).
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


# ────────────────────────────────────────────────────────────────────
# Pre-flight validation pra cadastrar_prospecto no HubSoft
# ────────────────────────────────────────────────────────────────────

def _validar_cpf(cpf: str) -> bool:
    """Algoritmo padrao de verificacao de CPF (2 digitos verificadores)."""
    s = ''.join(ch for ch in (cpf or '') if ch.isdigit())
    if len(s) != 11 or s == s[0] * 11:
        return False
    for i in (9, 10):
        soma = sum(int(s[k]) * ((i + 1) - k) for k in range(i))
        dv = (soma * 10 % 11) % 10
        if dv != int(s[i]):
            return False
    return True


def _ids_validos_no_cache(integracao, chave_cache: str, item_id_key: str) -> set:
    """Retorna set de IDs validos do catalogo cacheado em
    IntegracaoAPI.configuracoes_extras.cache[chave]. Vazio se cache nao sync.
    """
    try:
        cache = (integracao.configuracoes_extras or {}).get('cache') or {}
        itens = cache.get(chave_cache) or []
        return {int(it.get(item_id_key)) for it in itens if it.get(item_id_key) is not None}
    except Exception:
        return set()


def validar_lead_pronto_para_prospect(lead, integracao=None) -> tuple[str, str]:
    """Pre-flight check antes de chamar HubsoftService.cadastrar_prospecto.

    Retorna (status_api, motivo). Se passar todas as validacoes:
        ('pendente', '')   ← pode chamar cadastrar_prospecto

    Senao retorna um dos status especificos com motivo claro:
        ('incompleto', 'campos faltando: rg, email, ...')
        ('cpf_invalido', 'CPF nao passa no checksum')
        ('duplicado_no_tenant', 'CPF ja convertido em prospect (lead #X id_hs=Y)')
        ('vendedor_invalido', 'id_vendedor_rp=1618 nao existe no catalogo (77 itens)')

    Hoje so a Nuvyon usa HubSoft em prod — chamar so pra leads desse tenant.
    """
    # 1) Campos obrigatorios nao vazios
    faltando = []
    if not (lead.nome_razaosocial or '').strip():
        faltando.append('nome_razaosocial')
    if not (lead.cpf_cnpj or '').strip():
        faltando.append('cpf_cnpj')
    if not (lead.telefone or '').strip():
        faltando.append('telefone')
    if not (lead.email or '').strip():
        faltando.append('email')
    if not (lead.cep or '').strip():
        faltando.append('cep')
    if not (lead.numero_residencia or '').strip():
        faltando.append('numero_residencia')
    if not (lead.rg or '').strip():
        faltando.append('rg')
    if not lead.data_nascimento:
        faltando.append('data_nascimento')
    if faltando:
        return ('incompleto', f'campos faltando: {", ".join(faltando)}')

    # 2) CPF valido (algoritmo brasileiro)
    if not _validar_cpf(lead.cpf_cnpj):
        return ('cpf_invalido', f'CPF {lead.cpf_cnpj!r} nao passa no checksum')

    # 3) Duplicado no mesmo tenant (CPF ja convertido em prospect HubSoft).
    # Evita o cenario do Pedro Paulo (id_hubsoft=22633) tentar de novo e
    # receber erro generico do HubSoft mascarado como "vendedor invalido".
    from apps.comercial.leads.models import LeadProspecto
    cpf_norm = ''.join(ch for ch in (lead.cpf_cnpj or '') if ch.isdigit())
    if cpf_norm:
        dup = (
            LeadProspecto.all_tenants
            .filter(tenant_id=lead.tenant_id, cpf_cnpj=cpf_norm)
            .exclude(pk=lead.pk)
            .exclude(id_hubsoft__isnull=True)
            .exclude(id_hubsoft='')
            .order_by('-id')
            .first()
        )
        if dup:
            return (
                'duplicado_no_tenant',
                f'CPF {cpf_norm} ja virou prospect no mesmo tenant '
                f'(lead #{dup.pk} id_hubsoft={dup.id_hubsoft})',
            )

    # 4) id_vendedor_rp deve estar no catalogo cacheado (se cache existir).
    # Sem cache (catalogo nao sincronizado ainda), pula esta validacao.
    if integracao is not None and lead.id_vendedor_rp:
        ids_validos = _ids_validos_no_cache(integracao, 'vendedores', 'id')
        if ids_validos and int(lead.id_vendedor_rp) not in ids_validos:
            return (
                'vendedor_invalido',
                f'id_vendedor_rp={lead.id_vendedor_rp} nao existe no catalogo HubSoft '
                f'({len(ids_validos)} validos). Sincronize via '
                f'sincronizar_catalogo_cacheado("vendedores").',
            )

    # Tudo OK — segue pra cadastrar_prospecto.
    return ('pendente', '')


def integracao_envia_lead(integracao) -> bool:
    """Le `extras.modos_sync.enviar_lead` da IntegracaoAPI. Retorna True se
    cliente tem essa sub-flag ATIVADA (granular, alem da flag global
    ConfiguracaoEmpresa.enviar_leads_integracao). Default True (compatibilidade
    com tenants antigos sem modos_sync setado).
    """
    extras = (integracao.configuracoes_extras or {}) if integracao else {}
    modos = extras.get('modos_sync') or {}
    if 'enviar_lead' not in modos:
        return True
    return str(modos.get('enviar_lead', '')).lower() == 'ativado'
