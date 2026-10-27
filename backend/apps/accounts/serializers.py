import re

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.wilayah import KECAMATAN_KOTA_BATAM

from .models import User

# Angka, spasi, atau tanda hubung, boleh diawali "+"; 8–20 karakter (contoh: 0812-3456-7890, +62 812 3456 7890).
POLA_TELEPON = re.compile(r"^\+?[0-9][0-9 -]{6,18}[0-9]$")


def kolom_kecamatan():
    return serializers.ChoiceField(
        choices=KECAMATAN_KOTA_BATAM,
        required=False,
        allow_blank=True,
        error_messages={"invalid_choice": "Pilih kecamatan di Kota Batam, atau kosongkan."},
    )


class ValidasiTeleponMixin:
    def validate_no_telepon(self, value):
        value = value.strip()
        if value and not POLA_TELEPON.match(value):
            raise serializers.ValidationError(
                "Nomor telepon hanya boleh berisi angka, spasi, atau tanda hubung (boleh diawali +), 8–20 karakter."
            )
        return value


class ProfilSerializer(ValidasiTeleponMixin, serializers.ModelSerializer):
    kecamatan = kolom_kecamatan()

    class Meta:
        model = User
        fields = ["id", "email", "nama_lengkap", "no_telepon", "alamat", "kecamatan", "role"]
        read_only_fields = ["id", "email", "role"]


class RegistrasiSerializer(ValidasiTeleponMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})
    kecamatan = kolom_kecamatan()

    class Meta:
        model = User
        fields = ["email", "nama_lengkap", "no_telepon", "alamat", "kecamatan", "password"]
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


def validasi_sandi_baru(sandi, pengguna, kolom):
    try:
        password_validation.validate_password(sandi, pengguna)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({kolom: list(exc.messages)}) from exc


class UbahSandiSerializer(serializers.Serializer):
    password_lama = serializers.CharField(write_only=True, trim_whitespace=False)
    password_baru = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_password_lama(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Kata sandi saat ini salah.")
        return value

    def validate(self, attrs):
        if attrs["password_baru"] == attrs["password_lama"]:
            raise serializers.ValidationError(
                {"password_baru": "Kata sandi baru harus berbeda dari kata sandi saat ini."}
            )
        validasi_sandi_baru(attrs["password_baru"], self.context["request"].user, "password_baru")
        return attrs


class LupaSandiSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class TautanSandiSerializer(serializers.Serializer):
    """uid dan token dari tautan email atur ulang kata sandi."""

    PESAN_TIDAK_VALID = (
        "Tautan atur ulang kata sandi tidak valid atau sudah kedaluwarsa. Minta tautan baru di halaman Lupa "
        "kata sandi."
    )

    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)

    def validate(self, attrs):
        from .sandi import pengguna_dari_tautan

        pengguna = pengguna_dari_tautan(attrs["uid"], attrs["token"])
        if pengguna is None:
            raise serializers.ValidationError(self.PESAN_TIDAK_VALID, code="tautan_tidak_valid")
        attrs["pengguna"] = pengguna
        return attrs


class AturUlangSandiSerializer(TautanSandiSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        validasi_sandi_baru(attrs["password"], attrs["pengguna"], "password")
        return attrs
