"""
Views DRF para CRM via N8N / agentes externos.

Endpoints:
- POST   /api/v1/n8n/crm/oportunidades/          → criar oportunidade
- PUT    /api/v1/n8n/crm/oportunidades/<pk>/      → atualizar (mover estagio, atribuir)
- GET    /api/v1/n8n/crm/oportunidades/buscar/    → buscar por lead_id ou telefone
- POST   /api/v1/n8n/crm/tarefas/                 → criar tarefa
- PUT    /api/v1/n8n/crm/tarefas/<pk>/            → atualizar tarefa
- GET    /api/v1/n8n/crm/pipelines/               → listar pipelines com estagios
- GET    /api/v1/n8n/crm/estagios/                → listar estagios
- POST   /api/v1/n8n/inbox/enviar/                → enviar mensagem como bot
"""

import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sistema.authentication import APITokenAuthentication
from apps.sistema.utils import registrar_acao

from apps.comercial.crm.models import (
    Pipeline, PipelineEstagio, OportunidadeVenda, TarefaCRM,
    HistoricoPipelineEstagio,
)
from apps.comercial.leads.models import LeadProspecto

from .serializers_crm_n8n import (
    PipelineOutputSerializer,
    PipelineEstagioOutputSerializer,
    OportunidadeInputSerializer,
    OportunidadeUpdateSerializer,
    OportunidadeOutputSerializer,
    TarefaInputSerializer,
    TarefaUpdateSerializer,
    TarefaOutputSerializer,
    InboxEnviarMensagemSerializer,
)

logger = logging.getLogger(__name__)


class N8NAPIMixin:
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]


# =====================================================================
# Pipelines (read-only)
# =====================================================================

class PipelineListAPIView(N8NAPIMixin, APIView):
    """GET: Listar pipelines com estagios."""

    def get(self, request):
        pipelines = Pipeline.objects.prefetch_related('estagios').all()
        return Response({
            'success': True,
            'pipelines': PipelineOutputSerializer(pipelines, many=True).data,
        })


class EstagioListAPIView(N8NAPIMixin, APIView):
    """GET: Listar estagios. Filtro: ?pipeline_slug=vendas-b2b"""

    def get(self, request):
        qs = PipelineEstagio.objects.select_related('pipeline').order_by('pipeline_id', 'ordem')
        pipeline_slug = request.query_params.get('pipeline_slug')
        if pipeline_slug:
            qs = qs.filter(pipeline__slug=pipeline_slug)
        return Response({
            'success': True,
            'estagios': PipelineEstagioOutputSerializer(qs, many=True).data,
        })


# =====================================================================
# Oportunidades
# =====================================================================

