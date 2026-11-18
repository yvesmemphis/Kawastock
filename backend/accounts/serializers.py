from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    # write_only = on peut l'ENVOYER mais il n'est JAMAIS renvoyé dans la réponse.
    # validators = Django vérifie que le mot de passe est assez solide (8 caractères, etc.).
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        # On range les emails en minuscules : "Awa@X.ci" et "awa@x.ci" = la même personne.
        return value.strip().lower()

    def create(self, validated_data):
        # create_user (et non create) : il transforme le mot de passe en code secret illisible.
        return User.objects.create_user(**validated_data)


class MeSerializer(serializers.ModelSerializer):
    """'Qui suis-je, et dans quels commerces ai-je un badge ?'"""
    memberships = serializers.SerializerMethodField()
    profile_photo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name", "memberships",
            "profile_photo", "profile_photo_url", "theme", "language",
        ]
        read_only_fields = ["id", "email", "username", "memberships", "profile_photo_url"]

    @extend_schema_field(serializers.ListField(child=serializers.DictField(child=serializers.CharField())))
    def get_memberships(self, user) -> list[dict[str, str]]:
        # Mes badges actifs, dans des commerces actifs.
        badges = user.memberships.filter(is_active=True, shop__is_active=True).select_related("shop")
        return [
            {"shop_id": str(b.shop_id), "shop_name": b.shop.name, "role": b.role}
            for b in badges
        ]

    def get_profile_photo_url(self, user) -> str | None:
        return user.profile_photo.url if user.profile_photo else None

    def validate_profile_photo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("La photo ne doit pas dépasser 5 Mo.")
        return value