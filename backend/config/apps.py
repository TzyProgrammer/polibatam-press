from django.contrib.admin.apps import AdminConfig


class AdminPolibatamConfig(AdminConfig):
    """Menjadikan config.admin.AdminPolibatam sebagai admin.site bawaan."""

    default_site = "config.admin.AdminPolibatam"
