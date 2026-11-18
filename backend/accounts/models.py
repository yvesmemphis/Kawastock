from django.db import models

# Create your models here.
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Theme(models.TextChoices):
        LIGHT = "light", "Clair"
        DARK = "dark", "Sombre"

    class Language(models.TextChoices):
        FRENCH = "fr", "Français"
        ENGLISH = "en", "English"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    profile_photo = models.ImageField(upload_to="profile_photos/%Y/%m/", blank=True, null=True)
    theme = models.CharField(max_length=8, choices=Theme.choices, default=Theme.LIGHT)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.FRENCH)
    USERNAME_FIELD = "email"
    # Obligatoire pour createsuperuser : les autres champs à demander en plus de l'email.
    REQUIRED_FIELDS = ["username"]