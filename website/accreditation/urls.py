from django.urls import path

from . import views

urlpatterns = [
    path("setup/zones/", views.zones, name="zones"),
    path("setup/credentials/", views.types, name="types"),
    path("setup/items/", views.items, name="items"),
    path("people/", views.people, name="people"),
    path("people/new/", views.person_form, name="person_create"),
    path("people/export.csv", views.export_people, name="people_export"),
    path("people/<int:pk>/", views.person_detail, name="person_detail"),
    path("people/<int:pk>/edit/", views.person_form, name="person_edit"),
    path("approvals/", views.approvals, name="approvals"),
    path("companies/", views.companies, name="companies"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("scan/", views.scanner, name="scanner"),
    path("scan/api/", views.scan_api, name="scan_api"),
    path("scan/search/", views.search_api, name="scan_search"),
    path("scan/handout/<int:pk>/", views.handout_api, name="handout_api"),
]
