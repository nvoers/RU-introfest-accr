from django.urls import path

from . import views

urlpatterns = [
    path("teams/", views.teams, name="teams"),
    path("shifts/", views.shifts, name="shifts"),
    path("roster/", views.roster, name="roster"),
    path("volunteers/", views.volunteers, name="volunteers"),
]
