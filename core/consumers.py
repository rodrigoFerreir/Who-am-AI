import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import GameSession


class GameConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket para lidar com a lógica do jogo de adivinhação.
    Agora, principalmente gerencia a conexão WebSocket e envia mensagens para o frontend.
    A lógica pesada é delegada às tarefas Celery.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_session = None

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"game_{self.session_id}"

        print(f"DEBUG Consumer: Conectando WebSocket para session_id={self.session_id}")

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        self.game_session = await self.get_game_session_sync(self.session_id)

        if not self.game_session:
            print(
                f"DEBUG Consumer: GameSession {self.session_id} NÃO encontrada. Fechando conexão."
            )
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "system_message",
                        "message": "Sessão de jogo não encontrada. Por favor, inicie um novo jogo via API /api/start_game/.",
                    }
                )
            )
            await self.close()
            return

        print(
            f"DEBUG Consumer: GameSession {self.game_session.session_id} encontrada. Conexão aceita."
        )
        await self.send(
            text_data=json.dumps(
                {
                    "type": "system_message",
                    "message": f"Conectado à sessão {self.session_id}.",
                }
            )
        )
        # Envia as tentativas restantes atuais ao conectar, caso a sessão já exista
        await self.send(
            text_data=json.dumps(
                {
                    "type": "update_attempts",
                    "attempts_left": self.game_session.attempts_left,
                }
            )
        )

    async def disconnect(self, close_code):
        print(
            f"DEBUG Consumer: Desconectando WebSocket para session_id={self.session_id}"
        )
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    async def chat_message(self, event):
        message = event["message"]
        sender = event["sender"]
        await self.send(
            text_data=json.dumps(
                {"type": "chat_message", "sender": sender, "message": message}
            )
        )

    async def game_over(self, event):
        message = event["message"]
        score = event["score"]
        character_name = event["character_name"]
        character_image_url = event.get(
            "character_image_url"
        )  # NOVO: Recebe a URL da imagem

        await self.send(
            text_data=json.dumps(
                {
                    "type": "game_over",
                    "message": message,
                    "score": score,
                    "character_name": character_name,
                    "character_image_url": character_image_url,  # NOVO: Envia a URL da imagem para o frontend
                }
            )
        )

    async def error(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

    async def update_attempts(self, event):
        attempts_left = event["attempts_left"]
        await self.send(
            text_data=json.dumps(
                {"type": "update_attempts", "attempts_left": attempts_left}
            )
        )

    @database_sync_to_async
    def get_game_session_sync(self, session_id):
        try:
            session = GameSession.objects.get(session_id=session_id)
            return session
        except GameSession.DoesNotExist:
            return None
