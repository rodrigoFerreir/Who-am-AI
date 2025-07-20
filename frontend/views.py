from django.shortcuts import render

# Create your views here.
from django.shortcuts import render


def index_view(request):
    """
    Renderiza a página inicial do jogo.
    Esta view servirá como o ponto de entrada para o jogo principal.
    """
    return render(
        request, "frontend/game.html"
    )  # Agora renderiza game.html, que estenderá index.html


def login_page(request):
    """
    Renderiza a página de login.
    """
    return render(request, "frontend/login.html")


def signup_page(request):
    """
    Renderiza a página de registro.
    """
    return render(request, "frontend/signup.html")
