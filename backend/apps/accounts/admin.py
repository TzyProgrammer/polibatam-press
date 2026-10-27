from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.notifications import layanan as notifikasi

from .models import User
from .sandi import akhiri_semua_sesi


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "nama_lengkap", "role", "is_active")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("email", "nama_lengkap")
    readonly_fields = ("last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profil", {"fields": ("nama_lengkap", "no_telepon", "alamat", "kecamatan")}),
        ("Hak akses", {"fields": ("role", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Tanggal penting", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nama_lengkap", "role", "password1", "password2"),
        }),
    )

    def user_change_password(self, request, id, form_url=""):
        """Admin mengganti kata sandi pengguna lain: sesi JWT pengguna itu diakhiri dan ia diberi tahu."""
        respons = super().user_change_password(request, id, form_url)
        if request.method == "POST" and respons.status_code == 302:
            pengguna = self.get_object(request, unquote(id))
            if pengguna is not None:
                akhiri_semua_sesi(pengguna)
                # Akun admin memakai lupa kata sandi Django Admin, akun pembeli memakai halaman di frontend.
                notifikasi.sandi_diubah(pengguna, "admin" if pengguna.is_staff else "oleh_admin")
        return respons
