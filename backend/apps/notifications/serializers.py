from rest_framework import serializers

from .models import Notifikasi


class NotifikasiSerializer(serializers.ModelSerializer):
    kategori_label = serializers.CharField(source="get_kategori_display", read_only=True)

    class Meta:
        model = Notifikasi
        fields = ["id", "kategori", "kategori_label", "judul", "pesan", "tautan", "dibaca", "dibuat"]
        read_only_fields = fields
