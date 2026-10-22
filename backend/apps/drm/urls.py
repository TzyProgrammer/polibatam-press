from django.urls import path

from .views import KunciView, PlaylistView, SesiStreamingBaruView

urlpatterns = [
    path("audiobook/<int:produk_id>/sesi/", SesiStreamingBaruView.as_view(), name="drm-sesi-baru"),
    path("stream/<str:token>/playlist.m3u8", PlaylistView.as_view(), name="drm-playlist"),
    path("stream/<str:token>/kunci", KunciView.as_view(), name="drm-kunci"),
]
