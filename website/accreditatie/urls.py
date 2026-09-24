from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="event_list"), name="home"),
    path("events/", views.event_list, name="event_list"),
    path("events/new/", views.event_form, name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/edit/", views.event_form, name="event_edit"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("events/<int:pk>/setup/", views.event_setup, name="event_setup"),
    path("events/<int:pk>/check-in/", views.checkin, name="checkin"),
    path("events/<int:pk>/print/", views.event_print, name="event_print"),
    path("events/<int:pk>/export.csv", views.event_export, name="event_export"),
    path("events/<int:pk>/import/", views.event_import, name="event_import"),
    path("events/<int:pk>/entries/new/", views.entry_create, name="entry_create"),
    path("entries/<int:pk>/", views.entry_detail, name="entry_detail"),
    path("entries/<int:pk>/status/", views.entry_status, name="entry_status"),
]
