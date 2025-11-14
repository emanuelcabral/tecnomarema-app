import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Mensaje, Chat, LecturaMensaje, PerfilUsuario

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_type = self.scope['url_route']['kwargs']['chat_type']  # general, comision, privado
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']  # ID o 'general'
        self.room_group_name = f'chat_{self.chat_type}_{self.chat_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # En connect, envía estado inicial (e.g., unread count)
        unread = await self.get_unread_count()
        await self.send(text_data=json.dumps({'type': 'unread_update', 'unread': unread}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['type'] == 'message':
            # Guarda mensaje (usa tu lógica)
            mensaje = await self.save_message(data['texto'])
            # Broadcast a grupo (todos en el chat ven el mensaje)
            await self.channel_layer.group_send(self.room_group_name, {
                'type': 'chat_message',
                'message': {'id': mensaje.id, 'texto': mensaje.texto, 'remitente': mensaje.remitente.nombre_usuario},
            })
            # Actualiza unread para otros
            await self.update_unread_for_others()

        elif data['type'] == 'typing':
            await self.channel_layer.group_send(self.room_group_name, {'type': 'typing', 'user': self.scope['user'].nombre_usuario})

        elif data['type'] == 'read':
            await self.mark_as_read()  # Actualiza LecturaMensaje
            await self.channel_layer.group_send(self.room_group_name, {'type': 'read_update'})

    # Handlers para broadcast
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    async def typing(self, event):
        await self.send(text_data=json.dumps({'type': 'typing', 'user': event['user']}))

    async def read_update(self, event):
        unread = await self.get_unread_count()
        await self.send(text_data=json.dumps({'type': 'unread_update', 'unread': unread}))

    # Métodos async (usa @database_sync_to_async para DB)
    @database_sync_to_async
    def save_message(self, texto):
        # Tu lógica para crear Mensaje y retornar
        pass

    @database_sync_to_async
    def get_unread_count(self):
        # Calcula unread como en tu view
        pass

    @database_sync_to_async
    def update_unread_for_others(self):
        # Notifica o actualiza
        pass

    @database_sync_to_async
    def mark_as_read(self):
        # Actualiza LecturaMensaje.ultimo_mensaje_leido al último mensaje
        pass