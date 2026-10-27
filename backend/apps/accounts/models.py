from django.contrib.auth.models import AbstractUser
from django.db import models

from core.wilayah import KECAMATAN_KOTA_BATAM

from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        PEMBELI = "pembeli", "Pembeli"

    username = None
    email = models.EmailField("email", unique=True)
    nama_lengkap = models.CharField(max_length=150)
    no_telepon = models.CharField(max_length=20, blank=True)
    alamat = models.TextField(blank=True)
    # Kecamatan di Kota Batam, dipakai mengisi otomatis checkout delivery (opsional).
    kecamatan = models.CharField(max_length=50, blank=True, choices=[(k, k) for k in KECAMATAN_KOTA_BATAM])
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PEMBELI)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nama_lengkap"]

    objects = UserManager()

    def save(self, *args, **kwargs):
        # is_staff selalu mengikuti role
        self.is_staff = self.role == self.Role.ADMIN
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "role" in update_fields:
            kwargs["update_fields"] = {*update_fields, "is_staff"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
