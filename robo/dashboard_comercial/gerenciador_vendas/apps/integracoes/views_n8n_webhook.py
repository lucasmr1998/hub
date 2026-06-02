"""
Webhook publico do N8N pra receber leads qualificados de fluxos externos
(ex: orquestrador N8N do TR Carrion processa conversa WhatsApp -> chama aqui).

Endpoint: POST /api/public/n8n/lead/
Auth: header X-N8N-Webhook-Secret (env N8N_WEBHOOK_SECRET).
Payload JSON minimo: {tenant_slug, telefone, nome_razaosocial}.

Cria/atualiza LeadProspecto, cria OportunidadeVenda no pipeline padrao do tenant.
"""
import json
import logging
import os

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.sistema.models import Tenant
from apps.sistema.utils import registrar_acao
from apps.comercial.leads.models import LeadProspecto
from apps.comercial.crm.models import OportunidadeVenda, Pipeline, PipelineEstagio
from apps.comercial.viabilidade.models import CidadeViabilidade
from apps.inbox.models import CanalInbox, Conversa, Mensagem, EtiquetaConversa
from apps.comercial.crm.models import TagCRM

logger = logging.getLogger(__name__)


def _autorizado(request):
    """Valida o shared secret no header."""
    esperado = os.environ.get('N8N_WEBHOOK_SECRET', '')
    recebido = request.headers.get('X-N8N-Webhook-Secret', '')
    if not esperado:
        logger.warning('N8N_WEBHOOK_SECRET nao configurado no ambiente. Rejeitando.')
        return False
    return recebido == esperado


def _transferir_para_fila(conversa, tenant, oportunidade=None):
    """Transfere a conversa pra fila: regras de cidade PRIMEIRO (processar_seguro,
    ex: Palhoca->Flavia), depois round-robin da fila como fallback. So atribui se
    ainda nao tem agente."""
    if conversa.agente_id:
        return
    if oportunidade:
        try:
            from apps.comercial.crm.services.automacao_pipeline import processar_seguro
            processar_seguro(oportunidade=oportunidade)
            conversa.refresh_from_db(fields=['agente'])
        except Exception as e:
            logger.error(f'Erro avaliando regras de cidade p/ conversa {conversa.id}: {e}')
    if not conversa.agente_id:
        from apps.inbox.models import FilaInbox
        fila = FilaInbox.all_tenants.filter(
            tenant=tenant, ativo=True
        ).order_by('-prioridade').first()
        if fila:
            conversa.fila = fila
            conversa.equipe = fila.equipe
            conversa.save(update_fields=['fila', 'equipe'])
            try:
                from apps.inbox.distribution import distribuir_conversa
                distribuir_conversa(conversa, tenant)
            except Exception as e:
                logger.error(f'Erro distribuindo conversa {conversa.id}: {e}')


def _sanitizar_conteudo_midia(conteudo, tipo_conteudo, arquivo_url, arquivo_nome):
    """
    Quando o conteudo chega como o objeto de midia do WhatsApp serializado em
    JSON (acontece se o fluxo N8N pega message.content em vez de message.text),
    extrai os campos uteis e devolve um conteudo legivel pro Inbox.

    Retorna (conteudo, tipo_conteudo, arquivo_url, arquivo_nome).
    """
    texto = (conteudo or '').strip()
    if not (texto.startswith('{') and texto.endswith('}')):
        return conteudo, tipo_conteudo, arquivo_url, arquivo_nome
    if not any(k in texto for k in ('"mimetype"', '"directPath"', '"URL"')):
        return conteudo, tipo_conteudo, arquivo_url, arquivo_nome
    try:
        obj = json.loads(texto)
    except (json.JSONDecodeError, ValueError):
        return conteudo, tipo_conteudo, arquivo_url, arquivo_nome
    if not isinstance(obj, dict):
        return conteudo, tipo_conteudo, arquivo_url, arquivo_nome

    mime = str(obj.get('mimetype') or '').lower()
    nome = str(obj.get('title') or obj.get('fileName') or '').strip() or arquivo_nome
    url = obj.get('URL') or obj.get('url') or arquivo_url or ''
    if mime.startswith('image/'):
        return '\U0001F4F7 Imagem', 'imagem', url, nome
    if mime.startswith('audio/'):
        return '\U0001F3A4 Audio', 'audio', url, nome
    if mime.startswith('video/'):
        return '\U0001F3A5 Video', 'video', url, nome
    label = f'\U0001F4CE {nome}' if nome else '\U0001F4CE Documento'
    return label, 'arquivo', url, nome


def _ext_de_mime(mime):
    """Extensao de arquivo a partir do mimetype."""
    import mimetypes
    mapa = {
        'image/jpeg': '.jpg', 'image/jpg': '.jpg', 'image/png': '.png',
        'image/webp': '.webp', 'image/gif': '.gif', 'application/pdf': '.pdf',
        'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'audio/mp4': '.m4a',
        'video/mp4': '.mp4',
    }
    return mapa.get((mime or '').lower()) or mimetypes.guess_extension(mime or '') or '.bin'


def _baixar_midia_uazapi(tenant, mensagem, message_id):
    """
    Baixa a midia decriptada do Uazapi (POST /message/download) e anexa ao
    campo `arquivo` da Mensagem. Roda fora da transacao do webhook; qualquer
    falha so deixa a mensagem sem o arquivo (degradacao graciosa).
    """
    try:
        from apps.integracoes.models import IntegracaoAPI
        from apps.integracoes.services.uazapi import UazapiService
        from django.core.files.base import ContentFile

        integ = IntegracaoAPI.objects.filter(
            tenant=tenant, tipo='uazapi', ativa=True
        ).first()
        if not integ:
            logger.info(f'Sem integracao uazapi ativa no tenant {tenant.slug}; midia nao baixada')
            return
        conteudo_bytes, mime = UazapiService(integracao=integ).baixar_midia(message_id)
        if not conteudo_bytes:
            return
        nome_arq = f'{message_id}{_ext_de_mime(mime)}'
        mensagem.arquivo.save(nome_arq, ContentFile(conteudo_bytes), save=False)
        mensagem.arquivo_tamanho = len(conteudo_bytes)
        mensagem.save(update_fields=['arquivo', 'arquivo_tamanho'])
    except Exception as e:
        logger.warning(f'Falha ao baixar midia {message_id} do Uazapi: {e}')


