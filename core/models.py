from django.db import models
from django.contrib.auth.models import User


class GameSession(models.Model):
    """
    Representa uma sessão de jogo individual para um usuário.
    Armazena informações sobre o jogo, o personagem adivinhado e o resultado.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="game_sessions",
        null=True,
        blank=True,
    )
    session_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ID único para a sessão de jogo (UUID ou similar)",
    )
    theme = models.CharField(
        max_length=50, help_text="Tema do jogo (ex: Filmes, História)"
    )
    level = models.CharField(
        max_length=50,
        help_text="Nível de dificuldade (ex: Fácil, Médio, Difícil, Aleatório)",
    )
    character_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Nome do personagem que a IA escolheu",
    )
    is_completed = models.BooleanField(
        default=False,
        help_text="Indica se a sessão de jogo foi concluída",
    )
    score = models.IntegerField(
        default=0,
        help_text="Pontuação final do jogador nesta sessão",
    )
    start_time = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora de início da sessão",
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data e hora de término da sessão",
    )

    def __str__(self):
        return f"Sessão {self.session_id} - Usuário: {self.user.username} - Tema: {self.theme}"


class ChatMessage(models.Model):
    """
    Armazena cada mensagem trocada durante uma sessão de jogo.
    """

    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    sender = models.CharField(
        max_length=10,
        choices=[("user", "Usuário"), ("ai", "IA")],
        help_text="Remetente da mensagem (usuário ou IA)",
    )
    message_text = models.TextField(help_text="Conteúdo da mensagem")
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora da mensagem",
    )

    class Meta:
        ordering = ["timestamp"]  # Garante que as mensagens sejam ordenadas por tempo

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M')}] {self.sender.upper()}: {self.message_text[:50]}..."
