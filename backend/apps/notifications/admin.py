from django.contrib import admin

from .models import Notifikasi


@admin.register(Notifikasi)
class NotifikasiAdmin(admin.ModelAdmin):
    list_display = ("dibuat", "penerima", "kategori", "judul", "dibaca", "email_terkirim")
    list_filter = ("kategori", "dibaca", "email_terkirim")
    search_fields = ("penerima__email", "judul")
    date_hierarchy = "dibuat"
