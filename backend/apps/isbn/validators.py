from django.core.exceptions import ValidationError


def normalisasi_isbn(nilai):
    return "".join(c for c in str(nilai) if c not in " -")


def validasi_isbn13(nilai):
    """ISBN-13: 13 digit, awalan 978/979, dan digit periksa (bobot 1 dan 3) benar."""
    angka = normalisasi_isbn(nilai)
    if len(angka) != 13 or not angka.isdigit():
        raise ValidationError("ISBN harus terdiri dari 13 digit (tanda hubung boleh).")
    if not angka.startswith(("978", "979")):
        raise ValidationError("ISBN-13 harus diawali 978 atau 979.")
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(angka[:12]))
    if (10 - total % 10) % 10 != int(angka[12]):
        raise ValidationError("Digit periksa ISBN tidak valid.")
