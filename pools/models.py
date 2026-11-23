from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum


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


class Pool(models.Model):
    """A group booking: several client businesses share one provider service for a volume discount."""

    STATUS_OPEN = "open"
    STATUS_CONFIRMED = "confirmed"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open (accepting businesses)"),
        (STATUS_CONFIRMED, "Confirmed by provider"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    MIN_TO_CONFIRM = 2  # a pool needs at least 2 businesses to be confirmed

    pool_id = models.AutoField(primary_key=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pools_created")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="pools")
    title = models.CharField(max_length=120)
    location = models.CharField(max_length=160, help_text="Building / district where the cleaning happens.")
    scheduled_date = models.DateField()
    max_participants = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(2), MaxValueValidator(50)], verbose_name="Max businesses",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pools"
        ordering = ["scheduled_date", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN

    @property
    def participant_count(self):
        return self.memberships.count()

    @property
    def total_area(self):
        return self.memberships.aggregate(t=Sum("area_sqm"))["t"] or Decimal("0")

    @property
    def spots_left(self):
        return max(self.max_participants - self.participant_count, 0)

    @property
    def is_full(self):
        return self.spots_left == 0

    @property
    def current_discount(self):
        return self.service.discount_for(self.participant_count)

    @property
    def rate_per_sqm(self):
        factor = (Decimal("100") - self.current_discount) / Decimal("100")
        return (self.service.price_per_sqm * factor).quantize(Decimal("0.01"))

    @property
    def next_tier(self):
        """The next discount tier not yet reached (to encourage more businesses to join)."""
        return self.service.tiers.filter(min_participants__gt=self.participant_count).order_by("min_participants").first()


class PoolMembership(models.Model):
    """One business's share of a pool (how many sqm it wants cleaned)."""

    membership_id = models.AutoField(primary_key=True)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name="memberships")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pool_memberships")
    business_name = models.CharField(max_length=120)
    area_sqm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("10"))],
        verbose_name="Area to clean (sqm)",
    )
    notes = models.CharField(max_length=255, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pool_memberships"
        ordering = ["joined_at"]
        constraints = [models.UniqueConstraint(fields=["pool", "client"], name="uniq_membership_per_pool")]

    def __str__(self):
        return f"{self.business_name} in {self.pool}"

    @property
    def is_creator(self):
        return self.client_id == self.pool.created_by_id

    @property
    def estimated_cost(self):
        return (self.area_sqm * self.pool.rate_per_sqm).quantize(Decimal("0.01"))
