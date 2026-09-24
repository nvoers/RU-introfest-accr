from django.urls import path

from . import views

urlpatterns = [
    path("", views.hospitality_list, name="hospitality_list"),
]
