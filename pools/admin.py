from django.contrib import admin

from .models import PricingTier, Service


class TierInline(admin.TabularInline):
    model = PricingTier
    extra = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "provider", "category", "price_per_sqm", "is_published")
    list_filter = ("category", "is_published")
    inlines = [TierInline]
