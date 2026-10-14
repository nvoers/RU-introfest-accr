from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="event_list")),
    path("events/", views.event_list, name="event_list"),
    path("events/new/", views.event_create, name="event_create"),
    path("e/<slug:slug>/", views.dashboard, name="dashboard"),
    path("e/<slug:slug>/settings/", views.event_settings, name="event_settings"),
    path("e/<slug:slug>/settings/delete/", views.event_delete, name="event_delete"),
]
