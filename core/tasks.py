from app.celery import app as celery_app
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.utils import timezone
from .models import GameSession, ChatMessage
from .agent import GuessingGameAgent

# Instância global do agente de IA para as tarefas Celery.
# É importante que o agente seja criado aqui para ser reutilizado pelas tarefas.
global_game_agent = GuessingGameAgent()


# Funções auxiliares síncronas para interagir com o ORM do Django
def _get_game_session_sync(session_id):
    """Busca uma sessão de jogo no banco de dados (síncrona)."""
    try:
        session = GameSession.objects.get(session_id=session_id)
        print(
            f"DEBUG Celery Task DB: Sessão {session_id} encontrada no banco de dados."
        )
        return session
    except GameSession.DoesNotExist:
        print(
            f"DEBUG Celery Task DB: Sessão {session_id} NÃO encontrada no banco de dados."
        )
        return None


def _save_message_sync(session, sender, message_text):
    """Salva uma mensagem no banco de dados (síncrona)."""
    ChatMessage.objects.create(
        session=session, sender=sender, message_text=message_text
    )
    print(
        f"DEBUG Celery Task DB: Mensagem de '{sender}' salva para sessão {session.session_id}."
    )


def _calculate_score_sync(session):
    """Calcula a pontuação da sessão de jogo (síncrona)."""
    user_messages_count = session.chat_messages.filter(sender="user").count()
    base_score = 100
    deduction_per_message = 5
    score = max(0, base_score - (user_messages_count * deduction_per_message))
    print(
        f"DEBUG Celery Task: Pontuação calculada para sessão {session.session_id}: {score}"
    )
    return score


@celery_app.task(name="process_start_game_task")
def process_start_game_task(session_id, theme, level, user_id):
    """
    Tarefa Celery para iniciar um novo jogo.
    Define o número de tentativas e envia a primeira dica da IA.
    """
    print(
        f"DEBUG Celery Task: Iniciando tarefa process_start_game_task para sessão {session_id}"
    )
    game_session = _get_game_session_sync(session_id)

    if not game_session:
        print(
            f"ERRO Celery Task: Sessão {session_id} não encontrada para iniciar jogo."
        )
        return

    if user_id and not game_session.user_id:
        try:
            user = User.objects.get(id=user_id)
            game_session.user = user
            game_session.save()
            print(
                f"DEBUG Celery Task DB: Usuário {user.username} associado à sessão {session_id}."
            )
        except User.DoesNotExist:
            print(
                f"AVISO Celery Task DB: Usuário com ID {user_id} não encontrado para associar à sessão {session_id}."
            )
        except Exception as e:
            print(
                f"ERRO Celery Task DB: Erro ao associar usuário à sessão {session_id}: {e}"
            )

    try:
        # Define o número de tentativas com base no nível
        attempts_map = {"Facil": 10, "Medio": 8, "Dificil": 5}
        game_session.attempts_left = attempts_map.get(
            level, 7
        )  # Padrão para 7 se "Aleatorio" ou não mapeado
        game_session.theme = theme
        game_session.level = level
        game_session.save()  # Salva as tentativas iniciais e outros dados

        # Inicia o jogo com o agente de IA (que internamente define o character_name e gera a primeira dica)
        initial_hint = global_game_agent.start_new_game(theme, level)
        game_session.character_name = (
            global_game_agent.character_name
        )  # Atualiza o nome do personagem após a IA escolher
        game_session.save()  # Salva o nome do personagem

        _save_message_sync(game_session, "ai", initial_hint)

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_{session_id}",
            {"type": "chat_message", "sender": "ai", "message": initial_hint},
        )
        # Envia a contagem de tentativas para o frontend
        async_to_sync(channel_layer.group_send)(
            f"game_{session_id}",
            {"type": "update_attempts", "attempts_left": game_session.attempts_left},
        )
        print(
            f"DEBUG Celery Task: Jogo iniciado e dica inicial enviada para sessão {session_id}."
        )
    except Exception as e:
        print(
            f"ERRO Celery Task: Erro ao processar início do jogo para sessão {session_id}: {str(e)}"
        )
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_{session_id}",
            {"type": "error", "message": f"Erro ao iniciar o jogo: {str(e)}"},
        )


