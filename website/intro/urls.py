from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("hospitality/", include("hospitality.urls")),
    # Old URL prefix; keep bookmarks working.
    path("accreditatie/", RedirectView.as_view(pattern_name="event_list")),
    path("", include("accreditatie.urls")),
]

if settings.BROWSER_RELOAD:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
