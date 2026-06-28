"""
Utilitários compartilhados entre apps.
Extraídos de vendas_web/views.py durante a migração para apps modulares.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _parse_json_request(request):
    try:
        body = request.body.decode('utf-8') if isinstance(request.body, (bytes, bytearray)) else request.body
        return json.loads(body or '{}')
    except Exception:
        return None


def _parse_bool(value):
    if value is None:
        return None
    value_lower = str(value).strip().lower()
    if value_lower in ['1', 'true', 't', 'sim', 'yes', 'y']:
        return True
    if value_lower in ['0', 'false', 'f', 'nao', 'não', 'no', 'n']:
        return False
    return None


def _safe_ordering(ordering_param, allowed_fields):
    if not ordering_param:
        return None
    raw = ordering_param.strip()
    desc = raw.startswith('-')
    field = raw[1:] if desc else raw
    if field in allowed_fields:
        return f"-{field}" if desc else field
    return None


def _model_field_names(model_cls):
    # Campos concretos (exclui M2M e reversos)
    field_names = []
    for f in model_cls._meta.get_fields():
        if getattr(f, 'many_to_many', False) or getattr(f, 'one_to_many', False):
            continue
        if hasattr(f, 'attname'):
            field_names.append(f.name)
    return set(field_names)


def _serialize_instance(instance):
    from django.forms.models import model_to_dict
    from decimal import Decimal
    from datetime import date
    data = model_to_dict(instance)
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = float(value)
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, date):
            data[key] = value.isoformat()
    # Campos DateTime auto que podem não estar em model_to_dict
    for auto_dt in ['data_cadastro', 'data_atualizacao', 'data_criacao', 'data_processamento', 'data_inicio_processamento', 'data_fim_processamento', 'data_hora_contato', 'data_conversao_lead', 'data_conversao_venda']:
        if hasattr(instance, auto_dt):
            val = getattr(instance, auto_dt)
            if isinstance(val, datetime):
                data[auto_dt] = val.isoformat()
    # Campos de choices: adiciona display quando existir
    for display_field, getter in [
        ('status_api_display', 'get_status_api_display'),
        ('origem_display', 'get_origem_display'),
        ('status_display', 'get_status_display'),
        ('origem_contato_display', 'get_origem_contato_display')
    ]:
        if hasattr(instance, getter):
            try:
                data[display_field] = getattr(instance, getter)()
            except Exception:
                pass
    return data


def _resolve_fk(model_cls, field_name, value):
    """Resolve ids para FKs simples quando o payload vem com inteiro."""
    from apps.comercial.leads.models import LeadProspecto, Prospecto, HistoricoContato

    if value is None:
        return None
    if model_cls is Prospecto and field_name in ['lead', 'lead_id']:
        return LeadProspecto.objects.get(id=value) if value else None
    if model_cls is HistoricoContato and field_name in ['lead', 'lead_id']:
        return LeadProspecto.objects.get(id=value) if value else None
    return value


def _apply_updates(instance, updates):
    from apps.comercial.leads.models import LeadProspecto

    fields = _model_field_names(type(instance))
    for key, value in updates.items():
        if key in ['id', 'pk']:
            continue
        if key not in fields and not key.endswith('_id'):
            continue
        try:
            resolved_value = _resolve_fk(type(instance), key, value)
            # Coerção básica para campos de data quando vier string
            if key in fields and isinstance(resolved_value, str):
                try:
                    field_obj = type(instance)._meta.get_field(key)
                    internal_type = getattr(field_obj, 'get_internal_type', lambda: '')()
                    if internal_type == 'DateField':
                        # Tentar múltiplos formatos de data
                        date_formats = [
                            '%Y-%m-%d',      # 2002-11-14 (ISO)
                            '%d/%m/%Y',      # 14/11/2002 (BR)
                            '%d-%m-%Y',      # 14-11-2002
                            '%Y/%m/%d',      # 2002/11/14 (US)
                            '%m/%d/%Y',      # 11/14/2002 (US)
                        ]
                        coerced = None
                        for fmt in date_formats:
                            try:
                                coerced = datetime.strptime(resolved_value, fmt).date()
                                break
                            except ValueError:
                                continue
                        if coerced is None:
                            # Última tentativa com fromisoformat
                            try:
                                coerced = datetime.fromisoformat(resolved_value).date()
                            except ValueError:
                                raise ValueError(f'Formato de data inválido para campo "{key}". Use DD/MM/YYYY ou YYYY-MM-DD')
                        resolved_value = coerced
                    elif internal_type == 'DateTimeField':
                        # Tentar múltiplos formatos de datetime
                        datetime_formats = [
                            '%Y-%m-%d %H:%M:%S',      # 2002-11-14 15:30:00
                            '%Y-%m-%dT%H:%M:%S',      # 2002-11-14T15:30:00 (ISO)
                            '%d/%m/%Y %H:%M:%S',      # 14/11/2002 15:30:00 (BR)
                            '%d/%m/%Y %H:%M',         # 14/11/2002 15:30 (BR)
                            '%Y-%m-%d',               # 2002-11-14 (converte para datetime)
                            '%d/%m/%Y',               # 14/11/2002 (converte para datetime)
                        ]
                        coerced_dt = None
                        for fmt in datetime_formats:
                            try:
                                if fmt in ['%Y-%m-%d', '%d/%m/%Y']:
                                    # Para formatos só de data, adiciona hora 00:00:00
                                    date_part = datetime.strptime(resolved_value, fmt).date()
                                    coerced_dt = datetime.combine(date_part, datetime.min.time())
                                else:
                                    coerced_dt = datetime.strptime(resolved_value, fmt)
                                break
                            except ValueError:
                                continue
                        if coerced_dt is None:
                            # Última tentativa com fromisoformat
                            try:
                                coerced_dt = datetime.fromisoformat(resolved_value)
                            except ValueError:
                                raise ValueError(f'Formato de data/hora inválido para campo "{key}". Use DD/MM/YYYY HH:MM:SS ou YYYY-MM-DD HH:MM:SS')
                        resolved_value = coerced_dt
                except Exception:
                    pass
            setattr(instance, key, resolved_value)
        except LeadProspecto.DoesNotExist:
            raise ValueError('Lead relacionado não encontrado')
    instance.save()
    return instance


# Mapeamento de modulo legado pra (categoria, acao) usado pelo
# _criar_log_sistema. Quando algum endpoint criar log via essa funcao,
# `categoria` e `acao` sao derivados aqui automaticamente, em vez de
# ficarem vazios no banco (problema dos 2422 logs sem categoria).
#
# Pra novo codigo, prefira usar `registrar_acao` diretamente (que ja
# exige categoria/acao explicitos). Esse mapa cobre as 6 chamadas legadas
# existentes apenas.
_MAPA_MODULO_CATEGORIA = {
    'registrar_lead_api':       ('leads', 'criar'),
    'atualizar_lead_api':       ('leads', 'editar'),
    'registrar_historico_api':  ('leads', 'criar_historico'),
    'criar_fluxo_api':          ('atendimento', 'criar'),
    'deletar_fluxo_api':        ('atendimento', 'excluir'),
    'atualizar_fluxo_api':      ('atendimento', 'editar'),
}


def _criar_log_sistema(nivel, modulo, mensagem, dados_extras=None, request=None):
    """
    Cria um log no sistema (helper legado). Para novo codigo, prefira
    `registrar_acao(categoria, acao, entidade, entidade_id, mensagem, ...)`.

    Args:
        nivel: Nivel do log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        modulo: Modulo/funcao que gerou o log
        mensagem: Mensagem do log
        dados_extras: Dados JSON extras (opcional)
        request: Request HTTP para extrair IP e usuario (opcional)

    Categoria e acao sao derivados de `modulo` via _MAPA_MODULO_CATEGORIA.
    Modulo desconhecido cai em categoria='sistema' acao='evento'.
    """
    try:
        from apps.sistema.models import LogSistema

        ip = None
        usuario = None
        tenant = None

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')

            if request.user.is_authenticated:
                usuario = request.user.username

            tenant = getattr(request, 'tenant', None)

        if not tenant:
            try:
                from apps.sistema.middleware import get_current_tenant
                tenant = get_current_tenant()
            except Exception:
                tenant = None

        categoria, acao = _MAPA_MODULO_CATEGORIA.get(modulo, ('sistema', 'evento'))

        LogSistema.objects.create(
            tenant=tenant,
            categoria=categoria,
            acao=acao,
            nivel=nivel,
            modulo=modulo,
            mensagem=mensagem,
            dados_extras=dados_extras,
            usuario=usuario,
            ip=ip,
        )
    except Exception as e:
        # Se falhar ao criar log, nao interromper o fluxo principal
        logger.warning("Erro ao criar log: %s", str(e))


import re as _re
_AUDITAR_REDACT_RE = _re.compile(
    r'("(?:cpf_cnpj|cpf|rg|password|senha|api_token|token|secret|client_secret|api_key)"\s*:\s*)"[^"]*"',
    _re.IGNORECASE,
)
_AUDITAR_MAX = 4000  # bytes por payload (caber em LogSistema com folga)


def _auditar_redact(text):
    """Substitui valores de campos sensiveis por [REDACTED]. JSON-aware."""
    if not isinstance(text, str):
        return text
    return _AUDITAR_REDACT_RE.sub(r'\1"[REDACTED]"', text)


def _auditar_payload_req(request):
    """Captura body do request com PII redacted e truncado."""
    try:
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return None
        raw = request.body.decode('utf-8', errors='replace')[:_AUDITAR_MAX]
        return _auditar_redact(raw)
    except Exception:
        return None


def _auditar_payload_resp(content):
    """Captura body da response com PII redacted e truncado."""
    try:
        s = content.decode('utf-8', errors='replace')[:_AUDITAR_MAX] if content else ''
        return _auditar_redact(s)
    except Exception:
        return None


def auditar(categoria, acao, entidade):
    """
    Decorator que registra log de auditoria apos views POST/PUT/DELETE.

    Loga TANTO sucesso QUANTO erros (status >= 400) — sucessos vao com nivel
    INFO, erros 4xx com WARNING e 5xx com ERROR.

    Inclui em dados_extras: status_code, payload_req (body do request) e
    payload_resp (body da response). Ambos com PII sensivel redacted
    (cpf_cnpj, rg, password, token, etc.) e truncados em 4000 chars.

    Uso:
        @auditar('crm', 'criar', 'nota')
        def api_nota_criar(request): ...
    """
    import functools
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            payload_req = _auditar_payload_req(request)
            response = view_func(request, *args, **kwargs)
            try:
                import json as _json
                status = getattr(response, 'status_code', 0)
                content = response.content if hasattr(response, 'content') else b''
                payload_resp = _auditar_payload_resp(content)
                eid = None
                msg_default = f'{acao} {entidade}'
                msg = msg_default
                if status < 400:
                    try:
                        data = _json.loads(content) if content else {}
                        eid = data.get('id') or data.get('pk') or (args[0] if args else None)
                        msg = data.get('message', data.get('mensagem', msg_default))
                    except Exception:
                        pass
                    nivel = 'INFO'
                else:
                    eid = args[0] if args else None
                    msg = f'ERRO {status} em {acao} {entidade}'
                    nivel = 'WARNING' if status < 500 else 'ERROR'

                dados_extras = {
                    'status_code': status,
                    'metodo': request.method,
                    'payload_req': payload_req,
                    'payload_resp': payload_resp,
                }
                registrar_acao(
                    categoria, acao, entidade, eid, str(msg)[:200],
                    request=request, dados_extras=dados_extras, nivel=nivel,
                )
            except Exception as e:
                logger.warning('auditar fallback: %s', str(e))
                try:
                    registrar_acao(categoria, acao, entidade,
                                   args[0] if args else None,
                                   f'{acao} {entidade}', request=request)
                except Exception:
                    pass
            return response
        return wrapper
    return decorator


def registrar_acao(categoria, acao, entidade, entidade_id, mensagem, request=None, dados_extras=None, nivel='INFO'):
    """
    Registra uma acao de auditoria no LogSistema.

    Args:
        categoria: auth, leads, crm, inbox, suporte, cs, marketing, config, admin, sistema
        acao: criar, editar, excluir, mover, atribuir, login, logout, validar, aprovar, rejeitar
        entidade: lead, oportunidade, tarefa, conversa, ticket, usuario, campanha, segmento, etc.
        entidade_id: PK do objeto afetado (int ou None)
        mensagem: Descricao da acao
        request: HttpRequest para extrair IP, usuario e tenant
        dados_extras: dict com dados adicionais
        nivel: INFO (padrao), WARNING, ERROR
    """
    try:
        from apps.sistema.models import LogSistema
        from apps.sistema.middleware import get_current_tenant

        ip = None
        usuario = None
        tenant = None

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            if request.user.is_authenticated:
                usuario = request.user.username
            tenant = getattr(request, 'tenant', None)

        if not tenant:
            tenant = get_current_tenant()

        LogSistema.objects.create(
            tenant=tenant,
            nivel=nivel,
            modulo=f'{categoria}.{acao}',
            mensagem=mensagem,
            dados_extras=dados_extras,
            usuario=usuario,
            ip=ip,
            categoria=categoria,
            acao=acao,
            entidade=entidade,
            entidade_id=int(entidade_id) if entidade_id else None,
        )
    except Exception as e:
        logger.warning("Erro ao registrar acao: %s", str(e))


def get_client_ip(request):
    """Função para obter o IP real do cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
