from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Shop, ShopMembership


class ShopSerializer(serializers.ModelSerializer):
    # "Mon rôle dans ce commerce" : pratique pour l'écran Vue (afficher ou cacher des boutons).
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            "id", "name", "slug", "currency", "default_min_stock", "timezone",
            "is_active", "my_role", "created_at",
        ]
        # On ne peut pas choisir soi-même le slug ni réactiver un commerce.
        read_only_fields = ["id", "slug", "is_active", "created_at"]
        extra_kwargs = {"default_min_stock": {"min_value": 0}}

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_my_role(self, shop) -> str | None:
        badge = shop.memberships.filter(user=self.context["request"].user, is_active=True).first()
        return badge.role if badge else None


class MembershipSerializer(serializers.ModelSerializer):
    """Pour AFFICHER un employé, et modifier son rôle ou son état."""
    email = serializers.CharField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ShopMembership
        fields = ["id", "email", "username", "role", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_role(self, value):
        # Un seul propriétaire par commerce pour le MVP : on ne "nomme" pas de second patron.
        if value == ShopMembership.Role.OWNER:
            raise serializers.ValidationError("Le rôle de propriétaire ne peut pas être attribué.")
        return value


class MemberCreateSerializer(serializers.Serializer):
    """Pour RECEVOIR la demande d'ajout d'un employé."""
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=[
        (value, label) for value, label in ShopMembership.Role.choices if value != "owner"
    ])

    def validate_email(self, value):
        from accounts.models import User
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Cet email a déjà un compte.")
        return value

    def validate_username(self, value):
        from accounts.models import User
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur existe déjà.")
        return value