@celery_app.task(name="process_player_message_task")
def process_player_message_task(session_id, player_message, user_id_from_api):
    """
    Tarefa Celery para processar a mensagem de um jogador.
    Classifica a entrada, interage com a IA, gerencia tentativas e envia a resposta.
    """
    print(
        f"DEBUG Celery Task: Iniciando tarefa process_player_message_task para sessão {session_id}, mensagem: '{player_message[:50]}'"
    )
    game_session = _get_game_session_sync(session_id)

    if not game_session:
        print(
            f"ERRO Celery Task: Sessão {session_id} não encontrada para processar mensagem do jogador."
        )
        return

    if (
        game_session.user
        and user_id_from_api
        and game_session.user.id != user_id_from_api
    ):
        print(
            f"AVISO Celery Task: Usuário {user_id_from_api} tentando enviar mensagem para sessão {session_id} de outro usuário {game_session.user.id}."
        )
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_{session_id}",
            {
                "type": "error",
                "message": "Você não tem permissão para enviar mensagens para esta sessão.",
            },
        )
        return

    _save_message_sync(game_session, "user", player_message)
    print(f"DEBUG Celery Task: Mensagem do usuário salva para sessão {session_id}.")

    channel_layer = get_channel_layer()
    # Envia a mensagem do jogador para o grupo de chat (para que o cliente veja que foi enviada)
    async_to_sync(channel_layer.group_send)(
        f"game_{session_id}",
        {"type": "chat_message", "sender": "user", "message": player_message},
    )

    try:
        # Classifica a entrada do usuário
        input_type = global_game_agent.classify_user_input(player_message)
        print(f"DEBUG Celery Task: Entrada do usuário classificada como: {input_type}")

        # Decrementa tentativas apenas se for uma tentativa de adivinhação
        if input_type == "guess":
            game_session.attempts_left -= 1
            game_session.save()  # Salva a nova contagem de tentativas
            print(
                f"DEBUG Celery Task: Tentativas restantes para sessão {session_id}: {game_session.attempts_left}"
            )
            # Envia a contagem de tentativas atualizada para o frontend
            async_to_sync(channel_layer.group_send)(
                f"game_{session_id}",
                {
                    "type": "update_attempts",
                    "attempts_left": game_session.attempts_left,
                },
            )

        ai_response = global_game_agent.process_player_input(
            player_message, game_session.attempts_left
        )
        print(
            f"DEBUG Celery Task: Resposta da IA para sessão {session_id}: {ai_response[:50]}..."
        )

        _save_message_sync(game_session, "ai", ai_response)

        async_to_sync(channel_layer.group_send)(
            f"game_{session_id}",
            {"type": "chat_message", "sender": "ai", "message": ai_response},
        )

        # Lógica de fim de jogo
        if "Sim, você acertou!" in ai_response:
            game_session.is_completed = True
            game_session.character_name = global_game_agent.character_name
            game_session.score = _calculate_score_sync(game_session)
            game_session.end_time = timezone.now()
            game_session.save()
            return

        if (
            game_session.attempts_left <= 0 and input_type == "guess"
        ):  # Fim de jogo por tentativas esgotadas
            # Garante que o jogo só termine por tentativas esgotadas se a última foi um guess
            game_session.is_completed = True
            game_session.character_name = global_game_agent.character_name
            game_session.score = _calculate_score_sync(
                game_session
            )  # Pontuação final mesmo sem acertar
            game_session.end_time = timezone.now()
            game_session.save()

            async_to_sync(channel_layer.group_send)(
                f"game_{session_id}",
                {
                    "type": "game_over",
                    "message": f"Suas tentativas acabaram! O personagem era: {game_session.character_name}.",
                    "score": game_session.score,
                    "character_name": game_session.character_name,
                },
            )

    except Exception as e:
        print(
            f"ERRO Celery Task: Erro ao processar mensagem do jogador para sessão {session_id}: {str(e)}"
        )
        async_to_sync(channel_layer.group_send)(
            f"game_{session_id}",
            {
                "type": "error",
                "message": f"Erro ao processar sua mensagem com a IA: {str(e)}",
            },
        )
