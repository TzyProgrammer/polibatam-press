from django.urls import path

from .views import DetailPengajuanISBNView, PengajuanISBNView

urlpatterns = [
    path("pengajuan/", PengajuanISBNView.as_view(), name="isbn-pengajuan"),
    path("pengajuan/<int:pk>/", DetailPengajuanISBNView.as_view(), name="isbn-pengajuan-detail"),
]