@csrf_exempt
@require_POST
def receber_lead(request):
    """
    Recebe lead qualificado de um fluxo N8N externo.

    Body JSON esperado (campos opcionais marcados com ?):
        tenant_slug:        str   - slug do tenant destino (obrigatorio)
        telefone:           str   - E.164 ou nacional (obrigatorio)
        nome_razaosocial:   str   - nome completo do lead (obrigatorio)
        email:              str?  - email
        cep:                str?  - CEP do endereco
        cidade:             str?
        estado:             str?  - UF
        bairro:             str?
        rua:                str?
        numero:             str?  - numero da residencia
        complemento:        str?
        plano_interesse:    str?  - texto livre / nome do plano
        observacoes:        str?  - observacoes adicionais (vai pra anotacao da oportunidade)
        origem:             str?  - default "whatsapp_n8n"
        canal_entrada:      str?  - default "whatsapp"
        dados_extras:       dict? - JSON livre salvo em dados_custom

    Retorna:
        201 + {sucesso: true, lead_id, oportunidade_id} se criou
        200 + {sucesso: true, lead_id, oportunidade_id, ja_existia: true} se ja existia
        400 se payload invalido
        401 se secret invalido
        404 se tenant nao existe
    """
    if not _autorizado(request):
        return JsonResponse({'sucesso': False, 'erro': 'Nao autorizado'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'sucesso': False, 'erro': 'JSON invalido'}, status=400)

    tenant_slug = (payload.get('tenant_slug') or '').strip()
    telefone = (payload.get('telefone') or '').strip()
    nome = (payload.get('nome_razaosocial') or '').strip()

    erros = []
    if not tenant_slug:
        erros.append('tenant_slug obrigatorio')
    if not telefone:
        erros.append('telefone obrigatorio')
    if not nome:
        erros.append('nome_razaosocial obrigatorio')
    if erros:
        return JsonResponse({'sucesso': False, 'erros': erros}, status=400)

    tenant = Tenant.objects.filter(slug=tenant_slug, ativo=True).first()
    if not tenant:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant {tenant_slug!r} nao encontrado'}, status=404)

    # Normaliza telefone (so digitos)
    telefone_normalizado = ''.join(c for c in telefone if c.isdigit())

    with transaction.atomic():
        # Procura lead existente por telefone no tenant
        lead = LeadProspecto.all_tenants.filter(
            tenant=tenant, telefone__contains=telefone_normalizado[-9:]
        ).first()

        ja_existia = bool(lead)

        # Parse data_nascimento se vier formato DD/MM/AAAA
        from datetime import datetime
        data_nasc = None
        raw_data = (payload.get('data_nascimento') or '').strip()
        if raw_data:
            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                try:
                    data_nasc = datetime.strptime(raw_data, fmt).date()
                    break
                except ValueError:
                    continue

        if not lead:
            lead = LeadProspecto.objects.create(
                tenant=tenant,
                nome_razaosocial=nome,
                telefone=telefone,
                email=payload.get('email') or '',
                cep=payload.get('cep') or '',
                cidade=payload.get('cidade') or '',
                estado=payload.get('estado') or '',
                bairro=payload.get('bairro') or '',
                rua=payload.get('rua') or '',
                numero_residencia=payload.get('numero') or '',
                cpf_cnpj=payload.get('cpf') or '',
                data_nascimento=data_nasc,
                origem=payload.get('origem') or 'whatsapp_n8n',
                canal_entrada=payload.get('canal_entrada') or 'whatsapp',
            )
        else:
            # Atualiza campos vazios
            campos_atualizaveis = {
                'email': payload.get('email'),
                'cep': payload.get('cep'),
                'cidade': payload.get('cidade'),
                'estado': payload.get('estado'),
                'bairro': payload.get('bairro'),
                'rua': payload.get('rua'),
                'numero_residencia': payload.get('numero'),
                'cpf_cnpj': payload.get('cpf'),
                'data_nascimento': data_nasc,
            }
            atualizou = False
            for campo, valor in campos_atualizaveis.items():
                if valor and not getattr(lead, campo, None):
                    setattr(lead, campo, valor)
                    atualizou = True
            if atualizou:
                lead.save()

        # lead_id e unico: o lead tem no maximo UMA oportunidade. Buscar qualquer
        # uma (inclusive em estagio final) evita tentar criar uma segunda e violar
        # a constraint unique(lead_id).
        oportunidade = OportunidadeVenda.all_tenants.filter(
            tenant=tenant, lead=lead,
        ).first()

        if not oportunidade:
            pipeline = Pipeline.all_tenants.filter(tenant=tenant, padrao=True).first()
            if not pipeline:
                pipeline = Pipeline.all_tenants.filter(tenant=tenant).first()
            estagio = None
            if pipeline:
                estagio = PipelineEstagio.all_tenants.filter(
                    tenant=tenant, pipeline=pipeline,
                ).order_by('ordem').first()
            plano = (payload.get('plano_interesse') or '').strip()
            titulo = f'{nome} - {plano}' if plano else nome
            obs = payload.get('observacoes') or ''
            dados_extras = payload.get('dados_extras') or {}
            if obs:
                dados_extras['observacoes_n8n'] = obs[:2000]
            if plano:
                dados_extras['plano_interesse_texto'] = plano
            if not estagio:
                return JsonResponse({
                    'sucesso': False,
                    'erro': 'Tenant nao possui pipeline com estagios configurados',
                }, status=409)
            oportunidade = OportunidadeVenda.objects.create(
                tenant=tenant,
                lead=lead,
                pipeline=pipeline,
                estagio=estagio,
                titulo=titulo[:255],
                dados_custom=dados_extras,
                origem_crm='automatico',
            )

        # Sinais extras pro motor de pipeline (usado pela Nuvyon: o bot N8N
        # reporta progresso a cada etapa). Dirigem as regras de automacao.
        tags_in = payload.get('tags') or []
        if isinstance(tags_in, list):
            for tag_nome in tags_in:
                tag_nome = str(tag_nome).strip()
                if not tag_nome:
                    continue
                tag, _ = TagCRM.all_tenants.get_or_create(
                    tenant=tenant, nome=tag_nome, defaults={'cor_hex': '#94a3b8'},
                )
                oportunidade.tags.add(tag)

        lead_campos = payload.get('lead_campos') or {}
        if isinstance(lead_campos, dict) and lead_campos:
            CAMPOS_PERMITIDOS = {
                'id_plano_rp', 'status_api', 'cpf_cnpj', 'email', 'cep',
                'cidade', 'estado', 'bairro', 'rua', 'numero_residencia',
            }
            campos_ok = []
            for campo, valor in lead_campos.items():
                if campo not in CAMPOS_PERMITIDOS or valor in (None, ''):
                    continue
                # Coage conforme o tipo do campo; ignora valor invalido em vez
                # de derrubar a request (ex: id_plano_rp eh int).
                try:
                    field = LeadProspecto._meta.get_field(campo)
                    if field.get_internal_type() in ('IntegerField', 'BigIntegerField', 'PositiveIntegerField'):
                        valor = int(valor)
                    setattr(lead, campo, valor)
                    campos_ok.append(campo)
                except (ValueError, TypeError) as exc:
                    logger.warning(f'[receber_lead] campo {campo}={valor!r} invalido: {exc}')
            if campos_ok:
                lead.save(update_fields=campos_ok)

        hist_status = (payload.get('historico_status') or '').strip()
        if hist_status:
            from apps.comercial.leads.models import HistoricoContato
            HistoricoContato.objects.create(
                tenant=tenant, lead=lead, telefone=telefone,
                status=hist_status,
                nome_contato=nome or lead.nome_razaosocial,
            )

        # Log de auditoria
        try:
            registrar_acao(
                'integracao', 'criar_lead' if not ja_existia else 'atualizar_lead', 'lead',
                lead.id,
                f'Lead via N8N webhook: {nome} ({telefone}). Oport #{oportunidade.id}.',
                request=request,
            )
        except Exception:
            pass

    # Re-avalia as regras de pipeline com os sinais aplicados (fora da
    # transacao — o motor faz seus proprios saves/IO).
    try:
        from apps.comercial.crm.services.automacao_pipeline import processar_seguro
        processar_seguro(oportunidade=oportunidade)
    except Exception as exc:
        logger.warning(f'[receber_lead] Falha ao reavaliar regras: {exc}')

    status = 200 if ja_existia else 201
    # Recarrega pra refletir movimento de estagio feito pelo motor
    try:
        oportunidade.refresh_from_db(fields=['estagio'])
    except Exception:
        pass
    return JsonResponse({
        'sucesso': True,
        'tenant': tenant.slug,
        'lead_id': lead.id,
        'oportunidade_id': oportunidade.id,
        'estagio_id': oportunidade.estagio_id,
        'estagio_nome': oportunidade.estagio.nome if oportunidade.estagio_id else None,
        'ja_existia': ja_existia,
    }, status=status)


