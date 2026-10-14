from django.urls import path

from . import views

urlpatterns = [
    path("p/<str:token>/", views.portal_home, name="portal_home"),
    path("t/<str:token>/", views.ticket, name="ticket"),
    path("v/<str:token>/", views.volunteer_signup, name="volunteer_signup"),
]
