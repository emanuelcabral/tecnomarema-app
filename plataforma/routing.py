from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<chat_type>\w+)/(?P<chat_id>[\w-]+)/$', consumers.ChatConsumer.as_asgi()),
    # Ej: ws/chat/general/ , ws/chat/comision/20735/ , ws/chat/privado/user123/
]