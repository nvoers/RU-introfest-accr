from django.urls import path

from . import views

urlpatterns = [
    path("", views.artist_list, name="artist_list"),
    path("<int:pk>/", views.artist_detail, name="artist_detail"),
    path("timetable/", views.timetable, name="timetable"),
    path("logistics/", views.logistics, name="logistics"),
    path("stages/", views.stages, name="stages"),
]
