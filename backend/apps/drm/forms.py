from django import forms

BATAS_UKURAN_PDF = 100 * 1024 * 1024  # sama dengan client_max_body_size Nginx


class FormLacakKebocoran(forms.Form):
    berkas = forms.FileField(
        label="PDF yang diduga bocor",
        help_text="Maksimal 100 MB. Berkas hanya dibaca untuk dicari kodenya, tidak disimpan.",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,.pdf"}),
    )

    def clean_berkas(self):
        berkas = self.cleaned_data["berkas"]
        if berkas.size > BATAS_UKURAN_PDF:
            raise forms.ValidationError("Berkas terlalu besar (maksimal 100 MB).")
        return berkas
