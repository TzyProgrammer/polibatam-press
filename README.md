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
| Mailpit  | `MAILPIT_HOST_PORT`  | 8025   |

Bila `S3_HOST_PORT` diubah, sesuaikan juga `S3_PUBLIC_ENDPOINT_URL`.

Menghentikan: `docker compose down` (tambahkan `-v` untuk menghapus data volume).

## Frontend (Vue)

Frontend dijalankan di laptop (bukan di Docker), sementara backend tetap di Docker. Prasyarat: Node.js 22.13+ (diuji dengan Node 24; pdfjs-dist memerlukan minimal 22.13) dan backend dari langkah di atas sudah berjalan.

```bash
cd frontend
npm install        # sekali, dan setiap package.json berubah
npm run dev        # buka http://localhost:5173
```

Vite meneruskan `/api/...` ke Nginx di `http://127.0.0.1:8080`, sehingga peramban hanya berhubungan dengan satu origin dan API tidak memerlukan CORS. Bila `NGINX_HOST_PORT` diubah, buat `frontend/.env.local` berisi `VITE_BACKEND=http://127.0.0.1:<port>`. `npm run build` menghasilkan `frontend/dist/`.

Tahap H1 berisi beranda dan katalog, detail buku, masuk, daftar, dan profil. Tahap H2 menambah keranjang, checkout, pembayaran QRIS (Snap), riwayat pesanan, dan detail pesanan. Tahap H3 menambah Koleksi, pembaca ebook (PDF.js), dan pemutar audiobook (hls.js). Tahap H4 menambah pengajuan ISBN, panel notifikasi di header, dan halaman Notifikasi.

Pembaca ebook dan pemutar audiobook mengambil berkas langsung dari bucket (`localhost:8333`), jadi origin frontend harus terdaftar di aturan CORS bucket. `.env.example` sudah berisi `CORS_ALLOWED_ORIGINS=http://localhost:5173`; pastikan `.env` Anda juga memuatnya, lalu jalankan `docker compose exec django python manage.py init_storage` dan periksa bahwa keluarannya menyebut `http://localhost:5173`.

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