def _normalizar_cidade(s):
    """Lowercase + remove acentos basicos pra match case/acento-insensitivo."""
    if not s:
        return ''
    import unicodedata
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return s.strip().lower()


@csrf_exempt
@require_POST
def viabilidade_check(request):
    """
    Verifica se o tenant atende uma cidade/estado.

    Body JSON:
        tenant_slug: str  (obrigatorio)
        cidade:      str  (obrigatorio)
        estado:      str  (opcional — UF de 2 letras pra desambiguar)
        cep:         str? (opcional — se informado, prioriza match por CEP)

    Retorna:
        200 {atendido: true,  cidade_match, estado, cep_match?}
        200 {atendido: false, cidade_match: null, estado, cidades_atendidas: [...]}
        400 payload invalido
        401 secret invalido
        404 tenant nao existe
    """
    if not _autorizado(request):
        return JsonResponse({'sucesso': False, 'erro': 'Nao autorizado'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'sucesso': False, 'erro': 'JSON invalido'}, status=400)

    tenant_slug = (payload.get('tenant_slug') or '').strip()
    cidade = (payload.get('cidade') or '').strip()
    estado = (payload.get('estado') or '').strip().upper()
    cep = (payload.get('cep') or '').strip()

    if not tenant_slug or not cidade:
        return JsonResponse({
            'sucesso': False,
            'erro': 'tenant_slug e cidade sao obrigatorios',
        }, status=400)

    tenant = Tenant.objects.filter(slug=tenant_slug, ativo=True).first()
    if not tenant:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant {tenant_slug!r} nao encontrado'}, status=404)

    qs = CidadeViabilidade.all_tenants.filter(tenant=tenant)
    if estado:
        qs = qs.filter(estado=estado)

    cep_match = None
    if cep:
        cep_norm = ''.join(c for c in cep if c.isdigit())
        if len(cep_norm) == 8:
            cep_formatado = f'{cep_norm[:5]}-{cep_norm[5:]}'
            cep_match_qs = qs.filter(cep__in=[cep_norm, cep_formatado]).first()
            if cep_match_qs:
                cep_match = cep_match_qs.cep

    cidade_norm = _normalizar_cidade(cidade)
    cidade_match_obj = None
    for c in qs.iterator():
        if _normalizar_cidade(c.cidade) == cidade_norm:
            cidade_match_obj = c
            break

    atendido = bool(cep_match) or bool(cidade_match_obj)

    response = {
        'sucesso': True,
        'tenant': tenant.slug,
        'atendido': atendido,
        'cidade_match': cidade_match_obj.cidade if cidade_match_obj else None,
        'estado': estado or (cidade_match_obj.estado if cidade_match_obj else None),
        'cep_match': cep_match,
    }
    if not atendido:
        response['cidades_atendidas'] = list(
            qs.values_list('cidade', 'estado').distinct().order_by('cidade')[:50]
        )

    return JsonResponse(response, status=200)


