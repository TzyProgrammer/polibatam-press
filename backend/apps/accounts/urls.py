from django.urls import path

from .views import LoginView, LogoutView, ProfilView, RefreshView, RegistrasiView

urlpatterns = [
    path("registrasi/", RegistrasiView.as_view(), name="auth-registrasi"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("profil/", ProfilView.as_view(), name="auth-profil"),
]
