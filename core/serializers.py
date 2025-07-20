from rest_framework import serializers
from django.contrib.auth.models import User


class StartGameRequestSerializer(serializers.Serializer):
    """
    Serializador para receber tema e nível ao iniciar um novo jogo.
    """

    theme = serializers.CharField(
        max_length=50,
        help_text="O tema do jogo (ex: Filmes, História).",
    )
    level = serializers.CharField(
        max_length=50,
        help_text="O nível de dificuldade (ex: Fácil, Médio, Difícil, Aleatório).",
    )


class StartGameResponseSerializer(serializers.Serializer):
    """
    Serializador para retornar o session_id ao iniciar um novo jogo.
    """

    session_id = serializers.CharField(
        max_length=100,
        help_text="ID único da sessão de jogo.",
    )


class MessageSerializer(serializers.Serializer):
    """
    Serializador para receber uma mensagem do usuário e o session_id.
    """

    session_id = serializers.CharField(
        max_length=100,
        help_text="ID da sessão de jogo.",
    )
    message = serializers.CharField(
        max_length=1000,
        help_text="A mensagem a ser enviada para a IA.",
    )


# O AIResponseSerializer não será mais usado diretamente pela API REST para enviar a resposta da IA ao cliente,
# pois as respostas virão via WebSocket. No entanto, podemos mantê-lo para consistência ou se for necessário
# para outros fins de depuração/log.
class AIResponseSerializer(serializers.Serializer):
    """
    Serializador para retornar a resposta da IA. (Principalmente para uso interno ou depuração agora)
    """

    response = serializers.CharField(help_text="A resposta gerada pela IA.")
    character_name = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Nome do personagem, se adivinhado.",
    )


class UserRegisterSerializer(serializers.ModelSerializer):
    """
    Serializador para registro de usuário.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ("username", "email", "password", "password2")
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "As senhas não conferem."})
        return data

    def create(self, validated_data):
        validated_data.pop("password2")  # Remove password2 antes de criar o usuário
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializador para login de usuário.
    """

    username = serializers.CharField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )


class UserSerializer(serializers.ModelSerializer):
    """
    Serializador para retornar detalhes do usuário.
    """

    class Meta:
        model = User
        fields = (
            "id",
            "username",
        )
        read_only_fields = ("id", "username")