@csrf_exempt
@require_POST
def inbox_mensagem(request):
    """
    Registra mensagem no Inbox e garante Conversa + Lead + Oportunidade.

    Body JSON:
        tenant_slug:     str    (obrigatorio)
        telefone:        str    (obrigatorio)
        conteudo:        str    (obrigatorio — texto da mensagem)
        direcao:         str    'recebida' (do cliente) | 'enviada' (do bot/agente)
        canal_identif:   str?   identificador do canal (default: usa primeiro whatsapp do tenant)
        nome_contato:    str?   nome do cliente (atualiza Lead se vier)
        tipo_conteudo:   str?   'texto' (default), 'imagem', 'arquivo', etc.
        arquivo_url:     str?   URL se conteudo for media
        modo_atendimento:str?   bot | humano | finalizado_bot — atualiza a Conversa
        dados_lead:      dict?  {cpf, data_nascimento, cidade, ...} pra atualizar Lead
        msg_id_externo:  str?   ID do Wazapi pra dedup
    """
    if not _autorizado(request):
        return JsonResponse({'sucesso': False, 'erro': 'Nao autorizado'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'sucesso': False, 'erro': 'JSON invalido'}, status=400)

    tenant_slug = (payload.get('tenant_slug') or '').strip()
    telefone = (payload.get('telefone') or '').strip()
    conteudo = payload.get('conteudo') or ''
    direcao = (payload.get('direcao') or 'recebida').strip()

    if not tenant_slug or not telefone or not conteudo:
        return JsonResponse({'sucesso': False, 'erro': 'tenant_slug, telefone e conteudo obrigatorios'}, status=400)

    tipo_conteudo = (payload.get('tipo_conteudo') or 'texto').strip()
    arquivo_url = (payload.get('arquivo_url') or '').strip()
    arquivo_nome = (payload.get('arquivo_nome') or '').strip()
    conteudo, tipo_conteudo, arquivo_url, arquivo_nome = _sanitizar_conteudo_midia(
        conteudo, tipo_conteudo, arquivo_url, arquivo_nome)

    tenant = Tenant.objects.filter(slug=tenant_slug, ativo=True).first()
    if not tenant:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant {tenant_slug!r} nao encontrado'}, status=404)

    nome_contato = (payload.get('nome_contato') or '').strip() or 'Lead WhatsApp'
    telefone_norm = ''.join(c for c in telefone if c.isdigit())

    # Validacao antecipada de modo_atendimento (Bug 2)
    modo_in = payload.get('modo_atendimento')
    if modo_in and modo_in not in dict(Conversa.MODO_ATENDIMENTO_CHOICES):
        return JsonResponse(
            {'sucesso': False, 'erro': 'modo_atendimento invalido. Aceitos: bot, humano, finalizado_bot'},
            status=400,
        )

    # Validacao antecipada de tags (Bug 4)
    if 'tags' in payload and not isinstance(payload.get('tags'), list):
        return JsonResponse({'sucesso': False, 'erro': 'tags deve ser uma lista'}, status=400)

    # Acumulador de avisos nao-bloqueantes
    avisos = []

    # Validacao basica de cpf em dados_lead (Bug 3) — ignora se invalido
    _dados_lead_in = payload.get('dados_lead') or {}
    if isinstance(_dados_lead_in, dict) and _dados_lead_in.get('cpf'):
        _cpf_raw = str(_dados_lead_in.get('cpf'))
        _cpf_digits = ''.join(c for c in _cpf_raw if c.isdigit())
        if len(_cpf_digits) not in (11, 14):
            avisos.append(f'cpf invalido ({len(_cpf_digits)} digitos); campo ignorado')
            _dados_lead_in = {k: v for k, v in _dados_lead_in.items() if k != 'cpf'}
            payload['dados_lead'] = _dados_lead_in

    with transaction.atomic():
        # 1. Canal — usa o identificador se vier, senao primeiro whatsapp do tenant
        canal_identif = (payload.get('canal_identif') or '').strip()
        canal_qs = CanalInbox.all_tenants.filter(tenant=tenant, tipo='whatsapp', ativo=True)
        if canal_identif:
            canal = canal_qs.filter(identificador_canal=canal_identif).first() or canal_qs.first()
        else:
            canal = canal_qs.first()
        if not canal:
            return JsonResponse({'sucesso': False, 'erro': 'Nenhum canal whatsapp ativo no tenant'}, status=409)

        # 2. Lead — find or create por telefone
        lead = LeadProspecto.all_tenants.filter(
            tenant=tenant, telefone__contains=telefone_norm[-9:]
        ).first()
        if not lead:
            lead = LeadProspecto.objects.create(
                tenant=tenant,
                nome_razaosocial=nome_contato,
                telefone=telefone,
                origem='whatsapp_n8n',
                canal_entrada='whatsapp',
            )

        # Atualiza nome se chegou
        if payload.get('nome_contato') and lead.nome_razaosocial in ('', 'Lead WhatsApp'):
            lead.nome_razaosocial = nome_contato
            lead.save(update_fields=['nome_razaosocial'])

        # Atualiza campos extras se dados_lead vier
        dados_lead = payload.get('dados_lead') or {}
        if dados_lead:
            campos_map = {
                'email': 'email', 'cep': 'cep', 'cidade': 'cidade', 'estado': 'estado',
                'bairro': 'bairro', 'rua': 'rua', 'numero': 'numero_residencia',
                'cpf': 'cpf_cnpj',
            }
            atualizou = False
            for k_in, k_model in campos_map.items():
                v = dados_lead.get(k_in)
                if v and not getattr(lead, k_model, None):
                    # Sanitiza tamanho — N8N/Vero envia dados livres, pode estourar max_length.
                    # Trunca defensivamente pra evitar StringDataRightTruncation 500.
                    field = LeadProspecto._meta.get_field(k_model)
                    max_len = getattr(field, 'max_length', None)
                    v_str = str(v).strip()
                    if max_len and len(v_str) > max_len:
                        v_str = v_str[:max_len]
                    setattr(lead, k_model, v_str)
                    atualizou = True
            # data_nascimento parsing
            raw_data = (dados_lead.get('data_nascimento') or '').strip()
            if raw_data and not lead.data_nascimento:
                from datetime import datetime
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        lead.data_nascimento = datetime.strptime(raw_data, fmt).date()
                        atualizou = True
                        break
                    except ValueError:
                        continue
            if atualizou:
                # FAILSAFE — lead.save() falhando NUNCA pode derrubar o registro
                # da mensagem. A mensagem em si eh PRIORIDADE. Logamos o erro
                # e seguimos. Aviso vai pro caller via 'avisos' na resposta.
                try:
                    lead.save()
                except Exception as save_exc:
                    logger.error(
                        '[N8N inbox] lead.save() falhou (lead pk=%s tenant=%s): %s — '
                        'mensagem sera registrada mesmo assim',
                        getattr(lead, 'pk', None), tenant_slug, save_exc,
                    )
                    avisos.append(f'lead nao atualizado: {type(save_exc).__name__}')

        # 3. Oportunidade — find or create (lead_id e unico: reusa qualquer existente)
        oportunidade = OportunidadeVenda.all_tenants.filter(
            tenant=tenant, lead=lead
        ).first()
        if not oportunidade:
            pipeline = Pipeline.all_tenants.filter(tenant=tenant, padrao=True).first() or \
                       Pipeline.all_tenants.filter(tenant=tenant).first()
            estagio = None
            if pipeline:
                estagio = PipelineEstagio.all_tenants.filter(
                    tenant=tenant, pipeline=pipeline
                ).order_by('ordem').first()
            if estagio:
                oportunidade = OportunidadeVenda.objects.create(
                    tenant=tenant, lead=lead, pipeline=pipeline, estagio=estagio,
                    titulo=lead.nome_razaosocial[:255], origem_crm='automatico',
                    dados_custom=dados_lead or {},
                )

        # 4. Conversa — find or create
        conversa = Conversa.all_tenants.filter(
            tenant=tenant, canal=canal, contato_telefone__contains=telefone_norm[-9:]
        ).exclude(status__in=['resolvida', 'arquivada']).first()
        ja_existia_conversa = bool(conversa)

        if not conversa:
            # numero eh calculado pelo Conversa.save() — usa select_for_update
            # + retry contra race (corrigido em 42e9101). Aqui passamos vazio e
            # deixamos o save fazer o trabalho seguro.
            conversa = Conversa(
                tenant=tenant, canal=canal, lead=lead,
                contato_nome=lead.nome_razaosocial, contato_telefone=telefone,
                contato_email=lead.email or '',
                status='aberta', modo_atendimento='bot',
                oportunidade=oportunidade,
            )
            conversa.save()

        # Sincroniza snapshot da Conversa com o Lead — campos contato_* sao
        # snapshot e podem ficar com placeholder se a Conversa foi criada
        # antes do Lead ter nome/email. Atualiza se mudou.
        conv_updates = []
        if lead.nome_razaosocial and lead.nome_razaosocial != 'Lead WhatsApp' and \
           conversa.contato_nome in ('', 'Lead WhatsApp', None):
            conversa.contato_nome = lead.nome_razaosocial
            conv_updates.append('contato_nome')
        if lead.email and not conversa.contato_email:
            conversa.contato_email = lead.email
            conv_updates.append('contato_email')
        if conv_updates:
            conversa.save(update_fields=conv_updates)

        # Atualiza modo se vier (validacao ja feita no inicio — Bug 2)
        # CRITICO: nunca regredir 'humano' -> 'bot' a partir do webhook
        # do Vero. Isso destrava o bot pra responder por cima do agente
        # humano (caso Michele 02/06/2026 — bot mandou 4 msgs depois da
        # Kelle ter assumido). Se a conversa ja esta em 'humano' OU tem
        # agente atribuido, o webhook NAO pode rebaixar o modo.
        modo = payload.get('modo_atendimento')
        if modo:
            modo_atual = conversa.modo_atendimento
            tem_agente = bool(conversa.agente_id)
            quer_voltar_pra_bot = (modo == 'bot' and (modo_atual == 'humano' or tem_agente))
            if quer_voltar_pra_bot:
                logger.warning(
                    '[N8N inbox] Tentativa de regredir modo humano->bot bloqueada '
                    '(conv=%s tenant=%s agente_id=%s). Mantendo modo=%s.',
                    conversa.id, tenant.slug, conversa.agente_id, modo_atual,
                )
                avisos.append('modo_atendimento mantido humano (agente atribuido)')
            else:
                modo_mudou = (modo_atual != modo)
                if modo_mudou:
                    conversa.modo_atendimento = modo
                    conversa.save(update_fields=['modo_atendimento'])

                if modo in ('finalizado_bot', 'humano') and (modo_atual != modo) and not conversa.agente_id:
                    _transferir_para_fila(conversa, tenant, oportunidade)

        # Atualiza Oportunidade.dados_custom com estado do atendimento — pra motor de automacoes
        atendimento_estado = payload.get('atendimento_estado')
        if atendimento_estado and oportunidade:
            dc = dict(oportunidade.dados_custom or {})
            dc['atendimento_estado'] = atendimento_estado
            from django.utils import timezone as _tz
            dc['atendimento_atualizado_em'] = _tz.now().isoformat()
            oportunidade.dados_custom = dc
            oportunidade.save(update_fields=['dados_custom'])

        # Tags — aplica em Conversa (etiquetas) E Oportunidade (tags)
        tags_in = payload.get('tags') or []
        if isinstance(tags_in, list) and tags_in:
            for tag_slug in tags_in:
                tag_slug = str(tag_slug).strip().lower()
                if not tag_slug:
                    continue
                # EtiquetaConversa
                etiq, _ = EtiquetaConversa.objects.get_or_create(
                    tenant=tenant, nome=tag_slug,
                    defaults={'cor_hex': '#94a3b8'},
                )
                conversa.etiquetas.add(etiq)
                # TagCRM (na Oportunidade)
                if oportunidade:
                    tag_crm, _ = TagCRM.objects.get_or_create(
                        tenant=tenant, nome=tag_slug,
                        defaults={'cor_hex': '#94a3b8'},
                    )
                    oportunidade.tags.add(tag_crm)

        # 5. Mensagem — sempre cria (com dedup)
        msg_id_ext = (payload.get('msg_id_externo') or '').strip()
        # remetente_tipo: 'recebida' -> contato; senao 'bot', exceto se o
        # payload pedir explicitamente 'agente' (mensagem que um humano
        # enviou direto pelo WhatsApp, fora do bot).
        remetente_tipo = 'contato' if direcao == 'recebida' else 'bot'
        if direcao != 'recebida' and payload.get('remetente_tipo') == 'agente':
            remetente_tipo = 'agente'
        # Dedup se vier msg_id
        if msg_id_ext and Mensagem.all_tenants.filter(
            tenant=tenant, conversa=conversa, identificador_externo=msg_id_ext
        ).exists():
            mensagem = Mensagem.all_tenants.filter(
                tenant=tenant, conversa=conversa, identificador_externo=msg_id_ext
            ).first()
            mensagem_criada = False
        else:
            # Bug 1 — fallback de dedup por hash quando nao tem msg_id_externo.
            # So pra texto: midia vira label generico ('Imagem') e o hash
            # colidiria entre envios distintos.
            mensagem_dup = None
            if not msg_id_ext and tipo_conteudo == 'texto':
                from datetime import timedelta
                from django.utils import timezone as _tz
                limite = _tz.now() - timedelta(seconds=30)
                mensagem_dup = Mensagem.all_tenants.filter(
                    tenant=tenant, conversa=conversa,
                    conteudo=conteudo[:5000],
                    remetente_tipo=remetente_tipo,
                    data_envio__gte=limite,
                ).first()

            if mensagem_dup:
                mensagem = mensagem_dup
                mensagem_criada = False
            else:
                if remetente_tipo == 'contato':
                    remetente_nome = lead.nome_razaosocial
                elif remetente_tipo == 'agente':
                    remetente_nome = 'Atendente'
                else:
                    remetente_nome = 'Vero Bot'
                mensagem = Mensagem.objects.create(
                    tenant=tenant, conversa=conversa,
                    remetente_tipo=remetente_tipo, remetente_nome=remetente_nome,
                    tipo_conteudo=tipo_conteudo,
                    conteudo=conteudo[:5000],
                    arquivo_url=arquivo_url[:500],
                    arquivo_nome=arquivo_nome[:255],
                    identificador_externo=msg_id_ext,
                )
                mensagem_criada = True

                # Atualiza Conversa pra a lista do Inbox refletir a nova
                # mensagem: ordem (sobe pro topo via ultima_mensagem_em),
                # preview (texto que aparece no card) e badge de nao-lidas
                # quando a mensagem veio do cliente.
                from apps.inbox.services import preview_mensagem
                conversa.ultima_mensagem_em = mensagem.data_envio
                conversa.ultima_mensagem_preview = preview_mensagem(
                    mensagem.conteudo, mensagem.tipo_conteudo
                )
                campos_conv = ['ultima_mensagem_em', 'ultima_mensagem_preview']
                if remetente_tipo == 'contato':
                    conversa.mensagens_nao_lidas = (conversa.mensagens_nao_lidas or 0) + 1
                    campos_conv.append('mensagens_nao_lidas')
                conversa.save(update_fields=campos_conv)

    # Notifica Inbox aberto via WebSocket pra atualizacao em tempo real
    # (lista sobe automaticamente + push de nova mensagem na conversa).
    # Fora da transacao porque eh IO de rede.
    if mensagem_criada:
        try:
            from apps.inbox.services import _notificar_ws_nova_mensagem
            _notificar_ws_nova_mensagem(conversa, mensagem)
        except Exception as ws_err:
            logger.warning(f'Falha ao notificar WS sobre nova mensagem: {ws_err}')

    # Midia: baixa o arquivo decriptado do Uazapi e armazena. Fora da
    # transacao — IO de rede nao deve segurar lock de banco.
    if (mensagem_criada and msg_id_ext
            and tipo_conteudo in ('imagem', 'arquivo', 'audio', 'video')
            and not mensagem.arquivo):
        _baixar_midia_uazapi(tenant, mensagem, msg_id_ext)

    status_code = 201 if not ja_existia_conversa else 200
    resp = {
        'sucesso': True,
        'conversa_id': conversa.id,
        'conversa_numero': conversa.numero,
        'conversa_modo': conversa.modo_atendimento,
        'lead_id': lead.id,
        'oportunidade_id': oportunidade.id if oportunidade else None,
        'mensagem_id': mensagem.id,
        'mensagem_criada': mensagem_criada,
        'conversa_ja_existia': ja_existia_conversa,
    }
    if avisos:
        resp['avisos'] = avisos
    return JsonResponse(resp, status=status_code)


