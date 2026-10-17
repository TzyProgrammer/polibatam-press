from django.test import TestCase

from .models import User


class UserManagerTests(TestCase):
    def test_create_user_dengan_email(self):
        user = User.objects.create_user(email="Budi@Example.com", password="rahasia123", nama_lengkap="Budi")
        self.assertEqual(user.email, "Budi@example.com")
        self.assertTrue(user.check_password("rahasia123"))
        self.assertEqual(user.role, "pembeli")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(User.username)

    def test_create_user_tanpa_email_gagal(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="x")

    def test_create_superuser(self):
        user = User.objects.create_superuser(email="admin@example.com", password="rahasia123", nama_lengkap="Admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, "admin")

    def test_role_admin_otomatis_is_staff(self):
        user = User.objects.create_user(email="a@example.com", password="x", nama_lengkap="A", role="admin")
        self.assertTrue(user.is_staff)
        user.role = "pembeli"
        user.save()
        self.assertFalse(user.is_staff)

    def test_email_unik(self):
        User.objects.create_user(email="dup@example.com", password="x", nama_lengkap="A")
        with self.assertRaises(Exception):
            User.objects.create_user(email="dup@example.com", password="x", nama_lengkap="B")
