import json
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken  # Importar RefreshToken
from django.contrib.auth import authenticate  # Importar authenticate

# Importa as tarefas Celery
from .tasks import process_start_game_task, process_player_message_task

from .serializers import (
    StartGameRequestSerializer,
    StartGameResponseSerializer,
    MessageSerializer,
    UserRegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
)
from .models import GameSession  # Apenas para criar a sessão, o resto é na task


class StartGameAPIView(APIView):
    """
    API View para iniciar um novo jogo.
    Recebe tema e nível, cria uma sessão e enfileira uma tarefa Celery.
    Retorna o session_id.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        serializer = StartGameRequestSerializer(data=request.data)
        if serializer.is_valid():
            theme = serializer.validated_data["theme"]
            level = serializer.validated_data["level"]
            session_id = str(uuid.uuid4())  # Gera um ID de sessão único

            print(
                f"DEBUG API: Recebida requisição para iniciar jogo. session_id={session_id}, user={request.user.username}"
            )

            try:
                # Cria a sessão de jogo no banco de dados.
                # A associação do usuário é feita aqui, pois a sessão precisa existir para o WebSocket.
                game_session = GameSession.objects.create(
                    session_id=session_id,
                    theme=theme,
                    level=level,
                    user=request.user,  # Associe o usuário logado
                )
                print(
                    f"DEBUG API: GameSession {game_session.session_id} criada no banco de dados."
                )
            except Exception as e:
                print(f"DEBUG API: ERRO ao criar GameSession: {str(e)}")
                return Response(
                    {"error": f"Erro ao criar sessão de jogo: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Enfileira a tarefa Celery para processar o início do jogo e obter a primeira dica.
            process_start_game_task.delay(session_id, theme, level, request.user.id)
            print(
                f"DEBUG API: Tarefa 'process_start_game_task' enfileirada para sessão {session_id}."
            )

            response_data = {"session_id": session_id}
            response_serializer = StartGameResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AIMessageView(APIView):
    """
    API View para enviar uma mensagem do usuário para a sessão de jogo.
    Enfileira uma tarefa Celery para processar a mensagem.
    A resposta da IA será enviada de volta via WebSocket.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data["session_id"]
            player_message = serializer.validated_data["message"]
            user_id = request.user.id  # Pega o ID do usuário autenticado

            print(
                f"DEBUG API: Recebida mensagem para sessão {session_id}, mensagem='{player_message[:50]}'"
            )

            # Enfileira a tarefa Celery para processar a mensagem do jogador.
            process_player_message_task.delay(session_id, player_message, user_id)
            print(
                f"DEBUG API: Tarefa 'process_player_message_task' enfileirada para sessão {session_id}."
            )

            # A resposta HTTP para esta requisição é apenas um ACK.
            # A resposta real da IA virá via WebSocket.
            return Response(
                {"status": "Mensagem recebida e encaminhada."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRegisterAPIView(APIView):
    """
    API View para registro de novos usuários.
    """

    permission_classes = [AllowAny]

    def post(self, request, format=None):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            if user:
                return Response(
                    {"message": "Usuário registrado com sucesso."},
                    status=status.HTTP_201_CREATED,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginAPIView(APIView):
    """
    API View para login de usuários, retornando tokens JWT.
    """

    permission_classes = [
        AllowAny
    ]  # Permite que usuários não autenticados acessem esta view

    def post(self, request, format=None):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data["username"]
            password = serializer.validated_data["password"]

            user = authenticate(request, username=username, password=password)

            if user is not None:
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                        "username": user.username,  # Incluir o nome de usuário na resposta
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"detail": "Credenciais inválidas."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetailAPIView(APIView):
    """
    API View para retornar os detalhes do usuário autenticado.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
