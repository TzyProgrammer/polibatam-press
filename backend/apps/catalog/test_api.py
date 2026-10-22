"""Tes Tahap E: API katalog publik (FR-05 katalog, FR-07 pencarian dan filter)."""

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.drm.models import PaketAudio
from core.testing import STORAGES_MEMORI, berkas_uji

from .models import Kategori, Produk
from .testing import buat_buku, buat_produk


@override_settings(STORAGES=STORAGES_MEMORI)
class KatalogTestCase(APITestCase):
    def setUp(self):
        self.teknik = Kategori.objects.create(nama="Teknik", slug="teknik")
        self.sastra = Kategori.objects.create(nama="Sastra", slug="sastra")
        Kategori.objects.create(nama="Kosong", slug="kosong")

        self.keamanan = buat_buku(
            "Keamanan Data Modern", "Budi Santoso", self.teknik, umur_hari=3, isbn="9786020000001",
            sinopsis="Pengantar keamanan data.", sampul=berkas_uji("sampul.jpg"),
        )
        self.keamanan_cetak = buat_produk(self.keamanan, Produk.Format.CETAK, 75000, stok=5)
        self.keamanan_ebook = buat_produk(self.keamanan, Produk.Format.EBOOK, 40000)

        self.puisi = buat_buku("Puisi Senja", "Siti Aminah", self.sastra, umur_hari=2)
        self.puisi_audio = buat_produk(self.puisi, Produk.Format.AUDIOBOOK, 60000)
        PaketAudio.objects.filter(produk=self.puisi_audio).update(status=PaketAudio.Status.SIAP)
        self.puisi_cetak = buat_produk(self.puisi, Produk.Format.CETAK, 50000, stok=0)

        self.belum_siap = buat_buku("Audiobook Belum Siap", umur_hari=1)
        self.belum_siap_audio = buat_produk(self.belum_siap, Produk.Format.AUDIOBOOK, 55000)

        self.nonaktif = buat_buku("Buku Nonaktif", aktif=False)
        buat_produk(self.nonaktif, Produk.Format.CETAK, 30000, stok=2)
        self.tanpa_produk_aktif = buat_buku("Tanpa Produk Aktif")
        buat_produk(self.tanpa_produk_aktif, Produk.Format.CETAK, 30000, stok=2, aktif=False)

    def daftar(self, **parameter):
        response = self.client.get(reverse("katalog-buku"), parameter)
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def slug(self, response):
        return [b["slug"] for b in response.data["results"]]


