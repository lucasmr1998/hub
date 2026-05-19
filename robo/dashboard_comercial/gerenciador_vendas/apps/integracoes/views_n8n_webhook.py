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

        # Cria oportunidade se ainda nao existir uma aberta
        oportunidade = OportunidadeVenda.all_tenants.filter(
            tenant=tenant, lead=lead,
        ).exclude(
            estagio__is_final_ganho=True
        ).exclude(
            estagio__is_final_perdido=True
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

    status = 200 if ja_existia else 201
    return JsonResponse({
        'sucesso': True,
        'tenant': tenant.slug,
        'lead_id': lead.id,
        'oportunidade_id': oportunidade.id,
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

    tenant = Tenant.objects.filter(slug=tenant_slug, ativo=True).first()
    if not tenant:
        return JsonResponse({'sucesso': False, 'erro': f'Tenant {tenant_slug!r} nao encontrado'}, status=404)

    nome_contato = (payload.get('nome_contato') or '').strip() or 'Lead WhatsApp'
    telefone_norm = ''.join(c for c in telefone if c.isdigit())

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
                    setattr(lead, k_model, v)
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
                lead.save()

        # 3. Oportunidade — find or create
        oportunidade = OportunidadeVenda.all_tenants.filter(
            tenant=tenant, lead=lead
        ).exclude(estagio__is_final_ganho=True).exclude(estagio__is_final_perdido=True).first()
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
            ultimo_numero = Conversa.all_tenants.filter(tenant=tenant).count()
            conversa = Conversa.objects.create(
                tenant=tenant, numero=ultimo_numero + 1, canal=canal, lead=lead,
                contato_nome=lead.nome_razaosocial, contato_telefone=telefone,
                contato_email=lead.email or '',
                status='aberta', modo_atendimento='bot',
                oportunidade=oportunidade,
            )

        # Atualiza modo se vier
        modo = payload.get('modo_atendimento')
        if modo and modo in dict(Conversa.MODO_ATENDIMENTO_CHOICES):
            if conversa.modo_atendimento != modo:
                conversa.modo_atendimento = modo
                conversa.save(update_fields=['modo_atendimento'])

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

        # 5. Mensagem — sempre cria
        msg_id_ext = (payload.get('msg_id_externo') or '').strip()
        # Dedup se vier msg_id
        if msg_id_ext and Mensagem.all_tenants.filter(
            tenant=tenant, conversa=conversa, identificador_externo=msg_id_ext
        ).exists():
            mensagem = Mensagem.all_tenants.filter(
                tenant=tenant, conversa=conversa, identificador_externo=msg_id_ext
            ).first()
            mensagem_criada = False
        else:
            remetente_tipo = 'contato' if direcao == 'recebida' else 'bot'
            mensagem = Mensagem.objects.create(
                tenant=tenant, conversa=conversa,
                remetente_tipo=remetente_tipo, remetente_nome=lead.nome_razaosocial if remetente_tipo == 'contato' else 'Vero Bot',
                tipo_conteudo=(payload.get('tipo_conteudo') or 'texto'),
                conteudo=conteudo[:5000],
                arquivo_url=(payload.get('arquivo_url') or '')[:500],
                identificador_externo=msg_id_ext,
            )
            mensagem_criada = True

    status_code = 201 if not ja_existia_conversa else 200
    return JsonResponse({
        'sucesso': True,
        'conversa_id': conversa.id,
        'conversa_numero': conversa.numero,
        'conversa_modo': conversa.modo_atendimento,
        'lead_id': lead.id,
        'oportunidade_id': oportunidade.id if oportunidade else None,
        'mensagem_id': mensagem.id,
        'mensagem_criada': mensagem_criada,
        'conversa_ja_existia': ja_existia_conversa,
    }, status=status_code)
