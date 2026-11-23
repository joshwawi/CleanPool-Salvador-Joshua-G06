from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import User
from pools.models import Pool, PoolMembership, PricingTier, Service

PASSWORD = "CleanPool#2026"


class Command(BaseCommand):
    help = "Create demo accounts and sample services/pools for testing (safe to run more than once)."

    def handle(self, *args, **opts):
        def user(email, name, role, **extra):
            u, created = User.objects.get_or_create(email=email, defaults={"full_name": name, "role": role, **extra})
            if created:
                u.set_password(PASSWORD)
                u.save()
            return u

        user("admin@cleanpool.test", "Demo Admin", User.ROLE_ADMIN, is_staff=True, is_superuser=True)
        prov = user("provider@cleanpool.test", "Sparkle Cleaners", User.ROLE_PROVIDER)
        c1 = user("client1@cleanpool.test", "Maria Santos", User.ROLE_CLIENT)
        c2 = user("client2@cleanpool.test", "Juan Dela Cruz", User.ROLE_CLIENT)

        svc, made = Service.objects.get_or_create(
            provider=prov, title="Office deep cleaning", defaults={
                "category": "office", "service_area": "Cebu IT Park", "price_per_sqm": Decimal("80.00"),
                "description": "Floors, workstations, restrooms and pantry.", "is_published": True})
        if made:
            PricingTier.objects.create(service=svc, min_participants=2, discount_percent=10)
            PricingTier.objects.create(service=svc, min_participants=4, discount_percent=20)

        if not Pool.objects.filter(title="IT Park Friday cleaning").exists():
            pool = Pool.objects.create(created_by=c1, service=svc, title="IT Park Friday cleaning",
                                       location="Cebu IT Park, Tower 2", max_participants=5,
                                       scheduled_date=date.today() + timedelta(days=14))
            PoolMembership.objects.create(pool=pool, client=c1, business_name="Santos Trading", area_sqm=Decimal("120"))
            PoolMembership.objects.create(pool=pool, client=c2, business_name="Dela Cruz Printing", area_sqm=Decimal("80"))
        self.stdout.write(self.style.SUCCESS(f"Demo data ready. All demo accounts use password: {PASSWORD}"))
