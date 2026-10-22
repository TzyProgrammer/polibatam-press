from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import LoginSerializer, ProfilSerializer, RegistrasiSerializer


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