@csrf_exempt
def conversa_estado(request):
    """
    GET ?tenant_slug=<slug>&telefone=<numero>

    Retorna o estado atual da conversa pra o N8N decidir se segue com o bot
    ou se cala (operador humano assumiu).

    Resposta:
        {
            existe: bool,
            modo_atendimento: 'bot' | 'humano' | 'finalizado_bot' | null,
            agente_id: int | null,
            agente_nome: str | null,
            atualizado_em: iso8601 | null,
            bot_pode_atuar: bool,   # flag canonico — o Vero DEVE checar este,
                                    # nao o modo_atendimento isolado. True so
                                    # se modo='bot' E agente_id=None E status
                                    # nao for resolvida/arquivada.
        }
    """
    if not _autorizado(request):
        return JsonResponse({'sucesso': False, 'erro': 'Nao autorizado'}, status=401)

    tenant_slug = (request.GET.get('tenant_slug') or '').strip()
    telefone = (request.GET.get('telefone') or '').strip()
    if not tenant_slug or not telefone:
        return JsonResponse({'sucesso': False, 'erro': 'tenant_slug e telefone obrigatorios'}, status=400)

    tenant = Tenant.objects.filter(slug=tenant_slug, ativo=True).first()
    if not tenant:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant {tenant_slug!r} nao encontrado'}, status=404)

    telefone_norm = ''.join(c for c in telefone if c.isdigit())
    conversa = Conversa.all_tenants.filter(
        tenant=tenant, contato_telefone__contains=telefone_norm[-9:]
    ).exclude(status__in=['arquivada']).order_by('-id').first()

    if not conversa:
        return JsonResponse({
            'sucesso': True, 'existe': False,
            'modo_atendimento': None, 'agente_id': None, 'agente_nome': None,
            'bot_pode_atuar': True,
        }, status=200)

    agente_nome = None
    if conversa.agente_id:
        full = (conversa.agente.get_full_name() or '').strip()
        agente_nome = full or conversa.agente.username

    # Regra invariante: agente atribuido = bot calado, sem excecao.
    # Tambem cala se modo nao for 'bot' (humano/finalizado_bot) ou se
    # conversa ja foi resolvida.
    bot_pode_atuar = bool(
        conversa.modo_atendimento == 'bot'
        and conversa.agente_id is None
        and conversa.status not in ('resolvida', 'arquivada')
    )

    return JsonResponse({
        'sucesso': True,
        'existe': True,
        'conversa_id': conversa.id,
        'modo_atendimento': conversa.modo_atendimento,
        'status': conversa.status,
        'agente_id': conversa.agente_id,
        'agente_nome': agente_nome,
        'atualizado_em': conversa.ultima_mensagem_em.isoformat() if conversa.ultima_mensagem_em else None,
        'bot_pode_atuar': bot_pode_atuar,
    }, status=200)


