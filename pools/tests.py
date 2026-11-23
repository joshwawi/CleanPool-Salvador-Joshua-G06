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


# ======================= Pool booking (core feature) =======================
from datetime import date, timedelta  # noqa: E402

from .models import Pool, PoolMembership  # noqa: E402


class PoolBookingTests(TestCase):
    def setUp(self):
        self.provider = make_user("prov@test.com", "provider")
        self.other_provider = make_user("prov2@test.com", "provider")
        self.c1 = make_user("c1@test.com", "client")
        self.c2 = make_user("c2@test.com", "client")
        self.c3 = make_user("c3@test.com", "client")
        self.admin = User.objects.create_superuser("admin@test.com", PW)
        self.svc = Service.objects.create(provider=self.provider, title="Office deep clean", service_area="Cebu",
                                          price_per_sqm=Decimal("100"), is_published=True)
        PricingTier.objects.create(service=self.svc, min_participants=2, discount_percent=10)
        PricingTier.objects.create(service=self.svc, min_participants=3, discount_percent=20)
        self.draft = Service.objects.create(provider=self.provider, title="Draft service", service_area="Cebu",
                                            price_per_sqm=Decimal("10"), is_published=False)
        self.future = date.today() + timedelta(days=7)

    def login(self, user):
        self.client.logout()
        self.client.login(username=user.email, password=PW)

    def new_pool(self, owner=None, **kw):
        owner = owner or self.c1
        pool = Pool.objects.create(created_by=owner, service=self.svc, title="Friday pool", location="IT Park",
                                   scheduled_date=self.future, max_participants=kw.pop("max_participants", 3), **kw)
        PoolMembership.objects.create(pool=pool, client=owner, business_name="Owner Biz", area_sqm=Decimal("100"))
        return pool

    def create_payload(self, **over):
        data = {"service": self.svc.pk, "title": "Friday pool", "location": "IT Park",
                "scheduled_date": self.future.isoformat(), "max_participants": 4, "notes": "",
                "business_name": "Biz One", "area_sqm": "200"}
        data.update(over)
        return data

    # ---- create / validation ----
    def test_client_creates_pool_and_membership_linked_to_user(self):
        self.login(self.c1)
        r = self.client.post(reverse("pools:pool_create"), self.create_payload())
        pool = Pool.objects.get()
        self.assertRedirects(r, reverse("pools:pool_detail", args=[pool.pk]))
        self.assertEqual(pool.created_by, self.c1)
        self.assertEqual(pool.memberships.get().client, self.c1)

    def test_create_validation(self):
        self.login(self.c1)
        url = reverse("pools:pool_create")
        for bad in ({"scheduled_date": date.today().isoformat()},   # not in the future
                    {"max_participants": 1},                         # below minimum
                    {"area_sqm": "5"},                               # below 10 sqm
                    {"service": self.draft.pk},                      # unpublished service
                    {"title": "abc"}):
            r = self.client.post(url, self.create_payload(**bad))
            self.assertEqual(r.status_code, 200, bad)
        self.assertEqual(Pool.objects.count(), 0)

    # ---- access control & roles ----
    def test_logged_out_redirected(self):
        self.assertEqual(self.client.get(reverse("pools:pool_list")).status_code, 302)

    def test_role_restrictions(self):
        self.login(self.provider)
        self.assertEqual(self.client.get(reverse("pools:pool_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("pools:pool_create")).status_code, 403)
        self.login(self.c1)
        self.assertEqual(self.client.get(reverse("pools:provider_pools")).status_code, 403)
        self.assertEqual(self.client.get(reverse("pools:admin_pools")).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("pools:admin_pools")).status_code, 200)

    def test_only_owner_can_edit_cancel_delete_pool(self):
        pool = self.new_pool()
        self.login(self.c2)
        self.assertEqual(self.client.get(reverse("pools:pool_edit", args=[pool.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("pools:pool_cancel", args=[pool.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("pools:pool_delete", args=[pool.pk])).status_code, 404)

    def test_pool_detail_visibility(self):
        pool = self.new_pool()
        self.login(self.c2)  # non-member can see open pool
        r = self.client.get(reverse("pools:pool_detail", args=[pool.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Owner Biz")  # member details hidden from non-members
        self.login(self.other_provider)
        self.assertEqual(self.client.get(reverse("pools:pool_detail", args=[pool.pk])).status_code, 403)
        self.login(self.provider)
        self.assertContains(self.client.get(reverse("pools:pool_detail", args=[pool.pk])), "Owner Biz")

    def test_cancelled_pool_hidden_from_non_members(self):
        pool = self.new_pool(status=Pool.STATUS_CANCELLED)
        self.login(self.c2)
        self.assertEqual(self.client.get(reverse("pools:pool_detail", args=[pool.pk])).status_code, 403)

    # ---- join / leave / update ----
    def test_join_applies_tier_discount(self):
        pool = self.new_pool()
        self.login(self.c2)
        self.client.post(reverse("pools:pool_join", args=[pool.pk]), {"business_name": "Biz Two", "area_sqm": "50"})
        self.assertEqual(pool.participant_count, 2)
        self.assertEqual(pool.current_discount, Decimal("10"))
        self.assertEqual(pool.rate_per_sqm, Decimal("90.00"))
        self.login(self.c3)
        self.client.post(reverse("pools:pool_join", args=[pool.pk]), {"business_name": "Biz Three", "area_sqm": "50"})
        self.assertEqual(pool.rate_per_sqm, Decimal("80.00"))
        self.assertEqual(PoolMembership.objects.get(client=self.c3).estimated_cost, Decimal("4000.00"))

    def test_cannot_join_twice_or_when_full_or_not_open(self):
        pool = self.new_pool(max_participants=2)
        self.login(self.c1)
        self.client.post(reverse("pools:pool_join", args=[pool.pk]), {"business_name": "Again", "area_sqm": "20"})
        self.assertEqual(pool.participant_count, 1)
        self.login(self.c2)
        self.client.post(reverse("pools:pool_join", args=[pool.pk]), {"business_name": "B2", "area_sqm": "20"})
        self.login(self.c3)
        self.client.post(reverse("pools:pool_join", args=[pool.pk]), {"business_name": "B3", "area_sqm": "20"})
        self.assertEqual(pool.participant_count, 2)  # full
        pool2 = self.new_pool(owner=self.c2, status=Pool.STATUS_CONFIRMED)
        self.client.post(reverse("pools:pool_join", args=[pool2.pk]), {"business_name": "B3", "area_sqm": "20"})
        self.assertEqual(pool2.participant_count, 1)

    def test_join_validation_rejects_small_area(self):
        pool = self.new_pool()
        self.login(self.c2)
        self.client.post(reverse("pools:pool_join", args=[pool.pk]), {"business_name": "B2", "area_sqm": "1"})
        self.assertEqual(pool.participant_count, 1)

    def test_update_own_share_only_and_leave(self):
        pool = self.new_pool()
        m = PoolMembership.objects.create(pool=pool, client=self.c2, business_name="B2", area_sqm=Decimal("30"))
        self.login(self.c3)
        self.assertEqual(self.client.get(reverse("pools:membership_edit", args=[m.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("pools:membership_leave", args=[m.pk])).status_code, 404)
        self.login(self.c2)
        self.client.post(reverse("pools:membership_edit", args=[m.pk]), {"business_name": "B2 Ltd", "area_sqm": "60", "notes": ""})
        m.refresh_from_db()
        self.assertEqual((m.business_name, m.area_sqm), ("B2 Ltd", Decimal("60.00")))
        self.client.post(reverse("pools:membership_leave", args=[m.pk]))
        self.assertFalse(PoolMembership.objects.filter(pk=m.pk).exists())

    def test_creator_cannot_leave_own_pool(self):
        pool = self.new_pool()
        m = pool.memberships.get()
        self.login(self.c1)
        self.client.post(reverse("pools:membership_leave", args=[m.pk]))
        self.assertTrue(PoolMembership.objects.filter(pk=m.pk).exists())

    # ---- update / cancel / delete ----
    def test_owner_edits_pool_but_not_below_current_members(self):
        pool = self.new_pool()
        PoolMembership.objects.create(pool=pool, client=self.c2, business_name="B2", area_sqm=Decimal("30"))
        PoolMembership.objects.create(pool=pool, client=self.c3, business_name="B3", area_sqm=Decimal("30"))
        self.login(self.c1)
        url = reverse("pools:pool_edit", args=[pool.pk])
        payload = {"service": self.svc.pk, "title": "Renamed pool", "location": "IT Park",
                   "scheduled_date": self.future.isoformat(), "max_participants": 2, "notes": ""}
        self.client.post(url, payload)
        pool.refresh_from_db()
        self.assertEqual(pool.title, "Friday pool")  # rejected: 3 already joined
        payload["max_participants"] = 5
        self.client.post(url, payload)
        pool.refresh_from_db()
        self.assertEqual((pool.title, pool.max_participants), ("Renamed pool", 5))

    def test_delete_rules(self):
        solo = self.new_pool()
        shared = self.new_pool()
        PoolMembership.objects.create(pool=shared, client=self.c2, business_name="B2", area_sqm=Decimal("30"))
        self.login(self.c1)
        self.client.post(reverse("pools:pool_delete", args=[shared.pk]))
        self.assertTrue(Pool.objects.filter(pk=shared.pk).exists())
        self.client.post(reverse("pools:pool_delete", args=[solo.pk]))
        self.assertFalse(Pool.objects.filter(pk=solo.pk).exists())

    def test_owner_cancels_open_pool(self):
        pool = self.new_pool()
        self.login(self.c1)
        self.client.post(reverse("pools:pool_cancel", args=[pool.pk]))
        pool.refresh_from_db()
        self.assertEqual(pool.status, Pool.STATUS_CANCELLED)

    def test_service_with_pools_cannot_be_deleted_by_cascade(self):
        self.new_pool()
        self.login(self.provider)
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.svc.delete()

    # ---- provider workflow ----
    def test_provider_confirms_only_with_two_businesses(self):
        pool = self.new_pool()
        self.login(self.provider)
        url = reverse("pools:pool_action", args=[pool.pk, "confirm"])
        self.client.post(url)
        pool.refresh_from_db()
        self.assertEqual(pool.status, Pool.STATUS_OPEN)
        PoolMembership.objects.create(pool=pool, client=self.c2, business_name="B2", area_sqm=Decimal("30"))
        self.client.post(url)
        pool.refresh_from_db()
        self.assertEqual(pool.status, Pool.STATUS_CONFIRMED)
        self.client.post(reverse("pools:pool_action", args=[pool.pk, "complete"]))
        pool.refresh_from_db()
        self.assertEqual(pool.status, Pool.STATUS_COMPLETED)

    def test_other_provider_and_client_cannot_change_status(self):
        pool = self.new_pool()
        for user in (self.other_provider, self.c1):
            self.login(user)
            self.assertEqual(self.client.post(reverse("pools:pool_action", args=[pool.pk, "decline"])).status_code, 403)
        pool.refresh_from_db()
        self.assertEqual(pool.status, Pool.STATUS_OPEN)

    def test_confirmed_pool_is_locked_for_members(self):
        pool = self.new_pool(status=Pool.STATUS_CONFIRMED)
        m = pool.memberships.get()
        self.login(self.c1)
        self.client.post(reverse("pools:membership_edit", args=[m.pk]), {"business_name": "X Biz", "area_sqm": "999", "notes": ""})
        m.refresh_from_db()
        self.assertEqual(m.area_sqm, Decimal("100.00"))
        self.assertEqual(self.client.post(reverse("pools:pool_cancel", args=[pool.pk])).status_code, 302)
        pool.refresh_from_db()
        self.assertEqual(pool.status, Pool.STATUS_CONFIRMED)

    def test_admin_can_cancel_but_not_confirm(self):
        pool = self.new_pool()
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse("pools:pool_action", args=[pool.pk, "confirm"])).status_code, 403)
        self.client.post(reverse("pools:pool_action", args=[pool.pk, "cancel"]))
        pool.refresh_from_db()
        self.assertEqual(pool.status, Pool.STATUS_CANCELLED)

    # ---- dashboards ----
    def test_role_dashboards_show_pool_data(self):
        pool = self.new_pool()
        self.login(self.c1)
        self.assertContains(self.client.get(reverse("accounts:client_dashboard")), "Friday pool")
        self.login(self.provider)
        self.assertEqual(self.client.get(reverse("accounts:provider_dashboard")).status_code, 200)
        self.assertContains(self.client.get(reverse("pools:provider_pools")), "Friday pool")
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("accounts:admin_dashboard")), "Manage all pools")
        self.assertContains(self.client.get(reverse("pools:admin_pools")), pool.title)

    def test_browse_and_search(self):
        self.new_pool()
        self.login(self.c2)
        self.assertContains(self.client.get(reverse("pools:pool_list"), {"q": "IT Park"}), "Friday pool")
        self.assertNotContains(self.client.get(reverse("pools:pool_list"), {"q": "zzz"}), "Friday pool")

    # Every page in the flow renders (200) for the role that uses it.
    def test_all_pages_render(self):
        pool = self.new_pool()
        m = pool.memberships.get()
        pages = [
            (self.c1, ["pools:pool_list", "pools:my_pools", "pools:pool_create", "accounts:client_dashboard", "accounts:profile"], []),
            (self.c1, ["pools:pool_detail", "pools:pool_edit", "pools:pool_delete"], [pool.pk]),
            (self.c1, ["pools:membership_edit"], [m.pk]),
            (self.provider, ["pools:service_list", "pools:service_create", "pools:provider_pools", "accounts:provider_dashboard"], []),
            (self.provider, ["pools:service_detail", "pools:service_edit", "pools:service_delete", "pools:pool_detail"], None),
            (self.admin, ["pools:admin_pools", "accounts:admin_dashboard"], []),
        ]
        for user, names, args in pages:
            self.login(user)
            for name in names:
                a = args
                if a is None:
                    a = [pool.pk] if name == "pools:pool_detail" else [self.svc.pk]
                self.assertEqual(self.client.get(reverse(name, args=a)).status_code, 200, name)
