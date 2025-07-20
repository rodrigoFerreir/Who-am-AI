from django.urls import re_path
from .consumers import GameConsumer

websocket_urlpatterns = [
    # Define uma URL WebSocket para o chat do jogo.
    # O <str:session_id> permite que cada sessão de jogo tenha um chat isolado.
    re_path(r"ws/game/(?P<session_id>[^/]+)/$", GameConsumer.as_asgi()),
]