@csrf_exempt
@require_POST
def transferir_fila(request):
    """Transfere a conversa de um telefone pra fila humana (regras de cidade
    primeiro, depois round-robin). Usado pelo follow-up ao esgotar os toques.

    Body JSON: {tenant_slug, telefone}. Auth: X-N8N-Webhook-Secret.
    """
    if not _autorizado(request):
        return JsonResponse({'sucesso': False, 'erro': 'Nao autorizado'}, status=401)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'sucesso': False, 'erro': 'JSON invalido'}, status=400)

    tenant_slug = (payload.get('tenant_slug') or '').strip()
    telefone = (payload.get('telefone') or '').strip()
    if not tenant_slug or not telefone:
        return JsonResponse({'sucesso': False, 'erro': 'tenant_slug e telefone obrigatorios'}, status=400)

    tenant = Tenant.objects.filter(slug=tenant_slug, ativo=True).first()
    if not tenant:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant {tenant_slug!r} nao encontrado'}, status=404)

    telefone_norm = ''.join(c for c in telefone if c.isdigit())
    conversa = Conversa.all_tenants.filter(
        tenant=tenant, contato_telefone__contains=telefone_norm[-9:]
    ).exclude(status__in=['arquivada', 'resolvida']).select_related('oportunidade').order_by('-id').first()
    if not conversa:
        return JsonResponse({'sucesso': False, 'erro': 'Conversa nao encontrada'}, status=404)

    if conversa.agente_id:
        return JsonResponse({'sucesso': True, 'ja_atribuida': True, 'agente_id': conversa.agente_id})

    if conversa.modo_atendimento != 'finalizado_bot':
        conversa.modo_atendimento = 'finalizado_bot'
        conversa.save(update_fields=['modo_atendimento'])

    _transferir_para_fila(conversa, tenant, conversa.oportunidade)
    conversa.refresh_from_db(fields=['agente', 'fila'])
    return JsonResponse({
        'sucesso': True, 'conversa_id': conversa.id,
        'agente_id': conversa.agente_id, 'fila_id': conversa.fila_id,
    })


