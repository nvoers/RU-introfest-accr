from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(url="accreditatie/events/")),
    path("events/", views.EventListView.as_view(), name="event_list"),
    path("event/<int:pk>/", views.EventDetailView.as_view(), name="event_detail"),
    path("events/new", views.NewEventView.as_view(), name="new_event"),
    path(
        "access_entry/<int:pk>/",
        views.AccessEntryDetailView.as_view(),
        name="access_entry_detail",
    ),
    path(
        "event/<int:pk>/access_entries/new",
        views.NewAccessEntryView.as_view(),
        name="new_access_entry",
    ),
]
