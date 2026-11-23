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

    # Client: pools
    path("pools/", views.pool_list, name="pool_list"),
    path("pools/mine/", views.my_pools, name="my_pools"),
    path("pools/new/", views.pool_create, name="pool_create"),
    path("pools/<int:pk>/", views.pool_detail, name="pool_detail"),
    path("pools/<int:pk>/edit/", views.pool_edit, name="pool_edit"),
    path("pools/<int:pk>/cancel/", views.pool_cancel, name="pool_cancel"),
    path("pools/<int:pk>/delete/", views.pool_delete, name="pool_delete"),
    path("pools/<int:pk>/join/", views.pool_join, name="pool_join"),
    path("memberships/<int:pk>/edit/", views.membership_edit, name="membership_edit"),
    path("memberships/<int:pk>/leave/", views.membership_leave, name="membership_leave"),
    # Provider / admin
    path("provider/pools/", views.provider_pools, name="provider_pools"),
    path("pools/<int:pk>/<str:action>/", views.pool_action, name="pool_action"),
    path("manage/pools/", views.admin_pools, name="admin_pools"),
]
