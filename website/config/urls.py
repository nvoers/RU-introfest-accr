from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("portal.urls")),
    path("", include("core.urls")),
    path("e/<slug:slug>/", include("accreditation.urls")),
    path("e/<slug:slug>/artists/", include("artists.urls")),
    path("e/<slug:slug>/crew/", include("crew.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
