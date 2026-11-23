from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Service(models.Model):
    """A cleaning service offered by a provider. Clients pool bookings on it."""

    CATEGORY_CHOICES = [
        ("office", "Office cleaning"),
        ("restaurant", "Restaurant / kitchen"),
        ("retail", "Retail / mall"),
        ("warehouse", "Warehouse / industrial"),
        ("other", "Other"),
    ]

    service_id = models.AutoField(primary_key=True)
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="services")
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default="office")
    description = models.TextField(blank=True)
    service_area = models.CharField(max_length=120, help_text="City / district you serve.")
    price_per_sqm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Price per sqm (₱)",
    )
    is_published = models.BooleanField(default=False, help_text="Only published services can be pooled by clients.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "services"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def discount_for(self, participants):
        """Best tier discount (%) reached with this many participating businesses."""
        tier = self.tiers.filter(min_participants__lte=participants).order_by("-min_participants").first()
        return tier.discount_percent if tier else Decimal("0")


class PricingTier(models.Model):
    """Volume discount: once a pool has `min_participants` businesses, `discount_percent` applies."""

    tier_id = models.AutoField(primary_key=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="tiers")
    min_participants = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(100)], verbose_name="Minimum businesses",
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("90"))],
        verbose_name="Discount (%)",
    )

    class Meta:
        db_table = "pricing_tiers"
        ordering = ["min_participants"]
        constraints = [models.UniqueConstraint(fields=["service", "min_participants"], name="uniq_tier_per_service")]

    @property
    def discounted_price(self):
        factor = (Decimal("100") - self.discount_percent) / Decimal("100")
        return (self.service.price_per_sqm * factor).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.min_participants}+ businesses → {self.discount_percent}% off"
