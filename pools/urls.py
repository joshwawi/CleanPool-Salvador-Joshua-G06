from django.urls import path

from . import views

app_name = "pools"

urlpatterns = [
    # Provider: manage own services and pricing tiers
    path("services/", views.service_list, name="service_list"),
    path("services/new/", views.service_create, name="service_create"),
    path("services/<int:pk>/", views.service_detail, name="service_detail"),
    path("services/<int:pk>/edit/", views.service_edit, name="service_edit"),
    path("services/<int:pk>/delete/", views.service_delete, name="service_delete"),
    path("services/<int:pk>/tiers/add/", views.tier_add, name="tier_add"),
    path("tiers/<int:pk>/delete/", views.tier_delete, name="tier_delete"),
]