@csrf_exempt
@require_POST
def registrar_imagem_lead(request):
    """
    Registra uma imagem/documento enviado pelo lead durante o fluxo do bot.

    Body JSON:
        tenant_slug:  str  - slug do tenant (obrigatorio)
        lead_id:      int  - id do lead (opcional se telefone for enviado)
        telefone:     str  - telefone do lead (fallback quando lead_id ausente)
        link_url:     str  - URL da imagem/documento (obrigatorio)
        descricao:    str? - descricao do documento (ex: 'RG frente', 'RG verso')

    Retorna:
        201 + {sucesso: true, imagem_id, lead_id} se criou
        400 se payload invalido
        401 se secret invalido
        404 se lead nao encontrado
    """
    if not _autorizado(request):
        return JsonResponse({'sucesso': False, 'erro': 'Nao autorizado'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'sucesso': False, 'erro': 'JSON invalido'}, status=400)

    tenant_slug = (payload.get('tenant_slug') or '').strip()
    lead_id = payload.get('lead_id')
    telefone = (payload.get('telefone') or '').strip()
    link_url = (payload.get('link_url') or '').strip()
    descricao = (payload.get('descricao') or '').strip()

    erros = []
    if not tenant_slug:
        erros.append('tenant_slug obrigatorio')
    if not lead_id and not telefone:
        erros.append('lead_id ou telefone obrigatorio')
    if not link_url:
        erros.append('link_url obrigatorio')
    if erros:
        return JsonResponse({'sucesso': False, 'erros': erros}, status=400)

    try:
        tenant = Tenant.objects.get(slug=tenant_slug)
    except Tenant.DoesNotExist:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant "{tenant_slug}" nao encontrado'}, status=404)

    lead = None
    if lead_id:
        try:
            lead = LeadProspecto.all_tenants.get(pk=lead_id, tenant=tenant)
        except LeadProspecto.DoesNotExist:
            lead = None

    if lead is None and telefone:
        tel_normalizado = ''.join(ch for ch in telefone if ch.isdigit())
        if tel_normalizado:
            lead = (
                LeadProspecto.all_tenants
                .filter(tenant=tenant, telefone__contains=tel_normalizado[-9:])
                .order_by('-id')
                .first()
            )

    if lead is None:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Lead nao encontrado (lead_id={lead_id}, telefone={telefone})',
        }, status=404)

    # Resolve link_url pra path interno autenticado antes de salvar — URLs
    # externas (whatsapp/uazapi) expiram em horas e quebram preview na UI.
    # Bug recorrente corrigido em 02/06/2026 (44 imagens broken em prod).
    # Estrategia: bate Mensagem.arquivo_url == link_url no mesmo lead; se
    # nao casar, deixa o link externo (a UI tem fallback na leitura via
    # utils.resolver_link_interno_imagem).
    url_final = link_url
    try:
        from apps.inbox.models import Mensagem as InboxMensagem
        msg = InboxMensagem.all_tenants.filter(
            conversa__lead=lead, arquivo_url=link_url
        ).exclude(arquivo='').first()
        if msg and msg.arquivo and msg.conversa_id:
            url_final = f'/inbox/api/conversas/{msg.conversa_id}/midia/{msg.pk}/'
        else:
            # Fallback: se nao bateu por arquivo_url, pega a Mensagem imagem
            # mais recente do lead que tenha arquivo salvo. N8N geralmente
            # registra a img logo depois do webhook inbox_mensagem baixar.
            msg_recente = InboxMensagem.all_tenants.filter(
                conversa__lead=lead,
                tipo_conteudo__in=('imagem', 'arquivo', 'documento'),
            ).exclude(arquivo='').order_by('-data_envio').first()
            if msg_recente and msg_recente.arquivo and msg_recente.conversa_id:
                url_final = f'/inbox/api/conversas/{msg_recente.conversa_id}/midia/{msg_recente.pk}/'
    except Exception as resolve_exc:
        logger.warning('[N8N lead/imagem] resolver link interno falhou: %s', resolve_exc)

    from apps.comercial.leads.models import ImagemLeadProspecto
    imagem = ImagemLeadProspecto.all_tenants.create(
        tenant=tenant,
        lead=lead,
        link_url=url_final,
        descricao=descricao or 'Documento enviado pelo bot',
    )

    logger.info('[N8N] Imagem registrada para lead %s (%s)', lead.id, descricao)
    return JsonResponse({'sucesso': True, 'imagem_id': imagem.pk, 'lead_id': lead.id}, status=201)


