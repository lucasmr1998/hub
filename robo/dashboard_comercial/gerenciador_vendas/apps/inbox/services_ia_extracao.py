"""Sugestoes de preenchimento de campos do Lead via IA (LLM-first com validacao pos).

Thin proxy pra um webhook N8N que faz:
  1. recebe { texto, mensagem_id, tenant_slug, lead_id }
  2. chama OpenAI gpt-4o-mini com structured output
  3. valida pos (regex, checksum CPF, trecho_origem in texto)
  4. devolve sugestoes filtradas com confianca >= 0.7

URL do webhook lida em settings.N8N_WEBHOOK_EXTRAIR_CAMPOS_URL.
Workflow versionado em robo/docs/context/n8n-workflows/hubtrix_extrair_campos_v1.json.
"""
import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CAMPOS_PERMITIDOS = {
    'nome_razaosocial', 'cpf_cnpj', 'email', 'data_nascimento',
    'rg', 'cep', 'cidade', 'estado',
    # v1.1
    'nome_mae',     # vai pra dados_custom (LeadProspecto nao tem field dedicado)
    'endereco',     # TextField — rua + numero + bairro fundidos
    'observacoes',  # TextField
}

CAMPOS_DADOS_CUSTOM = {'nome_mae'}  # campos que aplicam em dados_custom (JSON), nao em campo direto


class ExtracaoError(Exception):
    pass


def extrair_campos(mensagem) -> dict[str, Any]:
    """Dispara extracao de campos a partir de uma Mensagem.

    Retorna {'sugestoes': [...], 'total_brutas': int, 'total_validadas': int}.
    Cada sugestao: {campo, valor, trecho_origem, confianca}.

    Levanta ExtracaoError se webhook nao configurado, timeout ou resposta invalida.
    """
    webhook_url = getattr(settings, 'N8N_WEBHOOK_EXTRAIR_CAMPOS_URL', '') or ''
    if not webhook_url:
        raise ExtracaoError(
            'N8N_WEBHOOK_EXTRAIR_CAMPOS_URL nao configurado. '
            'Defina em settings ou env.'
        )

    texto = (mensagem.conteudo or '').strip()
    if not texto:
        return {'sugestoes': [], 'total_brutas': 0, 'total_validadas': 0}

    tenant = getattr(mensagem.conversa, 'tenant', None)
    lead = getattr(mensagem.conversa, 'lead', None)

    payload = {
        'texto': texto,
        'mensagem_id': mensagem.pk,
        'tenant_slug': getattr(tenant, 'slug', None),
        'lead_id': getattr(lead, 'pk', None),
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
    except requests.exceptions.Timeout:
        raise ExtracaoError('Timeout chamando N8N (30s)')
    except Exception as exc:
        raise ExtracaoError(f'Erro de rede chamando N8N: {exc}')

    if resp.status_code != 200:
        raise ExtracaoError(f'N8N respondeu {resp.status_code}: {resp.text[:200]}')

    try:
        data = resp.json()
    except Exception as exc:
        raise ExtracaoError(f'Resposta N8N nao e JSON valido: {exc}')

    if isinstance(data, list):
        data = data[0] if data else {}

    sugestoes = data.get('sugestoes', [])

    sugestoes_seguras = []
    for s in sugestoes:
        if not isinstance(s, dict):
            continue
        campo = s.get('campo')
        if campo not in CAMPOS_PERMITIDOS:
            continue
        valor = s.get('valor')
        trecho = s.get('trecho_origem', '')
        conf = s.get('confianca', 0)
        if not valor or not isinstance(conf, (int, float)) or conf < 0.7:
            continue
        if trecho and trecho.lower() not in texto.lower():
            continue
        sugestoes_seguras.append({
            'campo': campo,
            'valor': str(valor),
            'trecho_origem': trecho,
            'confianca': float(conf),
        })

    # Sanitiza rejeitadas (vindas do validador N8N) pra exibir no UI
    rejeitadas_safe = []
    for r in data.get('rejeitadas', []) or []:
        if not isinstance(r, dict):
            continue
        campo = r.get('campo')
        if campo not in CAMPOS_PERMITIDOS:
            continue
        rejeitadas_safe.append({
            'campo': campo,
            'valor': str(r.get('valor', '')),
            'trecho_origem': str(r.get('trecho_origem', '')),
            'motivos': r.get('motivos', []) if isinstance(r.get('motivos'), list) else [],
        })

    return {
        'sugestoes': sugestoes_seguras,
        'rejeitadas': rejeitadas_safe,
        'total_brutas': int(data.get('total_brutas', len(sugestoes))),
        'total_validadas': len(sugestoes_seguras),
    }


def aplicar_sugestoes(lead, sugestoes: list[dict], usuario=None) -> dict[str, Any]:
    """Aplica lista de sugestoes selecionadas no LeadProspecto.

    Cada item: {campo, valor}. Campos fora do catalogo sao ignorados.
    Retorna {'aplicados': [...], 'ignorados': [...]}
    """
    from datetime import date

    aplicados = []
    ignorados = []
    fields_dir = []  # campos direto no LeadProspecto pra update_fields
    dados_custom_changed = False

    for s in sugestoes:
        if not isinstance(s, dict):
            ignorados.append({'item': s, 'motivo': 'nao e dict'})
            continue
        campo = s.get('campo')
        valor = s.get('valor')
        if campo not in CAMPOS_PERMITIDOS:
            ignorados.append({'campo': campo, 'motivo': 'campo nao permitido'})
            continue
        if not valor:
            ignorados.append({'campo': campo, 'motivo': 'valor vazio'})
            continue

        if campo == 'data_nascimento':
            try:
                ano, mes, dia = str(valor).split('-')
                valor_norm = date(int(ano), int(mes), int(dia))
            except Exception:
                ignorados.append({'campo': campo, 'motivo': 'data invalida'})
                continue
        elif campo == 'cpf_cnpj':
            valor_norm = ''.join(c for c in str(valor) if c.isdigit())
            if len(valor_norm) not in (11, 14):
                ignorados.append({'campo': campo, 'motivo': 'cpf/cnpj invalido'})
                continue
        elif campo == 'cep':
            valor_norm = ''.join(c for c in str(valor) if c.isdigit())
            if len(valor_norm) != 8:
                ignorados.append({'campo': campo, 'motivo': 'cep invalido'})
                continue
        elif campo == 'estado':
            valor_norm = str(valor).strip().upper()[:2]
        else:
            valor_norm = str(valor).strip()

        if campo in CAMPOS_DADOS_CUSTOM:
            dc = dict(lead.dados_custom or {})
            dc[campo] = str(valor_norm)
            lead.dados_custom = dc
            dados_custom_changed = True
        else:
            setattr(lead, campo, valor_norm)
            fields_dir.append(campo)
        aplicados.append({'campo': campo, 'valor': str(valor_norm)})

    if aplicados:
        update_fields = fields_dir + ['data_atualizacao']
        if dados_custom_changed:
            update_fields.append('dados_custom')
        lead.save(update_fields=list(set(update_fields)))

    return {'aplicados': aplicados, 'ignorados': ignorados}