class DaftarBukuTests(KatalogTestCase):
    def test_hanya_buku_aktif_dengan_produk_aktif(self):
        response = self.daftar()
        self.assertEqual(response.data["count"], 3)
        # Urutan bawaan: terbaru lebih dulu.
        self.assertEqual(self.slug(response), ["audiobook-belum-siap", "puisi-senja", "keamanan-data-modern"])
        keamanan = response.data["results"][2]
        self.assertEqual(keamanan["harga_mulai"], 40000)
        self.assertEqual(keamanan["kategori"], {"nama": "Teknik", "slug": "teknik"})
        self.assertEqual([p["format"] for p in keamanan["produk"]], ["cetak", "ebook"])

    def test_tidak_ada_kueri_berulang_per_buku(self):
        with self.assertNumQueries(3):  # hitung total, halaman buku, produk aktif + paket audio
            self.daftar()

    def test_pencarian_judul_penulis_isbn_dan_beberapa_kata(self):
        for q, hasil in (
            ("keamanan", ["keamanan-data-modern"]),
            ("SITI", ["puisi-senja"]),
            ("9786020000001", ["keamanan-data-modern"]),
            ("data budi", ["keamanan-data-modern"]),  # setiap kata harus cocok di salah satu kolom
            ("data siti", []),
        ):
            with self.subTest(q=q):
                self.assertEqual(self.slug(self.daftar(q=q)), hasil)

    def test_filter_kategori_dan_format(self):
        self.assertEqual(self.slug(self.daftar(kategori="teknik")), ["keamanan-data-modern"])
        self.assertEqual(self.slug(self.daftar(format="audiobook")), ["audiobook-belum-siap", "puisi-senja"])
        self.assertEqual(self.slug(self.daftar(format="ebook", kategori="sastra")), [])
        response = self.client.get(reverse("katalog-buku"), {"format": "pdf"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Format harus salah satu dari: cetak, ebook, audiobook.")

    def test_urutan(self):
        self.assertEqual(
            self.slug(self.daftar(urutan="judul")), ["audiobook-belum-siap", "keamanan-data-modern", "puisi-senja"]
        )
        self.assertEqual(
            self.slug(self.daftar(urutan="harga")), ["keamanan-data-modern", "puisi-senja", "audiobook-belum-siap"]
        )
        self.assertEqual(
            self.slug(self.daftar(urutan="-harga")), ["audiobook-belum-siap", "puisi-senja", "keamanan-data-modern"]
        )
        self.assertEqual(self.client.get(reverse("katalog-buku"), {"urutan": "acak"}).status_code, 400)

    def test_halaman(self):
        for nomor in range(15):
            buat_produk(buat_buku(f"Buku Tambahan {nomor:02d}"), Produk.Format.CETAK, 20000, stok=1)
        response = self.daftar()
        self.assertEqual((response.data["count"], len(response.data["results"])), (18, 12))
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(len(self.daftar(ukuran=5).data["results"]), 5)
        response = self.client.get(reverse("katalog-buku"), {"page": 99})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Halaman tidak ditemukan.")

    def test_token_kedaluwarsa_tidak_menghalangi_katalog(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer token.rusak.kedaluwarsa")
        self.assertEqual(self.client.get(reverse("katalog-buku")).status_code, 200)


class DetailBukuTests(KatalogTestCase):
    def detail(self, buku):
        return self.client.get(reverse("katalog-buku-detail", args=[buku.slug]))

    def test_detail_dan_ketersediaan_produk(self):
        response = self.detail(self.keamanan)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sinopsis"], "Pengantar keamanan data.")
        self.assertEqual(response.data["isbn"], "9786020000001")
        self.assertIn("X-Amz-Expires=3600", response.data["sampul"])  # presigned URL 1 jam
        cetak, ebook = response.data["produk"]
        self.assertEqual(
            cetak,
            {"id": self.keamanan_cetak.pk, "format": "cetak", "format_label": "Buku cetak", "harga": 75000,
             "stok": 5, "tersedia": True, "keterangan": ""},
        )
        self.assertEqual((ebook["stok"], ebook["tersedia"]), (None, True))

        produk = {p["format"]: p for p in self.detail(self.puisi).data["produk"]}
        self.assertEqual((produk["audiobook"]["tersedia"], produk["cetak"]["tersedia"]), (True, False))
        self.assertEqual(produk["cetak"]["keterangan"], "Stok habis")
        self.assertIsNone(self.detail(self.puisi).data["sampul"])
        audio = self.detail(self.belum_siap).data["produk"][0]
        self.assertEqual((audio["tersedia"], audio["keterangan"]), (False, "Sedang disiapkan"))

    def test_buku_yang_tidak_tampil_di_katalog(self):
        for slug in (self.nonaktif.slug, self.tanpa_produk_aktif.slug, "tidak-ada"):
            with self.subTest(slug=slug):
                response = self.client.get(reverse("katalog-buku-detail", args=[slug]))
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.data["detail"], "Buku tidak ditemukan.")

    def test_produk_nonaktif_tidak_tampil(self):
        self.keamanan_ebook.aktif = False
        self.keamanan_ebook.save()
        formats = [p["format"] for p in self.detail(self.keamanan).data["produk"]]
        self.assertEqual(formats, ["cetak"])


class KategoriTests(KatalogTestCase):
    def test_kategori_dengan_jumlah_buku(self):
        response = self.client.get(reverse("katalog-kategori"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(k["slug"], k["jumlah_buku"]) for k in response.data],
            [("kosong", 0), ("sastra", 1), ("teknik", 1)],
        )
