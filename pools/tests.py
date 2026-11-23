from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import PricingTier, Service

PW = "StrongPass!234"


def make_user(email, role):
    return User.objects.create_user(email, PW, full_name=email.split("@")[0], role=role)


class ServiceManagementTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1@test.com", "provider")
        self.p2 = make_user("p2@test.com", "provider")
        self.client_user = make_user("c1@test.com", "client")
        self.svc = Service.objects.create(provider=self.p1, title="Office deep clean", service_area="Cebu",
                                          price_per_sqm=Decimal("50"), is_published=True)

    def login(self, email):
        self.client.login(username=email, password=PW)

    def test_provider_creates_service_linked_to_self(self):
        self.login("p1@test.com")
        r = self.client.post(reverse("pools:service_create"), {
            "title": "Kitchen sanitising", "category": "restaurant", "service_area": "Mandaue",
            "price_per_sqm": "75.00", "description": "", "is_published": "on"})
        self.assertEqual(r.status_code, 302)
        s = Service.objects.get(title="Kitchen sanitising")
        self.assertEqual(s.provider, self.p1)

    def test_invalid_service_rejected(self):
        self.login("p1@test.com")
        r = self.client.post(reverse("pools:service_create"), {
            "title": "abc", "category": "office", "service_area": "X", "price_per_sqm": "-5"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Service.objects.count(), 1)

    def test_client_cannot_open_provider_pages(self):
        self.login("c1@test.com")
        self.assertEqual(self.client.get(reverse("pools:service_list")).status_code, 403)

    def test_provider_cannot_edit_or_delete_others_service(self):
        self.login("p2@test.com")
        self.assertEqual(self.client.get(reverse("pools:service_edit", args=[self.svc.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("pools:service_delete", args=[self.svc.pk])).status_code, 404)
        self.assertTrue(Service.objects.filter(pk=self.svc.pk).exists())

    def test_provider_updates_and_deletes_own_service(self):
        self.login("p1@test.com")
        self.client.post(reverse("pools:service_edit", args=[self.svc.pk]), {
            "title": "Office deep clean XL", "category": "office", "service_area": "Cebu",
            "price_per_sqm": "60", "description": "", "is_published": "on"})
        self.svc.refresh_from_db()
        self.assertEqual(self.svc.price_per_sqm, Decimal("60.00"))
        self.client.post(reverse("pools:service_delete", args=[self.svc.pk]))
        self.assertFalse(Service.objects.filter(pk=self.svc.pk).exists())

    def test_tiers_add_duplicate_rejected_and_discount_lookup(self):
        self.login("p1@test.com")
        url = reverse("pools:tier_add", args=[self.svc.pk])
        self.client.post(url, {"min_participants": 3, "discount_percent": "10"})
        self.client.post(url, {"min_participants": 3, "discount_percent": "20"})  # duplicate
        self.client.post(url, {"min_participants": 5, "discount_percent": "95"})  # > 90 invalid
        self.client.post(url, {"min_participants": 5, "discount_percent": "20"})
        self.assertEqual(self.svc.tiers.count(), 2)
        self.assertEqual(self.svc.discount_for(2), Decimal("0"))
        self.assertEqual(self.svc.discount_for(4), Decimal("10"))
        self.assertEqual(self.svc.discount_for(9), Decimal("20"))

    def test_tier_delete_only_own(self):
        tier = PricingTier.objects.create(service=self.svc, min_participants=3, discount_percent=10)
        self.login("p2@test.com")
        self.assertEqual(self.client.post(reverse("pools:tier_delete", args=[tier.pk])).status_code, 404)
        self.login("p1@test.com")
        self.client.post(reverse("pools:tier_delete", args=[tier.pk]))
        self.assertFalse(PricingTier.objects.filter(pk=tier.pk).exists())
