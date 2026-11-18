import os
from corsheaders.defaults import default_headers
from .base import *      # on reprend tout de base.py, puis on durcit

# Jamais de mode "démonstration" sur un vrai serveur : en cas d'erreur,
# DEBUG=True afficherait au visiteur des morceaux de votre code et de vos réglages.
DEBUG = False

# Les adresses qui ont le droit de parler à Django, écrites dans le .env du SERVEUR :
# DJANGO_ALLOWED_HOSTS=api.kawastock.example
ALLOWED_HOSTS = [h.strip() for h in os.environ["DJANGO_ALLOWED_HOSTS"].split(",")]

# Les sites Vue autorisés à utiliser l'API : CORS_ALLOWED_ORIGINS=https://app.kawastock.example
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ["CORS_ALLOWED_ORIGINS"].split(",")]
CORS_ALLOW_HEADERS = list(default_headers) + ["x-shop-id"]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS      # pour que l'admin marche en https

# --- Tout passer en https (le "cadenas" du navigateur) ---
SECURE_SSL_REDIRECT = True                       # http:// est renvoyé vers https://
SESSION_COOKIE_SECURE = True                     # les cookies ne voyagent qu'en https
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000                   # "ce site, c'est https pour 1 an"
# Derrière un serveur web (nginx...), Django ne voit pas le https lui-même :
# on lui dit de croire l'en-tête que le serveur web ajoute.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Où ranger les fichiers du site d'admin une fois "collectés" pour le serveur.
STATIC_ROOT = BASE_DIR / "staticfiles"