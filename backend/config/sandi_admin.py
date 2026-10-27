"""Lupa kata sandi Django Admin (tautan "Lupa…" di halaman masuk admin).

Memakai alur bawaan Django (PasswordResetView dan seterusnya) dengan tiga penyesuaian:
- hanya akun admin (is_staff) yang dikirimi tautan; akun pembeli memakai halaman Lupa kata sandi di frontend;
- permintaan dibatasi per alamat IP agar halaman ini tidak dipakai membanjiri kotak masuk admin;
- setelah kata sandi diatur ulang, semua sesi JWT akun itu diakhiri dan pemberitahuan keamanan dikirim.
Jawaban halaman tetap sama walaupun email tidak terdaftar atau batas tercapai (tidak membocorkan akun).
"""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.urls import reverse

from apps.accounts.sandi import akhiri_semua_sesi
from apps.notifications import layanan as notifikasi

BATAS_PERMINTAAN_PER_JAM = 5


def ip_klien(request):
    # Satu proxy (Nginx) di depan Django, sama dengan NUM_PROXIES di REST_FRAMEWORK.
    terusan = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if terusan:
        return terusan.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


class FormLupaSandiAdmin(PasswordResetForm):
    def get_users(self, email):
        return (pengguna for pengguna in super().get_users(email) if pengguna.is_staff)


class KonteksAdminMixin:
    """Judul situs admin untuk template registration/* bawaan Django admin, tanpa menu samping (halaman ini
    dibuka sebelum masuk, jadi menu akan kosong)."""

    def get_context_data(self, **kwargs):
        from django.contrib import admin

        return {
            **admin.site.each_context(self.request),
            "is_nav_sidebar_enabled": False,
            **super().get_context_data(**kwargs),
        }


class LupaSandiAdminView(KonteksAdminMixin, auth_views.PasswordResetView):
    form_class = FormLupaSandiAdmin
    subject_template_name = "registration/admin_atur_ulang_subjek.txt"
    email_template_name = "registration/admin_atur_ulang_email.txt"
    html_email_template_name = "registration/admin_atur_ulang_email.html"
    extra_email_context = {"menit": settings.PASSWORD_RESET_TIMEOUT // 60}

    def form_valid(self, form):
        kunci = f"lupa-sandi-admin:{ip_klien(self.request)}"
        cache.add(kunci, 0, timeout=60 * 60)
        if cache.incr(kunci) > BATAS_PERMINTAAN_PER_JAM:
            return HttpResponseRedirect(self.get_success_url())
        return super().form_valid(form)


class LupaSandiAdminTerkirimView(KonteksAdminMixin, auth_views.PasswordResetDoneView):
    pass


class AturUlangSandiAdminView(KonteksAdminMixin, auth_views.PasswordResetConfirmView):
    def form_valid(self, form):
        respons = super().form_valid(form)
        akhiri_semua_sesi(form.user)
        notifikasi.sandi_diubah(form.user, "admin")
        return respons


class AturUlangSandiAdminSelesaiView(KonteksAdminMixin, auth_views.PasswordResetCompleteView):
    def get_context_data(self, **kwargs):
        # Tautan "Masuk" menuju halaman masuk admin (LOGIN_URL bawaan Django tidak dipakai proyek ini).
        return {**super().get_context_data(**kwargs), "login_url": reverse("admin:login")}