@csrf_exempt
@require_POST
def consultar_status_conversa(request):
    """Retorna o status da conversa ATIVA de um telefone, pra workflows N8N
    decidirem se devem enviar mensagem automatica (ex: follow-up so dispara
    se conversa ainda esta com bot/sem agente).

    Body JSON:
        tenant_slug (obrigatorio)
        telefone    (obrigatorio)

    Resposta:
        {
          'achou': True/False,
          'conversa_id': int,
          'modo_atendimento': 'bot'|'humano'|'finalizado_bot',
          'status': 'aberta'|'pendente'|'resolvida',
          'assumida': bool,
          'agente_id': int|None,
          'eh_humano_assumida': bool   # atalho: True se modo='humano' E assumida=True
        }
    """
    if not _autorizado(request):
        return JsonResponse({'sucesso': False, 'erro': 'Nao autorizado'}, status=401)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'sucesso': False, 'erro': 'JSON invalido'}, status=400)

    tenant_slug = (payload.get('tenant_slug') or '').strip()
    telefone = (payload.get('telefone') or '').strip()
    if not tenant_slug or not telefone:
        return JsonResponse({'sucesso': False, 'erro': 'tenant_slug e telefone obrigatorios'}, status=400)

    tenant = Tenant.objects.filter(slug=tenant_slug, ativo=True).first()
    if not tenant:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant {tenant_slug!r} nao encontrado'}, status=404)

    telefone_norm = ''.join(c for c in telefone if c.isdigit())
    if not telefone_norm:
        return JsonResponse({'sucesso': False, 'erro': 'telefone sem digitos'}, status=400)

    conversa = (
        Conversa.all_tenants
        .filter(tenant=tenant, contato_telefone__contains=telefone_norm[-9:])
        .order_by('-ultima_mensagem_em', '-data_abertura')
        .first()
    )
    if not conversa:
        return JsonResponse({
            'sucesso': True,
            'achou': False,
            'eh_humano_assumida': False,
        })
    eh_humano_assumida = bool(conversa.modo_atendimento == 'humano' and conversa.assumida)
    tem_agente_atribuido = bool(conversa.agente_id)
    # nao_disparar_bot: TRUE se humano de alguma forma ja entrou na conversa.
    # Cron de follow-up deve descartar se este flag for True (mais conservador
    # que so eh_humano_assumida — atribuicao automatica sem assumir tambem conta).
    nao_disparar_bot = bool(
        eh_humano_assumida
        or tem_agente_atribuido
        or conversa.modo_atendimento == 'humano'
    )
    return JsonResponse({
        'sucesso': True,
        'achou': True,
        'conversa_id': conversa.pk,
        'modo_atendimento': conversa.modo_atendimento,
        'status': conversa.status,
        'assumida': conversa.assumida,
        'agente_id': conversa.agente_id,
        'eh_humano_assumida': eh_humano_assumida,
        'tem_agente_atribuido': tem_agente_atribuido,
        'nao_disparar_bot': nao_disparar_bot,
    })
