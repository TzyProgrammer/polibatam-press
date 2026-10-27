from django.core.cache import cache
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User
from .sandi import ganti_sandi
from .serializers import (
    AturUlangSandiSerializer,
    LoginSerializer,
    LupaSandiSerializer,
    ProfilSerializer,
    RegistrasiSerializer,
    TautanSandiSerializer,
    UbahSandiSerializer,
)
from .tasks import kirim_tautan_atur_ulang_sandi

# Jeda minimum antar-email atur ulang untuk satu akun, agar kotak masuk tidak dibanjiri.
JEDA_EMAIL_ATUR_ULANG_DETIK = 60


class RegistrasiView(generics.CreateAPIView):
    """FR-03: registrasi akun pembeli."""

    serializer_class = RegistrasiSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "registrasi"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pengguna = serializer.save()
        return Response(ProfilSerializer(pengguna).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """FR-01: login dengan email dan kata sandi, menghasilkan access token dan refresh token."""

    serializer_class = LoginSerializer
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    """Menukar refresh token dengan access token dan refresh token baru; yang lama di-blacklist."""

    throttle_scope = "refresh"


class LogoutView(APIView):
    """FR-02: logout dengan mem-blacklist refresh token milik pengguna."""

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response({"detail": "Refresh token wajib dikirim."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh = RefreshToken(token)
            if str(refresh.get(jwt_settings.USER_ID_CLAIM)) != str(request.user.pk):
                return Response({"detail": "Refresh token bukan milik Anda."}, status=status.HTTP_403_FORBIDDEN)
            refresh.blacklist()
        except TokenError:
            return Response(
                {"detail": "Refresh token tidak valid atau sudah kedaluwarsa."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfilView(generics.RetrieveUpdateAPIView):
    """FR-04: melihat dan mengubah profil sendiri (email dan peran tidak bisa diubah)."""

    serializer_class = ProfilSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class UbahSandiView(APIView):
    """Ubah kata sandi dari halaman Profil. Semua sesi lain dikeluarkan; perangkat ini menerima token baru."""

    throttle_scope = "ubah_sandi"

    def post(self, request):
        serializer = UbahSandiSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        ganti_sandi(request.user, serializer.validated_data["password_baru"], "ubah")
        refresh = RefreshToken.for_user(request.user)
        return Response(
            {
                "detail": "Kata sandi berhasil diubah. Perangkat lain yang masih masuk sudah dikeluarkan.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class LupaSandiView(APIView):
    """Kirim tautan atur ulang kata sandi ke email pembeli.

    Jawaban selalu sama, baik email terdaftar maupun tidak, agar halaman ini tidak bisa dipakai untuk
    menebak email yang terdaftar. Email dikirim worker Celery, jadi lama respons juga tidak membedakannya.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "lupa_sandi"

    PESAN = (
        "Bila email tersebut terdaftar sebagai akun pembeli, tautan untuk mengatur ulang kata sandi sudah "
        "dikirim. Periksa kotak masuk dan folder spam Anda."
    )

    def post(self, request):
        serializer = LupaSandiSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pengguna = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True, role=User.Role.PEMBELI
        ).first()
        if pengguna and pengguna.has_usable_password():
            if cache.add(f"lupa-sandi:{pengguna.pk}", 1, timeout=JEDA_EMAIL_ATUR_ULANG_DETIK):
                pengguna_id = pengguna.pk
                transaction.on_commit(lambda: kirim_tautan_atur_ulang_sandi.delay(pengguna_id))
        return Response({"detail": self.PESAN})


class CekTautanSandiView(APIView):
    """Periksa tautan atur ulang sebelum formulir kata sandi baru ditampilkan."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "atur_ulang_sandi"

    def post(self, request):
        serializer = TautanSandiSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"email": serializer.validated_data["pengguna"].email})


class AturUlangSandiView(APIView):
    """Simpan kata sandi baru dari tautan email. Tautan langsung gugur dan semua sesi dikeluarkan."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "atur_ulang_sandi"

    def post(self, request):
        serializer = AturUlangSandiSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pengguna = serializer.validated_data["pengguna"]
        ganti_sandi(pengguna, serializer.validated_data["password"], "atur_ulang")
        return Response(
            {"detail": "Kata sandi berhasil diatur ulang. Silakan masuk dengan kata sandi baru.", "email": pengguna.email}
        )
