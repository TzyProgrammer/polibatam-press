from django.urls import path

from .views import (
    AturUlangSandiView,
    CekTautanSandiView,
    LoginView,
    LogoutView,
    LupaSandiView,
    ProfilView,
    RefreshView,
    RegistrasiView,
    UbahSandiView,
)

urlpatterns = [
    path("registrasi/", RegistrasiView.as_view(), name="auth-registrasi"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("profil/", ProfilView.as_view(), name="auth-profil"),
    path("ubah-sandi/", UbahSandiView.as_view(), name="auth-ubah-sandi"),
    path("lupa-sandi/", LupaSandiView.as_view(), name="auth-lupa-sandi"),
    path("atur-ulang-sandi/", AturUlangSandiView.as_view(), name="auth-atur-ulang-sandi"),
    path("atur-ulang-sandi/cek/", CekTautanSandiView.as_view(), name="auth-cek-tautan-sandi"),
]
