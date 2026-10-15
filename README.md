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

3. Migrasi database dan buat bucket S3:

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
