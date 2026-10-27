"""Situs Django Admin Polibatam Press: judul berbahasa Indonesia, menu yang dikelompokkan, dan halaman tambahan.

Halaman tambahan adalah halaman admin yang bukan daftar model (misalnya Lacak kebocoran).
Halaman itu didaftarkan dari admin.py milik app dan tampil di menu kiri serta beranda admin
seperti model biasa, sehingga mudah ditemukan.

Menu beranda dan menu kiri tidak mengikuti urutan app bawaan Django, tetapi BAGIAN_MENU di bawah
(urutan dari pemilik, 26 Oktober). Alamat halaman tidak berubah: pengelompokan hanya tampilan.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, reverse

# (judul bagian, app_label untuk tautan judul atau None, [(app_label, object_name model / slug halaman)])
BAGIAN_MENU = (
    ("Katalog", "catalog", [("catalog", "Kategori"), ("catalog", "Buku")]),
    ("ISBN", "isbn", [("isbn", "PengajuanISBN")]),
    ("Pesanan", "orders", [("orders", "Pesanan")]),
    ("Konten Digital (DRM)", "drm", [("drm", "HakAkses"), ("drm", "lacakkebocoran")]),
    ("Akun", "accounts", [("accounts", "User")]),
    ("Autentikasi dan Otorisasi", "auth", [("auth", "Group")]),
    (
        "Log",
        None,
        [
            ("drm", "SalinanEbook"),
            ("drm", "PaketAudio"),
            ("drm", "SesiStreaming"),
            ("notifications", "Notifikasi"),
            ("orders", "LogNotifikasiMidtrans"),
            ("drm", "LogAksesKunci"),
            ("token_blacklist", "BlacklistedToken"),
            ("token_blacklist", "OutstandingToken"),
        ],
    ),
)


@dataclass(frozen=True)
class HalamanTambahan:
    app_label: str
    nama: str
    slug: str
    view: Callable
    izin: str  # izin yang diperlukan untuk melihat menu dan membuka halaman

    @property
    def nama_url(self):
        return f"{self.app_label}_{self.slug.replace('-', '_')}"

    @property
    def object_name(self):
        return self.slug.replace("-", "")


class AdminPolibatam(admin.AdminSite):
    site_header = "Admin Marketplace Polibatam Press"
    site_title = "Admin Marketplace Polibatam Press"
    index_title = "Admin Marketplace Polibatam Press"

    def __init__(self, name="admin"):
        super().__init__(name)
        self._halaman_tambahan = []

    @property
    def site_url(self):
        """Tautan "Lihat situs" menuju halaman pembeli (frontend Vue), bukan ke backend."""
        return settings.FRONTEND_URL

    def each_context(self, request):
        konteks = super().each_context(request)
        konteks["admin_sesi_menit"] = settings.ADMIN_SESI_TIDAK_AKTIF_MENIT
        return konteks

    def daftarkan_halaman(self, app_label, nama, slug, view, izin):
        self._halaman_tambahan.append(HalamanTambahan(app_label, nama, slug, view, izin))

    def get_urls(self):
        tambahan = [
            path(f"{h.app_label}/{h.slug}/", self.admin_view(h.view), name=h.nama_url)
            for h in self._halaman_tambahan
        ]
        tambahan.append(path("sesi-aktif/", self.admin_view(self.sesi_aktif), name="sesi_aktif"))
        return tambahan + super().get_urls()

    def sesi_aktif(self, request):
        """Dipanggil admin-sesi.js selama admin aktif; batas tidak aktif diperbarui oleh middleware."""
        return HttpResponse(status=204)

    def password_change(self, request, extra_context=None):
        """Ganti sandi admin (tautan di header). Setelah berhasil, pemberitahuan keamanan dikirim ke email admin."""
        respons = super().password_change(request, extra_context)
        if request.method == "POST" and respons.status_code == 302:
            from apps.notifications import layanan as notifikasi

            notifikasi.sandi_diubah(request.user, "admin")
        return respons

    def _app_dict_lengkap(self, request, app_label=None):
        """App dict bawaan ditambah halaman tambahan yang boleh dilihat pengguna ini."""
        app_dict = self._build_app_dict(request, app_label)
        for h in self._halaman_tambahan:
            if h.app_label not in app_dict or not request.user.has_perm(h.izin):
                continue
            app_dict[h.app_label]["models"].append(
                {
                    "model": None,
                    "name": h.nama,
                    "object_name": h.object_name,
                    "perms": {"add": False, "change": False, "delete": False, "view": True},
                    "admin_url": reverse(f"{self.name}:{h.nama_url}", current_app=self.name),
                    "add_url": None,
                    "view_only": True,
                }
            )
        return app_dict

    def get_app_list(self, request, app_label=None):
        app_dict = self._app_dict_lengkap(request, app_label)
        if app_label:
            # Halaman indeks satu app (/admin/<app>/) tetap menampilkan model app itu saja.
            app_list = list(app_dict.values())
            for app in app_list:
                app["models"].sort(key=lambda m: m["name"])
            return app_list

        model_per_kunci = {
            (label, model["object_name"]): model for label, app in app_dict.items() for model in app["models"]
        }
        terpakai = set()
        app_list = []
        for judul, label_tautan, daftar in BAGIAN_MENU:
            models = []
            for kunci in daftar:
                if kunci in model_per_kunci:
                    models.append(model_per_kunci[kunci])
                    terpakai.add(kunci)
            if not models:
                continue
            bagian_app = app_dict.get(label_tautan) if label_tautan else None
            app_list.append(
                {
                    "name": judul,
                    "app_label": label_tautan or judul.lower(),
                    # Bagian gabungan (Log) tidak punya halaman indeks sendiri, jadi judulnya bukan tautan.
                    "app_url": bagian_app["app_url"] if bagian_app else "",
                    "has_module_perms": True,
                    "models": models,
                }
            )

        # Model yang belum masuk BAGIAN_MENU (misalnya model baru) tetap tampil, di bagian akhir.
        sisa = [m for kunci, m in model_per_kunci.items() if kunci not in terpakai]
        if sisa:
            sisa.sort(key=lambda m: m["name"])
            app_list.append(
                {"name": "Lainnya", "app_label": "lainnya", "app_url": "", "has_module_perms": True, "models": sisa}
            )
        return app_list
