from django.urls import path
from . import views

urlpatterns = [
    path("", views.index_view, name="home"),
    path("accounts/login/", views.login_page, name="login"),
    path("accounts/signup/", views.signup_page, name="signup"),
]
