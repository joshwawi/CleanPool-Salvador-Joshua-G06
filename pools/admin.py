from django.contrib import admin

from .models import Pool, PoolMembership, PricingTier, Service


class TierInline(admin.TabularInline):
    model = PricingTier
    extra = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "provider", "category", "price_per_sqm", "is_published")
    list_filter = ("category", "is_published")
    inlines = [TierInline]


class MembershipInline(admin.TabularInline):
    model = PoolMembership
    extra = 0


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("title", "service", "created_by", "scheduled_date", "status")
    list_filter = ("status",)
    inlines = [MembershipInline]
