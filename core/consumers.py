import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone  # Importe timezone
from .models import GameSession, ChatMessage
from .agent import GuessingGameAgent


class GameConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket para lidar com a lógica do jogo de adivinhação.
    Gerencia a comunicação em tempo real entre o cliente e o agente de IA.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_agent = GuessingGameAgent()
        self.game_session = None

    async def connect(self):
        print("Conectando ao WebSocket...")
        print(self.scope)
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"game_{self.session_id}"

        print(f"Conectando ao grupo de jogo: {self.room_group_name}")

        # Adiciona o canal ao grupo de chat
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()  # Aceita a conexão WebSocket primeiro

        # Tenta buscar a sessão de jogo. A sessão deve ser criada pela API de start_game.
        self.game_session = await self.get_game_session(self.session_id)

        if not self.game_session:
            # Se a sessão não for encontrada, envia uma mensagem de erro e fecha a conexão.
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "system_message",
                        "message": "Sessão de jogo não encontrada. Por favor, inicie um novo jogo via API /api/start_game/.",
                    }
                )
            )
            await self.close()  # Fechar explicitamente a conexão se a sessão não for válida.
            return  # Sai do método connect.

        # Envia uma mensagem de confirmação de conexão
        await self.send(
            text_data=json.dumps(
                {
                    "type": "system_message",
                    "message": f"Conectado à sessão {self.session_id}.",
                }
            )
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # Todas as interações agora serão via handlers de grupo.

    async def start_game_from_api(self, event):
        session_id = event["session_id"]
        theme = event["theme"]
        level = event["level"]
        user_id = event.get("user_id")  # ID do usuário autenticado pela API

        self.game_session = await self.get_game_session(session_id)
        if not self.game_session:
            print(f"Erro: Sessão {session_id} não encontrada para iniciar jogo.")
            return

        # Se a sessão foi criada sem usuário (ex: antes do login), associe-a agora.
        if user_id and not self.game_session.user_id:
            try:
                user = await database_sync_to_async(User.objects.get)(id=user_id)
                self.game_session.user = user
                await database_sync_to_async(self.game_session.save)()
            except User.DoesNotExist:
                print(
                    f"Aviso: Usuário com ID {user_id} não encontrado para associar à sessão {session_id}."
                )

        try:
            initial_hint = await database_sync_to_async(self.game_agent.start_new_game)(
                theme, level
            )
            self.game_session.theme = theme
            self.game_session.level = level
            await database_sync_to_async(self.game_session.save)()

            await self.save_message(self.game_session, "ai", initial_hint)

            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "sender": "ai", "message": initial_hint},
            )
        except Exception as e:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "error", "message": f"Erro ao iniciar o jogo: {str(e)}"},
            )

    async def player_message_from_api(self, event):
        session_id = event["session_id"]
        player_message = event["message"]
        user_id_from_api = event.get(
            "user_id"
        )  # ID do usuário que enviou a mensagem via API

        self.game_session = await self.get_game_session(session_id)
        if not self.game_session:
            print(
                f"Erro: Sessão {session_id} não encontrada para processar mensagem do jogador."
            )
            return

        # Opcional: Verificar se o user_id da API corresponde ao user_id da sessão, se a sessão tiver um usuário.
        # Isso adiciona uma camada de segurança para garantir que apenas o proprietário da sessão envie mensagens.
        if (
            self.game_session.user
            and user_id_from_api
            and self.game_session.user.id != user_id_from_api
        ):
            print(
                f"Aviso de segurança: Usuário {user_id_from_api} tentando enviar mensagem para sessão {session_id} de outro usuário {self.game_session.user.id}."
            )
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "error",
                    "message": "Você não tem permissão para enviar mensagens para esta sessão.",
                },
            )
            return

        await self.save_message(self.game_session, "user", player_message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "sender": "user", "message": player_message},
        )

        try:
            ai_response = await database_sync_to_async(
                self.game_agent.process_player_input
            )(player_message)

            await self.save_message(self.game_session, "ai", ai_response)

            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "sender": "ai", "message": ai_response},
            )

            if "Sim, você acertou!" in ai_response:
                self.game_session.is_completed = True
                self.game_session.character_name = self.game_agent.character_name
                self.game_session.score = await self.calculate_score()
                self.game_session.end_time = timezone.now()
                await database_sync_to_async(self.game_session.save)()

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "game_over",
                        "message": f"Parabéns! Você adivinhou o personagem: {self.game_session.character_name}!",
                        "score": self.game_session.score,
                        "character_name": self.game_session.character_name,
                    },
                )
        except Exception as e:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "error",
                    "message": f"Erro ao processar sua mensagem com a IA: {str(e)}",
                },
            )

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

        await self.send(
            text_data=json.dumps(
                {
                    "type": "game_over",
                    "message": message,
                    "score": score,
                    "character_name": character_name,
                }
            )
        )

    async def error(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

    @database_sync_to_async
    def get_game_session(self, session_id):
        try:
            return GameSession.objects.get(session_id=session_id)
        except GameSession.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, session, sender, message_text):
        ChatMessage.objects.create(
            session=session, sender=sender, message_text=message_text
        )

    @database_sync_to_async
    def calculate_score(self):
        user_messages_count = self.game_session.chat_messages.filter(
            sender="user"
        ).count()
        base_score = 100
        deduction_per_message = 5
        score = max(0, base_score - (user_messages_count * deduction_per_message))
        return score
