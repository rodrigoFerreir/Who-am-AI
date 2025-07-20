import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny  # Importe AllowAny
from rest_framework_simplejwt.tokens import RefreshToken  # Para gerar tokens JWT
from django.contrib.auth import authenticate  # Para autenticar usuários

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .serializers import (
    StartGameRequestSerializer,
    StartGameResponseSerializer,
    MessageSerializer,
    UserRegisterSerializer,
    UserLoginSerializer,
)

from .models import GameSession


class StartGameAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        serializer = StartGameRequestSerializer(data=request.data)
        if serializer.is_valid():
            theme = serializer.validated_data["theme"]
            level = serializer.validated_data["level"]
            session_id = str(uuid.uuid4())

            print(
                f"DEBUG API: Tentando criar GameSession com session_id={session_id}, user={request.user.username}"
            )

            try:
                game_session = GameSession.objects.create(
                    session_id=session_id, theme=theme, level=level, user=request.user
                )
                print(
                    f"DEBUG API: GameSession {game_session.session_id} criada com sucesso."
                )
            except Exception as e:
                print(f"DEBUG API: ERRO ao criar GameSession: {str(e)}")
                return Response(
                    {"error": f"Erro ao criar sessão de jogo: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"game_{session_id}",
                {
                    "type": "start_game_from_api",
                    "session_id": session_id,
                    "theme": theme,
                    "level": level,
                    "user_id": request.user.id,
                },
            )

            response_data = {"session_id": session_id}
            response_serializer = StartGameResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AIMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data["session_id"]
            player_message = serializer.validated_data["message"]

            print(
                f"DEBUG API: Recebida mensagem para session_id={session_id}, message='{player_message}'"
            )

            channel_layer = get_channel_layer()
            try:
                async_to_sync(channel_layer.group_send)(
                    f"game_{session_id}",
                    {
                        "type": "player_message_from_api",
                        "message": player_message,
                        "session_id": session_id,
                        "user_id": request.user.id,
                    },
                )
                print(
                    f"DEBUG API: Mensagem encaminhada para WebSocket group game_{session_id}"
                )
            except Exception as e:
                print(
                    f"DEBUG API: ERRO ao encaminhar mensagem para WebSocket: {str(e)}"
                )
                return Response(
                    {
                        "error": f"Erro ao encaminhar mensagem para o WebSocket: {str(e)}"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {"status": "Mensagem recebida e encaminhada."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRegisterAPIView(APIView):
    """
    API View para registro de novos usuários.
    """

    permission_classes = [
        AllowAny
    ]  # Permite que usuários não autenticados acessem esta view

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
                    {"access": str(refresh.access_token), "refresh": str(refresh)},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"detail": "Credenciais inválidas."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
