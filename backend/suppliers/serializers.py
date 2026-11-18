from rest_framework import serializers
from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        exclude = ["shop"]     # le commerce est décidé par le mixin, pas par le client