from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(url="accreditatie/events/")),
    path("events/", views.EventListView.as_view(), name="event_list"),
    path("event/<int:pk>/", views.event, name="event_detail"),
]
