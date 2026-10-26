"""Batas waktu tidak aktif untuk sesi Django Admin.

Admin memakai sesi berbasis cookie (berbeda dengan pembeli yang memakai JWT). Pengamanannya:
- cookie sesi berakhir saat peramban ditutup (SESSION_EXPIRE_AT_BROWSER_CLOSE di settings);
- sesi diakhiri bila tidak ada permintaan ke /admin/ selama ADMIN_SESI_TIDAK_AKTIF_MENIT (bawaan 30 menit).
Halaman admin yang terbuka memberi tahu server selama admin aktif (static/polibatam/admin-sesi.js), sehingga
mengisi formulir panjang tidak dianggap tidak aktif.
"""

import time
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

KUNCI_AKTIF_TERAKHIR = "admin_aktif_terakhir"


class BatasSesiAdminMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.path.startswith(reverse("admin:index")):
            sekarang = int(time.time())
            terakhir = request.session.get(KUNCI_AKTIF_TERAKHIR)
            batas = settings.ADMIN_SESI_TIDAK_AKTIF_MENIT * 60
            if terakhir is not None and sekarang - terakhir > batas:
                logout(request)
                if request.path == reverse("admin:sesi_aktif"):
                    return HttpResponse(status=401)
                messages.info(
                    request,
                    f"Sesi admin berakhir karena tidak ada aktivitas selama {settings.ADMIN_SESI_TIDAK_AKTIF_MENIT} "
                    "menit. Silakan masuk kembali.",
                )
                return redirect(f"{reverse('admin:login')}?next={quote(request.get_full_path())}")
            request.session[KUNCI_AKTIF_TERAKHIR] = sekarang
        return self.get_response(request)