3. Lewat frontend (http://localhost:5173, Tahap H2): masukkan produk ke keranjang → Lanjut ke checkout → pilih pengiriman bila ada buku cetak (delivery: alamat + kecamatan di Kota Batam; takeaway: diambil di Gedung TA Kampus Polibatam, Lantai 1, Kantor Polibatam Store) → "Buat pesanan dan bayar". Jendela Snap terbuka otomatis di halaman pembayaran. Halaman uji (bagian 5–6, "Checkout dan bayar") tetap bisa dipakai.
4. Di popup Snap pilih QRIS, salin URL gambar QR, lalu bayar di QRIS Simulator https://simulator.sandbox.midtrans.com/v2/qris/index. Jangan membayar dengan aplikasi bank atau e-wallet sungguhan.
5. Halaman pembayaran memeriksa status ke Midtrans tiap 15 detik selama tab terlihat; tombol "Cek status pembayaran" memeriksanya saat itu juga (di halaman uji: bagian 7, "Cek status"). Setelah lunas, halaman pindah ke detail pesanan, dan ebook serta audiobook masuk ke koleksi. Pesanan yang tidak dibayar sampai batas waktu (bawaan 60 menit) ditutup otomatis oleh `celery-beat` dan stok buku cetaknya kembali.
6. Admin → Orders → Pesanan: ubah status pengiriman (delivery: diproses → dikirim → selesai; takeaway: diproses → siap diambil → selesai). Semua notifikasi Midtrans tercatat di Log notifikasi Midtrans.
7. Opsional, notifikasi otomatis (webhook): buat tunnel publik ke `http://localhost:8080` (misalnya cloudflared atau ngrok), tambahkan domain tunnel ke `DJANGO_ALLOWED_HOSTS`, lalu isi Payment Notification URL di dashboard sandbox dengan `https://<domain-tunnel>/api/pembayaran/midtrans/notifikasi/`. Tanpa tunnel, status tetap diperbarui lewat "Cek status" dan pemeriksaan berkala.

## Uji koleksi, pembaca ebook, dan pemutar audiobook (Tahap H3)

1. Pastikan aturan CORS bucket memuat `http://localhost:5173` (lihat bagian Frontend).
2. Miliki ebook dan audiobook: beli lewat frontend, atau beri hak akses dengan `buat_akses_uji` (bagian "Uji konten digital").
3. Buka http://localhost:5173/koleksi. Setiap item menampilkan status kontennya; tombol Baca atau Putar aktif bila konten bisa dibuka. Salinan ebook yang belum siap disiapkan saat dibuka (pembaca menunggu sampai siap).
4. Pembaca ebook: berpindah halaman lewat tombol, isian nomor halaman, panah kiri/kanan atau Page Up/Down, dan geser kiri/kanan di layar sentuh; perbesar/perkecil, tombol persen untuk kembali pas layar, dan layar penuh. Watermark ("Properti Milik Polibatam Press", "Dibeli Oleh <nama>", email disamarkan, nomor pesanan, kode) terlihat di setiap halaman. Di layar lebar halaman tampil berpasangan seperti buku terbuka (sampul depan dan belakang sendiri). Tidak ada tombol unduh.
5. Pemutar audiobook: Putar membuat sesi streaming baru; tersedia jeda, mundur/maju 15 detik, seret garis waktu, kecepatan, dan volume. Audiobook dikemas AAC, jadi gunakan Chrome, Edge, Firefox, atau Safari biasa (Chromium tanpa codec AAC tidak bisa memutarnya).
6. Posisi halaman terakhir dan posisi dengar terakhir diingat per akun di peramban yang sama.
7. Admin → DRM → Hak akses: nonaktifkan hak akses → di Koleksi item itu menjadi "Akses dinonaktifkan admin" dan tidak bisa dibuka; aktifkan lagi → bisa dibuka kembali. Pembeli menerima notifikasi untuk keduanya.

## Uji notifikasi dan pengajuan ISBN

1. Lewat frontend (Tahap H4): buka http://localhost:5173/isbn. Tamu melihat cara mengajukan beserta tombol Masuk dan Daftar; setelah masuk, formulir dan daftar "Pengajuan saya" tampil.
2. Ajukan naskah PDF atau DOCX (maksimal 20 MB; pilih berkas atau seret ke kotak unggah). Berkas lain yang hanya diganti namanya menjadi .pdf/.docx ditolak dengan pesan di bawah isian.
3. Admin → ISBN → Pengajuan ISBN: ubah status menunggu verifikasi → diproses, lalu diproses → selesai (wajib ISBN-13 valid, misalnya 978-602-8519-93-9) atau ditolak (wajib alasan). Kolom yang tidak berlaku untuk status terpilih terkunci. Pemohon menerima notifikasi untuk setiap perubahan status; detail pengajuan (`/isbn/<id>`) menampilkan lini status, nomor ISBN beserta tombol salin, atau alasan penolakan.
4. Lonceng di header membuka panel notifikasi (angka belum dibaca dimuat ulang tiap 30 detik selama tab terlihat). Memilih notifikasi menandainya dibaca dan membuka halaman terkait; "Tandai semua dibaca" dan "Lihat semua notifikasi" (`/notifikasi`, dengan filter Belum dibaca) tersedia.
5. Notifikasi muncul saat pembayaran lunas atau pesanan ditutup, saat admin mengubah status pengiriman, saat admin menonaktifkan atau mengaktifkan hak akses, dan saat status pengajuan ISBN berubah.
6. Halaman uji (bagian 8 notifikasi, bagian 9 pengajuan ISBN) tetap bisa dipakai.

## Email (notifikasi dan atur ulang kata sandi)

Setiap notifikasi di aplikasi juga dikirim ke email pembeli, begitu pula tautan atur ulang kata sandi dan pemberitahuan setelah kata sandi berubah. Email dikirim worker Celery, jadi layanan `celery` harus berjalan.

- Pengembangan: semua email ditangkap Mailpit (layanan `mailpit` di Docker Compose, lisensi MIT) dan tidak terkirim ke internet. Buka kotak masuknya di http://localhost:8025. Tidak perlu mengisi apa pun di `.env`.
- Email sungguhan (misalnya untuk video demo): isi bagian `EMAIL_*` di `.env` sesuai `.env.example` (contoh SMTP Gmail dengan sandi aplikasi), lalu `docker compose up -d django celery`. Jangan meng-commit nilai itu.
- `EMAIL_NOTIFIKASI_AKTIF=False` mematikan salinan email notifikasi (notifikasi tetap tampil di aplikasi).

## Uji revisi Tahap R

1. Terapkan perubahan: `docker compose up -d --build` (layanan `mailpit` baru), `docker compose exec django python manage.py migrate` (kolom kecamatan), lalu `cd frontend && npm run dev`.
2. Daftar di http://localhost:5173/daftar: formulir di kanan pada panel biru tua, foto Tower A di kiri; perpindahan Masuk ↔ Daftar memakai panel foto yang bergeser seperti pintu geser (formulir tidak ikut bergeser). Setelah mendaftar, pembeli diarahkan ke halaman Masuk dengan email terisi (tidak langsung masuk). Kecamatan opsional tersimpan di profil.
3. Tema: tombol di header berputar Sistem → Terang → Gelap (di ponsel lewat laci menu). Pilihan tetap setelah halaman dimuat ulang.
4. Profil → Ubah kata sandi: sandi lama salah ditolak; setelah berhasil, perangkat lain keluar dan email "Kata sandi diubah" masuk ke Mailpit.
5. Masuk → "Lupa kata sandi?" → isi email → buka email di Mailpit → tombol "Buat kata sandi baru" → simpan → masuk dengan kata sandi baru. Tautan berlaku 60 menit dan hanya sekali pakai.
6. Checkout delivery: telepon, alamat, dan kecamatan terisi dari profil. Bila diubah, muncul modal "Ubah data di profil?": "Ya" mengganti data profil, "Tidak" hanya untuk pesanan ini, Escape membatalkan. Profil yang masih kosong langsung terisi tanpa modal.
7. Admin: halaman masuk berlogo dengan latar foto Gedung Utama; tautan "Lupa Password?" (khusus akun admin); menu berkelompok; sesi berakhir setelah 30 menit tanpa aktivitas (`ADMIN_SESI_TIDAK_AKTIF_MENIT`) dan saat peramban ditutup; formulir buku dengan baris produk per format dan tombol Hapus bermodal; pengajuan ISBN mengikuti alur menunggu verifikasi → diproses → selesai/ditolak.
8. Pembaca ebook di layar laptop: sampul depan tampil sendiri, lalu halaman 2–3, 4–5, dan seterusnya berdampingan seperti buku terbuka; sampul belakang tampil sendiri. Tombol satu/dua halaman ada di bilah atas (di ponsel selalu satu halaman).
9. Watermark ebook: baris diagonal "Properti Milik Polibatam Press", "Dibeli Oleh <nama>", lalu email samaran · nomor pesanan. Salinan yang dibuat sebelum perubahan ini perlu diproses ulang: Admin → Salinan ebook → pilih → aksi "Proses ulang salinan ebook terpilih".
