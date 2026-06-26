from django.urls import path

from . import views

urlpatterns = [
    path("", views.HospitalityListView.as_view(), name="hospitality_list"),
]
