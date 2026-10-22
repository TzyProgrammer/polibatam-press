"""Situs Django Admin Polibatam Press: judul berbahasa Indonesia dan halaman tambahan di menu.

Halaman tambahan adalah halaman admin yang bukan daftar model (misalnya Lacak kebocoran).
Halaman itu didaftarkan dari admin.py milik app dan tampil di menu kiri serta beranda admin
seperti model biasa, sehingga mudah ditemukan.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.contrib import admin
from django.urls import path, reverse


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


class AdminPolibatam(admin.AdminSite):
    site_header = "Admin Marketplace Polibatam Press"
    site_title = "Admin Marketplace Polibatam Press"
    index_title = "Admin Marketplace Polibatam Press"

    def __init__(self, name="admin"):
        super().__init__(name)
        self._halaman_tambahan = []

    def daftarkan_halaman(self, app_label, nama, slug, view, izin):
        self._halaman_tambahan.append(HalamanTambahan(app_label, nama, slug, view, izin))

    def get_urls(self):
        tambahan = [
            path(f"{h.app_label}/{h.slug}/", self.admin_view(h.view), name=h.nama_url)
            for h in self._halaman_tambahan
        ]
        return tambahan + super().get_urls()

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        for app in app_list:
            for h in self._halaman_tambahan:
                if h.app_label != app["app_label"] or not request.user.has_perm(h.izin):
                    continue
                app["models"].append(
                    {
                        "model": None,
                        "name": h.nama,
                        "object_name": h.slug.replace("-", ""),
                        "perms": {"add": False, "change": False, "delete": False, "view": True},
                        "admin_url": reverse(f"{self.name}:{h.nama_url}", current_app=self.name),
                        "add_url": None,
                        "view_only": True,
                    }
                )
            app["models"].sort(key=lambda m: m["name"])
        return app_list
