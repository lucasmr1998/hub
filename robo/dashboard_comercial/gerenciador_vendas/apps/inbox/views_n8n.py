"""
Endpoints de webhook para receber/enviar mensagens via N8N ou qualquer sistema externo.

Autenticação: APITokenAuthentication (Bearer token via header).
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sistema.authentication import APITokenAuthentication

from .serializers import (
    MensagemRecebidaSerializer,
    StatusMensagemSerializer,
    ConversaOutputSerializer,
    MensagemOutputSerializer,
)
from . import services

logger = logging.getLogger(__name__)


class N8NAPIMixin:
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]


class InboxMensagemRecebidaAPIView(N8NAPIMixin, APIView):
    """
    POST: Recebe mensagem de um contato (WhatsApp, widget, etc).

    Payload:
    {
        "telefone": "5511999998888",
        "nome": "João Silva",
        "conteudo": "Olá, preciso de ajuda",
        "tipo_conteudo": "texto",
        "canal_tipo": "whatsapp",
        "identificador_externo": "wamid.xxx",
        "arquivo_url": "",
        "metadata": {},
        "tenant_slug": "megalink"
    }
    """

    def post(self, request):
        serializer = MensagemRecebidaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        # Resolver tenant
        tenant = services.resolver_tenant(data.get('tenant_slug'))
        if not tenant:
            return Response(
                {'success': False, 'error': 'Tenant não encontrado'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversa, mensagem, nova = services.receber_mensagem(
            telefone=data['telefone'],
            nome=data.get('nome', ''),
            conteudo=data.get('conteudo', ''),
            tenant=tenant,
            tipo_conteudo=data.get('tipo_conteudo', 'texto'),
            identificador_externo=data.get('identificador_externo', ''),
            metadata=data.get('metadata'),
            canal_tipo=data.get('canal_tipo', 'whatsapp'),
            arquivo_url=data.get('arquivo_url', ''),
            arquivo_nome=data.get('arquivo_nome', ''),
        )

        return Response({
            'success': True,
            'nova_conversa': nova,
            'conversa': ConversaOutputSerializer(conversa).data,
            'mensagem': MensagemOutputSerializer(mensagem).data,
        }, status=status.HTTP_201_CREATED)


class InboxStatusMensagemAPIView(N8NAPIMixin, APIView):
    """
    POST: Callback de status de mensagem (entregue, lida, erro).

    Payload:
    {
        "identificador_externo": "wamid.xxx",
        "status": "entregue",
        "tenant_slug": "megalink"
    }
    """

    def post(self, request):
        serializer = StatusMensagemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        tenant = services.resolver_tenant(data.get('tenant_slug'))

        mensagem = services.atualizar_status_entrega(
            identificador_externo=data['identificador_externo'],
            status_entrega=data['status'],
            tenant=tenant,
        )

        if not mensagem:
            return Response(
                {'success': False, 'error': 'Mensagem não encontrada'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'success': True,
            'mensagem': MensagemOutputSerializer(mensagem).data,
        })
