from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "nama_lengkap", "role", "is_active")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("email", "nama_lengkap")
    readonly_fields = ("last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profil", {"fields": ("nama_lengkap", "no_telepon", "alamat")}),
        ("Hak akses", {"fields": ("role", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Tanggal penting", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nama_lengkap", "role", "password1", "password2"),
        }),
    )