class OportunidadeAPIView(N8NAPIMixin, APIView):
    """POST: Criar oportunidade. PUT: Atualizar por pk."""

    def post(self, request):
        serializer = OportunidadeInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        lead_id = data['lead_id']

        try:
            lead = LeadProspecto.objects.get(pk=lead_id)
        except LeadProspecto.DoesNotExist:
            return Response({'success': False, 'error': 'Lead nao encontrado'}, status=status.HTTP_404_NOT_FOUND)

        # Verificar se ja existe
        if OportunidadeVenda.objects.filter(lead=lead).exists():
            oport = OportunidadeVenda.objects.get(lead=lead)
            return Response({
                'success': True,
                'created': False,
                'message': 'Oportunidade ja existe',
                'oportunidade': OportunidadeOutputSerializer(oport).data,
            })

        # Buscar pipeline
        pipeline = None
        if data.get('pipeline_slug'):
            pipeline = Pipeline.objects.filter(slug=data['pipeline_slug']).first()
        if not pipeline:
            pipeline = Pipeline.objects.filter(padrao=True).first() or Pipeline.objects.first()

        # Buscar estagio
        estagio = None
        if data.get('estagio_slug') and pipeline:
            estagio = PipelineEstagio.objects.filter(pipeline=pipeline, slug=data['estagio_slug']).first()
        if not estagio and pipeline:
            estagio = PipelineEstagio.objects.filter(pipeline=pipeline).order_by('ordem').first()
        if not estagio:
            estagio = PipelineEstagio.objects.order_by('ordem').first()

        if not estagio:
            return Response({'success': False, 'error': 'Nenhum estagio encontrado'}, status=status.HTTP_400_BAD_REQUEST)

        # Responsavel
        responsavel = None
        if data.get('responsavel_username'):
            responsavel = User.objects.filter(username=data['responsavel_username']).first()

        oport = OportunidadeVenda.objects.create(
            lead=lead,
            pipeline=pipeline,
            estagio=estagio,
            responsavel=responsavel,
            titulo=data.get('titulo') or lead.nome_razaosocial,
            valor_estimado=data.get('valor_estimado') or lead.valor,
            prioridade=data.get('prioridade', 'normal'),
            origem_crm='automatico',
        )

        registrar_acao('crm', 'criar', 'oportunidade', oport.pk,
                       f'Oportunidade criada via API: {oport.titulo}', request=request)

        return Response({
            'success': True,
            'created': True,
            'oportunidade': OportunidadeOutputSerializer(oport).data,
        }, status=status.HTTP_201_CREATED)

    def put(self, request, pk=None):
        if not pk:
            return Response({'success': False, 'error': 'pk obrigatorio'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            oport = OportunidadeVenda.objects.select_related('estagio', 'pipeline').get(pk=pk)
        except OportunidadeVenda.DoesNotExist:
            return Response({'success': False, 'error': 'Oportunidade nao encontrada'}, status=status.HTTP_404_NOT_FOUND)

        serializer = OportunidadeUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        campos_atualizados = []

        # Mover estagio
        if 'estagio_slug' in data and data['estagio_slug']:
            novo_estagio = PipelineEstagio.objects.filter(slug=data['estagio_slug']).first()
            if novo_estagio and novo_estagio != oport.estagio:
                estagio_anterior = oport.estagio
                horas = (timezone.now() - oport.data_entrada_estagio).total_seconds() / 3600
                HistoricoPipelineEstagio.objects.create(
                    oportunidade=oport,
                    estagio_anterior=estagio_anterior,
                    estagio_novo=novo_estagio,
                    motivo='Movido via API N8N',
                    tempo_no_estagio_horas=round(horas, 2),
                )
                oport.estagio = novo_estagio
                oport.data_entrada_estagio = timezone.now()
                campos_atualizados.extend(['estagio', 'data_entrada_estagio'])

        # Atribuir responsavel
        if 'responsavel_username' in data and data['responsavel_username']:
            user = User.objects.filter(username=data['responsavel_username']).first()
            if user:
                oport.responsavel = user
                campos_atualizados.append('responsavel')

        # Outros campos
        for campo in ['titulo', 'valor_estimado', 'prioridade', 'motivo_perda']:
            if campo in data and data[campo]:
                setattr(oport, campo, data[campo])
                campos_atualizados.append(campo)

        # Dados customizados (merge com existentes)
        # Aceita tanto {"dados_custom": {"campo": "valor"}} quanto {"dados_custom.campo": "valor"}
        custom = oport.dados_custom or {}
        if 'dados_custom' in data and data['dados_custom']:
            custom.update(data['dados_custom'])
        # Campos flat com prefixo "dados_custom." (ex: N8N "Using Fields Below")
        for key, val in request.data.items():
            if key.startswith('dados_custom.') and val:
                campo_custom = key.replace('dados_custom.', '', 1)
                custom[campo_custom] = val
        if custom != (oport.dados_custom or {}):
            oport.dados_custom = custom
            campos_atualizados.append('dados_custom')

        if campos_atualizados:
            oport.save(update_fields=campos_atualizados + ['data_atualizacao'])

        registrar_acao('crm', 'editar', 'oportunidade', oport.pk,
                       f'Oportunidade atualizada via API: {", ".join(campos_atualizados)}', request=request)

        return Response({
            'success': True,
            'oportunidade': OportunidadeOutputSerializer(oport).data,
        })


class OportunidadeBuscaAPIView(N8NAPIMixin, APIView):
    """GET: Buscar oportunidade. ?lead_id=123 ou ?telefone=5511999"""

    def get(self, request):
        lead_id = request.query_params.get('lead_id')
        telefone = request.query_params.get('telefone')

        if lead_id:
            oport = OportunidadeVenda.objects.filter(lead_id=lead_id, ativo=True).first()
        elif telefone:
            oport = OportunidadeVenda.objects.filter(lead__telefone__icontains=telefone, ativo=True).first()
        else:
            return Response({'success': False, 'error': 'Informe lead_id ou telefone'}, status=status.HTTP_400_BAD_REQUEST)

        if not oport:
            return Response({'success': True, 'encontrado': False, 'oportunidade': None})

        return Response({
            'success': True,
            'encontrado': True,
            'oportunidade': OportunidadeOutputSerializer(oport).data,
        })


# =====================================================================
# Tarefas
# =====================================================================

class TarefaAPIView(N8NAPIMixin, APIView):
    """POST: Criar tarefa. PUT: Atualizar por pk."""

    def post(self, request):
        serializer = TarefaInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Lead
        lead = None
        if data.get('lead_id'):
            lead = LeadProspecto.objects.filter(pk=data['lead_id']).first()

        # Oportunidade
        oportunidade = None
        if data.get('oportunidade_id'):
            oportunidade = OportunidadeVenda.objects.filter(pk=data['oportunidade_id']).first()
        elif lead:
            oportunidade = OportunidadeVenda.objects.filter(lead=lead).first()

        # Responsavel
        responsavel = None
        if data.get('responsavel_username'):
            responsavel = User.objects.filter(username=data['responsavel_username']).first()
        if not responsavel:
            responsavel = User.objects.filter(is_staff=True, is_active=True).first()

        if not responsavel:
            return Response({'success': False, 'error': 'Nenhum responsavel disponivel'}, status=status.HTTP_400_BAD_REQUEST)

        tarefa = TarefaCRM.objects.create(
            lead=lead,
            oportunidade=oportunidade,
            responsavel=responsavel,
            titulo=data['titulo'],
            descricao=data.get('descricao', ''),
            tipo=data.get('tipo', 'followup'),
            prioridade=data.get('prioridade', 'normal'),
            data_vencimento=data.get('data_vencimento') or (timezone.now() + timedelta(days=1)),
        )

        registrar_acao('crm', 'criar', 'tarefa', tarefa.pk,
                       f'Tarefa criada via API: {tarefa.titulo}', request=request)

        return Response({
            'success': True,
            'tarefa': TarefaOutputSerializer(tarefa).data,
        }, status=status.HTTP_201_CREATED)

    def put(self, request, pk=None):
        if not pk:
            return Response({'success': False, 'error': 'pk obrigatorio'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tarefa = TarefaCRM.objects.get(pk=pk)
        except TarefaCRM.DoesNotExist:
            return Response({'success': False, 'error': 'Tarefa nao encontrada'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TarefaUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        campos = []

        if 'status' in data:
            tarefa.status = data['status']
            campos.append('status')
            if data['status'] == 'concluida':
                tarefa.data_conclusao = timezone.now()
                campos.append('data_conclusao')

        if 'resultado' in data:
            tarefa.resultado = data['resultado']
            campos.append('resultado')

        if 'prioridade' in data:
            tarefa.prioridade = data['prioridade']
            campos.append('prioridade')

        if 'responsavel_username' in data:
            user = User.objects.filter(username=data['responsavel_username']).first()
            if user:
                tarefa.responsavel = user
                campos.append('responsavel')

        if campos:
            tarefa.save(update_fields=campos + ['data_atualizacao'])

        registrar_acao('crm', 'editar', 'tarefa', tarefa.pk,
                       f'Tarefa atualizada via API: {", ".join(campos)}', request=request)

        return Response({
            'success': True,
            'tarefa': TarefaOutputSerializer(tarefa).data,
        })


# =====================================================================
# Inbox — Enviar mensagem como bot
# =====================================================================

class InboxEnviarAPIView(N8NAPIMixin, APIView):
    """POST: Enviar mensagem no inbox como bot."""

    def post(self, request):
        serializer = InboxEnviarMensagemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        telefone = data['telefone']
        conteudo = data['conteudo']
        remetente_nome = data.get('remetente_nome', 'Bot')

        from apps.inbox.models import Conversa, Mensagem

        # Buscar conversa ativa pelo telefone
        conversa = Conversa.objects.filter(
            contato_telefone__icontains=telefone,
            status__in=['aberta', 'pendente'],
        ).order_by('-ultima_mensagem_em').first()

        if not conversa:
            return Response({
                'success': False,
                'error': f'Nenhuma conversa ativa para o telefone {telefone}',
            }, status=status.HTTP_404_NOT_FOUND)

        # Criar mensagem como bot
        msg = Mensagem(
            tenant=conversa.tenant,
            conversa=conversa,
            remetente_tipo='bot',
            remetente_nome=remetente_nome,
            tipo_conteudo='texto',
            conteudo=conteudo,
        )
        msg._skip_automacao = True
        msg.save()

        # Atualizar conversa
        conversa.ultima_mensagem_em = msg.data_envio
        conversa.ultima_mensagem_preview = conteudo[:255]
        conversa.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])

        # Enviar via webhook (WhatsApp)
        from apps.inbox.services import _enviar_webhook_async
        _enviar_webhook_async(conversa, msg)

        registrar_acao('inbox', 'enviar_bot', 'conversa', conversa.pk,
                       f'Mensagem bot enviada via API para {telefone}', request=request)

        return Response({
            'success': True,
            'mensagem_id': msg.pk,
            'conversa_id': conversa.pk,
        }, status=status.HTTP_201_CREATED)
