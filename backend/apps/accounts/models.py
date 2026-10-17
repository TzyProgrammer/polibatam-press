from django.contrib.auth.models import AbstractUser
from django.db import models

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
