from django.urls import path
from .views import (
    UserRegisterAPIView,
    UserLoginAPIView,
    StartGameAPIView,
    AIMessageView,
    UserDetailAPIView,
)

urlpatterns = [
    path("me/", UserDetailAPIView.as_view(), name="api_user_details"),
    path("login/", UserLoginAPIView.as_view(), name="api_login"),
    path("register/", UserRegisterAPIView.as_view(), name="api_register"),
    path("new/game/", StartGameAPIView.as_view(), name="api_start_game"),
    path("message/", AIMessageView.as_view(), name="api_message"),
]
