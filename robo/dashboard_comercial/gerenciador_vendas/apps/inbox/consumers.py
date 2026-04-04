"""
WebSocket consumer para o Inbox.

Cada agente conectado entra no grupo do tenant.
Ao selecionar uma conversa, entra no grupo da conversa.
Recebe notificações de nova mensagem, typing, atualização de conversa.
"""

import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class InboxConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        # Obter tenant do perfil do usuário
        self.tenant_id = await self._get_tenant_id()
        if not self.tenant_id:
            await self.close()
            return

        self.tenant_group = f'inbox_tenant_{self.tenant_id}'
        self.user_group = f'inbox_user_{self.user.id}'
        self.conversa_group = None

        # Entrar nos grupos globais
        await self.channel_layer.group_add(self.tenant_group, self.channel_name)
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        await self.accept()
        logger.info("Inbox WS conectado: user=%s tenant=%s", self.user.id, self.tenant_id)

    async def disconnect(self, _close_code):
        # Auto-offline ao desconectar
        await self._set_status('offline')

        # Sair dos grupos
        if hasattr(self, 'tenant_group'):
            await self.channel_layer.group_discard(self.tenant_group, self.channel_name)
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        if self.conversa_group:
            await self.channel_layer.group_discard(self.conversa_group, self.channel_name)

    async def receive_json(self, content):
        """Recebe comandos do cliente."""
        action = content.get('action')

        if action == 'join_conversa':
            conversa_id = content.get('conversa_id')
            if conversa_id:
                # Sair do grupo anterior
                if self.conversa_group:
                    await self.channel_layer.group_discard(self.conversa_group, self.channel_name)
                # Entrar no novo grupo
                self.conversa_group = f'inbox_conversa_{conversa_id}'
                await self.channel_layer.group_add(self.conversa_group, self.channel_name)

        elif action == 'leave_conversa':
            if self.conversa_group:
                await self.channel_layer.group_discard(self.conversa_group, self.channel_name)
                self.conversa_group = None

        elif action == 'typing':
            # Broadcast typing indicator para a conversa
            conversa_id = content.get('conversa_id')
            if conversa_id:
                group = f'inbox_conversa_{conversa_id}'
                await self.channel_layer.group_send(group, {
                    'type': 'indicador_digitando',
                    'user_id': self.user.id,
                    'user_name': await self._get_user_name(),
                    'conversa_id': conversa_id,
                })

        elif action == 'set_status':
            novo_status = content.get('status')
            if novo_status in ('online', 'ausente', 'offline'):
                await self._set_status(novo_status)

        elif action == 'mark_read':
            conversa_id = content.get('conversa_id')
            if conversa_id:
                await self._mark_read(conversa_id)

    # ── Handlers de eventos (recebidos via channel_layer.group_send) ──

    async def nova_mensagem(self, event):
        """Notifica o cliente de nova mensagem."""
        await self.send_json({
            'type': 'nova_mensagem',
            'conversa_id': event.get('conversa_id'),
            'mensagem': event.get('mensagem'),
        })

    async def conversa_atualizada(self, event):
        """Notifica o cliente de mudança em conversa (status, agente, etc)."""
        await self.send_json({
            'type': 'conversa_atualizada',
            'conversa_id': event.get('conversa_id'),
            'changes': event.get('changes'),
        })

    async def indicador_digitando(self, event):
        """Notifica typing indicator (não envia de volta para quem está digitando)."""
        if event.get('user_id') != self.user.id:
            await self.send_json({
                'type': 'typing',
                'conversa_id': event.get('conversa_id'),
                'user_name': event.get('user_name'),
            })

    # ── Helpers async ──────────────────────────────────────────────────

    @database_sync_to_async
    def _get_tenant_id(self):
        try:
            perfil = self.user.perfilusuario
            return perfil.tenant_id if perfil.tenant_id else None
        except Exception:
            return None

    @database_sync_to_async
    def _get_user_name(self):
        return self.user.get_full_name() or self.user.username

    @database_sync_to_async
    def _set_status(self, status):
        from .models import PerfilAgenteInbox
        try:
            perfil, _ = PerfilAgenteInbox.all_tenants.get_or_create(
                user=self.user,
                defaults={'tenant_id': self.tenant_id}
            )
            perfil.status = status
            perfil.save(update_fields=['status', 'ultimo_status_em'])
        except Exception:
            pass

    @database_sync_to_async
    def _mark_read(self, conversa_id):
        from .models import Conversa
        try:
            conversa = Conversa.all_tenants.get(pk=conversa_id, tenant_id=self.tenant_id)
            from . import services
            services.marcar_mensagens_lidas(conversa)
        except Conversa.DoesNotExist:
            pass
