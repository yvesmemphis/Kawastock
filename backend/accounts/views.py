from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions
from .serializers import MeSerializer, RegisterSerializer
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    # Pour s'inscrire, on n'est évidemment pas encore connecté : porte ouverte à tous.
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

class LoginView(TokenObtainPairView):
    # "Surveille combien de fois cette porte s'ouvre, par adresse IP."
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"
    
    
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer

    def get_object(self):
        # "L'objet à montrer, c'est la personne connectée elle-même."
        return self.request.user