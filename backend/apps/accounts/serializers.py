import re

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User

# Angka, spasi, atau tanda hubung, boleh diawali "+"; 8–20 karakter (contoh: 0812-3456-7890, +62 812 3456 7890).
POLA_TELEPON = re.compile(r"^\+?[0-9][0-9 -]{6,18}[0-9]$")


class ValidasiTeleponMixin:
    def validate_no_telepon(self, value):
        value = value.strip()
        if value and not POLA_TELEPON.match(value):
            raise serializers.ValidationError(
                "Nomor telepon hanya boleh berisi angka, spasi, atau tanda hubung (boleh diawali +), 8–20 karakter."
            )
        return value


class ProfilSerializer(ValidasiTeleponMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "nama_lengkap", "no_telepon", "alamat", "role"]
        read_only_fields = ["id", "email", "role"]


class RegistrasiSerializer(ValidasiTeleponMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["email", "nama_lengkap", "no_telepon", "alamat", "password"]
        # Keunikan email diperiksa di validate_email agar tidak membedakan huruf besar dan kecil.
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, value):
        # Email disimpan dalam huruf kecil; pengecekan duplikat tidak membedakan huruf besar dan kecil.
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Email sudah terdaftar.")
        return email

    def validate(self, attrs):
        calon = User(email=attrs["email"], nama_lengkap=attrs.get("nama_lengkap", ""))
        try:
            password_validation.validate_password(attrs["password"], calon)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Registrasi publik selalu menghasilkan akun pembeli; akun admin hanya dibuat lewat Django Admin.
        return User.objects.create_user(password=password, role=User.Role.PEMBELI, **validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {"no_active_account": "Email atau kata sandi salah."}

    def validate(self, attrs):
        # Login tidak membedakan huruf besar dan kecil pada email. Bila ternyata ada lebih dari
        # satu akun yang cocok (hanya mungkin lewat admin), dipakai pencocokan persis.
        email = attrs.get(self.username_field, "").strip()
        cocok = list(User.objects.filter(email__iexact=email).values_list("email", flat=True)[:2])
        attrs[self.username_field] = cocok[0] if len(cocok) == 1 else email
        data = super().validate(attrs)
        data["pengguna"] = ProfilSerializer(self.user).data
        return data
