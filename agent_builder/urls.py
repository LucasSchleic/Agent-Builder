from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("api/", include("core.api.urls")),
    path("", include("core.api.urls_ui")),
] + static(settings.STATIC_URL, document_root=settings.BASE_DIR / "core" / "static")