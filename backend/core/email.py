"""Pengiriman email aplikasi (notifikasi dan keamanan akun) dalam dua bentuk: teks biasa dan HTML.

Setiap email memakai pasangan template `<nama>.txt` dan `<nama>.html`. Template HTML memperluas
email/dasar.html (kepala biru Polibatam Press, kaki berisi keterangan email otomatis).
Fungsi di sini dipanggil dari task Celery, bukan dari request, agar lambatnya SMTP tidak menahan halaman.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

PREFIX_SUBJEK = "[Polibatam Press]"


def tautan_frontend(path=""):
    """URL lengkap halaman pembeli dari path seperti /pesanan/PP-123 (kosong = beranda)."""
    return settings.FRONTEND_URL + (path or "").lstrip("/")


def kirim_email(ke, subjek, template, konteks):
    """Kirim satu email ke satu alamat. Melempar exception bila SMTP gagal (task yang mengulang)."""
    konteks = {"subjek": subjek, "url_situs": settings.FRONTEND_URL, **konteks}
    teks = render_to_string(f"{template}.txt", konteks)
    html = render_to_string(f"{template}.html", konteks)
    pesan = EmailMultiAlternatives(
        subject=f"{PREFIX_SUBJEK} {subjek}", body=teks, from_email=settings.DEFAULT_FROM_EMAIL, to=[ke]
    )
    pesan.attach_alternative(html, "text/html")
    pesan.send()
