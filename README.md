# polibatam-press

Marketplace buku digital (Django 5.2 LTS + DRF, Celery, PostgreSQL 17, Valkey, SeaweedFS, Nginx). Proof of concept lokal.

## Menjalankan lokal

Prasyarat: Docker Desktop (WSL2).

1. Salin `.env.example` menjadi `.env`, lalu isi nilai yang kosong (password DB, `DJANGO_SECRET_KEY`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, dst.). File `.env` tidak boleh di-commit.
2. Jalankan layanan:

   ```bash
   docker compose up -d --build
   docker compose ps
   ```

3. Migrasi database, lalu buat bucket S3 beserta aturan CORS-nya (jalankan ulang bila origin di `.env` berubah):

   ```bash
   docker compose exec django python manage.py migrate
   docker compose exec django python manage.py init_storage
   ```

4. Verifikasi:

   ```bash
   curl http://localhost:8080/api/health/                              # db, broker, storage = ok
   docker compose exec django ffmpeg -version
   docker compose exec django python manage.py shell -c "from core.tasks import ping; print(ping.delay().get(timeout=10))"   # pong
   ```

Port host (semua terikat ke `127.0.0.1`, bisa diubah lewat `.env`):

| Layanan  | Variabel             | Bawaan |
|----------|----------------------|--------|
| Nginx    | `NGINX_HOST_PORT`    | 8080   |
| S3       | `S3_HOST_PORT`       | 8333   |
| Postgres | `POSTGRES_HOST_PORT` | 15432  |

Bila `S3_HOST_PORT` diubah, sesuaikan juga `S3_PUBLIC_ENDPOINT_URL`.

Menghentikan: `docker compose down` (tambahkan `-v` untuk menghapus data volume).

## Uji konten digital (hanya saat `DJANGO_DEBUG=True`)

1. Tambahkan buku beserta produk Audiobook (MP3) dan/atau Ebook (PDF) di http://localhost:8080/admin/. Untuk audiobook, tunggu status DRM "Siap diputar".
2. Daftarkan akun pembeli di http://localhost:8080/uji-pemutar/ (bagian "Daftar").
3. Beri akun itu hak akses tanpa checkout (tanpa `--produk` perintah ini menampilkan daftar produk digital):

   ```bash
   docker compose exec django python manage.py buat_akses_uji --email <email pembeli> --produk <ID produk>
   ```

4. Buka halaman uji lewat `http://localhost:8080` (origin yang terdaftar di CORS bucket), login, lalu putar audiobook, jalankan uji keamanan, atau ambil salinan ebook ber-watermark.
5. Lacak kebocoran: unggah PDF salinan di Admin → menu DRM → "Lacak kebocoran".
6. Katalog dan keranjang: bagian 5 halaman uji. Katalog juga bisa dibuka langsung di http://localhost:8080/api/katalog/buku/ (contoh: `?q=data&tipe=ebook&urutan=harga`).

## Uji checkout dan pembayaran (Midtrans sandbox)

1. Buat akun sandbox di https://dashboard.sandbox.midtrans.com, lalu salin Server Key dan Client Key (Settings → Access Keys) ke `MIDTRANS_SERVER_KEY` dan `MIDTRANS_CLIENT_KEY` di `.env`. Jangan pernah membagikan atau meng-commit server key.
2. Terapkan perubahan (paket `requests` dan layanan `celery-beat` baru):

   ```bash
   docker compose up -d --build
   docker compose exec django python manage.py migrate
   docker compose exec django python manage.py check     # tidak ada peringatan orders.W001/W002
   ```

3. Di halaman uji (bagian 5–6): masukkan produk ke keranjang, isi pengiriman bila ada buku cetak (delivery: alamat + kecamatan di Kota Batam; takeaway: diambil di Gedung TA Kampus Polibatam, Lantai 1, Kantor Polibatam Store), lalu "Checkout dan bayar".
4. Di popup Snap pilih QRIS, salin URL gambar QR, lalu bayar di QRIS Simulator https://simulator.sandbox.midtrans.com/v2/qris/index. Jangan membayar dengan aplikasi bank atau e-wallet sungguhan.
5. Bagian 7: "Cek status" membaca status dari Midtrans; setelah lunas, ebook dan audiobook muncul di koleksi. Pesanan yang tidak dibayar sampai batas waktu (bawaan 60 menit) ditutup otomatis oleh `celery-beat` dan stok buku cetaknya kembali.
6. Admin → Orders → Pesanan: ubah status pengiriman (delivery: diproses → dikirim → selesai; takeaway: diproses → siap diambil → selesai). Semua notifikasi Midtrans tercatat di Log notifikasi Midtrans.
7. Opsional, notifikasi otomatis (webhook): buat tunnel publik ke `http://localhost:8080` (misalnya cloudflared atau ngrok), tambahkan domain tunnel ke `DJANGO_ALLOWED_HOSTS`, lalu isi Payment Notification URL di dashboard sandbox dengan `https://<domain-tunnel>/api/pembayaran/midtrans/notifikasi/`. Tanpa tunnel, status tetap diperbarui lewat "Cek status" dan pemeriksaan berkala.
