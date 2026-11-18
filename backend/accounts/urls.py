from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import MeView, RegisterView, LoginView

urlpatterns = [
    path("auth/register/", RegisterView.as_view()),                 # créer son compte
    path("auth/token/", TokenObtainPairView.as_view()),             # se connecter -> access + refresh
    path("auth/token/refresh/", TokenRefreshView.as_view()),        # racheter un access avec le refresh
    path("auth/me/", MeView.as_view()),       
    path("auth/token/", LoginView.as_view()),# qui suis-je ?
]